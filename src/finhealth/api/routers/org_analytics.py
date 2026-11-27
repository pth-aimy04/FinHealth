"""Organization-scoped corporate risk analytics and 2-4 company comparison routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from finhealth.api.dependencies import ModelRegistryState, get_db
from finhealth.api.schemas.analytics import CompanyAssessmentView, OrgCompareResponseView
from finhealth.api.security import OrgContext, require_org_role
from finhealth.api.services_org import compare_org_companies, get_org_company_assessment

router = APIRouter(prefix="/api/v1/org/companies", tags=["org-analytics"])


def _get_model_registry(request: Request) -> ModelRegistryState | None:
    """Resolve app-scoped model registry when attached to FastAPI state."""
    return getattr(request.app.state, "model_registry", None)


def _parse_company_ids(raw_ids: str) -> list[int]:
    """Parse a comma-separated list of positive integer company IDs."""
    tokens = [token.strip() for token in raw_ids.split(",")]
    if not tokens or any(not token for token in tokens):
        raise HTTPException(
            status_code=422,
            detail="Danh sách mã doanh nghiệp không hợp lệ (không được chứa phần tử rỗng).",
        )
    parsed: list[int] = []
    for token in tokens:
        if not token.isdigit():
            raise HTTPException(
                status_code=422,
                detail=f"Mã doanh nghiệp không hợp lệ: '{token}'.",
            )
        value = int(token)
        if value <= 0:
            raise HTTPException(status_code=422, detail="Mã doanh nghiệp phải là số nguyên dương.")
        parsed.append(value)
    return parsed


@router.get("/compare", response_model=OrgCompareResponseView)
def compare_organization_companies(
    request: Request,
    ids: Annotated[str, Query(description="Comma-separated 2 to 4 organization company IDs")],
    db: Annotated[Session, Depends(get_db)],
    org_ctx: Annotated[OrgContext, Depends(require_org_role("viewer"))],
    common_fiscal_year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
) -> OrgCompareResponseView:
    """Compare 2 to 4 companies within the active organization workspace."""
    company_ids = _parse_company_ids(ids)
    return compare_org_companies(
        db,
        org_id=org_ctx.organization.id,
        company_ids=company_ids,
        common_fiscal_year=common_fiscal_year,
        model_registry=_get_model_registry(request),
    )


@router.get("/{company_id}/analysis", response_model=CompanyAssessmentView)
def get_organization_company_analysis(
    request: Request,
    company_id: int,
    db: Annotated[Session, Depends(get_db)],
    org_ctx: Annotated[OrgContext, Depends(require_org_role("viewer"))],
    fiscal_year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
) -> CompanyAssessmentView:
    """Return full V1.0 CompanyAssessmentView with 5 pillars, drivers, peers, and M11 history."""
    return get_org_company_assessment(
        db,
        org_id=org_ctx.organization.id,
        company_id=company_id,
        model_registry=_get_model_registry(request),
        fiscal_year=fiscal_year,
        force_recompute=False,
    )


@router.post("/{company_id}/recompute", response_model=CompanyAssessmentView)
def recompute_organization_company_analysis(
    request: Request,
    company_id: int,
    db: Annotated[Session, Depends(get_db)],
    org_ctx: Annotated[OrgContext, Depends(require_org_role("analyst"))],
    fiscal_year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
) -> CompanyAssessmentView:
    """Recompute and persist OrgAssessment snapshots for all finalized periods of a company."""
    return get_org_company_assessment(
        db,
        org_id=org_ctx.organization.id,
        company_id=company_id,
        model_registry=_get_model_registry(request),
        fiscal_year=fiscal_year,
        force_recompute=True,
    )
