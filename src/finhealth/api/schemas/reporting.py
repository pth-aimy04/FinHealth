"""Validated public contracts for report lineage and reporting-period arithmetic."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field

from finhealth.api.schemas.models import ApiSchema


class FilingVersionSchema(ApiSchema):
    """One stored observation with its publication date and per-field source evidence."""

    id: int
    issuer_key: str
    accession: str
    form_type: str
    scope: str
    fiscal_year: int
    fiscal_period: str
    period_end: date
    published_on: date
    captured_at: datetime
    capture_kind: str
    source_url: str | None
    fingerprint: str
    values: dict[str, int | float | None]
    provenance: dict[str, dict[str, Any]]
    missing_reasons: dict[str, str]
    ratios: dict[str, float | None]
    accounting_framework: str | None = None
    audit_status: str | None = None
    issuer_name: str | None = None
    disclosure_url: str | None = None
    ingestion_method: str | None = None


class QuarterFlowSchema(ApiSchema):
    """A quarter flow and derived comparisons with explicit missingness and source inputs."""

    value: float | None
    reason: str | None
    unit: str | None
    start: date | None
    end: date
    sources: list[dict[str, Any]]
    yoy_change: float | None
    qoq_change: float | None
    yoy_growth: float | None
    qoq_growth: float | None
    ttm: float | None
    ttm_reason: str | None


class QuarterlyReportSchema(ApiSchema):
    """Quarter-only observations keyed by the issuer's fiscal year and period."""

    fiscal_year: int
    fiscal_period: Literal["Q1", "Q2", "Q3", "Q4"]
    period_end: date
    flows: dict[str, QuarterFlowSchema]


class ReportResponseSchema(ApiSchema):
    """Available report versions and reporting-only quarterly series."""

    issuer_key: str
    as_of: date | None
    versions: list[FilingVersionSchema]
    quarterly_series: list[QuarterlyReportSchema]


class ReportAlertSchema(ApiSchema):
    """A versioned change rule with both source observation identifiers."""

    rule: str
    rule_version: int = Field(ge=1)
    previous_filing_id: int
    filing_id: int
    published_on: date
    changed_fields: list[str]
    source_url: str | None


class ForecastEvidenceSchema(ApiSchema):
    """Frozen original or explicitly unverified legacy inference evidence."""

    id: int
    filing_version_id: int
    model_version: str
    input_status: Literal["verified_inputs", "legacy_unverified"]
    reported_inputs: dict[str, float | None] | None
    fitted_inputs: dict[str, float] | None
    outputs: dict[str, Any]
    fingerprint: str


class DataQualitySchema(ApiSchema):
    """Actual annual snapshot denominator and observed metric counts."""

    report_count: int = Field(ge=0)
    observed: dict[str, int]
