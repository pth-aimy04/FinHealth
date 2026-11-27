"""Session-bound repositories; callers commit or roll back the complete unit of work.

Upserts use natural-key lookups within the caller's transaction. Unique constraints
remain the final guard against concurrent insert races; callers must retry the whole
transaction after an IntegrityError rather than reuse a failed session.
"""

import re
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import ScalarSelect

from finhealth.core.constants import US_GAAP_TAG_FALLBACKS
from finhealth.db.lineage import archive_forecast, archive_statement
from finhealth.db.lineage_models import ForecastEvidence
from finhealth.db.models import Company, FinancialMetric, FinancialStatement, ModelPrediction

_ACCOUNTING_FIELDS = frozenset(US_GAAP_TAG_FALLBACKS)
_METRIC_FIELDS = frozenset(FinancialMetric.__table__.columns.keys()) - {
    "id",
    "statement_id",
    "company_id",
    "fiscal_year",
    "fiscal_period",
}
_PREDICTION_FIELDS = frozenset(ModelPrediction.__table__.columns.keys()) - {
    "id",
    "company_id",
    "source_statement_id",
    "model_version",
    "target_fiscal_year",
    "target_fiscal_period",
    "created_at",
}


def latest_annual_statement_id(fiscal_year: int | None = None) -> ScalarSelect[int]:
    """Correlate the newest annual statement with the company in the enclosing query."""
    statement = FinancialStatement.__table__.alias("annual_snapshot")
    query = select(statement.c.id).where(
        statement.c.company_id == Company.id, statement.c.form_type == "10-K"
    )
    if fiscal_year is not None:
        query = query.where(statement.c.fiscal_year == fiscal_year)
    return (
        query.order_by(statement.c.period_end_date.desc(), statement.c.id.desc())
        .limit(1)
        .correlate(Company.__table__)
        .scalar_subquery()
    )


def normalize_cik(cik: object) -> str:
    """Strip optional CIK markers at either end and pad one to ten ASCII digits."""
    if isinstance(cik, bool) or not isinstance(cik, (str, int)):
        raise ValueError("CIK must be a string or integer containing 1 to 10 ASCII digits")
    value = re.sub(r"(?i)^CIK\s*|\s*CIK$", "", str(cik).strip()).strip()
    if re.fullmatch(r"[0-9]{1,10}", value) is None:
        raise ValueError("CIK must contain 1 to 10 ASCII digits after removing CIK markers")
    return value.zfill(10)


def _validate_payload(data: dict[str, Any], allowed: frozenset[str]) -> None:
    """Reject unknown fields and attempts to overwrite identity or relationship keys."""
    unknown = data.keys() - allowed
    if unknown:
        raise ValueError(f"Unsupported payload fields: {', '.join(sorted(unknown))}")


def _require_statement(session: Session, statement_id: int, company_id: int) -> FinancialStatement:
    """Reject absent source statements and mismatched company ownership."""
    statement = session.get(FinancialStatement, statement_id)
    if statement is None or statement.company_id != company_id:
        raise ValueError("Source statement must exist and belong to the supplied company")
    return statement


