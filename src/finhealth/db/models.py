"""Typed relational contracts for financial fundamentals, features, and predictions."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import conv

from finhealth.db.base import Base, TimestampMixin, utc_now

CIK_SQL_SERVER_CHECK = "LEN(cik) = 10 AND cik COLLATE Latin1_General_100_BIN2 NOT LIKE '%[^0-9]%'"


def _outside_sqlserver(*args: object, dialect: Dialect, **kwargs: object) -> bool:
    """Enable the original DDL clauses on other supported engines."""
    return dialect.name != "mssql"


class Company(TimestampMixin, Base):
    """An SEC registrant identified by a canonical ten-digit CIK."""

    __tablename__ = "companies"
    # Portable ASCII digit validation, including SQLite's non-enforcing VARCHAR length.
    __table_args__ = (
        CheckConstraint(
            "length(cik) = 10 AND "
            "replace(replace(replace(replace(replace(replace(replace(replace("
            "replace(replace(cik, '0', ''), '1', ''), '2', ''), '3', ''), '4', ''), "
            "'5', ''), '6', ''), '7', ''), '8', ''), '9', '') = ''",
            name="cik_format",
        ).ddl_if(callable_=_outside_sqlserver),
        CheckConstraint(CIK_SQL_SERVER_CHECK, name="cik_format").ddl_if(dialect="mssql"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(
        String(255).with_variant(Unicode(255), "mssql"), nullable=False
    )
    sic_code: Mapped[str | None] = mapped_column(String(10), index=True)
    sector: Mapped[str | None] = mapped_column(String(100))

    statements: Mapped[list["FinancialStatement"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )
    metrics: Mapped[list["FinancialMetric"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )
    predictions: Mapped[list["ModelPrediction"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", passive_deletes=True
    )


class FinancialStatement(Base):
    """The latest accepted filing for a company, fiscal period, and form."""

    __tablename__ = "financial_statements"
    __table_args__ = (
        Index(
            "ix_statement_company_period_lookup", "company_id", "period_end_date", "form_type", "id"
        ),
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_period",
            "form_type",
            name="uq_statement_company_period_form",
        ),
        CheckConstraint(
            "fiscal_year >= 1990 AND fiscal_year <= 2100",
            name=conv("ck_statement_fiscal_year_range"),
        ),
        # Composite references prevent assigning a company's statement to another company.
        UniqueConstraint("id", "company_id", name="uq_statement_id_company"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    accession_number: Mapped[str] = mapped_column(String(32), nullable=False)
    form_type: Mapped[str] = mapped_column(String(10), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(nullable=False, index=True)
    fiscal_period: Mapped[str] = mapped_column(String(10), nullable=False)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    filed_date: Mapped[date] = mapped_column(Date, nullable=False)

    total_assets: Mapped[float | None] = mapped_column(Float)
    current_assets: Mapped[float | None] = mapped_column(Float)
    total_liabilities: Mapped[float | None] = mapped_column(Float)
    current_liabilities: Mapped[float | None] = mapped_column(Float)
    stockholders_equity: Mapped[float | None] = mapped_column(Float)
    retained_earnings: Mapped[float | None] = mapped_column(Float)
    revenues: Mapped[float | None] = mapped_column(Float)
    operating_income: Mapped[float | None] = mapped_column(Float)
    net_income: Mapped[float | None] = mapped_column(Float)
    operating_cash_flow: Mapped[float | None] = mapped_column(Float)
    eps_basic: Mapped[float | None] = mapped_column(Float)
    eps_diluted: Mapped[float | None] = mapped_column(Float)
    cash_and_equivalents: Mapped[float | None] = mapped_column(Float)
    interest_expense: Mapped[float | None] = mapped_column(Float)
    capex: Mapped[float | None] = mapped_column(Float)
    field_provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))

    company: Mapped[Company] = relationship(back_populates="statements")
    metric: Mapped["FinancialMetric | None"] = relationship(
        back_populates="statement",
        foreign_keys="FinancialMetric.statement_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    predictions: Mapped[list["ModelPrediction"]] = relationship(
        back_populates="source_statement",
        foreign_keys="ModelPrediction.source_statement_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FinancialMetric(Base):
    """One engineered feature record per normalized financial statement."""

    __tablename__ = "financial_metrics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["statement_id", "company_id"],
            ["financial_statements.id", "financial_statements.company_id"],
            name="fk_metric_statement_company",
            ondelete="CASCADE",
        ),
        # SQL Server permits a single cascade path, through the composite reference.
        ForeignKeyConstraint(
            ["statement_id"], ["financial_statements.id"], ondelete="CASCADE"
        ).ddl_if(callable_=_outside_sqlserver),
        ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ).ddl_if(callable_=_outside_sqlserver),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    company_id: Mapped[int] = mapped_column(index=True, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(nullable=False, index=True)
    fiscal_period: Mapped[str] = mapped_column(String(10), nullable=False)
    roa: Mapped[float | None] = mapped_column(Float)
    roe: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    debt_ratio: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)
    current_ratio: Mapped[float | None] = mapped_column(Float)
    operating_margin: Mapped[float | None] = mapped_column(Float)
    ocf_ratio: Mapped[float | None] = mapped_column(Float)
    cash_ratio: Mapped[float | None] = mapped_column(Float)
    interest_coverage: Mapped[float | None] = mapped_column(Float)
    fcf_to_liabilities: Mapped[float | None] = mapped_column(Float)
    working_capital_ratio: Mapped[float | None] = mapped_column(Float)
    retained_earnings_ratio: Mapped[float | None] = mapped_column(Float)
    ebit_to_assets: Mapped[float | None] = mapped_column(Float)
    asset_turnover: Mapped[float | None] = mapped_column(Float)
    altman_z_score: Mapped[float | None] = mapped_column(Float)
    altman_zone: Mapped[str | None] = mapped_column(String(20))
    roa_yoy_delta: Mapped[float | None] = mapped_column(Float)
    roe_yoy_delta: Mapped[float | None] = mapped_column(Float)
    debt_ratio_yoy_delta: Mapped[float | None] = mapped_column(Float)
    ocf_ratio_yoy_delta: Mapped[float | None] = mapped_column(Float)
    negative_ocf_streak: Mapped[int] = mapped_column(default=0, nullable=False)
    pca_comp_1: Mapped[float | None] = mapped_column(Float)
    pca_comp_2: Mapped[float | None] = mapped_column(Float)
    pca_comp_3: Mapped[float | None] = mapped_column(Float)
    cluster_id: Mapped[int | None] = mapped_column()
    cluster_label: Mapped[str | None] = mapped_column(String(100))

    company: Mapped[Company] = relationship(back_populates="metrics")
    statement: Mapped[FinancialStatement] = relationship(
        back_populates="metric", foreign_keys=[statement_id]
    )


class ModelPrediction(Base):
    """A versioned next-period forecast with distress probability and SHAP values."""

    __tablename__ = "model_predictions"
    __table_args__ = (
        Index("ix_prediction_company_created_lookup", "company_id", "created_at", "id"),
        UniqueConstraint(
            "company_id",
            "source_statement_id",
            "model_version",
            name="uq_prediction_company_stmt_version",
        ),
        CheckConstraint(
            "distress_probability IS NULL OR "
            "(distress_probability >= 0.0 AND distress_probability <= 1.0)",
            name=conv("ck_prediction_prob_bounds"),
        ),
        ForeignKeyConstraint(
            ["source_statement_id", "company_id"],
            ["financial_statements.id", "financial_statements.company_id"],
            name="fk_prediction_statement_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ).ddl_if(callable_=_outside_sqlserver),
        ForeignKeyConstraint(
            ["source_statement_id"], ["financial_statements.id"], ondelete="CASCADE"
        ).ddl_if(callable_=_outside_sqlserver),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(index=True, nullable=False)
    source_statement_id: Mapped[int] = mapped_column(index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    target_fiscal_year: Mapped[int] = mapped_column(nullable=False)
    target_fiscal_period: Mapped[str] = mapped_column(String(10), nullable=False)
    pred_roa: Mapped[float | None] = mapped_column(Float)
    pred_roe: Mapped[float | None] = mapped_column(Float)
    pred_eps: Mapped[float | None] = mapped_column(Float)
    pred_debt_ratio: Mapped[float | None] = mapped_column(Float)
    pred_ocf_ratio: Mapped[float | None] = mapped_column(Float)
    distress_probability: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str | None] = mapped_column(String(32))
    shap_explanations: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    company: Mapped[Company] = relationship(back_populates="predictions")
    source_statement: Mapped[FinancialStatement] = relationship(
        back_populates="predictions", foreign_keys=[source_statement_id]
    )
