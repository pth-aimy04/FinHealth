"""Thin company analysis, retrieval, and cluster-map endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from finhealth.api.dependencies import (
    get_active_model_bundle,
    get_db,
    get_sec_edgar_client,
    require_write_access,
)
from finhealth.api.schemas import (
    ClusterPointSchema,
    CompanyFullAnalysisSchema,
    CompanySummarySchema,
)
from finhealth.api.schemas.models import (
    CompanyComparisonResponseSchema,
    CompanyScreeningFilters,
    StressScenarioRequestSchema,
    StressSimulationResponseSchema,
)
from finhealth.api.security import check_prediction_rate, request_limit, require_admin
from finhealth.api.services import FinancialAnalysisService
from finhealth.db.account_models import AdminAuditLog, User
from finhealth.ingestion.sec_client import SecEdgarClient
from finhealth.ml.registry import ModelArtifactBundle

router = APIRouter(tags=["companies"])
FormType = Literal["10-K", "10-Q"]
_SUMMARY_LIST = TypeAdapter(list[CompanySummarySchema])
_CLUSTER_LIST = TypeAdapter(list[ClusterPointSchema])
_COMPANY_ANALYSIS = TypeAdapter(CompanyFullAnalysisSchema)


@router.get("/companies", response_model=list[CompanySummarySchema])
def list_companies(
    db: Annotated[Session, Depends(get_db)],
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    filters: Annotated[CompanyScreeningFilters, Depends()],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    """Return persisted company snapshots with bounded stable pagination."""
    summaries = FinancialAnalysisService().list_company_summaries(
        db, limit, offset, bundle.model_version if bundle else None, filters=filters,
    )
    return Response(_SUMMARY_LIST.dump_json(summaries), media_type="application/json")


@router.get("/companies/compare", response_model=CompanyComparisonResponseSchema)
def compare_companies(
    db: Annotated[Session, Depends(get_db)],
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    identifiers: Annotated[str, Query(min_length=1, max_length=180)],
    common_fiscal_year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
) -> CompanyComparisonResponseSchema:
    """Compare two to four stored issuers with an optional common annual fiscal year."""
    return FinancialAnalysisService().compare_companies(db, identifiers, common_fiscal_year, bundle)


@router.get("/companies/{identifier}", response_model=CompanyFullAnalysisSchema)
def get_company(
    identifier: str,
    db: Annotated[Session, Depends(get_db)],
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    form_type: FormType = "10-K",
    include_provenance: bool = False,
) -> Response:
    """Read stored annual or quarterly analysis without performing ingestion."""
    analysis = FinancialAnalysisService().get_company_full_analysis(
        db, identifier, form_type, bundle, include_provenance=include_provenance
    )
    return Response(_COMPANY_ANALYSIS.dump_json(analysis), media_type="application/json")


@router.post(
    "/companies/{identifier}/analyze", response_model=CompanyFullAnalysisSchema,
    dependencies=[Depends(require_write_access)],
)
async def analyze_company(
    identifier: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    sec_client: Annotated[SecEdgarClient, Depends(get_sec_edgar_client)],
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
    actor: Annotated[User, Depends(require_admin)],
    form_type: FormType = "10-K",
    force_refresh: bool = False,
) -> CompanyFullAnalysisSchema:
    """Run SEC ingestion, ETL, optional actual model inference, and atomic persistence."""
    if request.app.state.settings.ingestion_worker_enabled:
        raise HTTPException(409, "Submit refresh through the ingestion queue")
    request_limit(db, request, "direct-refresh", 10)
    db.add(AdminAuditLog(actor_id=actor.id, action="company.refresh", target=identifier,
                         outcome="requested"))
    db.commit()
    result = await FinancialAnalysisService().ingest_and_analyze_company(
        db, sec_client, identifier, bundle, form_type, force_refresh
    )
    db.add(AdminAuditLog(actor_id=actor.id, action="company.refresh", target=identifier))
    db.commit()
    return result


@router.get("/clusters/map", response_model=list[ClusterPointSchema])
def cluster_map(
    db: Annotated[Session, Depends(get_db)],
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
) -> Response:
    """Read real latest assigned PCA positions from the database."""
    points = FinancialAnalysisService().get_cluster_map_points(
        db, bundle.model_version if bundle else None
    )
    return Response(_CLUSTER_LIST.dump_json(points), media_type="application/json")


@router.post("/companies/{identifier}/simulate", response_model=StressSimulationResponseSchema,
             dependencies=[Depends(check_prediction_rate)])
def simulate_company(
    identifier: str,
    scenario: StressScenarioRequestSchema,
    db: Annotated[Session, Depends(get_db)],
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
) -> StressSimulationResponseSchema:
    """Evaluate a hypothetical scenario without persisting statements or predictions."""
    return FinancialAnalysisService().simulate_company(db, identifier, scenario, bundle)
