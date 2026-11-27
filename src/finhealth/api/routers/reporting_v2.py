"""Batch Excel assessment (S03) and executive PDF report (M12) endpoints."""

import re
from typing import Annotated, Any, cast

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from finhealth.api.dependencies import ModelRegistryState, get_db
from finhealth.api.schemas.analytics import (
    LEGAL_DISCLAIMER_VI,
    AltmanView,
    AssessmentSummaryView,
    BusinessDriverView,
    CashFlowOverlayView,
    CompanyAssessmentView,
    ConfidenceView,
    DiagnosticsView,
    DriversSplitView,
    MultiPeriodHistoryPointView,
    OrgCompanyMetaView,
    PeerContextView,
    PillarsOverviewView,
)
from finhealth.api.schemas.batch_reporting import (
    BatchJobDetail,
    BatchJobStatus,
    BatchJobSummary,
    BatchRowResult,
    BatchRowStatus,
)
from finhealth.api.security import (
    OrgContext,
    aware_time,
    consume_limit,
    require_org_role,
    require_user,
)
from finhealth.api.services import FinancialAnalysisService
from finhealth.api.services_org import (
    FI_EXCLUSION_REASON_VI,
    RISK_TIER_LABELS_VI,
    _compute_total_opex_to_revenue,
    _score_statement_with_adapter,
    get_org_company_assessment,
)
from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.account_models import User
from finhealth.db.batch_models import OrgBatchJob, OrgBatchJobRow
from finhealth.db.models import Company, FinancialStatement
from finhealth.etl.altman import compute_altman_assessment
from finhealth.etl.corporate_finance import (
    compute_accounting_checklist,
    compute_dupont,
    compute_health_pillars_v2,
    compute_quality_of_earnings,
)
from finhealth.etl.driver_narrative import translate_drivers_to_business
from finhealth.etl.financial_ratios import _finite, _safe_div, compute_statement_ratios
from finhealth.ingestion.schemas import is_financial_institution_sic, is_manufacturing_sic
from finhealth.ml.feature_contracts import ConfidenceLevel, RiskTier
from finhealth.reporting.batch_excel import (
    MAX_BATCH_FILE_BYTES,
    generate_batch_export_bytes,
    generate_batch_template_bytes,
    sort_batch_rows_by_risk,
)
from finhealth.reporting.batch_worker import (
    create_batch_job_from_upload,
    run_batch_job_background,
)
from finhealth.reporting.pdf_generator import generate_company_assessment_pdf

router = APIRouter(prefix="/api/v1", tags=["reporting"])

Db = Annotated[Session, Depends(get_db)]
ViewerCtx = Annotated[OrgContext, Depends(require_org_role("viewer"))]
AnalystCtx = Annotated[OrgContext, Depends(require_org_role("analyst"))]

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PDF_RATE_LIMIT = 30
_PDF_RATE_WINDOW_SEC = 600
_BATCH_UPLOAD_RATE_LIMIT = 15
_BATCH_UPLOAD_RATE_WINDOW_SEC = 600


def _get_model_registry(request: Request) -> ModelRegistryState | None:
    """Resolve app-scoped model registry when attached to FastAPI state."""
    return getattr(request.app.state, "model_registry", None)


def _safe_slug(value: str, fallback: str = "report") -> str:
    """Create an ASCII-safe filename slug for Content-Disposition headers."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return (cleaned[:64] or fallback)


def _serialize_job_summary(job: OrgBatchJob) -> BatchJobSummary:
    """Serialize an OrgBatchJob ORM row into BatchJobSummary."""
    return BatchJobSummary(
        id=job.id,
        organization_id=job.organization_id,
        created_by=job.created_by,
        filename=job.filename,
        status=cast(BatchJobStatus, job.status),
        model_version=job.model_version,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        succeeded_rows=job.succeeded_rows,
        failed_rows=job.failed_rows,
        error_message=job.error_message,
        summary=job.summary_json,
        created_at=aware_time(job.created_at),
        started_at=aware_time(job.started_at) if job.started_at else None,
        finished_at=aware_time(job.finished_at) if job.finished_at else None,
    )


def _load_org_batch_job_or_404(db: Session, org_id: int, job_id: int) -> OrgBatchJob:
    """Fetch a batch job strictly scoped to the caller's active organization."""
    job = db.scalar(
        select(OrgBatchJob).where(
            OrgBatchJob.id == job_id,
            OrgBatchJob.organization_id == org_id,
        )
    )
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy lô thẩm định trong không gian làm việc này.",
        )
    return job


