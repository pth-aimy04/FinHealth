"""Organization-scoped private company CRUD, multi-period BCTC, XML/Excel import, and seeding."""

from datetime import date
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db
from finhealth.api.schemas.org_financials import (
    FI_EXCLUSION_MESSAGE,
    BusinessType,
    ListingStatus,
    OrgCompanyCreateInput,
    OrgCompanyResponse,
    OrgCompanyUpdateInput,
    OrgStatementInput,
    OrgStatementResponse,
    OrgStatementUpdateInput,
    RelationshipTag,
    SampleCompanySummary,
    SampleSeedResponse,
    ValidationReportSchema,
)
from finhealth.api.security import OrgContext, aware_time, require_org_role
from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.org_models import OrgCompany, OrgFinancialStatement
from finhealth.etl.accounting_validator import validate_financial_statement
from finhealth.etl.excel_templates import (
    MAX_EXCEL_UPLOAD_BYTES,
    generate_bctc_template_bytes,
    parse_bctc_excel_bytes,
)
from finhealth.etl.financial_ratios import compute_statement_ratios
from finhealth.etl.htkk_xml_parser import MAX_HTKK_XML_BYTES, parse_htkk_xml_bytes
from finhealth.etl.vn_accounting_mapper import (
    ALL_STATEMENT_NUMERIC_FIELDS,
    MONETARY_STATEMENT_FIELDS,
    PER_SHARE_FIELDS,
    normalize_vas_regime,
)
from finhealth.etl.vn_samples import seed_vn_sample_companies

router = APIRouter(tags=["org-companies"])

Db = Annotated[Session, Depends(get_db)]
ViewerCtx = Annotated[OrgContext, Depends(require_org_role("viewer"))]
AnalystCtx = Annotated[OrgContext, Depends(require_org_role("analyst"))]
AdminCtx = Annotated[OrgContext, Depends(require_org_role("org_admin"))]

_DISPLAY_UNIT_MAP: dict[tuple[str, int], str] = {
    ("VND", 1): "VND",
    ("VND", 1_000): "THOUSAND_VND",
    ("VND", 1_000_000): "MILLION_VND",
    ("VND", 1_000_000_000): "BILLION_VND",
    ("USD", 1): "USD",
    ("USD", 1_000): "THOUSAND_USD",
    ("USD", 1_000_000): "MILLION_USD",
    ("USD", 1_000_000_000): "BILLION_USD",
}


def _resolve_display_unit(currency: str, unit_scale: int, explicit: str | None) -> str:
    """Derive a stable display unit label when not explicitly provided."""
    if explicit and explicit.strip():
        return explicit.strip()[:16]
    return _DISPLAY_UNIT_MAP.get((currency, unit_scale), currency)


def _serialize_company(company: OrgCompany) -> OrgCompanyResponse:
    """Convert an OrgCompany ORM row into its API response with FI scoring gate."""
    scoring_eligible = company.business_type != "financial_institution"
    return OrgCompanyResponse(
        id=company.id,
        organization_id=company.organization_id,
        name=company.name,
        tax_code=company.tax_code,
        ticker=company.ticker,
        sector_code=company.sector_code,
        sector_name=company.sector_name,
        business_type=cast(BusinessType, company.business_type),
        listing_status=cast(ListingStatus, company.listing_status),
        relationship_tag=cast(RelationshipTag, company.relationship_tag),
        archived=company.archived,
        is_sample=company.is_sample,
        scoring_eligible=scoring_eligible,
        scoring_exclusion_reason=None if scoring_eligible else FI_EXCLUSION_MESSAGE,
        created_at=aware_time(company.created_at),
        updated_at=aware_time(company.updated_at),
    )


def _statement_numeric_dict(stmt: OrgFinancialStatement) -> dict[str, float | None]:
    """Extract all 26 numeric fields from an OrgFinancialStatement row."""
    return {field: getattr(stmt, field) for field in ALL_STATEMENT_NUMERIC_FIELDS}


