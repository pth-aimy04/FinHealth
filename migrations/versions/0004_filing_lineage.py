"""Create the additive filing and forecast lineage storage."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.orm import Session

from finhealth.db.lineage import backfill_legacy_evidence
from finhealth.db.lineage_models import FilingVersion, ForecastEvidence, IngestionRun

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the append-only history and the ingestion job table."""
    for model in (FilingVersion, ForecastEvidence):
        model.__table__.create(op.get_bind())
    # Freeze the original schema: later account fields belong to revision 0005.
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identifier", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("company_cik", sa.String(10)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    if context.is_offline_mode():
        return
    with Session(bind=op.get_bind(), join_transaction_mode="rollback_only") as session:
        backfill_legacy_evidence(session)


def downgrade() -> None:
    """Remove the lineage tables in foreign-key order."""
    for model in (IngestionRun, ForecastEvidence, FilingVersion):
        model.__table__.drop(op.get_bind())
