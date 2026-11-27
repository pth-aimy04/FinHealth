"""Offline verification of the locally captured SEC panel and its published bundle."""

import json
import re
import sqlite3
import tracemalloc
from collections.abc import Callable, Iterator
from contextlib import closing
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import pytest
from coverage import Coverage
from fastapi.testclient import TestClient
from sklearn.decomposition import PCA
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, r2_score, roc_auc_score

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.main import create_app
from finhealth.core.config import Settings
from finhealth.core.constants import US_GAAP_TAG_FALLBACKS
from finhealth.etl.annual import (
    _decode_companyfacts,
    as_reported_annual_payload,
    load_annual_companyfacts,
)
from finhealth.etl.financial_ratios import CREDIT_RATIO_COLUMNS
from finhealth.etl.pipeline import FinancialEtlPipeline
from finhealth.ml.distress_classifier import DistressClassifier
from finhealth.ml.explainer import ShapExplainer
from finhealth.ml.forecaster import NextPeriodForecaster
from finhealth.ml.preprocessing import FinancialPreprocessor
from finhealth.ml.registry import (
    ModelArtifactBundle,
    load_bundle,
    predict_for_company_records,
    train_and_evaluate_pipeline,
)
from finhealth.ml.splitter import (
    FORECAST_TARGET_COLUMNS,
    RATIO_FEATURE_COLUMNS,
    TEMPORAL_FEATURE_COLUMNS,
    TemporalSplitter,
    build_next_period_panel,
    derive_distress_label,
    prepare_validation_test,
    training_horizon_rows,
)

DATA = Path(__file__).resolve().parents[2] / "data"
RAW = DATA / "raw/sec_edgar/companyfacts"
PARQUET = DATA / "processed/parquet/sec_real_panel.parquet"
SQLITE = PARQUET.with_name("finhealth.sqlite3")
MODELS = DATA / "artifacts/models"
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}", re.ASCII)
FORECAST = tuple(f"pred_{name}" for name in FORECAST_TARGET_COLUMNS)
PCA_COLUMNS = ("pca_comp_1", "pca_comp_2", "pca_comp_3")
FINANCIAL_COLUMNS = tuple(US_GAAP_TAG_FALLBACKS)
METRICS = (
    *RATIO_FEATURE_COLUMNS,
    *TEMPORAL_FEATURE_COLUMNS,
    *CREDIT_RATIO_COLUMNS,
    "altman_z_score",
    "altman_zone",
)


@pytest.fixture(scope="module")
def real_panel() -> pd.DataFrame:
    """Require the local Stage 8 evidence without fetching or generating replacement data."""
    if not PARQUET.is_file():
        pytest.skip(f"Local SEC audit dataset required: {PARQUET}")
    panel = pd.read_parquet(PARQUET)
    assert (len(panel), panel["cik"].nunique()) == (1506, 98)
    assert "0001826011" not in set(panel["cik"])
    assert not panel["sic_code"].astype(int).between(6000, 6799).any()
    return panel


@pytest.fixture(scope="module")
def bundle(real_panel: pd.DataFrame) -> ModelArtifactBundle:
    """Load the checksum-verified local artifact paired with the audited panel."""
    return load_bundle(MODELS / "v1.2.0")