def _serialize_statement(
    stmt: OrgFinancialStatement, *, is_manufacturing: bool
) -> OrgStatementResponse:
    """Serialize an OrgFinancialStatement with live validation summary and extended ratios."""
    numeric_map = _statement_numeric_dict(stmt)
    report = validate_financial_statement(numeric_map)
    ratios = compute_statement_ratios(numeric_map, is_manufacturing=is_manufacturing)
    return OrgStatementResponse(
        id=stmt.id,
        organization_id=stmt.organization_id,
        org_company_id=stmt.org_company_id,
        fiscal_year=stmt.fiscal_year,
        fiscal_period=stmt.fiscal_period,
        period_end_date=stmt.period_end_date,
        accounting_standard=stmt.accounting_standard,
        currency=stmt.currency,
        unit_scale=stmt.unit_scale,
        display_unit=stmt.display_unit,
        audit_status=stmt.audit_status,
        status=stmt.status,
        source_channel=stmt.source_channel,
        **numeric_map,
        validation=ValidationReportSchema.model_validate(report.to_dict()),
        ratios=ratios,
        raw_source_meta=stmt.raw_source_meta,
        created_at=aware_time(stmt.created_at),
        updated_at=aware_time(stmt.updated_at),
    )


def _get_org_company_or_404(db: Session, org_id: int, company_id: int) -> OrgCompany:
    """Fetch a company strictly scoped to the caller's active organization."""
    company = db.scalar(
        select(OrgCompany).where(
            OrgCompany.id == company_id,
            OrgCompany.organization_id == org_id,
        )
    )
    if company is None:
        raise HTTPException(404, "Không tìm thấy doanh nghiệp trong không gian làm việc này.")
    return company


def _get_org_statement_or_404(
    db: Session, org_id: int, company_id: int, statement_id: int
) -> OrgFinancialStatement:
    """Fetch a statement strictly scoped to the caller's organization and company."""
    stmt = db.scalar(
        select(OrgFinancialStatement).where(
            OrgFinancialStatement.id == statement_id,
            OrgFinancialStatement.org_company_id == company_id,
            OrgFinancialStatement.organization_id == org_id,
        )
    )
    if stmt is None:
        raise HTTPException(404, "Không tìm thấy báo cáo tài chính.")
    return stmt


def _scale_monetary_inputs(
    data: dict[str, Any], unit_scale: int
) -> dict[str, float | None]:
    """Scale monetary inputs to base currency while keeping per-share metrics unscaled."""
    scaled: dict[str, float | None] = {}
    for field in MONETARY_STATEMENT_FIELDS:
        val = data.get(field)
        scaled[field] = float(val) * float(unit_scale) if val is not None else None
    for field in PER_SHARE_FIELDS:
        val = data.get(field)
        scaled[field] = float(val) if val is not None else None

    # Auto-derive gross_profit and ebitda only when omitted and inputs exist.
    if (
        scaled["gross_profit"] is None
        and scaled["revenues"] is not None
        and scaled["cost_of_goods_sold"] is not None
    ):
        scaled["gross_profit"] = scaled["revenues"] - scaled["cost_of_goods_sold"]
    if (
        scaled["ebitda"] is None
        and scaled["operating_income"] is not None
        and scaled["depreciation_amortization"] is not None
    ):
        scaled["ebitda"] = scaled["operating_income"] + scaled["depreciation_amortization"]
    return scaled


def _enforce_finalization_gate(numeric_fields: dict[str, float | None]) -> dict[str, Any]:
    """Run accounting validator and reject finalization when hard structural errors exist."""
    report = validate_financial_statement(numeric_fields)
    report_dict = report.to_dict()
    if not report.is_balanced:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    "Không thể chốt (finalized) báo cáo tài chính khi còn lỗi cứng "
                    "cân đối kế toán. Vui lòng sửa các dòng lệch hoặc lưu nháp (draft)."
                ),
                "validation": report_dict,
            },
        )
    return report_dict


