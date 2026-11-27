"""Versioned financial disclosures and reproducible inference evidence."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from finhealth.db.base import Base, utc_now


class FilingVersion(Base):
    """An append-only normalized observation of one published report version."""

    __tablename__ = "filing_versions"
    __table_args__ = (
        UniqueConstraint("issuer_key", "fingerprint", name="uq_filing_versions_fingerprint"),
        Index("ix_filing_version_asof", "issuer_key", "period_end", "published_on", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    issuer_key: Mapped[str] = mapped_column(String(80))
    accession: Mapped[str] = mapped_column(String(80))
    form_type: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(24))
    fiscal_year: Mapped[int]
    fiscal_period: Mapped[str] = mapped_column(String(8))
    period_end: Mapped[date]
    published_on: Mapped[date]
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    fingerprint: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(1500))
    capture_kind: Mapped[str] = mapped_column(String(32))
    facts: Mapped[dict[str, Any]] = mapped_column(JSON)


class ForecastEvidence(Base):
    """Frozen reported inputs, fitted inputs and outputs for one inference."""

    __tablename__ = "forecast_evidence"
    __table_args__ = (
        UniqueConstraint(
            "filing_version_id", "model_version", "fingerprint", name="uq_forecast_evidence_input"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_version_id: Mapped[int] = mapped_column(ForeignKey("filing_versions.id"))
    model_version: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    input_status: Mapped[str] = mapped_column(String(32))
    reported_inputs: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    fitted_inputs: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    outputs: Mapped[dict[str, Any]] = mapped_column(JSON)


class IngestionRun(Base):
    """Durable state for a local, replayable ingestion job."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (Index(
        "uq_ingestion_active_key", "active_key", unique=True,
        mssql_where=text("active_key IS NOT NULL"),
        sqlite_where=text("active_key IS NOT NULL"),
        postgresql_where=text("active_key IS NOT NULL"),
    ),)

    id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0)
    company_cik: Mapped[str | None] = mapped_column(String(10))
    error_code: Mapped[str | None] = mapped_column(String(100))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stage: Mapped[str | None] = mapped_column(String(32))
    active_key: Mapped[str | None] = mapped_column(String(40))
    retry_of: Mapped[int | None]
