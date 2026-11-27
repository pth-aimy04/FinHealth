"""Equity cushions, train-only unit-variance geometry, and first-filed SEC annual selection."""

import copy

import numpy as np
import pandas as pd

from finhealth.etl.financial_ratios import compute_statement_ratios
from finhealth.ml.benchmark_data import build_benchmark_panel
from finhealth.ml.pca_clustering import FinancialHealthClusterer
from finhealth.ml.splitter import derive_distress_label, prepare_validation_test
from finhealth.ml.train_cli import as_reported_annual_payload


def test_five_percent_equity_cushion_and_ratio_bounds() -> None:
    """Reject equity slivers, retain the inclusive boundary, and clamp meaningful ratios."""
    base = {"total_assets": 100.0, "net_income": -10.0, "total_liabilities": 99.5}
    for equity in (-1, 0, 0.5, 4.999):
        result = compute_statement_ratios(base | {"stockholders_equity": equity})
        assert result["roe"] is result["debt_to_equity"] is None
    boundary = compute_statement_ratios(base | {"stockholders_equity": 5.0})
    assert boundary["roe"] == -2.0
    assert boundary["debt_to_equity"] == 19.9
    extreme = compute_statement_ratios(
        base | {"stockholders_equity": 5.0, "net_income": 1000.0, "total_liabilities": 200.0}
    )
    assert extreme["roe"] == 3.0
    assert extreme["debt_to_equity"] == 20.0
    assert (
        compute_statement_ratios(base | {"stockholders_equity": 5.0, "net_income": -1000.0})["roe"]
        == -3.0
    )


def test_unsupervised_training_geometry_is_zero_mean_and_unit_variance() -> None:
    """Every varying feature entering PCA has actual population variance one on training only."""
    panel = build_benchmark_panel()
    train = panel.loc[panel.fiscal_year <= 2021]
    model = FinancialHealthClusterer().fit(train)
    features = model.preprocessor.transform(train)
    standardized = model.standard_scaler.transform(model.scaler.transform(features))
    np.testing.assert_allclose(standardized.mean(axis=0), 0.0, atol=1e-12)
    np.testing.assert_allclose(standardized.var(axis=0), 1.0, atol=1e-12)
    assert model.preprocessor.winsorizer.lower_quantile == 0.05
    assert model.preprocessor.winsorizer.upper_quantile == 0.95
    statistics = model.standard_scaler.mean_.copy()
    model.transform(panel.loc[panel.fiscal_year > 2021].assign(roa=1e6))
    np.testing.assert_array_equal(model.standard_scaler.mean_, statistics)
    # This corpus is nondegenerate; do not manufacture a variance fraction to satisfy a cap.
    assert 0 < model.diagnostics_["explained_variance_ratio"][0] < 0.9


def test_fallback_outcomes_are_sparse_nonlinear_and_not_altman_labels() -> None:
    """Verify sparse deterministic outcomes, bounded ratios, and no circular Altman rule."""
    panel = build_benchmark_panel()
    assert 0.15 <= panel.is_distressed.mean() <= 0.25
    assert panel.roe.dropna().between(-3, 3).all()
    assert panel.debt_to_equity.dropna().between(0, 20).all()
    assert ((panel.stockholders_equity / panel.total_assets) >= 0.05).all()
    proxy_only = derive_distress_label(panel.drop(columns="is_distressed"))
    assert (proxy_only != panel.is_distressed).sum() > 0
    pd.testing.assert_series_equal(panel.is_distressed, build_benchmark_panel().is_distressed)


def test_first_filed_annual_context_excludes_quarterly_and_future_revisions() -> None:
    """Select first-filed annual values rather than later revisions or quarterly footnotes."""
    original = {
        "start": "2020-01-01",
        "end": "2020-12-31",
        "filed": "2021-02-15",
        "accn": "first",
        "form": "10-K",
        "fp": "FY",
        "fy": 2020,
        "val": 10.0,
    }
    rows = [
        original,
        original | {"filed": "2023-02-15", "accn": "revision", "val": 99.0},
        original | {"start": "2020-10-01", "end": "2020-12-31", "val": 3.0},
        original | {"form": "10-Q", "fp": "Q3", "end": "2020-09-30"},
    ]
    payload = {"cik": 320193, "facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": rows}}}}}
    before = copy.deepcopy(payload)
    selected = as_reported_annual_payload(payload)["facts"]["us-gaap"]["NetIncomeLoss"]["units"][
        "USD"
    ]
    assert selected[0] == original
    assert all(row["accn"] == "first" and row["form"] == "10-K" for row in selected)
    assert payload == before


def test_calibration_labels_precede_every_scored_test_origin() -> None:
    """A global threshold can use all admitted validation labels only after their publication."""
    validation = pd.DataFrame(
        {
            "next_is_distressed": [0, 1, 1],
            "next_filed_date": pd.to_datetime(["2024-02-01", "2024-04-01", "2025-01-01"]),
        }
    )
    test = pd.DataFrame({"filed_date": pd.to_datetime(["2024-03-01", "2024-04-01", "2025-02-01"])})
    admitted, scored, asof = prepare_validation_test(validation, test, 2022)
    assert len(admitted) == len(scored) == 2
    assert asof == "2024-04-01T00:00:00"
    assert admitted.next_filed_date.max() <= scored.filed_date.min()
