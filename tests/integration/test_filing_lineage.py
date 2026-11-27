"""Verify actual archival writes and cutoff reads using a self-contained SQL database."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from finhealth.api.main import create_app
from finhealth.api.reporting import _reported_ratios
from finhealth.core.config import Settings
from finhealth.db.lineage_models import FilingVersion, ForecastEvidence, IngestionRun
from finhealth.db.models import Base, FinancialStatement, ModelPrediction
from finhealth.db.repositories import (
    CompanyRepository,
    FinancialMetricRepository,
    FinancialStatementRepository,
    PredictionRepository,
)
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.pipeline import FinancialEtlPipeline
from finhealth.etl.report_periods import quarterly_series
from finhealth.etl.vietnam_pilot import seed_vietnam_disclosures
from finhealth.etl.xbrl_parser import SecXbrlParser
from finhealth.ingestion.jobs import _claim, _finish
from finhealth.ingestion.schemas import CompanyMetadata


def test_screening_filters_before_pagination_and_keeps_cohort(tmp_path: Path) -> None:
    """Query actual stored values, preserving missingness and the full benchmark cohort."""
    url = f"sqlite:///{(tmp_path / 'screen.db').as_posix()}"
    engine = create_db_engine(url)
    try:
        Base.metadata.create_all(engine)
        with create_session_factory(engine).begin() as session:
            for index, roa in enumerate((0.1, 0.2, None), start=1):
                company = CompanyRepository(session).upsert_company(
                    index, f"Issuer {index}", f"T{index}", "2000", "Manufacturing",
                )
                statement = FinancialStatementRepository(session).upsert_statement(
                    company.id, f"filing-{index}", "10-K", 2025, "FY", date(2025, 12, 31),
                    date(2026, 2, 1), {},
                )
                FinancialMetricRepository(session).upsert_metric(
                    statement.id, company.id, 2025, "FY",
                    {"roa": roa, "debt_ratio": 0.5, "current_ratio": 1.5, "ocf_ratio": 0.2},
                )
        settings = Settings(_env_file=None, DATABASE_URL=url, data_dir=tmp_path)
        with TestClient(create_app(settings)) as client:
            original = client.get("/api/v1/companies").raise_for_status().json()
            response = client.get("/api/v1/companies", params={"min_roa": 0.15, "limit": 1})
            [selected] = response.raise_for_status().json()
            assert selected["ticker"] == "T2"
            assert selected["composite_health_score"] == original[1]["composite_health_score"]
            assert client.get("/api/v1/companies?min_roa=0.15&offset=1").json() == []
            assert client.get("/api/v1/companies?q=%25").json() == []
            assert client.get("/api/v1/companies?max_debt_ratio=0.4").json() == []
            by_name = client.get("/api/v1/companies?min_current_ratio=1.5&q=T1").json()
            assert by_name == [original[0]]
            assert client.get("/api/v1/companies?min_roa=nan").status_code == 422
            assert client.get("/api/v1/companies?min_current_ratio=-1").status_code == 422
    finally:
        engine.dispose()


def test_restatement_preserves_original_forecast_and_cutoff(tmp_path: Path) -> None:
    """A replacement invalidates serving predictions while retaining their original evidence."""
    url = f"sqlite:///{(tmp_path / 'lineage.db').as_posix()}"
    engine = create_db_engine(url)
    try:
        Base.metadata.create_all(engine)
        with create_session_factory(engine).begin() as session:
            company = CompanyRepository(session).upsert_company("320193", "Apple", "AAPL")
            repo = FinancialStatementRepository(session)
            end = date(2025, 9, 30)
            first = repo.upsert_statement(
                company.id, "original", "10-K", 2025, "FY", end, date(2025, 10, 31),
                {"revenues": 100.0}, provenance={"revenues": {"unit": "USD"}},
                record_provenance=True,
            )
            PredictionRepository(session).upsert_prediction(
                company.id, first.id, "legacy", 2026, "FY", {"distress_probability": 0.2},
            )
            for _ in range(2):
                repo.upsert_statement(
                    company.id, "replacement", "10-K", 2025, "FY", end, date(2025, 12, 1),
                    {"revenues": 200.0}, provenance={"revenues": {"unit": "USD"}},
                    record_provenance=True,
                )
            assert session.scalar(select(ModelPrediction)) is None
            archived = session.scalar(select(ForecastEvidence).join(FilingVersion))
            assert archived is not None and archived.outputs["distress_probability"] == 0.2
            assert archived.input_status == "legacy_unverified"
            source = session.get(FilingVersion, archived.filing_version_id)
            assert source is not None and source.accession == "original"
            assert source.facts["values"]["revenues"] == 100.0
            assert seed_vietnam_disclosures(session) == 4
            assert seed_vietnam_disclosures(session) == 0
        settings = Settings(_env_file=None, DATABASE_URL=url, data_dir=tmp_path)
        with TestClient(create_app(settings)) as client:
            earlier = client.get("/api/v1/reports/AAPL", params={"as_of": "2025-11-30"}).json()
            assert [row["accession"] for row in earlier["versions"]] == ["original"]
            alerts = client.get("/api/v1/report-alerts/AAPL").json()
            assert len(alerts) == 1 and alerts[0]["changed_fields"] == ["revenues"]
            vn = client.get("/api/v1/reports/VN:HPG").json()["versions"][0]
            assert vn["values"]["revenues"] == 156116094618482
            assert vn["provenance"]["revenues"]["line"] == "10"
    finally:
        engine.dispose()


def test_quarter_ytd_derivation_and_trailing_window() -> None:
    """Subtract comparable accumulations and avoid summing past gaps or unit changes."""
    records = [
        {
            "fiscal_year": 2025, "fiscal_period": f"Q{index}", "period_end": end,
            "revenues": value, "provenance": {"revenues": {
                "duration_basis": basis, "start": "2025-10-01" if index == 4 else "2025-01-01",
                "unit": "USD", "currency": "USD", "filed": end, "end": end,
            }},
        }
        for index, end, value, basis in (
            (1, "2025-03-31", 10, "period"), (2, "2025-06-30", 24, "YTD"),
            (3, "2025-09-30", 39, "YTD"), (4, "2025-12-31", -2, "period"),
        )
    ]
    complete = quarterly_series(records)
    assert [row["flows"]["revenues"]["value"] for row in complete] == [10, 14, 15, -2]
    assert complete[-1]["flows"]["revenues"]["ttm"] == 37
    assert complete[1]["flows"]["revenues"]["qoq_growth"] == 0.4
    annual = {**records[-1], "fiscal_period": "FY", "revenues": 37, "provenance": {
        "revenues": {**records[-1]["provenance"]["revenues"], "filed": "2026-02-01",
                     "start": "2025-01-01"}
    }}
    derived = quarterly_series([*records[:3], annual])[-1]["flows"]["revenues"]
    assert derived["value"] == -2 and derived["ttm"] == 37 and len(derived["sources"]) == 4
    assert quarterly_series(records[::2])[-1]["flows"]["revenues"]["reason"] == "incompatible_ytd"
    records[-1]["provenance"]["revenues"]["unit"] = "VND"
    assert quarterly_series(records)[-1]["flows"]["revenues"]["ttm"] is None
    records[-1]["provenance"]["revenues"].update(unit="USD", start="2025-09-01")
    assert quarterly_series(records)[-1]["flows"]["revenues"]["ttm"] is None


def test_report_flow_ratios_require_same_duration() -> None:
    """Hide a cash conversion ratio mixing six-month OCF and three-month net income."""
    source = {"start": "2025-01-01", "end": "2025-06-30", "unit": "USD",
              "currency": "USD", "accn": "source", "filed": "2025-07-31",
              "duration_basis": "YTD"}
    quarter = {**source, "start": "2025-04-01", "duration_basis": "period"}
    values = {"operating_cash_flow": 60, "net_income": 10, "revenues": 100}
    provenance = {"operating_cash_flow": source, "net_income": quarter, "revenues": quarter}
    ratios = _reported_ratios(values, provenance)
    assert ratios["cash_conversion"] is None and ratios["net_margin"] == 0.1


def test_quarter_accession_requires_matching_report_end() -> None:
    """Exclude comparative balance snapshots that share a current filing's fiscal label."""
    payload = {"cik": 320193, "facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"form": "10-Q", "accn": "current", "end": "2025-12-27", "filed": "2026-01-30",
         "fy": 2026, "fp": "Q1", "val": 12},
        {"form": "10-Q", "accn": "current", "end": "2025-09-27", "filed": "2026-01-30",
         "fy": 2026, "fp": "Q1", "val": 10},
    ]}}}}}
    [record] = SecXbrlParser().parse(payload, quarter_report_dates={"current": date(2025, 12, 27)})
    assert (record.fiscal_year, record.fiscal_period, record.total_assets) == (2026, "Q1", 12)
    rows = payload["facts"]["us-gaap"]["Assets"]["units"]["USD"]
    rows.append({**rows[0], "form": "10-Q/A", "accn": "amended", "filed": "2026-02-01", "val": 13})
    [amended] = SecXbrlParser().amendments(payload, {"amended": date(2025, 12, 27)})
    assert amended.total_assets == 13 and amended.current_assets is None


