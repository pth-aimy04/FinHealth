"""Mathematical, XBRL context, transaction, and physical Parquet invariants."""

import builtins
import copy
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.base import Base
from finhealth.db.models import Company, FinancialMetric, FinancialStatement
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.feature_engineering import RatioWinsorizer, compute_temporal_features
from finhealth.etl.financial_ratios import (
    _safe_div,
    compute_altman_z_score,
    compute_statement_ratios,
)
from finhealth.etl.pipeline import FinancialEtlPipeline
from finhealth.etl.spark_session import create_spark_session
from finhealth.etl.xbrl_parser import SecXbrlParser
from finhealth.ingestion.schemas import CompanyMetadata


@pytest.fixture
def payload() -> dict[str, Any]:
    """Load the curated multi-period Apple fixture with comparative filing context."""
    path = Path(__file__).resolve().parents[1] / "fixtures/sec_companyfacts_0000320193_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_xbrl_parser_resolves_comparative_years_from_apple_fixture(payload: dict[str, Any]) -> None:
    """Do not collapse prior comparative periods sharing the filing-context fiscal year."""
    records = SecXbrlParser().parse(payload)
    assert [(r.period_end_date, r.fiscal_year, r.fiscal_period, r.form_type) for r in records] == [
        (date(2022, 9, 24), 2022, "FY", "10-K"),
        (date(2023, 9, 30), 2023, "FY", "10-K"),
        (date(2023, 12, 30), 2024, "Q1", "10-Q"),
    ]
    annual = records[1]
    assert (annual.total_assets, annual.revenues, annual.net_income, annual.eps_diluted) == (
        352583000000.0,
        383285000000.0,
        96995000000.0,
        6.13,
    )
    assert annual.current_assets == 143566000000
    assert annual.retained_earnings == -214000000
    assert annual.field_provenance["revenues"]["tag"] == "Revenues"
    assert records[2].current_liabilities == 133973000000
    assert records[0].field_provenance["eps_diluted"]["start"] == "2021-09-26"


def test_duration_priority_restatement_and_unit_resolution(payload: dict[str, Any]) -> None:
    """Quarter footnotes cannot replace annual flows; tag priority precedes filing recency."""
    concepts = payload["facts"]["us-gaap"]
    rows = concepts["NetIncomeLoss"]["units"]["USD"]
    annual = copy.deepcopy(rows[1])
    rows.extend(
        [
            {**annual, "start": "2023-07-01", "val": 999, "filed": "2025-01-01"},
            {**annual, "val": 200, "filed": "2024-01-01", "accn": "amend-001"},
            {**annual, "val": 300, "filed": "2024-01-01", "accn": "amend-002"},
        ]
    )
    # Wrong currency must not masquerade as dollars.
    concepts["Assets"]["units"]["EUR"] = [{**annual, "val": 999}]
    revenue = copy.deepcopy(concepts["Revenues"])
    revenue["units"]["USD"] = [{**annual, "val": 123, "filed": "2020-01-01"}]
    concepts["RevenueFromContractWithCustomerExcludingAssessedTax"] = revenue
    annual_result = SecXbrlParser().parse(payload)[1]
    assert annual_result.net_income == 300
    assert annual_result.total_assets == 352583000000
    assert annual_result.revenues == 123
    assert annual_result.accession_number == "amend-002"
    assert annual_result.field_provenance["net_income"]["filed"] == "2024-01-01"
    assert annual_result.field_provenance["revenues"]["tag"] == (
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    )


def test_quarter_preference_and_ocf_ytd_fallback(payload: dict[str, Any]) -> None:
    """Prefer single-quarter flows but preserve YTD cash flow explicitly when necessary."""
    concepts = payload["facts"]["us-gaap"]
    cash = concepts["NetCashProvidedByUsedInOperatingActivities"]["units"]["USD"]
    quarter = copy.deepcopy(cash[-1])
    ytd = {**quarter, "start": "2023-07-01", "val": 100, "filed": "2024-03-01"}
    cash.append(ytd)
    assert SecXbrlParser().parse(payload)[-1].operating_cash_flow == 39895000000
    cash.remove(cash[-2])
    result = SecXbrlParser().parse(payload)[-1]
    assert result.operating_cash_flow == 100
    assert result.field_provenance["operating_cash_flow"]["duration_basis"] == "YTD"
    net_income = concepts["NetIncomeLoss"]["units"]["USD"]
    net_income[-1]["start"] = "2023-07-01"
    assert SecXbrlParser().parse(payload)[-1].net_income is None


