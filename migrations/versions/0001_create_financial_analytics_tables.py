"""Create financial analytics tables

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import SchemaItem

from finhealth.db.models import CIK_SQL_SERVER_CHECK

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema changes for this revision."""
    sql_server = op.get_context().dialect.name == "mssql"
    cik_check = (
        CIK_SQL_SERVER_CHECK
        if sql_server
        else "length(cik) = 10 AND "
        "replace(replace(replace(replace(replace(replace(replace(replace("
        "replace(replace(cik, '0', ''), '1', ''), '2', ''), '3', ''), '4', ''), "
        "'5', ''), '6', ''), '7', ''), '8', ''), '9', '') = ''"
    )
    metric_extra_fks: tuple[SchemaItem, ...] = () if sql_server else (
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_financial_metrics_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["financial_statements.id"],
            name=op.f("fk_financial_metrics_statement_id_financial_statements"),
            ondelete="CASCADE",
        ),
    )
    prediction_extra_fks: tuple[SchemaItem, ...] = () if sql_server else (
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_model_predictions_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_statement_id"],
            ["financial_statements.id"],
            name=op.f("fk_model_predictions_source_statement_id_financial_statements"),
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=True),
        sa.Column("name", sa.Unicode(length=255) if sql_server else sa.String(255), nullable=False),
        sa.Column("sic_code", sa.String(length=10), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            cik_check,
            name=op.f("ck_companies_cik_format"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.create_index(op.f("ix_companies_cik"), "companies", ["cik"], unique=True)
    op.create_index(op.f("ix_companies_sic_code"), "companies", ["sic_code"], unique=False)
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=False)
    op.create_table(
        "financial_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("form_type", sa.String(length=10), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(length=10), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("filed_date", sa.Date(), nullable=False),
        sa.Column("total_assets", sa.Float(), nullable=True),
        sa.Column("current_assets", sa.Float(), nullable=True),
        sa.Column("total_liabilities", sa.Float(), nullable=True),
        sa.Column("current_liabilities", sa.Float(), nullable=True),
        sa.Column("stockholders_equity", sa.Float(), nullable=True),
        sa.Column("retained_earnings", sa.Float(), nullable=True),
        sa.Column("revenues", sa.Float(), nullable=True),
        sa.Column("operating_income", sa.Float(), nullable=True),
        sa.Column("net_income", sa.Float(), nullable=True),
        sa.Column("operating_cash_flow", sa.Float(), nullable=True),
        sa.Column("eps_basic", sa.Float(), nullable=True),
        sa.Column("eps_diluted", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "fiscal_year >= 1990 AND fiscal_year <= 2100",
            name=op.f("ck_statement_fiscal_year_range"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_financial_statements_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_financial_statements")),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_period",
            "form_type",
            name="uq_statement_company_period_form",
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_statement_id_company"),
    )
    op.create_index(
        op.f("ix_financial_statements_company_id"),
        "financial_statements",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_financial_statements_fiscal_year"),
        "financial_statements",
        ["fiscal_year"],
        unique=False,
    )
    op.create_table(
        "financial_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(length=10), nullable=False),
        sa.Column("roa", sa.Float(), nullable=True),
        sa.Column("roe", sa.Float(), nullable=True),
        sa.Column("eps", sa.Float(), nullable=True),
        sa.Column("debt_ratio", sa.Float(), nullable=True),
        sa.Column("debt_to_equity", sa.Float(), nullable=True),
        sa.Column("current_ratio", sa.Float(), nullable=True),
        sa.Column("operating_margin", sa.Float(), nullable=True),
        sa.Column("ocf_ratio", sa.Float(), nullable=True),
        sa.Column("working_capital_ratio", sa.Float(), nullable=True),
        sa.Column("retained_earnings_ratio", sa.Float(), nullable=True),
        sa.Column("ebit_to_assets", sa.Float(), nullable=True),
        sa.Column("asset_turnover", sa.Float(), nullable=True),
        sa.Column("altman_z_score", sa.Float(), nullable=True),
        sa.Column("altman_zone", sa.String(length=20), nullable=True),
        sa.Column("roa_yoy_delta", sa.Float(), nullable=True),
        sa.Column("roe_yoy_delta", sa.Float(), nullable=True),
        sa.Column("debt_ratio_yoy_delta", sa.Float(), nullable=True),
        sa.Column("ocf_ratio_yoy_delta", sa.Float(), nullable=True),
        sa.Column("negative_ocf_streak", sa.Integer(), nullable=False),
        sa.Column("pca_comp_1", sa.Float(), nullable=True),
        sa.Column("pca_comp_2", sa.Float(), nullable=True),
        sa.Column("pca_comp_3", sa.Float(), nullable=True),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("cluster_label", sa.String(length=100), nullable=True),
        *metric_extra_fks,
        sa.ForeignKeyConstraint(
            ["statement_id", "company_id"],
            ["financial_statements.id", "financial_statements.company_id"],
            name="fk_metric_statement_company",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_financial_metrics")),
        sa.UniqueConstraint("statement_id", name=op.f("uq_financial_metrics_statement_id")),
    )
    op.create_index(
        op.f("ix_financial_metrics_company_id"), "financial_metrics", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_financial_metrics_fiscal_year"), "financial_metrics", ["fiscal_year"], unique=False
    )
    op.create_table(
        "model_predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_statement_id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("target_fiscal_year", sa.Integer(), nullable=False),
        sa.Column("target_fiscal_period", sa.String(length=10), nullable=False),
        sa.Column("pred_roa", sa.Float(), nullable=True),
        sa.Column("pred_roe", sa.Float(), nullable=True),
        sa.Column("pred_eps", sa.Float(), nullable=True),
        sa.Column("pred_debt_ratio", sa.Float(), nullable=True),
        sa.Column("pred_ocf_ratio", sa.Float(), nullable=True),
        sa.Column("distress_probability", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(length=32), nullable=True),
        sa.Column("shap_explanations", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "distress_probability IS NULL OR "
            "(distress_probability >= 0.0 AND distress_probability <= 1.0)",
            name=op.f("ck_prediction_prob_bounds"),
        ),
        *prediction_extra_fks,
        sa.ForeignKeyConstraint(
            ["source_statement_id", "company_id"],
            ["financial_statements.id", "financial_statements.company_id"],
            name="fk_prediction_statement_company",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_predictions")),
        sa.UniqueConstraint(
            "company_id",
            "source_statement_id",
            "model_version",
            name="uq_prediction_company_stmt_version",
        ),
    )
    op.create_index(
        op.f("ix_model_predictions_company_id"), "model_predictions", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_model_predictions_source_statement_id"),
        "model_predictions",
        ["source_statement_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Reverse the schema changes for this revision."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_model_predictions_source_statement_id"), table_name="model_predictions")
    op.drop_index(op.f("ix_model_predictions_company_id"), table_name="model_predictions")
    op.drop_table("model_predictions")
    op.drop_index(op.f("ix_financial_metrics_fiscal_year"), table_name="financial_metrics")
    op.drop_index(op.f("ix_financial_metrics_company_id"), table_name="financial_metrics")
    op.drop_table("financial_metrics")
    op.drop_index(op.f("ix_financial_statements_fiscal_year"), table_name="financial_statements")
    op.drop_index(op.f("ix_financial_statements_company_id"), table_name="financial_statements")
    op.drop_table("financial_statements")
    op.drop_index(op.f("ix_companies_ticker"), table_name="companies")
    op.drop_index(op.f("ix_companies_sic_code"), table_name="companies")
    op.drop_index(op.f("ix_companies_cik"), table_name="companies")
    op.drop_table("companies")
    # ### end Alembic commands ###
