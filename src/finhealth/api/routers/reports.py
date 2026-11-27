"""Thin read-only endpoints for report versions, forecasts and coverage."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from finhealth.api import reporting
from finhealth.api.dependencies import get_db
from finhealth.api.schemas.reporting import (
    DataQualitySchema,
    ForecastEvidenceSchema,
    ReportAlertSchema,
    ReportResponseSchema,
)

router = APIRouter(tags=["reports"])


@router.get("/reports/{identifier}", response_model=ReportResponseSchema)
def list_reports(
    identifier: str, db: Annotated[Session, Depends(get_db)],
    as_of: date | None = None, period_kind: Annotated[str | None, Query(max_length=16)] = None,
) -> dict[str, Any]:
    """Return stored disclosures available by the requested publication cutoff."""
    return reporting.list_reports(identifier, db, as_of, period_kind)


@router.get("/report-alerts/{identifier}", response_model=list[ReportAlertSchema])
def report_alerts(
    identifier: str, db: Annotated[Session, Depends(get_db)], as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Read source-linked changes between compatible published report versions."""
    return reporting.report_alerts(identifier, db, as_of)


@router.get("/filings/{filing_id}/forecasts", response_model=list[ForecastEvidenceSchema])
def list_forecast_evidence(
    filing_id: int, db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Read archived inference inputs and outputs for the selected report."""
    return reporting.list_forecast_evidence(filing_id, db)


@router.get("/data-quality", response_model=DataQualitySchema)
def data_quality(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    """Count observed ratios in the latest annual company snapshots."""
    return reporting.data_quality(db)
