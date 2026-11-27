"""Real SQLite tests of repository behavior and relational integrity."""

from collections.abc import Iterator
from datetime import date, datetime, timezone
from typing import Any

import pytest
from sqlalchemy import Engine, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finhealth.db.base import Base
from finhealth.db.models import Company, FinancialMetric, FinancialStatement, ModelPrediction
from finhealth.db.repositories import (
    CompanyRepository,
    FinancialMetricRepository,
    FinancialStatementRepository,
    PredictionRepository,
    normalize_cik,
)
from finhealth.db.session import create_db_engine, create_session_factory


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Create an isolated in-memory database with production metadata and real FKs."""
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Give each test a real session with explicit transaction cleanup."""
    with create_session_factory(engine)() as session:
        yield session
        session.rollback()


@pytest.fixture
def company(session: Session) -> Company:
    """Insert an Apple registrant for source statement tests."""
    return CompanyRepository(session).upsert_company(320193, "Apple Inc.", "AAPL")


def _statement(
    session: Session,
    company_id: int,
    year: int = 2023,
    period: str = "FY",
    form: str = "10-K",
    end_date: date | None = None,
) -> FinancialStatement:
    """Insert a deterministic source statement through the actual repository."""
    return FinancialStatementRepository(session).upsert_statement(
        company_id,
        f"0000320193-{year % 100:02d}-000001",
        form,
        year,
        period,
        end_date or date(year, 12, 31),
        date(year + 1, 2, 1),
        {"net_income": 100.0},
    )


def _count(session: Session, model: type[Base]) -> int:
    """Count actual persisted rows for a mapped table."""
    return session.scalar(select(func.count()).select_from(model)) or 0


def _analytics(session: Session, company_id: int, statement_id: int) -> None:
    """Create both feature and forecast dependents for cascade tests."""
    FinancialMetricRepository(session).upsert_metric(
        statement_id, company_id, 2023, "FY", {"roa": 0.1}
    )
    PredictionRepository(session).upsert_prediction(
        company_id, statement_id, "v1", 2024, "FY", {"distress_probability": 0.2}
    )


def test_normalize_cik_valid_and_invalid() -> None:
    """Normalize permitted markers while rejecting ambiguous or non-ASCII identifiers."""
    valid: list[tuple[str | int, str]] = [
        ("320193", "0000320193"),
        (320193, "0000320193"),
        ("CIK0000789019", "0000789019"),
        (" cik 320193 CIK ", "0000320193"),
        ("320193cik", "0000320193"),
        ("0000320193", "0000320193"),
    ]
    for value, expected in valid:
        assert normalize_cik(value) == expected
    invalid: list[Any] = [
        "ABC123",
        "",
        "12345678901",
        "CIK",
        "12CIK34",
        "-123",
        -1,
        "１２３",
        "١٢٣",
        "123.0",
        "1 23",
        True,
        None,
        123.0,
    ]
    for value in invalid:
        with pytest.raises(ValueError, match="CIK must"):
            normalize_cik(value)


def test_company_upsert_idempotency(session: Session) -> None:
    """CIK variants update one row, preserve creation time, and refresh update time."""
    repo = CompanyRepository(session)
    first = repo.upsert_company("CIK320193", "Apple", "aapl", "3571", "Hardware")
    first_id, created = first.id, first.created_at
    assert created.tzinfo == timezone.utc
    first.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    session.flush()
    updated = repo.upsert_company(320193, "Apple Inc.", " aapl.us ", "7372", "Technology")
    session.commit()
    session.expire_all()
    assert updated.id == first_id
    assert _count(session, Company) == 1
    assert updated.cik == "0000320193"
    assert (updated.name, updated.ticker, updated.sic_code, updated.sector) == (
        "Apple Inc.",
        "AAPL.US",
        "7372",
        "Technology",
    )
    assert updated.created_at.replace(tzinfo=timezone.utc) == created
    assert updated.updated_at.replace(tzinfo=timezone.utc) > datetime(
        2000, 1, 1, tzinfo=timezone.utc
    )
    assert repo.get_by_cik("320193") is updated
    assert repo.get_by_ticker("aapl.us") is updated
    assert repo.get_by_cik("1") is None
    assert repo.get_by_ticker("MISSING") is None


def test_company_pagination(session: Session) -> None:
    """Pages are deterministic and invalid limits cannot become unbounded queries."""
    repo = CompanyRepository(session)
    for cik in (3, 1, 2):
        repo.upsert_company(cik, f"Company {cik}")
    assert [row.cik for row in repo.list_companies(limit=1, offset=1)] == ["0000000002"]
    assert repo.list_companies(limit=0) == []
    assert repo.list_companies(offset=99) == []
    for limit, offset in ((-1, 0), (1, -1)):
        with pytest.raises(ValueError, match="nonnegative"):
            repo.list_companies(limit, offset)