@router.get("/org/companies", response_model=list[OrgCompanyResponse])
def list_org_companies(
    ctx: ViewerCtx,
    db: Db,
    q: Annotated[str | None, Query(max_length=120)] = None,
    relationship_tag: Annotated[RelationshipTag | None, Query()] = None,
    business_type: Annotated[BusinessType | None, Query()] = None,
    include_archived: Annotated[bool, Query()] = False,
) -> list[OrgCompanyResponse]:
    """List private companies strictly isolated to the active organization."""
    stmt = select(OrgCompany).where(OrgCompany.organization_id == ctx.organization.id)
    if not include_archived:
        stmt = stmt.where(OrgCompany.archived.is_(False))
    if relationship_tag is not None:
        stmt = stmt.where(OrgCompany.relationship_tag == relationship_tag)
    if business_type is not None:
        stmt = stmt.where(OrgCompany.business_type == business_type)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                OrgCompany.name.ilike(pattern),
                OrgCompany.tax_code.ilike(pattern),
                OrgCompany.ticker.ilike(pattern),
            )
        )
    rows = db.scalars(stmt.order_by(OrgCompany.id.desc())).all()
    return [_serialize_company(row) for row in rows]


@router.post("/org/companies", response_model=OrgCompanyResponse, status_code=201)
def create_org_company(
    payload: OrgCompanyCreateInput,
    ctx: AnalystCtx,
    db: Db,
) -> OrgCompanyResponse:
    """Create a private company in the active organization (analyst/org_admin)."""
    company = OrgCompany(
        organization_id=ctx.organization.id,
        name=payload.name,
        tax_code=payload.tax_code,
        ticker=payload.ticker,
        sector_code=payload.sector_code,
        sector_name=payload.sector_name,
        business_type=payload.business_type,
        listing_status=payload.listing_status,
        relationship_tag=payload.relationship_tag,
        archived=False,
        is_sample=False,
    )
    db.add(company)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Mã số thuế (MST) này đã tồn tại trong không gian làm việc của bạn."
        ) from exc
    db.refresh(company)
    return _serialize_company(company)


@router.get("/org/companies/{company_id}", response_model=OrgCompanyResponse)
def get_org_company(company_id: int, ctx: ViewerCtx, db: Db) -> OrgCompanyResponse:
    """Retrieve one organization company by ID."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    return _serialize_company(company)


@router.patch("/org/companies/{company_id}", response_model=OrgCompanyResponse)
def update_org_company(
    company_id: int,
    payload: OrgCompanyUpdateInput,
    ctx: AnalystCtx,
    db: Db,
) -> OrgCompanyResponse:
    """Update company metadata or soft-archive flag (analyst/org_admin)."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(company, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Mã số thuế (MST) cập nhật bị trùng trong không gian làm việc."
        ) from exc
    db.refresh(company)
    return _serialize_company(company)


@router.delete("/org/companies/{company_id}", status_code=204)
def delete_org_company(company_id: int, ctx: AdminCtx, db: Db) -> None:
    """Permanently delete a company and its statements (org_admin only)."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    db.delete(company)
    db.commit()


@router.get(
    "/org/companies/{company_id}/statements",
    response_model=list[OrgStatementResponse],
)
def list_company_statements(
    company_id: int,
    ctx: ViewerCtx,
    db: Db,
) -> list[OrgStatementResponse]:
    """List multi-period statements for an organization company, newest first."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    rows = db.scalars(
        select(OrgFinancialStatement)
        .where(
            OrgFinancialStatement.organization_id == ctx.organization.id,
            OrgFinancialStatement.org_company_id == company.id,
        )
        .order_by(
            OrgFinancialStatement.fiscal_year.desc(),
            OrgFinancialStatement.fiscal_period.desc(),
        )
    ).all()
    is_mfg = company.business_type == "manufacturing"
    return [_serialize_statement(row, is_manufacturing=is_mfg) for row in rows]


