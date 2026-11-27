"""Organization-scoped private company directory, statements, and assessment history."""

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finhealth.db.base import Base, TimestampMixin, utc_now


class OrgCompany(TimestampMixin, Base):
    """A private company profile strictly isolated within one organization workspace."""

    __tablename__ = "org_companies"
    __table_args__ = (
        CheckConstraint(
            "business_type IN ('manufacturing', 'trade_service', 'financial_institution')",
            name="org_company_business_type",
        ),
        CheckConstraint(
            "listing_status IN ('listed', 'unlisted')",
            name="org_company_listing_status",
        ),
        CheckConstraint(
            "relationship_tag IN ('own_company', 'customer', 'supplier', "
            "'competitor', 'portfolio', 'other')",
            name="org_company_relationship_tag",
        ),
        UniqueConstraint("id", "organization_id", name="uq_org_company_id_org"),
        Index(
            "uq_org_company_org_tax_code",
            "organization_id",
            "tax_code",
            unique=True,
            sqlite_where=text("tax_code IS NOT NULL"),
            postgresql_where=text("tax_code IS NOT NULL"),
            mssql_where=text("tax_code IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    tax_code: Mapped[str | None] = mapped_column(String(20), index=True)
    ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    sector_code: Mapped[str | None] = mapped_column(String(20), index=True)
    sector_name: Mapped[str | None] = mapped_column(Unicode(120))
    business_type: Mapped[str] = mapped_column(
        String(32), default="trade_service", nullable=False
    )
    listing_status: Mapped[str] = mapped_column(String(16), default="unlisted", nullable=False)
    relationship_tag: Mapped[str] = mapped_column(String(32), default="other", nullable=False)
    archived: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_sample: Mapped[bool] = mapped_column(default=False, nullable=False)

    statements: Mapped[list["OrgFinancialStatement"]] = relationship(
        back_populates="company",
        primaryjoin=(
            "and_(OrgCompany.id == foreign(OrgFinancialStatement.org_company_id), "
            "OrgCompany.organization_id == foreign(OrgFinancialStatement.organization_id))"
        ),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrgFinancialStatement(TimestampMixin, Base):
    """A normalized multi-standard financial statement belonging to one organization company."""

    __tablename__ = "org_financial_statements"
    __table_args__ = (
        CheckConstraint(
            "fiscal_year >= 1990 AND fiscal_year <= 2100",
            name="org_stmt_fiscal_year_range",
        ),
        CheckConstraint(
            "accounting_standard IN ('TT99_2025', 'TT200_2014', 'TT133_2016', 'IFRS_USGAAP')",
            name="org_stmt_accounting_standard",
        ),
        CheckConstraint("currency IN ('VND', 'USD')", name="org_stmt_currency"),
        CheckConstraint(
            "unit_scale IN (1, 1000, 1000000, 1000000000)", name="org_stmt_unit_scale"
        ),
        CheckConstraint(
            "audit_status IN ('audited_unqualified', 'audited_qualified', "
            "'audited_adverse_disclaimer', 'unaudited')",
            name="org_stmt_audit_status",
        ),
        CheckConstraint("status IN ('draft', 'finalized')", name="org_stmt_status"),
        CheckConstraint(
            "source_channel IN ('web_form', 'excel_upload', 'htkk_xml', 'sample')",
            name="org_stmt_source_channel",
        ),
        UniqueConstraint(
            "org_company_id",
            "fiscal_year",
            "fiscal_period",
            name="uq_org_stmt_company_period",
        ),
        UniqueConstraint(
            "id",
            "org_company_id",
            "organization_id",
            name="uq_org_stmt_id_company_org",
        ),
        ForeignKeyConstraint(
            ["org_company_id", "organization_id"],
            ["org_companies.id", "org_companies.organization_id"],
            name="fk_org_stmt_company_org",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True, nullable=False)
    org_company_id: Mapped[int] = mapped_column(index=True, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(index=True, nullable=False)
    fiscal_period: Mapped[str] = mapped_column(String(10), default="FY", nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    accounting_standard: Mapped[str] = mapped_column(
        String(20), default="TT99_2025", nullable=False
    )
    currency: Mapped[str] = mapped_column(String(8), default="VND", nullable=False)
    unit_scale: Mapped[int] = mapped_column(default=1, nullable=False)
    display_unit: Mapped[str] = mapped_column(String(16), default="VND", nullable=False)
    audit_status: Mapped[str] = mapped_column(String(32), default="unaudited", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    source_channel: Mapped[str] = mapped_column(String(24), default="web_form", nullable=False)

    total_assets: Mapped[float | None] = mapped_column(Float)
    current_assets: Mapped[float | None] = mapped_column(Float)
    cash_and_equivalents: Mapped[float | None] = mapped_column(Float)
    accounts_receivable: Mapped[float | None] = mapped_column(Float)
    inventory: Mapped[float | None] = mapped_column(Float)
    total_liabilities: Mapped[float | None] = mapped_column(Float)
    current_liabilities: Mapped[float | None] = mapped_column(Float)
    short_term_debt: Mapped[float | None] = mapped_column(Float)
    long_term_debt: Mapped[float | None] = mapped_column(Float)
    accounts_payable: Mapped[float | None] = mapped_column(Float)
    stockholders_equity: Mapped[float | None] = mapped_column(Float)
    retained_earnings: Mapped[float | None] = mapped_column(Float)

    revenues: Mapped[float | None] = mapped_column(Float)
    cost_of_goods_sold: Mapped[float | None] = mapped_column(Float)
    gross_profit: Mapped[float | None] = mapped_column(Float)
    operating_expenses: Mapped[float | None] = mapped_column(Float)
    operating_income: Mapped[float | None] = mapped_column(Float)
    depreciation_amortization: Mapped[float | None] = mapped_column(Float)
    ebitda: Mapped[float | None] = mapped_column(Float)
    interest_expense: Mapped[float | None] = mapped_column(Float)
    net_income: Mapped[float | None] = mapped_column(Float)

    operating_cash_flow: Mapped[float | None] = mapped_column(Float)
    capex: Mapped[float | None] = mapped_column(Float)
    market_value_equity: Mapped[float | None] = mapped_column(Float)
    eps_basic: Mapped[float | None] = mapped_column(Float)
    eps_diluted: Mapped[float | None] = mapped_column(Float)

    validation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    raw_source_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)

    company: Mapped[OrgCompany] = relationship(
        back_populates="statements",
        primaryjoin=(
            "and_(OrgCompany.id == foreign(OrgFinancialStatement.org_company_id), "
            "OrgCompany.organization_id == foreign(OrgFinancialStatement.organization_id))"
        ),
    )
    assessments: Mapped[list["OrgAssessment"]] = relationship(
        back_populates="statement",
        primaryjoin=(
            "and_(OrgFinancialStatement.id == foreign(OrgAssessment.org_statement_id), "
            "OrgFinancialStatement.org_company_id == foreign(OrgAssessment.org_company_id), "
            "OrgFinancialStatement.organization_id == foreign(OrgAssessment.organization_id))"
        ),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OrgAssessment(Base):
    """Frozen multi-period risk assessment snapshot bound to statement and model version."""

    __tablename__ = "org_assessments"
    __table_args__ = (
        CheckConstraint(
            "scoring_mode IN ('single_period', 'multi_period', 'excluded')",
            name="org_assessment_scoring_mode",
        ),
        CheckConstraint(
            "pd_12m IS NULL OR (pd_12m >= 0.0 AND pd_12m <= 1.0)",
            name="org_assessment_pd_bounds",
        ),
        CheckConstraint(
            "health_score IS NULL OR (health_score >= 0.0 AND health_score <= 100.0)",
            name="org_assessment_health_bounds",
        ),
        CheckConstraint(
            "risk_tier IS NULL OR risk_tier IN ('STRONG', 'STABLE', 'WATCH', 'CRITICAL')",
            name="org_assessment_risk_tier",
        ),
        CheckConstraint(
            "confidence_level IS NULL OR confidence_level IN ('HIGH', 'MODERATE', 'LOW')",
            name="org_assessment_confidence_level",
        ),
        UniqueConstraint(
            "org_statement_id",
            "model_version",
            name="uq_org_assessment_stmt_model",
        ),
        Index("ix_org_assessment_company_created", "org_company_id", "created_at", "id"),
        ForeignKeyConstraint(
            ["org_statement_id", "org_company_id", "organization_id"],
            [
                "org_financial_statements.id",
                "org_financial_statements.org_company_id",
                "org_financial_statements.organization_id",
            ],
            name="fk_org_assessment_stmt_company_org",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(index=True, nullable=False)
    org_company_id: Mapped[int] = mapped_column(index=True, nullable=False)
    org_statement_id: Mapped[int] = mapped_column(index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), default="v1.0", nullable=False)
    scoring_mode: Mapped[str] = mapped_column(String(20), default="single_period", nullable=False)
    pd_12m: Mapped[float | None] = mapped_column(Float)
    health_score: Mapped[float | None] = mapped_column(Float)
    risk_tier: Mapped[str | None] = mapped_column(String(16))
    altman_variant: Mapped[str | None] = mapped_column(String(8))
    altman_z_score: Mapped[float | None] = mapped_column(Float)
    altman_zone: Mapped[str | None] = mapped_column(String(20))
    confidence_level: Mapped[str | None] = mapped_column(String(16))
    cash_flow_overlay_triggered: Mapped[bool] = mapped_column(default=False, nullable=False)
    confidence_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    drivers_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    pillars_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    diagnostics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    statement: Mapped[OrgFinancialStatement] = relationship(
        back_populates="assessments",
        primaryjoin=(
            "and_(OrgFinancialStatement.id == foreign(OrgAssessment.org_statement_id), "
            "OrgFinancialStatement.org_company_id == foreign(OrgAssessment.org_company_id), "
            "OrgFinancialStatement.organization_id == foreign(OrgAssessment.organization_id))"
        ),
    )