class CompanyRepository:
    """Create and query registrants by canonical SEC identity."""

    def __init__(self, session: Session) -> None:
        """Bind repository operations to the caller's transaction."""
        self.session = session

    def upsert_company(
        self,
        cik: str | int,
        name: str,
        ticker: str | None = None,
        sic_code: str | None = None,
        sector: str | None = None,
    ) -> Company:
        """Create or replace company attributes by CIK without committing."""
        normalized = normalize_cik(cik)
        company = self.get_by_cik(normalized)
        if company is None:
            company = Company(cik=normalized, name=name)
            self.session.add(company)
        company.name = name
        company.ticker = ticker.strip().upper() if ticker is not None else None
        company.sic_code = sic_code
        company.sector = sector
        self.session.flush()
        return company

    def get_by_cik(self, cik: str | int) -> Company | None:
        """Look up one company after validating and normalizing its CIK."""
        return self.session.scalar(select(Company).where(Company.cik == normalize_cik(cik)))

    def get_by_ticker(self, ticker: str) -> Company | None:
        """Return the lowest-ID match when tickers are shared by registrants."""
        return self.session.scalar(
            select(Company)
            .where(func.upper(Company.ticker) == ticker.strip().upper())
            .order_by(Company.id)
            .limit(1)
        )

    def list_companies(self, limit: int = 100, offset: int = 0) -> list[Company]:
        """Return a stable CIK-ordered page, rejecting negative pagination."""
        if limit < 0 or offset < 0:
            raise ValueError("limit and offset must be nonnegative")
        return list(
            self.session.scalars(select(Company).order_by(Company.cik).limit(limit).offset(offset))
        )


class FinancialStatementRepository:
    """Maintain latest-filed statements without overwriting newer restatements."""

    def __init__(self, session: Session) -> None:
        """Bind repository operations to the caller's transaction."""
        self.session = session

    def upsert_statement(
        self,
        company_id: int,
        accession_number: str,
        form_type: str,
        fiscal_year: int,
        fiscal_period: str,
        period_end_date: date,
        filed_date: date,
        accounting_data: dict[str, float | None],
        *,
        provenance: dict[str, Any] | None = None,
        record_provenance: bool = False,
        verified_quarter: bool = False,
    ) -> FinancialStatement:
        """Insert or patch a natural-key statement only for an equal or newer filing date.

        Absent accounting keys retain their current values; explicit None clears a fact.
        This table is a latest-filing view, not a point-in-time restatement archive.
        """
        _validate_payload(accounting_data, _ACCOUNTING_FIELDS)
        statement = self.session.scalar(
            select(FinancialStatement).where(
                FinancialStatement.company_id == company_id,
                FinancialStatement.fiscal_year == fiscal_year,
                FinancialStatement.fiscal_period == fiscal_period,
                FinancialStatement.form_type == form_type,
            )
        )
        company = self.session.get(Company, company_id)
        if company is None:
            raise ValueError("Statement company must exist")
        previous_version = (
            archive_statement(self.session, company.cik, statement, "legacy_snapshot")
            if statement is not None else None
        )
        kind = "sec_quarter_confirmed" if verified_quarter else "normalized"
        replacing_unverified = verified_quarter and previous_version is not None and (
            previous_version.capture_kind != kind
        )
        if statement is not None and filed_date < statement.filed_date and not replacing_unverified:
            # Older complete filings remain available for point-in-time reads.
            older = FinancialStatement(
                company_id=company_id, fiscal_year=fiscal_year, fiscal_period=fiscal_period,
                form_type=form_type, accession_number=accession_number, filed_date=filed_date,
                period_end_date=period_end_date, field_provenance=provenance,
                **accounting_data,
            )
            archive_statement(self.session, company.cik, older, kind)
            return statement
        if statement is None:
            statement = FinancialStatement(
                company_id=company_id,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                form_type=form_type,
            )
            self.session.add(statement)
        statement.accession_number = accession_number
        statement.period_end_date = period_end_date
        statement.filed_date = filed_date
        for key, value in accounting_data.items():
            setattr(statement, key, value)
        if record_provenance:
            statement.field_provenance = provenance
        self.session.flush()
        current_version = archive_statement(self.session, company.cik, statement, kind)
        if previous_version is not None and previous_version.id != current_version.id:
            forecasts = self.session.scalars(select(ModelPrediction).where(
                ModelPrediction.source_statement_id == statement.id
            ))
            for forecast in forecasts:
                known = self.session.scalar(select(ForecastEvidence.id).where(
                    ForecastEvidence.filing_version_id == previous_version.id,
                    ForecastEvidence.model_version == forecast.model_version,
                ).limit(1))
                if known is None:
                    archive_forecast(self.session, previous_version, forecast)
            self.session.execute(delete(ModelPrediction).where(
                ModelPrediction.source_statement_id == statement.id
            ))
        return statement

    def get_company_statements_chronological(
        self, company_id: int, form_type: str = "10-K"
    ) -> list[FinancialStatement]:
        """Return one company's statements in fiscal-year and period-end order."""
        return list(
            self.session.scalars(
                select(FinancialStatement)
                .where(
                    FinancialStatement.company_id == company_id,
                    FinancialStatement.form_type == form_type,
                )
                .order_by(FinancialStatement.fiscal_year, FinancialStatement.period_end_date)
            )
        )


