"""Real TreeSHAP contributions in XGBoost binary log-odds output space."""

from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import shap
from lightgbm import LGBMClassifier
from scipy.special import expit
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from finhealth.core.exceptions import ModelPipelineError
from finhealth.ml.distress_classifier import DistressClassifier


@lru_cache(maxsize=4)
def _tree_explainer(
    model: XGBClassifier | LGBMClassifier | RandomForestClassifier,
) -> shap.TreeExplainer:
    """Reuse tree parsing for a fitted model instance."""
    if isinstance(model, RandomForestClassifier):
        return shap.TreeExplainer(model)
    return shap.TreeExplainer(model, model_output="raw", feature_perturbation="tree_path_dependent")


class ShapExplainer:
    """Explain the exact fitted classifier inputs without fitting a background on test data."""

    def __init__(self, classifier: DistressClassifier) -> None:
        """Construct TreeExplainer from the actual fitted XGBoost ensemble."""
        if classifier.model_ is None:
            raise ModelPipelineError("SHAP requires a fitted classifier")
        self.classifier = classifier
        self.explainer = _tree_explainer(classifier.model_)

    def _explanation(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Return finite binary raw-margin SHAP values and their actual per-row base values."""
        if df.empty:
            raise ModelPipelineError("SHAP requires at least one row")
        return self._explain_values(self.classifier.preprocessor.transform(df))

    def _explain_values(self, inputs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Evaluate TreeSHAP for already preprocessed inputs."""
        explanation = self.explainer(inputs)
        values, base = np.asarray(explanation.values), np.asarray(explanation.base_values)
        if values.ndim == 3 and values.shape[2] == 2:
            values = values[:, :, 1]
            base = base[:, 1] if base.ndim == 2 else base[1]
        if values.ndim != 2 or values.shape != (len(inputs), len(self.classifier.feature_columns)):
            raise ModelPipelineError("Unexpected binary TreeSHAP output shape")
        if not np.isfinite(values).all() or not np.isfinite(base).all():
            raise ModelPipelineError("TreeSHAP returned nonfinite values")
        return values, np.broadcast_to(base, (len(inputs),))

    def explain_instance(
        self, df_row: pd.DataFrame | Mapping[str, Any], top_k: int = 10
    ) -> dict[str, Any]:
        """Return all log-odds contributions and ranked drivers with transformed model inputs."""
        df = df_row if isinstance(df_row, pd.DataFrame) else pd.DataFrame([dict(df_row)])
        if len(df) != 1 or top_k < 0:
            raise ModelPipelineError("Instance explanation requires exactly one row and top_k>=0")
        transformed = self.classifier.preprocessor.transform(df)
        values, base = self._explain_values(transformed)
        contributions = dict(
            zip(self.classifier.feature_columns, values[0].astype(float), strict=True)
        )
        inputs = dict(zip(self.classifier.feature_columns, transformed[0], strict=True))
        ordered = sorted(contributions, key=lambda key: (-abs(contributions[key]), key))[:top_k]
        margin = float(self.classifier.raw_margin_from_features(transformed)[0])
        is_rf = isinstance(self.classifier.model_, RandomForestClassifier)
        return {
            "base_value": float(base[0]),
            "output_space": "probability" if is_rf else "log_odds",
            "raw_margin": margin,
            "raw_probability": float(expit(margin)),
            "fitted_inputs": {key: float(value) for key, value in inputs.items()},
            "distress_probability": float(
                self.classifier.probabilities_from_features(transformed)[0]
            ),
            "contributions": {key: float(value) for key, value in contributions.items()},
            "top_drivers": [
                {
                    "feature": key,
                    "feature_value": float(inputs[key]),
                    "shap_value": float(contributions[key]),
                    "direction": "INCREASES_RISK" if contributions[key] >= 0 else "DECREASES_RISK",
                }
                for key in ordered
            ],
        }

    def compute_global_importance(self, df: pd.DataFrame) -> dict[str, float]:
        """Return actual held-out mean absolute TreeSHAP contributions for every feature."""
        values, _ = self._explanation(df)
        importance = dict(
            zip(self.classifier.feature_columns, np.abs(values).mean(axis=0), strict=True)
        )
        return {
            key: float(value)
            for key, value in sorted(importance.items(), key=lambda item: (-item[1], item[0]))
        }