def test_statement_upsert_and_restatement_handling(session: Session, company: Company) -> None:
    """Newer and equal-date amendments update in place; older filings cannot clobber them."""
    repo = FinancialStatementRepository(session)
    original = _statement(session, company.id)
    original_id = original.id
    amended = repo.upsert_statement(
        company.id,
        "new-accession",
        "10-K",
        2023,
        "FY",
        date(2023, 12, 31),
        date(2024, 3, 15),
        {"net_income": 120.0, "total_assets": 1000.0},
    )
    assert amended.id == original_id
    assert amended.net_income == 120.0
    stale = repo.upsert_statement(
        company.id,
        "stale-accession",
        "10-K",
        2023,
        "FY",
        date(2023, 9, 30),
        date(2024, 1, 10),
        {"net_income": -999.0, "total_assets": None},
    )
    assert stale.id == original_id
    assert stale.net_income == 120.0
    assert stale.total_assets == 1000.0
    assert stale.accession_number == "new-accession"
    assert stale.filed_date == date(2024, 3, 15)
    assert stale.period_end_date == date(2023, 12, 31)
    repo.upsert_statement(
        company.id,
        "same-date",
        "10-K",
        2023,
        "FY",
        date(2023, 12, 31),
        date(2024, 3, 15),
        {"net_income": None},
    )
    session.commit()
    session.expire_all()
    assert amended.net_income is None
    assert amended.total_assets == 1000.0
    assert amended.accession_number == "same-date"
    assert _count(session, FinancialStatement) == 1


def test_chronological_ordering(session: Session, company: Company) -> None:
    """Statements order by year then end date, with strict company and form filtering."""
    for year in (2024, 2022, 2023):
        _statement(session, company.id, year)
    _statement(session, company.id, 2023, "Q2", "10-Q", date(2023, 6, 30))
    _statement(session, company.id, 2023, "Q1", "10-Q", date(2023, 3, 31))
    other = CompanyRepository(session).upsert_company(789019, "Microsoft")
    _statement(session, other.id, 2021)
    repo = FinancialStatementRepository(session)
    assert [row.fiscal_year for row in repo.get_company_statements_chronological(company.id)] == [
        2022,
        2023,
        2024,
    ]
    assert [
        row.fiscal_period for row in repo.get_company_statements_chronological(company.id, "10-Q")
    ] == ["Q1", "Q2"]
    assert repo.get_company_statements_chronological(9999) == []


def test_metric_and_prediction_upsert_with_shap_json(session: Session, company: Company) -> None:
    """Features upsert once and actual JSON storage preserves nested SHAP contributions."""
    statement = _statement(session, company.id)
    metrics = FinancialMetricRepository(session)
    forecasts = PredictionRepository(session)
    metric = metrics.upsert_metric(
        statement.id,
        company.id,
        2023,
        "FY",
        {
            "roa": 0.1,
            "pca_comp_1": 1.25,
            "pca_comp_2": -0.5,
            "pca_comp_3": None,
            "cluster_id": 2,
            "cluster_label": "Stable",
            "altman_zone": "SAFE",
        },
    )
    metric_id = metric.id
    assert metric.negative_ocf_streak == 0
    same_metric = metrics.upsert_metric(
        statement.id,
        company.id,
        2023,
        "FY",
        {
            "roa": 0.12,
            "negative_ocf_streak": 2,
        },
    )
    assert same_metric.id == metric_id
    shap: dict[str, Any] = {"base_value": 0.1, "features": {"roa": -0.03, "debt_ratio": 0.2}}
    prediction = forecasts.upsert_prediction(
        company.id,
        statement.id,
        "xgb-v1",
        2024,
        "FY",
        {
            "pred_roa": 0.11,
            "distress_probability": 0.27,
            "risk_level": "MEDIUM",
            "shap_explanations": shap,
        },
    )
    prediction_id = prediction.id
    same_prediction = forecasts.upsert_prediction(
        company.id, statement.id, "xgb-v1", 2024, "FY", {"pred_roa": 0.13}
    )
    assert same_prediction.id == prediction_id
    session.commit()
    session.expunge_all()
    loaded_metric = session.get(FinancialMetric, metric_id)
    loaded_prediction = session.get(ModelPrediction, prediction_id)
    assert loaded_metric is not None and loaded_prediction is not None
    assert (loaded_metric.roa, loaded_metric.negative_ocf_streak) == (0.12, 2)
    assert (loaded_metric.pca_comp_1, loaded_metric.pca_comp_2, loaded_metric.pca_comp_3) == (
        1.25,
        -0.5,
        None,
    )
    assert (loaded_metric.cluster_id, loaded_metric.cluster_label) == (2, "Stable")
    assert loaded_prediction.shap_explanations == shap
    assert loaded_prediction.shap_explanations is not shap
    assert loaded_prediction.pred_roa == 0.13
    assert loaded_prediction.distress_probability == 0.27
    assert _count(session, FinancialMetric) == _count(session, ModelPrediction) == 1