def test_identity_fallbacks_missing_values_and_invalid_input(payload: dict[str, Any]) -> None:
    """Missing facts stay missing except the two explicitly requested accounting identities."""
    concepts = payload["facts"]["us-gaap"]
    del concepts["Liabilities"]
    records = SecXbrlParser().parse(payload)
    assert records[1].total_liabilities == 290437000000
    assert "derived" in records[1].field_provenance["total_liabilities"]
    concepts["Liabilities"] = {
        "units": {
            "USD": [
                {
                    "form": "10-K",
                    "fp": "FY",
                    "end": "2023-09-30",
                    "filed": "2023-11-03",
                    "accn": records[1].accession_number,
                    "val": 290437000000,
                }
            ]
        }
    }
    del concepts["StockholdersEquity"]
    assert SecXbrlParser().parse(payload)[1].stockholders_equity == 62146000000
    del concepts["Assets"]
    assert SecXbrlParser().parse(payload)[1].stockholders_equity is None
    with pytest.raises(EtlProcessingError):
        SecXbrlParser().parse({"cik": 320193, "facts": []})
    concepts["Liabilities"]["units"]["USD"][0]["end"] = "bad-date"
    with pytest.raises(EtlProcessingError, match="Malformed"):
        SecXbrlParser().parse(payload)
    assert SecXbrlParser().parse({"cik": 320193, "facts": {"dei": {}}}) == []


def test_balance_fallback_accounts_for_equity_scope(payload: dict[str, Any]) -> None:
    """Use consolidated equity for liabilities and reject unsupported balance identities."""
    concepts = payload["facts"]["us-gaap"]
    liabilities = concepts.pop("Liabilities")
    equity = concepts["StockholdersEquity"]["units"]["USD"]
    parent = next(row for row in equity if row["end"] == "2023-09-30")
    consolidated_tag = "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
    consolidated = {**parent, "val": parent["val"] + 1_000_000_000}
    concepts[consolidated_tag] = {"units": {"USD": [consolidated]}}
    row = SecXbrlParser().parse(payload)[1]
    assert row.stockholders_equity == 62_146_000_000
    assert row.total_liabilities == 289_437_000_000
    assert row.field_provenance["total_liabilities"]["input"]["tag"] == consolidated_tag
    concepts["TemporaryEquityCarryingAmountAttributableToParent"] = {
        "units": {"USD": [{**parent, "val": 1_000_000}]}
    }
    assert SecXbrlParser().parse(payload)[1].total_liabilities is None
    concepts["Liabilities"] = liabilities
    del concepts["StockholdersEquity"]
    assert SecXbrlParser().parse(payload)[1].stockholders_equity is None


def test_financial_ratios_and_negative_equity_guard(payload: dict[str, Any]) -> None:
    """Verify each ratio's actual mathematical definition and invalid denominator policy."""
    row = SecXbrlParser().parse(payload)[1].model_dump()
    ratios = compute_statement_ratios(row)
    assert ratios["roa"] == pytest.approx(96995000000 / 352583000000)
    assert ratios["roe"] == pytest.approx(96995000000 / 62146000000)
    assert ratios["debt_ratio"] == pytest.approx(290437000000 / 352583000000)
    assert ratios["debt_to_equity"] == pytest.approx(290437000000 / 62146000000)
    assert ratios["current_ratio"] == pytest.approx(143566000000 / 145308000000)
    assert ratios["operating_margin"] == pytest.approx(114301000000 / 383285000000)
    assert ratios["ocf_ratio"] == pytest.approx(110543000000 / 290437000000)
    assert ratios["working_capital_ratio"] == pytest.approx(-1742000000 / 352583000000)
    assert ratios["retained_earnings_ratio"] == pytest.approx(-214000000 / 352583000000)
    assert ratios["ebit_to_assets"] == pytest.approx(114301000000 / 352583000000)
    assert ratios["asset_turnover"] == pytest.approx(383285000000 / 352583000000)
    assert ratios["eps"] == 6.13
    distressed = compute_statement_ratios(
        {**row, "stockholders_equity": -50000000, "net_income": -10000000, "total_assets": 0}
    )
    for field in (
        "roe",
        "debt_to_equity",
        "roa",
        "debt_ratio",
        "working_capital_ratio",
        "retained_earnings_ratio",
        "ebit_to_assets",
        "asset_turnover",
    ):
        assert distressed[field] is None
    for den in (None, 0, 1e-10, float("nan"), float("inf")):
        assert _safe_div(1.0, den) is None
    assert _safe_div(None, 1) is None
    assert _safe_div(float("nan"), 1) is None
    assert _safe_div(1e308, 1e-8) is None
    assert compute_statement_ratios({"eps_diluted": float("nan"), "eps_basic": 2})["eps"] == 2