def test_incorrect_legacy_quarter_is_archived_before_quarantine() -> None:
    """Keep archival evidence while removing a falsely labeled comparative serving row."""
    engine = create_db_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        with create_session_factory(engine).begin() as session:
            company = CompanyRepository(session).upsert_company("320193", "Apple", "AAPL")
            repo = FinancialStatementRepository(session)
            bad = repo.upsert_statement(
                company.id, "q1-source", "10-Q", 2025, "Q1", date(2025, 9, 27),
                date(2026, 1, 30), {"total_assets": 10},
            )
            bad_id = bad.id
            wrong_year = repo.upsert_statement(
                company.id, "q1-source", "10-Q", 2025, "Q2", date(2025, 12, 27),
                date(2026, 1, 30), {"total_assets": 12},
            )
            wrong_year_id = wrong_year.id
            metadata = CompanyMetadata(
                cik="320193", name="Apple", ticker="AAPL",
                quarter_report_dates={"q1-source": date(2025, 12, 27)},
            )
            assert FinancialEtlPipeline().quarantine_comparative_quarters(
                session, company.id, metadata, {"q1-source": (2026, "Q1")},
            ) == 2
            assert session.get(FinancialStatement, bad_id) is None
            assert session.get(FinancialStatement, wrong_year_id) is None
            archived = session.scalar(select(FilingVersion).where(
                FilingVersion.accession == "q1-source",
            ))
            assert archived is not None and archived.facts["values"]["total_assets"] == 10
    finally:
        engine.dispose()


def test_persistent_dispatcher_retries_and_does_not_double_claim() -> None:
    """Claim and requeue actual job rows without contacting SEC."""
    engine = create_db_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        factory = create_session_factory(engine)
        with factory.begin() as session:
            session.add(IngestionRun(identifier="AAPL", status="queued"))
        first = _claim(factory)
        assert first is not None and first[1:] == ("AAPL", 1)
        assert _claim(factory) is None
        _finish(factory, first[0], 1, None, "SecRateLimitError", recoverable=True)
        second = _claim(factory)
        assert second == (first[0], "AAPL", 2)
        _finish(factory, first[0], 2, "0000320193", None)
        with factory() as session:
            job = session.get(IngestionRun, first[0])
            assert job is not None and job.status == "succeeded"
            assert job.company_cik == "0000320193"
        assert _claim(factory) is None
    finally:
        engine.dispose()
