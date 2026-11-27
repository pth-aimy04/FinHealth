"""Binary and multi-target metrics with explicit undefined-data edge cases."""

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    fbeta_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

from finhealth.core.exceptions import ModelPipelineError
from finhealth.etl.feature_engineering import RatioWinsorizer
from finhealth.ml.splitter import FORECAST_TARGET_COLUMNS


def binary_labels(values: Sequence[int] | pd.Series | np.ndarray) -> np.ndarray:
    """Validate a nonempty one-dimensional binary target vector without truncating floats."""
    labels = np.asarray(values)
    if labels.ndim != 1 or not len(labels) or not np.isin(labels, [0, 1]).all():
        raise ModelPipelineError("Labels must be a nonempty one-dimensional binary vector")
    return labels.astype(int)


def evaluate_binary_classification(
    y_true: Sequence[int] | pd.Series | np.ndarray,
    y_prob: Sequence[float] | np.ndarray,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Compute reproducible metrics; ROC AUC is None when only one true class exists."""
    labels, probabilities = binary_labels(y_true), np.asarray(y_prob, dtype=float)
    if (
        probabilities.shape != labels.shape
        or not np.isfinite(probabilities).all()
        or ((probabilities < 0) | (probabilities > 1)).any()
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ModelPipelineError("Probabilities/threshold must be finite in [0,1] and match labels")
    predicted = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(labels, predicted)),
        "precision": float(precision_score(labels, predicted, zero_division=0)),
        "recall": float(recall_score(labels, predicted, zero_division=0)),
        "f1_score": float(f1_score(labels, predicted, zero_division=0)),
        "f2_score": float(fbeta_score(labels, predicted, beta=2, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities))
        if len(np.unique(labels)) == 2
        else None,
        "pr_auc": float(average_precision_score(labels, probabilities)) if labels.any() else 0.0,
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "mean_probability": float(probabilities.mean()),
        "prevalence": float(labels.mean()),
        "threshold": float(threshold),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def evaluate_multitarget_regression(
    df_true: pd.DataFrame,
    df_pred: pd.DataFrame,
    target_columns: Sequence[str] = FORECAST_TARGET_COLUMNS,
    *,
    target_winsorizer: RatioWinsorizer | None = None,
) -> dict[str, dict[str, Any]]:
    """Score finite pairs, optionally clipping truth with training-fitted bounds."""
    if not df_true.index.is_unique or not df_pred.index.is_unique:
        raise ModelPipelineError("Regression evaluation requires unique row indices")
    if target_winsorizer is not None:
        df_true = target_winsorizer.transform(df_true.replace([np.inf, -np.inf], np.nan))
    report: dict[str, dict[str, Any]] = {}
    for column in target_columns:
        truth, prediction = f"next_{column}", f"pred_{column}"
        if truth not in df_true or prediction not in df_pred:
            raise ModelPipelineError(f"Missing regression column for {column}")
        aligned = pd.concat([df_true[truth], df_pred[prediction]], axis=1, join="inner")
        aligned = aligned.replace([np.inf, -np.inf], np.nan).dropna()
        count = len(aligned)
        report[column] = {
            "mae": float(mean_absolute_error(aligned[truth], aligned[prediction]))
            if count
            else None,
            "rmse": math.sqrt(mean_squared_error(aligned[truth], aligned[prediction]))
            if count
            else None,
            "r2": float(r2_score(aligned[truth], aligned[prediction])) if count >= 2 else None,
            "n_samples": count,
        }
    return report


def reliability_bins(
    labels: pd.Series, raw: np.ndarray, calibrated: np.ndarray
) -> list[dict[str, Any]]:
    """Compare mean model scores to observed rates within fixed probability deciles."""
    y = binary_labels(labels)
    rows: list[dict[str, Any]] = []
    for name, scores in (("raw", raw), ("calibrated", calibrated)):
        bins = np.minimum((scores * 10).astype(int), 9)
        for bucket in range(10):
            mask = bins == bucket
            if mask.any():
                rows.append(
                    {
                        "model": name,
                        "lower": bucket / 10,
                        "upper": (bucket + 1) / 10,
                        "n": int(mask.sum()),
                        "positives": int(y[mask].sum()),
                        "mean_probability": float(scores[mask].mean()),
                        "observed_prevalence": float(y[mask].mean()),
                    }
                )
    return rows