def _build_sec_assessment_view(
    db: Session,
    *,
    company: Company,
    model_registry: ModelRegistryState | None,
) -> CompanyAssessmentView:
    """Build a unified CompanyAssessmentView for an SEC-listed US company for PDF export."""
    statements = list(
        db.execute(
            select(FinancialStatement)
            .where(
                FinancialStatement.company_id == company.id,
                FinancialStatement.form_type == "10-K",
            )
            .order_by(FinancialStatement.fiscal_year.asc(), FinancialStatement.id.asc())
        ).scalars()
    )
    if not statements:
        raise HTTPException(
            status_code=404,
            detail=(
                "Chưa có báo cáo thường niên 10-K cho doanh nghiệp SEC "
                f"'{company.ticker or company.cik}'."
            ),
        )

    is_fi = is_financial_institution_sic(company.sic_code)
    is_mfg = not is_fi and is_manufacturing_sic(company.sic_code)
    business_type = (
        "financial_institution" if is_fi else "manufacturing" if is_mfg else "trade_service"
    )

    records: list[dict[str, Any]] = []
    history_points: list[MultiPeriodHistoryPointView] = []
    neg_ocf_streak = 0
    last_scored: dict[str, Any] = {}
    last_altman: dict[str, Any] = {}

    for idx, stmt in enumerate(statements):
        raw: dict[str, Any] = {
            "total_assets": stmt.total_assets,
            "current_assets": stmt.current_assets,
            "cash_and_equivalents": stmt.cash_and_equivalents,
            "accounts_receivable": stmt.accounts_receivable,
            "inventory": stmt.inventory,
            "total_liabilities": stmt.total_liabilities,
            "current_liabilities": stmt.current_liabilities,
            "short_term_debt": getattr(stmt, "short_term_debt", None),
            "long_term_debt": stmt.long_term_debt,
            "accounts_payable": getattr(stmt, "accounts_payable", None),
            "stockholders_equity": stmt.stockholders_equity,
            "retained_earnings": stmt.retained_earnings,
            "revenues": stmt.revenues,
            "cost_of_goods_sold": getattr(stmt, "cost_of_goods_sold", None),
            "gross_profit": getattr(stmt, "gross_profit", None),
            "operating_expenses": getattr(stmt, "operating_expenses", None),
            "operating_income": stmt.operating_income,
            "depreciation_amortization": getattr(stmt, "depreciation_amortization", None),
            "ebitda": getattr(stmt, "ebitda", None),
            "interest_expense": stmt.interest_expense,
            "net_income": stmt.net_income,
            "operating_cash_flow": stmt.operating_cash_flow,
            "capex": stmt.capex,
            "fiscal_year": stmt.fiscal_year,
            "fiscal_period": stmt.fiscal_period,
            "form_type": stmt.form_type,
            "filed_date": stmt.filed_date,
            "period_end_date": stmt.period_end_date,
            "accounting_standard": "US_GAAP",
            "currency": "USD",
            "audit_status": "audited_unqualified",
        }
        ratios = compute_statement_ratios(raw, is_manufacturing=is_mfg)
        equity = _finite(stmt.stockholders_equity)
        assets = _finite(stmt.total_assets)
        equity_to_assets = _safe_div(equity, assets, True)
        is_neg_eq = bool(equity is not None and equity <= 0.0)
        neg_eq_flag: float | None = (1.0 if is_neg_eq else 0.0) if equity is not None else None
        total_opex_ratio = _compute_total_opex_to_revenue(
            revenues=raw.get("revenues"),
            cogs=raw.get("cost_of_goods_sold"),
            operating_expenses=raw.get("operating_expenses"),
            ebitda=raw.get("ebitda"),
        )
        rec: dict[str, Any] = {
            **raw,
            **ratios,
            "equity_to_assets": equity_to_assets,
            "is_negative_equity": neg_eq_flag,
            "opex_to_revenue": total_opex_ratio,
            "cash_conversion_qoe": _safe_div(stmt.operating_cash_flow, stmt.net_income, True),
        }
        prior_rec = records[idx - 1] if idx > 0 else None
        has_prior = (
            prior_rec is not None and statements[idx - 1].fiscal_year == stmt.fiscal_year - 1
        )
        if has_prior and prior_rec is not None:
            for cur_k, delta_k in (
                ("roa", "roa_yoy_delta"),
                ("gross_margin", "gross_margin_yoy_delta"),
                ("debt_ratio", "debt_ratio_yoy_delta"),
                ("working_capital_ratio", "working_capital_yoy_delta"),
                ("ocf_ratio", "ocf_ratio_yoy_delta"),
                ("roe", "roe_yoy_delta"),
            ):
                cur_v, prev_v = _finite(rec.get(cur_k)), _finite(prior_rec.get(cur_k))
                rec[delta_k] = cur_v - prev_v if cur_v is not None and prev_v is not None else None
            cur_rev, prev_rev = _finite(rec.get("revenues")), _finite(prior_rec.get("revenues"))
            rec["revenue_growth_yoy"] = (
                (cur_rev - prev_rev) / prev_rev
                if cur_rev is not None and prev_rev is not None and prev_rev > 0
                else None
            )
        ocf = _finite(stmt.operating_cash_flow)
        neg_ocf_streak = neg_ocf_streak + 1 if (ocf is not None and ocf < 0.0) else 0

        if is_fi:
            scored = {
                "model_version": "excluded-fi",
                "scoring_mode": "excluded",
                "pd_12m": None,
                "health_score": None,
                "risk_tier": None,
                "confidence": None,
                "cash_flow_overlay": None,
                "shap_explanation": None,
            }
        else:
            scored = _score_statement_with_adapter(
                rec,
                prior_record=prior_rec if has_prior else None,
                has_prior=has_prior,
                negative_ocf_streak=neg_ocf_streak,
                audit_status="audited_unqualified",
                model_registry=model_registry,
            )
        altman = compute_altman_assessment(
            rec,
            business_type=business_type,
            listing_status="listed",
        )
        records.append(rec)
        last_scored = scored
        last_altman = altman
        history_points.append(
            MultiPeriodHistoryPointView(
                statement_id=stmt.id,
                fiscal_year=stmt.fiscal_year,
                fiscal_period=stmt.fiscal_period,
                accounting_standard="US_GAAP",
                currency="USD",
                audit_status="audited_unqualified",
                revenues=_finite(stmt.revenues),
                net_income=_finite(stmt.net_income),
                operating_cash_flow=_finite(stmt.operating_cash_flow),
                total_assets=_finite(stmt.total_assets),
                total_liabilities=_finite(stmt.total_liabilities),
                stockholders_equity=_finite(stmt.stockholders_equity),
                debt_ratio=_finite(rec.get("debt_ratio")),
                roa=_finite(rec.get("roa")),
                current_ratio=_finite(rec.get("current_ratio")),
                altman_variant=altman["variant"],
                altman_z_score=altman["score"],
                altman_zone=altman["zone"],
                health_score=_finite(scored.get("health_score")),
                pd_12m=_finite(scored.get("pd_12m")),
                risk_tier=cast(RiskTier | None, scored.get("risk_tier")),
            )
        )

    target_stmt = statements[-1]
    target_rec = records[-1]
    prior_rec = records[-2] if len(records) >= 2 else None

    pillars_raw = compute_health_pillars_v2(target_rec, prior_record=prior_rec)
    drivers_raw: dict[str, Any] = (
        {"strengths": [], "bottlenecks": [], "total_impact_share_pct": 0.0}
        if is_fi
        else translate_drivers_to_business(last_scored["shap_explanation"], target_rec)
    )
    dupont = compute_dupont(records)
    qoe = compute_quality_of_earnings(target_rec, prior_rec)
    checklist = compute_accounting_checklist(target_rec, prior_rec)

    tier = cast(RiskTier | None, last_scored.get("risk_tier"))
    health_score = _finite(last_scored.get("health_score"))
    pd_12m = _finite(last_scored.get("pd_12m"))
    takeaways: list[str] = []
    if is_fi:
        takeaways = [
            FI_EXCLUSION_REASON_VI,
            "Hồ sơ tổ chức tài chính chỉ dùng để tham khảo, "
            "không chấm điểm mô hình phi tài chính.",
        ]
    else:
        if tier is not None and health_score is not None and pd_12m is not None:
            pd_pct = f"{pd_12m * 100:.2f}%".replace(".", ",")
            score_str = f"{health_score:.1f}".replace(".", ",")
            takeaways.append(
                f"Sức khỏe tài chính đạt {score_str}/100 ({RISK_TIER_LABELS_VI[tier]}), "
                f"xác suất rủi ro 12 tháng ở mức {pd_pct}."
            )
        if drivers_raw.get("bottlenecks"):
            takeaways.append(f"Điểm nghẽn chính: {drivers_raw['bottlenecks'][0]['headline_vi']}.")
        if drivers_raw.get("strengths"):
            takeaways.append(f"Điểm tựa nổi bật: {drivers_raw['strengths'][0]['headline_vi']}.")

    summary = AssessmentSummaryView(
        scoring_eligible=not is_fi,
        scoring_mode=last_scored["scoring_mode"],
        model_version=str(last_scored["model_version"]),
        health_score=health_score,
        risk_tier=tier,
        risk_label_vi=(
            "Không áp dụng (Tổ chức tài chính)"
            if is_fi
            else RISK_TIER_LABELS_VI[tier]
            if tier is not None
            else "Chưa xếp loại"
        ),
        pd_12m=pd_12m,
        confidence=(
            ConfidenceView.model_validate(last_scored["confidence"])
            if last_scored.get("confidence") is not None
            else None
        ),
        cash_flow_overlay=(
            CashFlowOverlayView.model_validate(last_scored["cash_flow_overlay"])
            if last_scored.get("cash_flow_overlay") is not None
            else None
        ),
        top_3_takeaways_vi=takeaways[:3],
        unavailable_reason_vi=FI_EXCLUSION_REASON_VI if is_fi else None,
        legal_disclaimer_vi=LEGAL_DISCLAIMER_VI,
    )
    meta = OrgCompanyMetaView(
        id=company.id,
        organization_id=0,
        name=company.name,
        tax_code=company.cik,
        ticker=company.ticker,
        sector_code=company.sic_code,
        sector_name=company.sector,
        business_type=business_type,
        listing_status="listed",
        relationship_tag="sec_market",
        is_sample=False,
        fiscal_year=target_stmt.fiscal_year,
        accounting_standard="US_GAAP",
        currency="USD",
    )
    return CompanyAssessmentView(
        company=meta,
        summary=summary,
        altman=AltmanView.model_validate(last_altman),
        pillars=PillarsOverviewView.model_validate(pillars_raw),
        drivers=DriversSplitView(
            strengths=[
                BusinessDriverView.model_validate(item) for item in drivers_raw.get("strengths", [])
            ],
            bottlenecks=[
                BusinessDriverView.model_validate(item)
                for item in drivers_raw.get("bottlenecks", [])
            ],
            total_impact_share_pct=float(drivers_raw.get("total_impact_share_pct", 0.0)),
        ),
        diagnostics=DiagnosticsView(
            dupont=dupont,
            quality_of_earnings=qoe,
            accounting_checklist=checklist,
        ),
        history=history_points,
        peer_context=PeerContextView(
            benchmark_scope="unavailable",
            mapped_sector=company.sector,
            cohort_size=0,
            summary_label_vi="Dữ liệu đối chiếu chuẩn ngành SEC (US GAAP).",
            metrics={},
        ),
        legal_disclaimer_vi=LEGAL_DISCLAIMER_VI,
    )