def test_altman_z_score_manufacturing_vs_non_manufacturing() -> None:
    """Use independently calculated coefficients, missing-component gates, and both zone sets."""
    stmt = {
        "total_assets": 100,
        "current_assets": 50,
        "current_liabilities": 20,
        "retained_earnings": 10,
        "operating_income": 15,
        "stockholders_equity": 40,
        "total_liabilities": 60,
        "revenues": 120,
    }
    manufacturing = compute_altman_z_score(stmt)
    assert manufacturing["altman_z_score"] == pytest.approx(
        1.2 * 0.3 + 1.4 * 0.1 + 3.3 * 0.15 + 0.6 * (40 / 60) + 1.2
    )
    assert manufacturing["altman_zone"] == "GREY"
    non_manufacturing = compute_altman_z_score(stmt, False)
    assert non_manufacturing["altman_z_score"] == pytest.approx(
        6.56 * 0.3 + 3.26 * 0.1 + 6.72 * 0.15 + 1.05 * (40 / 60)
    )
    assert non_manufacturing["altman_zone"] == "SAFE"
    assert compute_altman_z_score({**stmt, "revenues": None})["altman_z_score"] is None
    assert compute_altman_z_score({**stmt, "revenues": None}, False) == non_manufacturing
    for score, zone in ((1.80, "DISTRESS"), (1.81, "GREY"), (2.99, "GREY"), (3.0, "SAFE")):
        only_turnover = dict.fromkeys(stmt, 0) | {
            "total_assets": 1,
            "total_liabilities": 1,
            "revenues": score,
        }
        assert compute_altman_z_score(only_turnover)["altman_zone"] == zone
    for score, zone in ((1.09, "DISTRESS"), (1.10, "GREY"), (2.60, "GREY"), (2.61, "SAFE")):
        only_equity = dict.fromkeys(stmt, 0) | {
            "total_assets": 1,
            "total_liabilities": 1,
            "stockholders_equity": score / 1.05,
        }
        assert compute_altman_z_score(only_equity, False)["altman_zone"] == zone


def test_temporal_deltas_and_negative_ocf_streak() -> None:
    """Backward-looking deltas, missing resets, and company/form isolation prevent mixing."""
    rows = [
        {
            "cik": "1",
            "form_type": "10-K",
            "fiscal_year": 2020 + i,
            "operating_cash_flow": ocf,
            "roa": i / 10,
            "roe": i / 5,
            "debt_ratio": 0.8 - i / 10,
            "ocf_ratio": i / 4,
        }
        for i, ocf in enumerate([100.0, -20.0, -35.0, 50.0])
    ]
    before = copy.deepcopy(rows)
    result = compute_temporal_features(list(reversed(rows)))
    assert [r["negative_ocf_streak"] for r in result] == [0, 1, 2, 0]
    for field, expected in (("roa", 0.1), ("roe", 0.2), ("debt_ratio", -0.1), ("ocf_ratio", 0.25)):
        assert result[0][f"{field}_yoy_delta"] is None
        assert [r[f"{field}_yoy_delta"] for r in result[1:]] == pytest.approx([expected] * 3)
    assert rows == before
    mixed = compute_temporal_features(
        rows
        + [
            {**rows[2], "cik": "2"},
            {**rows[2], "form_type": "10-Q"},
            {**rows[-1], "fiscal_year": 2024, "operating_cash_flow": None, "roa": None},
        ]
    )
    isolated = [r for r in mixed if r["cik"] == "2" or r["form_type"] == "10-Q"]
    assert all(r["roa_yoy_delta"] is None and r["negative_ocf_streak"] == 1 for r in isolated)
    assert mixed[-1]["negative_ocf_streak"] == 0
    assert mixed[-1]["roa_yoy_delta"] is None


def test_ratio_winsorizer_prevents_test_leakage() -> None:
    """Held-out extremes cannot affect training quantiles or mutate caller frames."""
    train = pd.DataFrame({"roe": [-0.5, -0.2, 0.1, 0.5, 0.8, math.nan]})
    test = pd.DataFrame({"roe": [50.0, -20.0, 0.2, math.nan], "label": [1, 0, 1, 0]})
    original = test.copy(deep=True)
    winsorizer = RatioWinsorizer(["roe"], 0.1, 0.9)
    with pytest.raises(EtlProcessingError, match="fitted"):
        winsorizer.transform(test)
    winsorizer.fit(train)
    bounds = copy.deepcopy(winsorizer.bounds_)
    transformed = winsorizer.transform(test)
    assert transformed["roe"].iloc[0] == pytest.approx(0.68)
    assert transformed["roe"].iloc[1] == pytest.approx(-0.38)
    assert transformed["roe"].iloc[2] == 0.2
    assert pd.isna(transformed["roe"].iloc[3])
    assert winsorizer.bounds_ == bounds
    pd.testing.assert_frame_equal(test, original)
    for invalid in (pd.DataFrame(), pd.DataFrame({"roe": [math.nan]}), pd.DataFrame({"bad": [1]})):
        with pytest.raises(EtlProcessingError):
            RatioWinsorizer(["roe"]).fit(invalid)
    with pytest.raises(ValueError):
        RatioWinsorizer(["roe"], 0.9, 0.1)