def test_metric_chronological_order_and_source_alignment(
    session: Session, company: Company
) -> None:
    """Metrics respect company, fiscal year, and period when sorting and writing."""
    repo = FinancialMetricRepository(session)
    for year, period in ((2024, "Q2"), (2023, "Q3"), (2024, "Q1")):
        statement = _statement(session, company.id, year, period, "10-Q")
        repo.upsert_metric(statement.id, company.id, year, period, {"roa": 0.1})
    assert [
        (row.fiscal_year, row.fiscal_period)
        for row in repo.get_company_metrics_chronological(company.id)
    ] == [(2023, "Q3"), (2024, "Q1"), (2024, "Q2")]
    with pytest.raises(ValueError, match="must match"):
        repo.upsert_metric(statement.id, company.id, 2020, "FY", {})
    assert repo.get_company_metrics_chronological(9999) == []


def test_latest_prediction_version_and_timestamp_tie(session: Session, company: Company) -> None:
    """Latest means creation time, then ID, with an optional exact version filter."""
    repo = PredictionRepository(session)
    assert repo.get_latest_prediction_for_company(company.id) is None
    statement = _statement(session, company.id)
    first = repo.upsert_prediction(company.id, statement.id, "v1", 2024, "FY", {})
    second = repo.upsert_prediction(company.id, statement.id, "v2", 2024, "FY", {})
    first.created_at = second.created_at = datetime(2024, 4, 1, tzinfo=timezone.utc)
    session.flush()
    assert repo.get_latest_prediction_for_company(company.id).id == second.id
    assert repo.get_latest_prediction_for_company(company.id, "v1").id == first.id
    assert repo.get_latest_prediction_for_company(company.id, "missing") is None
    assert repo.get_latest_prediction_for_company(9999) is None
    first.created_at = datetime(2024, 5, 1, tzinfo=timezone.utc)
    session.flush()
    assert repo.get_latest_prediction_for_company(company.id).id == first.id


@pytest.mark.parametrize("probability", [-0.01, 1.01])
def test_prediction_probability_bounds(
    session: Session, company: Company, probability: float
) -> None:
    """The relational check constraint rejects out-of-range probabilities."""
    statement = _statement(session, company.id)
    with pytest.raises(IntegrityError, match="ck_prediction_prob_bounds"), session.begin_nested():
        PredictionRepository(session).upsert_prediction(
            company.id, statement.id, "invalid", 2024, "FY", {"distress_probability": probability}
        )
    assert _count(session, ModelPrediction) == 0
    for version, value in (("zero", 0.0), ("one", 1.0), ("unknown", None)):
        PredictionRepository(session).upsert_prediction(
            company.id, statement.id, version, 2024, "FY", {"distress_probability": value}
        )
    assert _count(session, ModelPrediction) == 3


def test_database_constraints_and_foreign_keys(session: Session, company: Company) -> None:
    """Bypass repositories to demonstrate DB enforcement of CIK, uniqueness, year, and FKs."""
    assert session.scalar(text("PRAGMA foreign_keys")) == 1
    for cik in ("320193", "000032019x", "12345678901", company.cik):
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(Company(cik=cik, name="Invalid or duplicate"))
            session.flush()
    source = _statement(session, company.id)
    for year, owner in ((1989, company.id), (2101, company.id), (2023, 9999), (2023, company.id)):
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                FinancialStatement(
                    company_id=owner,
                    accession_number="duplicate",
                    form_type="10-K",
                    fiscal_year=year,
                    fiscal_period="FY",
                    period_end_date=date(2023, 12, 31),
                    filed_date=date(2024, 2, 1),
                )
            )
            session.flush()
    _analytics(session, company.id, source.id)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            FinancialMetric(
                statement_id=source.id, company_id=company.id, fiscal_year=2023, fiscal_period="FY"
            )
        )
        session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            ModelPrediction(
                company_id=company.id,
                source_statement_id=source.id,
                model_version="v1",
                target_fiscal_year=2024,
                target_fiscal_period="FY",
            )
        )
        session.flush()
    assert _count(session, Company) == _count(session, FinancialStatement) == 1


