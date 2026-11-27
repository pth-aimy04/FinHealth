"""Organization-scoped asynchronous Excel batch assessment persistence."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finhealth.db.base import Base, utc_now


class OrgBatchJob(Base):
    """A DB-backed background job tracking Excel batch assessment progress."""

    __tablename__ = "org_batch_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="org_batch_job_status",
        ),
        UniqueConstraint("id", "organization_id", name="uq_org_batch_job_id_org"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(64))
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    processed_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    succeeded_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Unicode(500))
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    rows: Mapped[list["OrgBatchJobRow"]] = relationship(
        back_populates="job",
        primaryjoin=(
            "and_(OrgBatchJob.id == foreign(OrgBatchJobRow.job_id), "
            "OrgBatchJob.organization_id == foreign(OrgBatchJobRow.organization_id))"
        ),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrgBatchJobRow(Base):
    """Per-row input and isolated assessment result within an Excel batch job."""

    __tablename__ = "org_batch_job_rows"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'excluded')",
            name="org_batch_row_status",
        ),
        CheckConstraint(
            "pd_12m IS NULL OR (pd_12m >= 0.0 AND pd_12m <= 1.0)",
            name="org_batch_row_pd_bounds",
        ),
        CheckConstraint(
            "health_score IS NULL OR (health_score >= 0.0 AND health_score <= 100.0)",
            name="org_batch_row_health_bounds",
        ),
        CheckConstraint(
            "risk_tier IS NULL OR risk_tier IN ('STRONG', 'STABLE', 'WATCH', 'CRITICAL')",
            name="org_batch_row_risk_tier",
        ),
        CheckConstraint(
            "confidence_level IS NULL OR confidence_level IN ('HIGH', 'MODERATE', 'LOW')",
            name="org_batch_row_confidence_level",
        ),
        UniqueConstraint("job_id", "row_index", name="uq_org_batch_row_job_index"),
        Index("ix_org_batch_row_job_pd", "job_id", "pd_12m"),
        ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["org_batch_jobs.id", "org_batch_jobs.organization_id"],
            name="fk_org_batch_row_job_org",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(index=True, nullable=False)
    organization_id: Mapped[int] = mapped_column(index=True, nullable=False)
    row_index: Mapped[int] = mapped_column(nullable=False)
    company_name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    tax_code: Mapped[str | None] = mapped_column(String(20))
    fiscal_year: Mapped[int | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    pd_12m: Mapped[float | None] = mapped_column(Float)
    health_score: Mapped[float | None] = mapped_column(Float)
    risk_tier: Mapped[str | None] = mapped_column(String(16))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    top_bottleneck_vi: Mapped[str | None] = mapped_column(Unicode(300))
    error_message: Mapped[str | None] = mapped_column(Unicode(500))
    input_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))

    job: Mapped[OrgBatchJob] = relationship(
        back_populates="rows",
        primaryjoin=(
            "and_(OrgBatchJob.id == foreign(OrgBatchJobRow.job_id), "
            "OrgBatchJob.organization_id == foreign(OrgBatchJobRow.organization_id))"
        ),
    )
