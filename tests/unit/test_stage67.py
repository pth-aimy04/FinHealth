"""Regression coverage for fundamental labels and comparable forecast metrics."""

import numpy as np
import pandas as pd
import pytest

from finhealth.etl.feature_engineering import RatioWinsorizer
from finhealth.ml.evaluator import evaluate_multitarget_regression
from finhealth.ml.splitter import derive_distress_label


def test_fundamental_distress_rules_ignore_altman_columns() -> None:
    """Trigger each branch separately and preserve observed labels and strict boundaries."""
    healthy = dict(
        roa=0.1,
        ocf_ratio=0.2,
        operating_margin=0.2,
        debt_ratio=0.4,
        current_ratio=1.2,
        negative_ocf_streak=0,
    )
    scenarios = [
        {},
        {"roa": -0.01, "ocf_ratio": 0.05},
        {"roa": -0.01, "negative_ocf_streak": 1},
        {"operating_margin": -0.06, "debt_ratio": 0.66},
        {"current_ratio": 0.89, "debt_ratio": 0.76, "ocf_ratio": 0.07},
        {"negative_ocf_streak": 2},
        {"roa": -0.03, "ocf_ratio": 0.06, "operating_margin": -0.05, "debt_ratio": 0.65},
        {"current_ratio": 0.90, "debt_ratio": 0.75, "ocf_ratio": 0.08},
        {"negative_ocf_streak": 2, "is_distressed": 0},
        {"is_bankrupt": 1},
    ]
    panel = pd.DataFrame([healthy | overrides for overrides in scenarios])
    expected = [0, 1, 1, 1, 1, 1, 0, 0, 0, 1]
    for score, zone in ((-10, "DISTRESS"), (10, "SAFE"), (np.nan, None)):
        assert derive_distress_label(
            panel.assign(altman_z_score=score, altman_zone=zone)
        ).tolist() == (expected)


def test_forecast_scoring_clips_only_finite_truth_at_fitted_bounds() -> None:
    """Retain raw errors and leave forecasts, missing values and learned bounds unchanged."""
    training = pd.DataFrame({"next_roa": [-0.3, 0.1, 0.4]})
    clipper = RatioWinsorizer(["next_roa"], 0, 1).fit(training)
    truth = pd.DataFrame({"next_roa": [-2.0, 0.2, np.inf]}, index=[4, 8, 12])
    predictions = pd.DataFrame({"pred_roa": [0.2, 1.0, -0.1]}, index=[8, 4, 12])
    raw = evaluate_multitarget_regression(truth, predictions, ["roa"])["roa"]
    clipped = evaluate_multitarget_regression(
        truth, predictions, ["roa"], target_winsorizer=clipper
    )["roa"]
    assert raw["mae"] == pytest.approx(1.5)
    assert clipped["mae"] == pytest.approx(0.65)
    assert raw["n_samples"] == clipped["n_samples"] == 2
    assert clipper.bounds_ == {"next_roa": (-0.3, 0.4)}
    assert truth.loc[4, "next_roa"] == -2.0