def test_end_to_end_etl_to_db_and_parquet(payload: dict[str, Any], tmp_path: Path) -> None:
    """Run the real parser, math, repositories, and PyArrow codec, and verify durable results."""
    pipeline = FinancialEtlPipeline()
    records = pipeline.process_company_facts_payload("320193", payload, "3571")
    metadata = CompanyMetadata(cik="320193", name="Apple Inc.", ticker="AAPL", sic_code="3571")
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        factory = create_session_factory(engine)
        with factory.begin() as session:
            pipeline.persist_to_database(session, metadata, records)
            pipeline.persist_to_database(session, metadata, records)
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Company)) == 1
            assert session.scalar(select(func.count()).select_from(FinancialStatement)) == 3
            metrics = list(session.scalars(select(FinancialMetric).order_by(FinancialMetric.id)))
            assert len(metrics) == 3
            assert metrics[1].roa == pytest.approx(96995000000 / 352583000000)
            assert metrics[1].roa_yoy_delta == pytest.approx(
                96995000000 / 352583000000 - 99803000000 / 352755000000
            )
            assert metrics[2].roa_yoy_delta is None  # Separate 10-Q sequence.
        path = pipeline.export_to_parquet(records, tmp_path / "processed" / "apple.parquet")
        restored = pd.read_parquet(path)
        assert len(restored) == 3
        assert restored["fiscal_year"].tolist() == [2022, 2023, 2024]
        assert restored["eps_diluted"].tolist() == [6.11, 6.13, 2.18]
        assert json.loads(restored["field_provenance"].iloc[1]) == records[1]["field_provenance"]
        assert path.read_bytes()[:4] == b"PAR1"
    finally:
        engine.dispose()


def test_etl_batch_rollback_and_stale_metrics(payload: dict[str, Any]) -> None:
    """Savepoint rollback undoes earlier writes; stale batches cannot clobber newer metrics."""
    pipeline = FinancialEtlPipeline()
    records = pipeline.process_company_facts_payload("320193", payload, "3571")
    metadata = CompanyMetadata(cik="320193", name="Apple")
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with create_session_factory(engine)() as session:
            invalid = copy.deepcopy(records)
            invalid[-1]["fiscal_year"] = 1800
            with pytest.raises(IntegrityError):
                pipeline.persist_to_database(session, metadata, invalid)
            assert session.scalar(select(func.count()).select_from(Company)) == 0
            pipeline.persist_to_database(session, metadata, records)
            stale = copy.deepcopy(records)
            for row in stale:
                row["filed_date"] = date(2020, 1, 1)
                row["roa"] = 999
            pipeline.persist_to_database(session, metadata, stale)
            assert all(m.roa != 999 for m in session.scalars(select(FinancialMetric)))
            session.rollback()
            assert session.scalar(select(func.count()).select_from(Company)) == 0
    finally:
        engine.dispose()


def test_optional_spark_missing_dependency_falls_back_to_real_parquet(
    payload: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate the optional import boundary, then exercise the actual fallback codec."""
    original_import = builtins.__import__

    def import_without_spark(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        """Reject only the external PySpark dependency while preserving all other imports."""
        if name == "pyspark" or name.startswith("pyspark."):
            raise ImportError("Optional Spark is unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_spark)
    with pytest.raises(EtlProcessingError, match="optional") as error:
        create_spark_session()
    assert isinstance(error.value.__cause__, ImportError)
    pipeline = FinancialEtlPipeline(use_spark=True)
    records = pipeline.process_company_facts_payload("320193", payload, "3571")
    path = pipeline.export_to_parquet(records, tmp_path / "fallback.parquet")
    restored = pd.read_parquet(path)
    assert len(restored) == 3
    assert restored["net_income"].iloc[1] == 96995000000


def test_parser_nonfinite_and_ambiguous_calendar(payload: dict[str, Any]) -> None:
    """Nonfinite observations remain missing and ambiguous natural keys fail explicitly."""
    concepts = payload["facts"]["us-gaap"]
    assets = concepts["Assets"]["units"]["USD"]
    assets[0]["val"] = float("inf")
    assert SecXbrlParser().parse(payload)[0].total_assets is None
    assets.append({**assets[1], "end": "2023-12-31"})
    with pytest.raises(EtlProcessingError, match="duplicate key"):
        SecXbrlParser().parse(payload)
