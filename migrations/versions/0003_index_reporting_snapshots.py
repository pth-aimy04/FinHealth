"""Index latest-period lookups without scanning statement provenance payloads."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add covering keys for the dashboard's per-company ordered lookups."""
    op.create_index(
        "ix_statement_company_period_lookup",
        "financial_statements",
        ["company_id", "period_end_date", "form_type", "id"],
    )
    op.create_index(
        "ix_prediction_company_created_lookup",
        "model_predictions",
        ["company_id", "created_at", "id"],
    )


def downgrade() -> None:
    """Remove the snapshot indexes."""
    op.drop_index("ix_prediction_company_created_lookup", table_name="model_predictions")
    op.drop_index("ix_statement_company_period_lookup", table_name="financial_statements")