@router.post(
    "/org/companies/{company_id}/statements",
    response_model=OrgStatementResponse,
    status_code=201,
)
def create_or_upsert_statement(
    company_id: int,
    payload: OrgStatementInput,
    ctx: AnalystCtx,
    db: Db,
) -> OrgStatementResponse:
    """Save a draft or finalized financial statement for a company period."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    raw_dump = payload.model_dump()
    scaled_fields = _scale_monetary_inputs(raw_dump, payload.unit_scale)

    if payload.status == "finalized":
        validation_dict = _enforce_finalization_gate(scaled_fields)
    else:
        validation_dict = validate_financial_statement(scaled_fields).to_dict()

    display_unit = _resolve_display_unit(
        payload.currency, payload.unit_scale, payload.display_unit
    )

    stmt = db.scalar(
        select(OrgFinancialStatement).where(
            OrgFinancialStatement.organization_id == ctx.organization.id,
            OrgFinancialStatement.org_company_id == company.id,
            OrgFinancialStatement.fiscal_year == payload.fiscal_year,
            OrgFinancialStatement.fiscal_period == payload.fiscal_period,
        )
    )
    if stmt is None:
        stmt = OrgFinancialStatement(
            organization_id=ctx.organization.id,
            org_company_id=company.id,
            fiscal_year=payload.fiscal_year,
            fiscal_period=payload.fiscal_period,
            period_end_date=payload.period_end_date,
            accounting_standard=payload.accounting_standard,
            currency=payload.currency,
            unit_scale=payload.unit_scale,
            display_unit=display_unit,
            audit_status=payload.audit_status,
            status=payload.status,
            source_channel="web_form",
            validation_summary=validation_dict,
            created_by=ctx.user.id,
            **scaled_fields,
        )
        db.add(stmt)
    else:
        stmt.period_end_date = payload.period_end_date
        stmt.accounting_standard = payload.accounting_standard
        stmt.currency = payload.currency
        stmt.unit_scale = payload.unit_scale
        stmt.display_unit = display_unit
        stmt.audit_status = payload.audit_status
        stmt.status = payload.status
        stmt.source_channel = "web_form"
        stmt.validation_summary = validation_dict
        for field, val in scaled_fields.items():
            setattr(stmt, field, val)

    db.commit()
    db.refresh(stmt)
    return _serialize_statement(stmt, is_manufacturing=company.business_type == "manufacturing")


@router.get(
    "/org/companies/{company_id}/statements/{statement_id}",
    response_model=OrgStatementResponse,
)
def get_company_statement(
    company_id: int,
    statement_id: int,
    ctx: ViewerCtx,
    db: Db,
) -> OrgStatementResponse:
    """Retrieve one statement with its live validation report and ratios."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    stmt = _get_org_statement_or_404(db, ctx.organization.id, company.id, statement_id)
    return _serialize_statement(stmt, is_manufacturing=company.business_type == "manufacturing")


@router.patch(
    "/org/companies/{company_id}/statements/{statement_id}",
    response_model=OrgStatementResponse,
)
def update_company_statement(
    company_id: int,
    statement_id: int,
    payload: OrgStatementUpdateInput,
    ctx: AnalystCtx,
    db: Db,
) -> OrgStatementResponse:
    """Update a statement and optionally transition draft -> finalized."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    stmt = _get_org_statement_or_404(db, ctx.organization.id, company.id, statement_id)

    updates = payload.model_dump(exclude_unset=True)
    effective_scale = int(updates.get("unit_scale", stmt.unit_scale))
    effective_currency = str(updates.get("currency", stmt.currency))

    for meta_field in (
        "period_end_date",
        "accounting_standard",
        "currency",
        "unit_scale",
        "audit_status",
    ):
        if meta_field in updates:
            setattr(stmt, meta_field, updates[meta_field])

    if "display_unit" in updates or "unit_scale" in updates or "currency" in updates:
        stmt.display_unit = _resolve_display_unit(
            effective_currency, effective_scale, updates.get("display_unit")
        )

    for field in MONETARY_STATEMENT_FIELDS:
        if field in updates:
            raw_val = updates[field]
            setattr(
                stmt,
                field,
                float(raw_val) * float(effective_scale) if raw_val is not None else None,
            )
    for field in PER_SHARE_FIELDS:
        if field in updates:
            raw_val = updates[field]
            setattr(stmt, field, float(raw_val) if raw_val is not None else None)

    target_status = str(updates.get("status", stmt.status))
    numeric_map = _statement_numeric_dict(stmt)
    if target_status == "finalized":
        stmt.validation_summary = _enforce_finalization_gate(numeric_map)
    else:
        stmt.validation_summary = validate_financial_statement(numeric_map).to_dict()
    stmt.status = target_status

    db.commit()
    db.refresh(stmt)
    return _serialize_statement(stmt, is_manufacturing=company.business_type == "manufacturing")


@router.post(
    "/org/companies/{company_id}/statements/{statement_id}/finalize",
    response_model=OrgStatementResponse,
)
def finalize_company_statement(
    company_id: int,
    statement_id: int,
    ctx: AnalystCtx,
    db: Db,
) -> OrgStatementResponse:
    """Transition a draft statement to finalized after passing hard accounting checks."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    stmt = _get_org_statement_or_404(db, ctx.organization.id, company.id, statement_id)
    numeric_map = _statement_numeric_dict(stmt)
    stmt.validation_summary = _enforce_finalization_gate(numeric_map)
    stmt.status = "finalized"
    db.commit()
    db.refresh(stmt)
    return _serialize_statement(stmt, is_manufacturing=company.business_type == "manufacturing")