def test_cross_company_analytics_are_rejected(session: Session, company: Company) -> None:
    """Repositories and composite DB constraints both prevent mixed-company provenance."""
    statement = _statement(session, company.id)
    other = CompanyRepository(session).upsert_company(789019, "Microsoft")
    for source_id in (statement.id, 9999):
        with pytest.raises(ValueError, match="belong"):
            FinancialMetricRepository(session).upsert_metric(source_id, other.id, 2023, "FY", {})
        with pytest.raises(ValueError, match="belong"):
            PredictionRepository(session).upsert_prediction(
                other.id, source_id, "v1", 2024, "FY", {}
            )
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            FinancialMetric(
                statement_id=statement.id, company_id=other.id, fiscal_year=2023, fiscal_period="FY"
            )
        )
        session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            ModelPrediction(
                company_id=other.id,
                source_statement_id=statement.id,
                model_version="v1",
                target_fiscal_year=2024,
                target_fiscal_period="FY",
            )
        )
        session.flush()


def test_payloads_cannot_override_identity_or_add_unknown_fields(
    session: Session, company: Company
) -> None:
    """Reject payload mistakes before altering any row."""
    statement = _statement(session, company.id)
    with pytest.raises(ValueError, match="Unsupported payload fields"):
        FinancialStatementRepository(session).upsert_statement(
            company.id,
            "bad",
            "10-K",
            2023,
            "FY",
            date(2023, 12, 31),
            date(2024, 3, 1),
            {"invented_fact": 1.0},
        )
    with pytest.raises(ValueError, match="Unsupported payload fields"):
        FinancialMetricRepository(session).upsert_metric(
            statement.id, company.id, 2023, "FY", {"company_id": 9999}
        )
    with pytest.raises(ValueError, match="Unsupported payload fields"):
        PredictionRepository(session).upsert_prediction(
            company.id, statement.id, "v1", 2024, "FY", {"created_at": datetime.now(timezone.utc)}
        )
    assert statement.accession_number != "bad"
    assert _count(session, FinancialMetric) == _count(session, ModelPrediction) == 0


@pytest.mark.parametrize("delete_mode", ["orm", "sql"])
def test_cascade_delete_company(session: Session, company: Company, delete_mode: str) -> None:
    """ORM and raw table deletion both remove all company dependents while retaining peers."""
    source = _statement(session, company.id)
    _analytics(session, company.id, source.id)
    other = CompanyRepository(session).upsert_company(789019, "Microsoft")
    other_statement = _statement(session, other.id)
    _analytics(session, other.id, other_statement.id)
    company_id, other_id = company.id, other.id
    session.commit()
    session.expunge_all()
    if delete_mode == "orm":
        target = session.get(Company, company_id)
        assert target is not None
        # Load collections so the ORM's delete-orphan paths are exercised too.
        assert len(target.statements) == len(target.metrics) == len(target.predictions) == 1
        session.delete(target)
    else:
        session.execute(delete(Company.__table__).where(Company.id == company_id))
    session.commit()
    session.expunge_all()
    for model in (Company, FinancialStatement, FinancialMetric, ModelPrediction):
        assert _count(session, model) == 1
    assert session.get(Company, company_id) is None
    assert session.get(Company, other_id) is not None


def test_statement_delete_cascades_to_analytics(session: Session, company: Company) -> None:
    """Deleting just a source statement removes features and forecasts but keeps the company."""
    source = _statement(session, company.id)
    _analytics(session, company.id, source.id)
    session.execute(delete(FinancialStatement.__table__).where(FinancialStatement.id == source.id))
    session.commit()
    assert _count(session, Company) == 1
    assert _count(session, FinancialStatement) == 0
    assert _count(session, FinancialMetric) == _count(session, ModelPrediction) == 0


def test_relationship_delete_orphans(session: Session, company: Company) -> None:
    """Removing children from company collections deletes their rows on flush."""
    source = _statement(session, company.id)
    _analytics(session, company.id, source.id)
    company.metrics.clear()
    company.predictions.clear()
    session.flush()
    assert _count(session, FinancialMetric) == _count(session, ModelPrediction) == 0
    company.statements.clear()
    session.flush()
    assert _count(session, FinancialStatement) == 0
    assert _count(session, Company) == 1


def test_repositories_do_not_commit(session: Session) -> None:
    """A caller rollback undoes the entire flushed company/statement/features/forecast unit."""
    company = CompanyRepository(session).upsert_company(320193, "Apple")
    source = _statement(session, company.id)
    _analytics(session, company.id, source.id)
    for model in (Company, FinancialStatement, FinancialMetric, ModelPrediction):
        assert _count(session, model) == 1
    session.rollback()
    for model in (Company, FinancialStatement, FinancialMetric, ModelPrediction):
        assert _count(session, model) == 0