@pytest.fixture(scope="module")
def database(real_panel: pd.DataFrame) -> Iterator[sqlite3.Connection]:
    """Open the persisted dataset read-only and reject an accidentally empty DB."""
    if not SQLITE.is_file():
        pytest.skip(f"Local SQLite audit snapshot required: {SQLITE}")
    with closing(sqlite3.connect(f"{SQLITE.as_uri()}?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


@pytest.fixture(scope="module")
def api(
    database: sqlite3.Connection, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[TestClient]:
    """Use actual FastAPI routes and SQLite with isolated model activation."""
    from finhealth.db.base import Base
    from finhealth.db.session import create_db_engine

    snapshot = tmp_path_factory.mktemp("forensic-api") / "snapshot.sqlite3"
    with sqlite3.connect(snapshot) as target:
        database.backup(target)
    engine = create_db_engine(f"sqlite:///{snapshot.as_posix()}")
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            data_dir=DATA,
            DATABASE_URL=f"sqlite:///{snapshot.as_posix()}",
        )
    )
    app.state.model_registry = ModelRegistryState()
    with TestClient(app) as client:
        yield client


def _nullable(value: Any) -> Any:
    """Compare missing scalars consistently across pandas, raw ETL and SQLite."""
    return None if pd.isna(value) else value


def _equal(actual: Any, expected: Any, tolerance: float = 1e-12) -> float:
    """Assert value/missing parity and return the numeric absolute difference."""
    actual, expected = _nullable(actual), _nullable(expected)
    if actual is None or expected is None or isinstance(expected, str):
        assert actual == expected
        return 0.0
    difference = abs(float(actual) - float(expected))
    assert difference < tolerance, (actual, expected, difference)
    return difference


def _observation_key(row: dict[str, Any]) -> tuple[Any, ...]:
    """Key an original fact by accession, economic period, filing date, and value."""
    return (row["accn"], row.get("start"), row["end"], row["filed"], row["val"])


def test_all_statement_provenance(real_panel: pd.DataFrame, database: sqlite3.Connection) -> None:
    """Verify every sourced value and statement against raw SEC and every persisted value."""
    assert [row[0] for row in database.execute("PRAGMA integrity_check")] == ["ok"]
    assert not database.execute("PRAGMA foreign_key_check").fetchall()
    persisted = database.execute(
        "SELECT c.cik, s.* FROM financial_statements s JOIN companies c ON c.id=s.company_id"
    ).fetchall()
    statements = {
        (row["cik"], row["accession_number"], row["period_end_date"]): row for row in persisted
    }
    metrics = {
        row["statement_id"]: row for row in database.execute("SELECT * FROM financial_metrics")
    }
    assert len(statements) == len(persisted) == len(metrics) == len(real_panel)
    direct = derived = missing = 0
    for cik, frame in real_panel.groupby("cik"):
        path = RAW / f"CIK{cik}.json"
        raw = json.loads(path.read_bytes())
        assert str(raw["cik"]).zfill(10) == cik
        pipeline = FinancialEtlPipeline()
        replay = pipeline.process_company_facts_payload(
            cik, load_annual_companyfacts(path), _nullable(frame.iloc[0]["sic_code"])
        )
        replayed = {(r["accession_number"], r["period_end_date"]): r for r in replay}
        facts = raw["facts"]["us-gaap"]
        sources: dict[tuple[str, str], set[tuple[Any, ...]]] = {}
        for row in frame.to_dict("records"):
            provenance = json.loads(row["field_provenance"])
            end, filed = row["period_end_date"].isoformat(), row["filed_date"].isoformat()
            accession = row["accession_number"]
            assert ACCESSION.fullmatch(accession) and filed >= end
            rebuilt = replayed[accession, row["period_end_date"]]
            assert rebuilt["field_provenance"] == provenance
            stored = statements.pop((cik, accession, end))
            assert json.loads(stored["field_provenance"]) == provenance
            assert stored["filed_date"] == filed and stored["form_type"] == row["form_type"]
            assert stored["fiscal_year"] == row["fiscal_year"]
            assert stored["fiscal_period"] == row["fiscal_period"]
            anchored = 0
            for field in FINANCIAL_COLUMNS:
                value, source = _nullable(row[field]), provenance.get(field)
                assert stored[field] == value
                assert rebuilt[field] == value
                if source is None:
                    assert value is None
                    missing += 1
                elif "derived" in source:
                    _check_derived_value(row, field, source, facts)
                    derived += 1
                else:
                    tag, unit = source["tag"], source["unit"]
                    assert tag in US_GAAP_TAG_FALLBACKS[field]
                    if (tag, unit) not in sources:
                        sources[tag, unit] = {
                            _observation_key(fact)
                            for fact in facts[tag]["units"][unit]
                            if fact.get("form") == "10-K"
                        }
                    assert source["accn"] == accession and source["end"] == end
                    assert source["filed"] == filed and source["currency"] == "USD"
                    assert (accession, source["start"], end, filed, value) in sources[tag, unit]
                    anchored += 1
                    direct += 1
            assert anchored > 0
            for field in METRICS:
                assert metrics[stored["id"]][field] == _nullable(row[field])
                assert rebuilt[field] == _nullable(row[field])
    assert not statements
    assert real_panel["data_source"].eq("cached_sec").all()
    print(
        f"SEC={len(real_panel)} replay={len(real_panel)} SQLite={len(real_panel)} "
        f"synthetic=0 direct={direct} "
        f"derived={derived} missing={missing}"
    )


def _check_derived_value(
    row: dict[str, Any], field: str, source: dict[str, Any], facts: dict[str, Any]
) -> None:
    """Verify the balance equation and any raw equity scope adjustment."""
    identity = source["derived"]
    other = "stockholders_equity" if field == "total_liabilities" else "total_liabilities"
    assert field in {"total_liabilities", "stockholders_equity"}
    if "input" in source:
        fact = source["input"]
        assert fact["accn"] == row["accession_number"]
        assert fact["end"] == row["period_end_date"].isoformat()
        assert fact["filed"] == row["filed_date"].isoformat()
        assert (fact["accn"], None, fact["end"], fact["filed"], source["value"]) in {
            _observation_key(item)
            for item in facts[fact["tag"]]["units"]["USD"]
            if item["form"] == "10-K"
        }
        if identity == "total_assets - consolidated_equity":
            assert field == "total_liabilities"
            expected = row["total_assets"] - source["value"]
        else:
            assert identity == f"total_assets - {other} - minority_interest"
            expected = row["total_assets"] - row[other] - source["value"]
    else:
        assert identity == f"total_assets - {other}"
        assert source["assumption"] == "no noncontrolling interests"
        expected = row["total_assets"] - row[other]
    assert row[field] == expected


def _divide(numerator: float, denominator: float) -> float:
    """Implement the documented positive-denominator rule independently of ETL."""
    return numerator / denominator if denominator >= 1e-9 else np.nan


def _manual_ratios(row: dict[str, Any], sic: int) -> dict[str, Any]:
    """Calculate all twelve ratios and both requested Altman variants from facts."""
    a, liabilities, e, r = (
        row[k] for k in ("total_assets", "total_liabilities", "stockholders_equity", "revenues")
    )
    ca, cl = row["current_assets"], row["current_liabilities"]
    ni, op, cf, re_ = (
        row[k]
        for k in ("net_income", "operating_income", "operating_cash_flow", "retained_earnings")
    )
    eligible = e if not (a > 0 and e < a * 0.05) else np.nan
    x1, x2, x3, x4, x5 = (
        _divide(ca - cl, a),
        _divide(re_, a),
        _divide(op, a),
        _divide(e, liabilities),
        _divide(r, a),
    )
    if 2000 <= sic <= 3999:
        z, low, high = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + x5, 1.81, 2.99
    else:
        z, low, high = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4, 1.10, 2.60
    return {
        "roa": _divide(ni, a),
        "roe": np.clip(_divide(ni, eligible), -3.0, 3.0),
        "eps": row["eps_basic"] if pd.isna(row["eps_diluted"]) else row["eps_diluted"],
        "debt_ratio": _divide(liabilities, a),
        "debt_to_equity": np.clip(_divide(liabilities, eligible), 0.0, 20.0),
        "current_ratio": _divide(ca, cl),
        "operating_margin": _divide(op, r),
        "ocf_ratio": _divide(cf, liabilities),
        "working_capital_ratio": x1,
        "retained_earnings_ratio": x2,
        "ebit_to_assets": x3,
        "asset_turnover": x5,
        "altman_z_score": z,
        "altman_zone": None
        if pd.isna(z)
        else "DISTRESS"
        if z < low
        else "SAFE"
        if z > high
        else "GREY",
    }


def _manual_label(ratios: dict[str, Any], streak: int) -> int:
    """Compute the specified fundamentals-only distress proxy from audited values."""
    a, o, d, m, c = (
        ratios[k] for k in ("roa", "ocf_ratio", "debt_ratio", "operating_margin", "current_ratio")
    )
    return int(
        streak >= 2
        or (a < 0 and (o < 0.06 or streak >= 1))
        or (d > 0.65 and (a < -0.03 or o < 0 or m < -0.05))
        or (c < 0.90 and d > 0.75 and (a < 0.02 or o < 0.08))
    )


@pytest.mark.parametrize(("ticker", "year"), [("AAPL", 2023), ("AAL", 2020), ("LUMN", 2023)])
def test_raw_ratio_trace(real_panel: pd.DataFrame, ticker: str, year: int) -> None:
    """Recompute a case from raw facts, including deltas and missingness, and print evidence."""
    history = real_panel.loc[real_panel["ticker"].eq(ticker)].sort_values("period_end_date")
    history = history.loc[history["fiscal_year"] <= year]
    row = history.iloc[-1].to_dict()
    assert row["fiscal_year"] == year
    cik, sic = row["cik"], row["sic_code"]
    payload = json.loads((RAW / f"CIK{cik}.json").read_bytes())
    etl = FinancialEtlPipeline().process_company_facts_payload(
        cik, as_reported_annual_payload(payload), sic
    )
    replayed = next(r for r in etl if r["fiscal_year"] == year)
    assert replayed["accession_number"] == row["accession_number"]
    ratios = _manual_ratios(row, int(sic))
    previous = _manual_ratios(history.iloc[-2].to_dict(), int(sic))
    streak = 0
    for flow in reversed(history["operating_cash_flow"].tolist()):
        if not flow < 0:
            break
        streak += 1
    label = _manual_label(ratios, streak)
    for name in ("roa", "roe", "debt_ratio", "ocf_ratio"):
        ratios[f"{name}_yoy_delta"] = ratios[name] - previous[name]
    ratios["negative_ocf_streak"] = streak
    assert int(derive_distress_label(pd.DataFrame([replayed])).iloc[0]) == label
    error = max(
        _equal(actual[name], expected)
        for name, expected in ratios.items()
        for actual in (row, replayed)
    )
    provenance = json.loads(row["field_provenance"])
    print(
        f"Trace {ticker} FY{year} CIK={cik} SIC={sic} accession={row['accession_number']} "
        f"period_end={row['period_end_date']} filed={row['filed_date']}"
    )
    print(
        json.dumps(
            {
                "facts": {
                    name: [_nullable(row[name]), provenance.get(name)] for name in FINANCIAL_COLUMNS
                },
                "metrics": {name: _nullable(row[name]) for name in METRICS},
                "is_distressed": label,
                "max_abs_error": error,
            },
            sort_keys=True,
            allow_nan=False,
        )
    )


def test_altman_distress_independence(real_panel: pd.DataFrame) -> None:
    """Override both Altman outputs at the extremes and compare every label."""
    initial = derive_distress_label(real_panel)
    for score, zone in [(999.0, "SAFE"), (-999.0, "DISTRESS")]:
        updated = derive_distress_label(real_panel.assign(altman_z_score=score, altman_zone=zone))
        changed = int(initial.ne(updated).sum())
        print(f"Altman override {score:+.1f}/{zone}: {changed}/{len(initial)} labels changed")
        assert changed == 0


@pytest.fixture(scope="module")
def splits(real_panel: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    """Reconstruct the saved run's 2021 fit, 2022 validation and embargoed test."""
    parts = TemporalSplitter().split(build_next_period_panel(real_panel), 2021, 2022)
    train = parts["train"].loc[pd.to_datetime(parts["train"]["filed_date"]) <= "2021-12-31"]
    train.attrs["train_end_year"] = 2021
    validation, test, _ = prepare_validation_test(parts["val"], parts["test"], 2022)
    return train, training_horizon_rows(train), validation, test


def _training_values(preprocessor: FinancialPreprocessor, frame: pd.DataFrame) -> np.ndarray:
    """Independently calculate quantile bounds, clipped medians and transformed arrays."""
    raw = frame[list(preprocessor.columns)].to_numpy(dtype=float)
    quantiles = np.nanquantile(
        raw, [preprocessor.lower_quantile, preprocessor.upper_quantile], axis=0
    )
    clipped = np.clip(raw, *quantiles)
    medians = np.nanmedian(clipped, axis=0)
    assert preprocessor.winsorizer is not None and preprocessor.winsorizer.bounds_ is not None
    bounds = np.array(list(preprocessor.winsorizer.bounds_.values()))
    np.testing.assert_allclose(bounds, quantiles.T, atol=1e-12, rtol=0)
    np.testing.assert_allclose(preprocessor.imputer.statistics_, medians, atol=1e-12, rtol=0)
    expected = np.where(np.isnan(clipped), medians, clipped)
    np.testing.assert_allclose(preprocessor.transform(frame), expected, atol=1e-12, rtol=0)
    return expected


def test_out_of_time_and_fitted_statistics(
    real_panel: pd.DataFrame, bundle: ModelArtifactBundle, splits: tuple[pd.DataFrame, ...]
) -> None:
    """Verify publication bounds and saved preprocessing against independent fit statistics."""
    train, supervised, validation, test = splits
    assert train.fiscal_year.max() < validation.fiscal_year.min()
    assert validation.fiscal_year.max() < test.fiscal_year.min()
    assert supervised.next_fiscal_year.max() <= train.fiscal_year.max()
    assert supervised.next_filed_date.max() <= pd.Timestamp("2021-12-31")
    assert (supervised.next_filed_date > supervised.filed_date).all()
    assert bundle.evaluation_report["split_summary"]["non_forward_supervised_rows"] == 0
    assert (pd.to_datetime(test.filed_date) >= validation.next_filed_date.max()).all()
    panel = real_panel.sort_values(["cik", "period_end_date"])
    assert not (panel.groupby("cik").filed_date.shift() > panel.filed_date).any()
    assert (len(train), len(supervised), len(validation), len(test)) == (1047, 900, 97, 196)
    c = bundle.clusterer
    train_values = _training_values(c.preprocessor, train)
    labeled = supervised.dropna(subset=["next_is_distressed"])
    _training_values(bundle.classifier.preprocessor, labeled)
    _training_values(bundle.forecaster.preprocessor, supervised)
    target_clipper = bundle.forecaster.target_winsorizer_
    assert target_clipper is not None and target_clipper.bounds_ is not None
    targets = supervised[list(target_clipper.columns)].to_numpy(dtype=float)
    np.testing.assert_allclose(
        list(target_clipper.bounds_.values()),
        np.nanquantile(targets, [0.025, 0.975], axis=0).T,
        atol=1e-12,
        rtol=0,
    )
    center = np.median(train_values, axis=0)
    scale = np.subtract(*np.percentile(train_values, [75, 25], axis=0))
    robust = (train_values - center) / scale
    mean, var = robust.mean(axis=0), robust.var(axis=0)
    for observed, expected in (
        (c.scaler.center_, center),
        (c.scaler.scale_, scale),
        (c.standard_scaler.mean_, mean),
        (c.standard_scaler.var_, var),
        (c.standard_scaler.scale_, np.sqrt(var)),
    ):
        np.testing.assert_allclose(observed, expected, atol=1e-12, rtol=0)
    standardized = (robust - mean) / np.sqrt(var)
    refit = PCA(n_components=3, random_state=42).fit(standardized)
    assert c.pca_ is not None
    np.testing.assert_allclose(c.pca_.mean_, refit.mean_, atol=1e-12, rtol=0)
    np.testing.assert_allclose(c.pca_.components_, refit.components_, atol=1e-12, rtol=0)
    np.testing.assert_allclose(
        c.pca_.explained_variance_, refit.explained_variance_, atol=1e-12, rtol=0
    )
    for preprocessor in (
        c.preprocessor,
        bundle.classifier.preprocessor,
        bundle.forecaster.preprocessor,
    ):
        full_bounds = (
            real_panel[list(preprocessor.columns)]
            .quantile([preprocessor.lower_quantile, preprocessor.upper_quantile])
            .to_numpy()
            .T
        )
        assert preprocessor.winsorizer is not None
        assert preprocessor.winsorizer.bounds_ is not None
        assert not np.allclose(full_bounds, list(preprocessor.winsorizer.bounds_.values()))
    print(
        f"Splits train={len(train)} FY{train.fiscal_year.min()}–{train.fiscal_year.max()} "
        f"supervised={len(supervised)} latest_target={supervised.next_filed_date.max()} "
        f"validation={len(validation)} FY2022 calibration={validation.next_filed_date.max()} "
        f"test={len(test)} FY{test.fiscal_year.min()}–{test.fiscal_year.max()} "
        f"first_test_filing={min(test.filed_date)}; fitted arrays within 1e-12"
    )


def test_tree_shap_all_held_out(
    bundle: ModelArtifactBundle, splits: tuple[pd.DataFrame, ...]
) -> None:
    """Rebuild the raw margin from SHAP and verify the published probability calibration."""
    test = splits[-1].dropna(subset=["next_is_distressed"])
    assert len(test) == 98
    p = bundle.classifier.predict_proba(test).astype(np.float64)
    raw = bundle.classifier.predict_raw_proba(test)
    margin = bundle.classifier.predict_raw_margin(test)
    contributions, base = ShapExplainer(bundle.classifier)._explanation(test)
    assert (p > 0).all() and (p < 1).all()
    expected = (
        raw if getattr(bundle.classifier, "model_type", "xgboost") == "random_forest" else margin
    )
    errors = np.abs(expected - (base + contributions.astype(float).sum(axis=1)))
    print(f"TreeSHAP max abs logit error={errors.max():.17g} n={len(errors)}")
    assert np.all(errors < 1e-5)
    labels = test["next_is_distressed"].astype(int)
    assert brier_score_loss(labels, p) < brier_score_loss(labels, raw)
    assert log_loss(labels, p) < log_loss(labels, raw)
    assert abs(p.mean() - labels.mean()) < abs(raw.mean() - labels.mean())


def test_paired_persistence_benchmark(
    bundle: ModelArtifactBundle, splits: tuple[pd.DataFrame, ...]
) -> None:
    """Recompute all five like-for-like benchmark rows and verify the achieved improvements."""
    test = splits[-1]
    pred = bundle.forecaster.predict(test)
    report = bundle.evaluation_report["forecasting_paired"]
    for name in FORECAST_TARGET_COLUMNS:
        cases = test.dropna(subset=[name, f"next_{name}"])
        target = cases[f"next_{name}"]
        for estimator, forecast in (
            ("persistence", cases[name]),
            ("model", pred.loc[cases.index, f"pred_{name}"]),
        ):
            stats = report[estimator][name]
            assert stats["n_samples"] == len(cases)
            assert stats["r2"] == pytest.approx(r2_score(target, forecast))
            assert stats["mae"] == pytest.approx(mean_absolute_error(target, forecast))
    for name in ("roa", "eps", "ocf_ratio"):
        assert report["model"][name]["r2"] > report["persistence"][name]["r2"]
        assert report["model"][name]["mae"] < report["persistence"][name]["mae"]


def test_training_target_permutation(
    bundle: ModelArtifactBundle, splits: tuple[pd.DataFrame, ...]
) -> None:
    """Train on seed-42 shuffled targets and score only untouched held-out targets."""
    shuffled, test = splits[1].copy(), splits[-1]
    rng = np.random.default_rng(42)
    for column in ("next_is_distressed", "next_debt_ratio", "next_ocf_ratio"):
        observed = shuffled[column].notna()
        shuffled.loc[observed, column] = rng.permutation(shuffled.loc[observed, column])
    pd.testing.assert_frame_equal(
        shuffled.drop(columns=["next_is_distressed", "next_debt_ratio", "next_ocf_ratio"]),
        splits[1].drop(columns=["next_is_distressed", "next_debt_ratio", "next_ocf_ratio"]),
    )
    clf = DistressClassifier(random_seed=42).fit(shuffled)
    reg = NextPeriodForecaster(random_seed=42).fit(shuffled)
    cases = test.dropna(subset=["next_is_distressed"])
    real_auc = roc_auc_score(cases.next_is_distressed, bundle.classifier.predict_proba(cases))
    shuffled_auc = roc_auc_score(cases.next_is_distressed, clf.predict_proba(cases))
    print(f"ROC AUC n={len(cases)} real={real_auc:.17g} shuffled={shuffled_auc:.17g}")
    selected_key = (
        "classification_selected"
        if "classification_selected" in bundle.evaluation_report
        else "classification_xgboost"
    )
    assert real_auc == bundle.evaluation_report[selected_key]["roc_auc"]
    assert real_auc > 0.9 and shuffled_auc < 0.65
    for target in ("debt_ratio", "ocf_ratio"):
        cases = test.dropna(subset=[f"next_{target}"])
        labels = cases[f"next_{target}"]
        real = r2_score(labels, bundle.forecaster.predict(cases)[f"pred_{target}"])
        # Test the direct estimator, so a persistence anchor cannot score the shuffled control.
        negative = r2_score(labels, reg.models_[target].predict(reg.preprocessor.transform(cases)))
        print(f"{target} R2 n={len(cases)} real={real:.17g} shuffled={negative:.17g}")
        assert real > 0.72 and real - negative > 0.5


def test_prediction_and_api_parity(
    real_panel: pd.DataFrame,
    bundle: ModelArtifactBundle,
    database: sqlite3.Connection,
    api: TestClient,
) -> None:
    """Compare all annual PCA and current forecasts, plus five complete REST snapshots."""
    pca = {
        (r["cik"], r["period_end_date"]): r
        for r in database.execute(
            "SELECT c.cik, s.period_end_date, m.* FROM financial_metrics m "
            "JOIN financial_statements s ON s.id=m.statement_id "
            "JOIN companies c ON c.id=m.company_id"
        )
    }
    predictions = {
        r["cik"]: r
        for r in database.execute(
            "SELECT c.cik, s.period_end_date, s.fiscal_year, p.* FROM model_predictions p "
            "JOIN companies c ON p.company_id=c.id "
            "JOIN financial_statements s ON s.id=p.source_statement_id WHERE p.model_version=?",
            (bundle.model_version,),
        )
    }
    assert len(pca) == len(real_panel) and len(predictions) == real_panel.cik.nunique()
    assert database.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == len(predictions)
    fields = (*FORECAST, "distress_probability", "risk_level", "model_version")
    max_pca = max_prediction = 0.0
    for cik, history in real_panel.groupby("cik"):
        history = history.sort_values("period_end_date")
        row = predictions[cik]
        assert row["period_end_date"] == history.iloc[-1].period_end_date.isoformat()
        assert row["target_fiscal_year"] == row["fiscal_year"] + 1
        assert row["target_fiscal_period"] == "FY"
        expected = predict_for_company_records(bundle, history)
        explanation = expected["shap_explanations"]
        stored_shap = json.loads(row["shap_explanations"])
        for field in fields:
            max_prediction = max(max_prediction, _equal(row[field], expected[field], 1e-7))
        _assert_explanation(stored_shap, explanation)
        for index, coordinates in bundle.clusterer.transform(history).iterrows():
            stored = pca[cik, history.loc[index, "period_end_date"].isoformat()]
            for field in (*PCA_COLUMNS, "cluster_id", "cluster_label"):
                max_pca = max(max_pca, _equal(stored[field], coordinates[field], 1e-7))
        ticker = history.iloc[-1].ticker
        if ticker in {"AAPL", "AAL", "CCL", "LUMN", "MSFT"}:
            response = api.get(f"/api/v1/companies/{ticker}")
            assert response.status_code == 200
            body = response.json()
            error = max(
                _equal(source[field], expected[field], 1e-7)
                for source, keys in (
                    (body["latest_prediction"], fields),
                    (body["history"][-1], (*PCA_COLUMNS, "cluster_id", "cluster_label")),
                )
                for field in keys
            )
            error = max(error, _assert_explanation(body["latest_prediction"], explanation))
            print(
                f"{ticker}: P(distress)={expected['distress_probability']:.17g} "
                f"max API error={error:.17g}"
            )
    print(
        f"SQLite PCA={len(pca)} max error={max_pca:.17g}; "
        f"forecasts={len(predictions)} max scalar error={max_prediction:.17g}"
    )


def _assert_explanation(actual: dict[str, Any], expected: dict[str, Any]) -> float:
    """Compare every SHAP contribution, base and ranked driver's serialized fields."""
    error = _equal(actual["base_value"], expected["base_value"], 1e-7)
    assert actual["output_space"] == expected["output_space"]
    assert actual["contributions"].keys() == expected["contributions"].keys()
    for name, value in expected["contributions"].items():
        error = max(error, _equal(actual["contributions"][name], value, 1e-7))
    for driver, reference in zip(actual["top_drivers"], expected["top_drivers"], strict=True):
        for key, value in reference.items():
            error = max(error, _equal(driver[key], value, 1e-7))
    return error


def _timing(
    name: str, operation: Callable[[], Any], samples: int, *, warm: bool = True
) -> tuple[float, float]:
    """Measure wall time without tracing, then capture the peak in a separate invocation."""
    coverage = Coverage.current()
    if coverage is not None:
        coverage.stop()
    try:
        if warm:
            operation()
        elapsed = []
        for _ in range(samples):
            start = perf_counter()
            operation()
            elapsed.append((perf_counter() - start) * 1_000)
        tracemalloc.start()
        try:
            operation()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    finally:
        if coverage is not None:
            coverage.start()
    median, p95 = (float(value) for value in np.percentile(elapsed, [50, 95]))
    print(f"BENCHMARK|{name}|{samples}|{median:.6f}|{p95:.6f}|{peak / 1_000_000:.6f}")
    return median, p95


def test_etl_and_inference_latency(real_panel: pd.DataFrame, bundle: ModelArtifactBundle) -> None:
    """Benchmark file-inclusive Apple ETL and the complete single-company prediction."""
    path = RAW / "CIK0000320193.json"
    pipeline = FinancialEtlPipeline()
    records = real_panel.loc[real_panel["ticker"].eq("AAPL")]

    def apple_etl() -> list[dict[str, Any]]:
        """Read the SEC file and compute the complete annual features."""
        return pipeline.process_company_facts_payload(
            "0000320193", load_annual_companyfacts(path), "3571"
        )

    def cold_decode() -> list[dict[str, Any]]:
        """Measure a new JSON decode with the OS file cache still warm."""
        _decode_companyfacts.cache_clear()
        return apple_etl()

    _timing("A Apple JSON + annual ETL (uncached decode)", cold_decode, 9)
    etl_ms, _ = _timing(
        "A Apple JSON + annual ETL (cached decode)",
        apple_etl,
        15,
    )
    prediction_ms, _ = _timing(
        "B AAPL inference + TreeSHAP", lambda: predict_for_company_records(bundle, records), 15
    )
    assert etl_ms < 25
    assert prediction_ms < 150


def _assert_nested_approx(actual: object, expected: object) -> None:
    """Compare nested evaluation reports with float ULP tolerance."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in actual:
            _assert_nested_approx(actual[key], expected[key])
    elif isinstance(actual, list) and isinstance(expected, list):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            _assert_nested_approx(left, right)
    elif isinstance(actual, float) or isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    else:
        assert actual == expected


def test_training_latency_and_saved_scores(
    real_panel: pd.DataFrame, bundle: ModelArtifactBundle
) -> None:
    """Benchmark a complete fit and compare independently reproduced saved metrics."""

    def train() -> None:
        """Fit and evaluate the full ML pipeline on the real time series."""
        fitted = train_and_evaluate_pipeline(real_panel, 2021, validation_end_year=2022)
        for section in ("classification_xgboost", "forecasting", "split_summary"):
            _assert_nested_approx(
                fitted.evaluation_report[section], bundle.evaluation_report[section]
            )

    elapsed, _ = _timing("C full training and evaluation", train, 1, warm=False)
    assert elapsed < 10_000


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/companies",
        "/companies/AAPL",
        "/clusters/map",
        "/models/evaluation",
    ],
)
def test_api_latency(api: TestClient, path: str) -> None:
    """Check warmed endpoint P95 over the populated SQLite database."""

    def get() -> None:
        """Include the complete HTTP response in the timed TestClient request."""
        assert api.get(f"/api/v1{path}").status_code == 200

    median, p95 = _timing(f"D GET /api/v1{path}", get, 25)
    assert median < 40 and p95 < 120