@router.delete("/org/companies/{company_id}/statements/{statement_id}", status_code=204)
def delete_company_statement(
    company_id: int,
    statement_id: int,
    ctx: AdminCtx,
    db: Db,
) -> None:
    """Permanently delete a financial statement (org_admin only)."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    stmt = _get_org_statement_or_404(db, ctx.organization.id, company.id, statement_id)
    db.delete(stmt)
    db.commit()


def _upsert_imported_draft(
    db: Session,
    *,
    ctx: OrgContext,
    company: OrgCompany,
    fiscal_year: int,
    fiscal_period: str,
    period_end_date: date | None,
    accounting_standard: str,
    currency: str,
    unit_scale: int,
    audit_status: str,
    source_channel: str,
    normalized_fields: dict[str, float | None],
    validation_dict: dict[str, Any],
    raw_source_meta: dict[str, Any],
) -> OrgFinancialStatement:
    """Persist an imported XML or Excel statement as a reviewable draft."""
    display_unit = _resolve_display_unit(currency, unit_scale, None)
    stmt = db.scalar(
        select(OrgFinancialStatement).where(
            OrgFinancialStatement.organization_id == ctx.organization.id,
            OrgFinancialStatement.org_company_id == company.id,
            OrgFinancialStatement.fiscal_year == fiscal_year,
            OrgFinancialStatement.fiscal_period == fiscal_period,
        )
    )
    if stmt is None:
        stmt = OrgFinancialStatement(
            organization_id=ctx.organization.id,
            org_company_id=company.id,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            period_end_date=period_end_date,
            accounting_standard=accounting_standard,
            currency=currency,
            unit_scale=unit_scale,
            display_unit=display_unit,
            audit_status=audit_status,
            status="draft",
            source_channel=source_channel,
            validation_summary=validation_dict,
            raw_source_meta=raw_source_meta,
            created_by=ctx.user.id,
            **normalized_fields,
        )
        db.add(stmt)
    else:
        stmt.period_end_date = period_end_date
        stmt.accounting_standard = accounting_standard
        stmt.currency = currency
        stmt.unit_scale = unit_scale
        stmt.display_unit = display_unit
        stmt.audit_status = audit_status
        stmt.status = "draft"
        stmt.source_channel = source_channel
        stmt.validation_summary = validation_dict
        stmt.raw_source_meta = raw_source_meta
        for field, val in normalized_fields.items():
            setattr(stmt, field, val)
    db.commit()
    db.refresh(stmt)
    return stmt


@router.post(
    "/org/companies/{company_id}/statements/import-xml",
    response_model=OrgStatementResponse,
    status_code=201,
)
async def import_htkk_xml_statement(
    company_id: int,
    ctx: AnalystCtx,
    db: Db,
    file: Annotated[UploadFile, File(...)],
    fiscal_year: Annotated[int | None, Form(ge=1990, le=2100)] = None,
    unit_scale: Annotated[int, Form()] = 1,
    accounting_standard: Annotated[str | None, Form()] = None,
) -> OrgStatementResponse:
    """Import an HTKK XML filing safely (defusedxml, <= 5 MB) into a draft statement."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    raw_bytes = await file.read(MAX_HTKK_XML_BYTES + 1)
    try:
        parsed = parse_htkk_xml_bytes(
            raw_bytes,
            override_standard=accounting_standard,
            unit_scale=unit_scale,
        )
    except EtlProcessingError as exc:
        raise HTTPException(422, str(exc)) from exc

    resolved_year = fiscal_year or parsed.fiscal_year
    if resolved_year is None:
        raise HTTPException(
            422, "Không xác định được năm tài chính từ tệp XML; vui lòng truyền fiscal_year."
        )

    stmt = _upsert_imported_draft(
        db,
        ctx=ctx,
        company=company,
        fiscal_year=resolved_year,
        fiscal_period=parsed.fiscal_period,
        period_end_date=parsed.period_end_date,
        accounting_standard=parsed.accounting_standard,
        currency="VND",
        unit_scale=unit_scale,
        audit_status="unaudited",
        source_channel="htkk_xml",
        normalized_fields=parsed.normalized_fields,
        validation_dict=parsed.validation.to_dict(),
        raw_source_meta={
            "filename": (file.filename or "upload.xml")[:120],
            "detected_tax_code": parsed.tax_code,
            "detected_company_name": parsed.company_name,
            "detected_standard": parsed.accounting_standard,
        },
    )
    return _serialize_statement(stmt, is_manufacturing=company.business_type == "manufacturing")


