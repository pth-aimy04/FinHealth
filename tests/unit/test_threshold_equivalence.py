"""Exact threshold selection parity against independently evaluated sklearn metrics."""

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score, fbeta_score, precision_score

from finhealth.ml.distress_classifier import DistressClassifier


@pytest.mark.parametrize("positive", [False, True, None])
@pytest.mark.parametrize("calibrated", [False, True])
def test_threshold_matches_sklearn_reference(positive: bool | None, calibrated: bool) -> None:
    """Compare original tie-breaking on ordinary, all-positive and all-negative validation."""
    rng = np.random.default_rng(42)
    train = pd.DataFrame({"signal": rng.normal(size=80), "next_is_distressed": np.tile([0, 1], 40)})
    classifier = DistressClassifier(feature_columns=["signal"], n_estimators=5).fit(train)
    validation = pd.DataFrame({"signal": rng.normal(size=37)})
    labels = (
        rng.integers(0, 2, len(validation))
        if positive is None
        else np.full(
            len(validation),
            int(positive),
            dtype=int,
        )
    )
    if calibrated:
        # Use actual fitting, not a mock of predictions or threshold selection.
        classifier.fit_calibration(validation, np.tile([0, 1], 19)[: len(validation)])
    probabilities = classifier.predict_proba(validation)
    thresholds = np.linspace(0.15, 0.85, 71)
    if classifier.calibration_ is not None:
        thresholds = np.unique(np.r_[probabilities, thresholds])
    reference = [
        (
            fbeta_score(labels, probabilities >= cutoff, beta=2, zero_division=0),
            f1_score(labels, probabilities >= cutoff, zero_division=0),
            precision_score(labels, probabilities >= cutoff, zero_division=0),
            cutoff,
        )
        for cutoff in thresholds
    ]
    best_f2 = max(row[0] for row in reference)
    expected = max(
        (row for row in reference if row[0] >= best_f2 - 0.02),
        key=lambda row: (row[1], row[2], row[0], -abs(row[3] - 0.5), -row[3]),
    )[3]
    assert classifier.optimize_threshold(validation, labels) == expected
