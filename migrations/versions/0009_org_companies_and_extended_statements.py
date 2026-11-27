"""Create organization company/statement tables and extend SEC statement columns."""

import sqlalchemy as sa
from alembic import op

from finhealth.db import org_models

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

EXTENDED_STATEMENT_COLUMNS = (
    "cost_of_goods_sold",
    "gross_profit",
    "operating_expenses",
    "depreciation_amortization",
    "ebitda",
    "accounts_receivable",
    "inventory",
    "accounts_payable",
    "long_term_debt",
    "short_term_debt",
    "market_value_equity",
)


def upgrade() -> None:
    """Add nullable statement fields and create tenant-isolated company/statement tables."""
    for name in EXTENDED_STATEMENT_COLUMNS:
        op.add_column("financial_statements", sa.Column(name, sa.Float(), nullable=True))

    bind = op.get_bind()
    org_models.OrgCompany.__table__.create(bind)
    org_models.OrgFinancialStatement.__table__.create(bind)


def downgrade() -> None:
    """Drop organization company/statement tables and remove extended SEC statement columns."""
    bind = op.get_bind()
    org_models.OrgFinancialStatement.__table__.drop(bind)
    org_models.OrgCompany.__table__.drop(bind)

    with op.batch_alter_table("financial_statements") as batch:
        for name in reversed(EXTENDED_STATEMENT_COLUMNS):
            batch.drop_column(name)
