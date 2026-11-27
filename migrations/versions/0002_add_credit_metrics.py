"""Store nullable underwriting inputs, provenance, and credit metrics."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

INPUTS = ("cash_and_equivalents", "interest_expense", "capex")
METRICS = ("cash_ratio", "interest_coverage", "fcf_to_liabilities")


def upgrade() -> None:
    """Add nullable fields without fabricating values for existing periods."""
    for name in INPUTS:
        op.add_column("financial_statements", sa.Column(name, sa.Float(), nullable=True))
    op.add_column(
        "financial_statements",
        sa.Column("field_provenance", sa.JSON(none_as_null=True), nullable=True),
    )
    for name in METRICS:
        op.add_column("financial_metrics", sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove only the fields introduced by this revision."""
    for name in METRICS:
        op.drop_column("financial_metrics", name)
    for name in (*INPUTS, "field_provenance"):
        op.drop_column("financial_statements", name)
