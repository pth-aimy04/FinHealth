"""Pydantic v2 contracts for asynchronous Excel batch jobs and reporting endpoints."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from finhealth.api.schemas.analytics import LEGAL_DISCLAIMER_VI
from finhealth.ml.feature_contracts import ConfidenceLevel, RiskTier

BatchJobStatus = Literal["queued", "running", "completed", "failed"]
BatchRowStatus = Literal["pending", "succeeded", "failed", "excluded"]


class BatchJobSummary(BaseModel):
    """High-level status and progress summary for an organization batch job."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by: int | None = None
    filename: str
    status: BatchJobStatus
    model_version: str | None = None
    total_rows: int = Field(ge=0)
    processed_rows: int = Field(ge=0)
    succeeded_rows: int = Field(ge=0)
    failed_rows: int = Field(ge=0)
    error_message: str | None = None
    summary: dict[str, Any] | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class BatchRowResult(BaseModel):
    """Single company assessment result inside a batch job, ranked by pd_12m descending."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    row_index: int
    risk_rank: int | None = None
    company_name: str
    tax_code: str | None = None
    fiscal_year: int | None = None
    status: BatchRowStatus
    pd_12m: float | None = Field(default=None, ge=0.0, le=1.0)
    health_score: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_tier: RiskTier | None = None
    confidence_level: ConfidenceLevel | None = None
    top_bottleneck_vi: str | None = None
    error_message: str | None = None
    result_meta: dict[str, Any] | None = None


class BatchJobDetail(BatchJobSummary):
    """Full batch job status with risk-ranked per-company rows."""

    rows: list[BatchRowResult] = Field(default_factory=list)
    legal_disclaimer_vi: str = LEGAL_DISCLAIMER_VI