@router.post(
    "/org/companies/{company_id}/statements/import-excel",
    response_model=OrgStatementResponse,
    status_code=201,
)
async def import_excel_statement(
    company_id: int,
    ctx: AnalystCtx,
    db: Db,
    file: Annotated[UploadFile, File(...)],
    fiscal_year: Annotated[int | None, Form(ge=1990, le=2100)] = None,
    unit_scale: Annotated[int | None, Form()] = None,
    accounting_standard: Annotated[str | None, Form()] = None,
) -> OrgStatementResponse:
    """Import a FinHealth BCTC Excel template safely (<= 5 MB, zip-bomb guarded) into draft."""
    company = _get_org_company_or_404(db, ctx.organization.id, company_id)
    raw_bytes = await file.read(MAX_EXCEL_UPLOAD_BYTES + 1)
    try:
        parsed = parse_bctc_excel_bytes(
            raw_bytes,
            override_standard=accounting_standard,
            override_unit_scale=unit_scale,
        )
    except EtlProcessingError as exc:
        raise HTTPException(422, str(exc)) from exc

    resolved_year = fiscal_year or parsed.fiscal_year
    if resolved_year is None:
        raise HTTPException(
            422, "Không xác định được năm tài chính từ tệp Excel; vui lòng truyền fiscal_year."
        )

    stmt = _upsert_imported_draft(
        db,
        ctx=ctx,
        company=company,
        fiscal_year=resolved_year,
        fiscal_period=parsed.fiscal_period,
        period_end_date=date(resolved_year, 12, 31) if parsed.fiscal_period == "FY" else None,
        accounting_standard=parsed.accounting_standard,
        currency=parsed.currency,
        unit_scale=parsed.unit_scale,
        audit_status=parsed.audit_status,
        source_channel="excel_upload",
        normalized_fields=parsed.normalized_fields,
        validation_dict=parsed.validation.to_dict(),
        raw_source_meta={
            "filename": (file.filename or "upload.xlsx")[:120],
            "detected_standard": parsed.accounting_standard,
        },
    )
    return _serialize_statement(stmt, is_manufacturing=company.business_type == "manufacturing")


@router.get("/templates/bctc/{standard}")
def download_bctc_template(
    standard: str,
    _ctx: ViewerCtx,
    fiscal_year: int = Query(default=2025, ge=1990, le=2100),
    unit_scale: int = Query(default=1_000_000),
) -> Response:
    """Download an official FinHealth Excel template for TT99_2025, TT200_2014, or TT133_2016."""
    try:
        regime = normalize_vas_regime(standard)
        content = generate_bctc_template_bytes(
            regime,
            fiscal_year=fiscal_year,
            unit_scale=unit_scale,
        )
    except EtlProcessingError as exc:
        raise HTTPException(422, str(exc)) from exc

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="FinHealth_BCTC_{regime}.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/org/samples/seed", response_model=SampleSeedResponse)
def seed_org_sample_companies(ctx: AnalystCtx, db: Db) -> SampleSeedResponse:
    """Idempotently seed the 3 Vietnamese sample companies into the active organization."""
    result = seed_vn_sample_companies(
        db,
        ctx.organization.id,
        created_by=ctx.user.id,
    )
    return SampleSeedResponse(
        created_companies=result["created_companies"],
        existing_companies=result["existing_companies"],
        created_statements=result["created_statements"],
        companies=[SampleCompanySummary(**item) for item in result["companies"]],
    )