class FinancialMetricRepository:
    """Maintain one feature row per source statement."""

    def __init__(self, session: Session) -> None:
        """Bind repository operations to the caller's transaction."""
        self.session = session

    def upsert_metric(
        self,
        statement_id: int,
        company_id: int,
        fiscal_year: int,
        fiscal_period: str,
        metric_data: dict[str, Any],
    ) -> FinancialMetric:
        """Create or patch features after checking source company and fiscal alignment."""
        _validate_payload(metric_data, _METRIC_FIELDS)
        source = _require_statement(self.session, statement_id, company_id)
        if (fiscal_year, fiscal_period) != (source.fiscal_year, source.fiscal_period):
            raise ValueError("Metric fiscal year and period must match the source statement")
        metric = self.session.scalar(
            select(FinancialMetric).where(FinancialMetric.statement_id == statement_id)
        )
        if metric is None:
            metric = FinancialMetric(
                statement_id=statement_id,
                company_id=company_id,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
            )
            self.session.add(metric)
        for key, value in metric_data.items():
            setattr(metric, key, value)
        self.session.flush()
        return metric

    def get_company_metrics_chronological(self, company_id: int) -> list[FinancialMetric]:
        """Return metrics in fiscal-year and fiscal-period lexical order."""
        return list(
            self.session.scalars(
                select(FinancialMetric)
                .where(FinancialMetric.company_id == company_id)
                .order_by(FinancialMetric.fiscal_year, FinancialMetric.fiscal_period)
            )
        )


class PredictionRepository:
    """Maintain forecasts keyed by source statement, company, and model version."""

    def __init__(self, session: Session) -> None:
        """Bind repository operations to the caller's transaction."""
        self.session = session

    def upsert_prediction(
        self,
        company_id: int,
        source_statement_id: int,
        model_version: str,
        target_fiscal_year: int,
        target_fiscal_period: str,
        prediction_data: dict[str, Any],
    ) -> ModelPrediction:
        """Create or patch a versioned prediction without allowing identity overrides."""
        _validate_payload(prediction_data, _PREDICTION_FIELDS)
        _require_statement(self.session, source_statement_id, company_id)
        prediction = self.session.scalar(
            select(ModelPrediction).where(
                ModelPrediction.company_id == company_id,
                ModelPrediction.source_statement_id == source_statement_id,
                ModelPrediction.model_version == model_version,
            )
        )
        if prediction is None:
            prediction = ModelPrediction(
                company_id=company_id,
                source_statement_id=source_statement_id,
                model_version=model_version,
            )
            self.session.add(prediction)
        prediction.target_fiscal_year = target_fiscal_year
        prediction.target_fiscal_period = target_fiscal_period
        for key, value in prediction_data.items():
            setattr(prediction, key, value)
        self.session.flush()
        return prediction

    def get_latest_prediction_for_company(
        self, company_id: int, model_version: str | None = None
    ) -> ModelPrediction | None:
        """Return the newest created forecast, breaking timestamp ties by descending ID."""
        query = select(ModelPrediction).where(ModelPrediction.company_id == company_id)
        if model_version is not None:
            query = query.where(ModelPrediction.model_version == model_version)
        return self.session.scalar(
            query.order_by(ModelPrediction.created_at.desc(), ModelPrediction.id.desc()).limit(1)
        )