# =============================================================================
# BATCH EXCEL ENDPOINTS (S03)
# =============================================================================


@router.get("/org/batch/template.xlsx")
def download_batch_excel_template(
    _ctx: ViewerCtx,
) -> Response:
    """Download the standardized multi-company batch assessment Excel template."""
    payload = generate_batch_template_bytes()
    return Response(
        content=payload,
        media_type=_XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="finhealth-batch-template.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/org/batch/jobs", response_model=BatchJobSummary, status_code=202)
async def create_batch_excel_job(
    request: Request,
    background_tasks: BackgroundTasks,
    ctx: AnalystCtx,
    db: Db,
    file: Annotated[UploadFile, File(description="Batch Excel .xlsx file (<=10 MB, <=500 rows)")],
) -> BatchJobSummary:
    """Upload a batch Excel file and enqueue asynchronous background risk scoring (202 Accepted)."""
    consume_limit(
        db,
        "batch-upload",
        f"org:{ctx.organization.id}:user:{ctx.user.id}",
        limit=_BATCH_UPLOAD_RATE_LIMIT,
        seconds=_BATCH_UPLOAD_RATE_WINDOW_SEC,
    )

    raw_bytes = await file.read(MAX_BATCH_FILE_BYTES + 1)
    if len(raw_bytes) > MAX_BATCH_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Tệp Excel vượt quá giới hạn tối đa 10 MB.",
        )

    try:
        job = create_batch_job_from_upload(
            db,
            org_id=ctx.organization.id,
            user_id=ctx.user.id,
            filename=file.filename,
            raw_bytes=raw_bytes,
        )
    except EtlProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        session_factory = sessionmaker(
            bind=db.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    summary = _serialize_job_summary(job)
    # Release request DB transaction before BackgroundTasks opens a worker session (SQLite-safe).
    db.close()

    background_tasks.add_task(
        run_batch_job_background,
        session_factory,
        summary.id,
        _get_model_registry(request),
    )
    return summary


@router.get("/org/batch/jobs", response_model=list[BatchJobSummary])
def list_batch_jobs(
    ctx: ViewerCtx,
    db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BatchJobSummary]:
    """List batch assessment jobs strictly isolated to the active organization."""
    jobs = list(
        db.scalars(
            select(OrgBatchJob)
            .where(OrgBatchJob.organization_id == ctx.organization.id)
            .order_by(OrgBatchJob.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return [_serialize_job_summary(job) for job in jobs]


@router.get("/org/batch/jobs/{job_id}", response_model=BatchJobDetail)
def get_batch_job_detail(
    job_id: int,
    ctx: ViewerCtx,
    db: Db,
) -> BatchJobDetail:
    """Return batch job progress and risk-ranked company results (pd_12m descending)."""
    job = _load_org_batch_job_or_404(db, ctx.organization.id, job_id)
    rows = list(
        db.scalars(
            select(OrgBatchJobRow).where(
                OrgBatchJobRow.job_id == job.id,
                OrgBatchJobRow.organization_id == ctx.organization.id,
            )
        ).all()
    )
    ranked = sort_batch_rows_by_risk(rows)
    row_results: list[BatchRowResult] = []
    rank_counter = 0
    for row in ranked:
        if row.status == "succeeded":
            rank_counter += 1
            rank_val: int | None = rank_counter
        else:
            rank_val = None
        row_results.append(
            BatchRowResult(
                id=row.id,
                row_index=row.row_index,
                risk_rank=rank_val,
                company_name=row.company_name,
                tax_code=row.tax_code,
                fiscal_year=row.fiscal_year,
                status=cast(BatchRowStatus, row.status),
                pd_12m=row.pd_12m,
                health_score=row.health_score,
                risk_tier=cast(RiskTier | None, row.risk_tier),
                confidence_level=cast(ConfidenceLevel | None, row.confidence_level),
                top_bottleneck_vi=row.top_bottleneck_vi,
                error_message=row.error_message,
                result_meta=row.result_json,
            )
        )

    base = _serialize_job_summary(job)
    return BatchJobDetail(**base.model_dump(), rows=row_results)


@router.get("/org/batch/jobs/{job_id}/export.xlsx")
def export_batch_job_excel(
    job_id: int,
    ctx: ViewerCtx,
    db: Db,
) -> Response:
    """Export the 2-sheet summary & risk-ranked Excel report for a batch job."""
    job = _load_org_batch_job_or_404(db, ctx.organization.id, job_id)
    rows = list(
        db.scalars(
            select(OrgBatchJobRow).where(
                OrgBatchJobRow.job_id == job.id,
                OrgBatchJobRow.organization_id == ctx.organization.id,
            )
        ).all()
    )
    payload = generate_batch_export_bytes(job, rows)
    return Response(
        content=payload,
        media_type=_XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="finhealth-batch-job-{job.id}.xlsx"',
            "Cache-Control": "no-store",
        },
    )


# =============================================================================
# EXECUTIVE PDF REPORT ENDPOINTS (M12)
# =============================================================================


@router.get("/org/companies/{company_id}/report.pdf")
def download_org_company_pdf_report(
    request: Request,
    company_id: int,
    ctx: ViewerCtx,
    db: Db,
    fiscal_year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
) -> Response:
    """Generate and return the A4 Vietnamese executive PDF report for an org company."""
    consume_limit(
        db,
        "pdf-report",
        f"user:{ctx.user.id}",
        limit=_PDF_RATE_LIMIT,
        seconds=_PDF_RATE_WINDOW_SEC,
    )
    assessment = get_org_company_assessment(
        db,
        org_id=ctx.organization.id,
        company_id=company_id,
        model_registry=_get_model_registry(request),
        fiscal_year=fiscal_year,
        force_recompute=False,
    )
    ref = f"ORG-{ctx.organization.id}-C{company_id}-FY{assessment.company.fiscal_year or 0}"
    pdf_bytes = generate_company_assessment_pdf(assessment, assessment_ref=ref)
    slug = _safe_slug(
        f"finhealth-{assessment.company.tax_code or assessment.company.ticker or company_id}-"
        f"{assessment.company.fiscal_year or 'latest'}"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/companies/{identifier}/assessment", response_model=CompanyAssessmentView)
def get_sec_company_assessment(
    request: Request,
    identifier: str,
    db: Db,
) -> CompanyAssessmentView:
    """Return the unified V1.0 scale-free assessment for an SEC issuer (matches PDF export)."""
    company = FinancialAnalysisService().resolve_company(db, identifier)
    return _build_sec_assessment_view(
        db,
        company=company,
        model_registry=_get_model_registry(request),
    )


@router.get("/companies/{identifier}/report.pdf")
def download_sec_company_pdf_report(
    request: Request,
    identifier: str,
    user: Annotated[User, Depends(require_user)],
    db: Db,
) -> Response:
    """Generate and return the A4 Vietnamese executive PDF report for an SEC issuer."""
    consume_limit(
        db,
        "pdf-report",
        f"user:{user.id}",
        limit=_PDF_RATE_LIMIT,
        seconds=_PDF_RATE_WINDOW_SEC,
    )
    company = FinancialAnalysisService().resolve_company(db, identifier)
    assessment = _build_sec_assessment_view(
        db,
        company=company,
        model_registry=_get_model_registry(request),
    )
    ref = f"SEC-{company.ticker or company.cik}-FY{assessment.company.fiscal_year or 0}"
    pdf_bytes = generate_company_assessment_pdf(assessment, assessment_ref=ref)
    slug = _safe_slug(
        f"finhealth-sec-{company.ticker or company.cik}-"
        f"{assessment.company.fiscal_year or 'latest'}"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{slug}.pdf"',
            "Cache-Control": "no-store",
        },
    )
