"""Next-period distress XGBoost, validation-only threshold selection, and real baselines."""

import math
from collections.abc import Sequence
from typing import Any, Literal

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from lightgbm import LGBMClassifier
from scipy.special import expit, logit
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from xgboost import XGBClassifier

from finhealth.core.exceptions import ModelPipelineError
from finhealth.etl.financial_ratios import (
    ALTMAN_MANUFACTURING_CUTOFF,
    ALTMAN_NON_MANUFACTURING_CUTOFF,
)
from finhealth.ingestion.schemas import is_manufacturing_sic
from finhealth.ml.evaluator import binary_labels, evaluate_binary_classification
from finhealth.ml.preprocessing import FinancialPreprocessor
from finhealth.ml.splitter import ML_FEATURE_COLUMNS, training_horizon_rows


def classify_risk_level(probability: float) -> str:
    """Map a valid distress probability to the specified fixed communication bands."""
    if not math.isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Probability must be finite and in [0,1]")
    return (
        "LOW"
        if probability < 0.20
        else "MEDIUM"
        if probability < 0.50
        else "HIGH"
        if probability < 0.75
        else "CRITICAL"
    )


def _classification_training(df: pd.DataFrame, target_col: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Keep observed labels and reject single-class training rather than inventing examples."""
    train = training_horizon_rows(df) if target_col.startswith("next_") else df.copy()
    if target_col not in train:
        raise ModelPipelineError(f"Missing classification target: {target_col}")
    train = train.loc[train[target_col].notna()]
    labels = binary_labels(train[target_col])
    if len(np.unique(labels)) != 2:
        raise ModelPipelineError("Classification training requires both distress classes")
    return train, labels


ModelType = Literal["xgboost", "lightgbm", "random_forest"]
ImbalanceStrategy = Literal["class_weight", "smote"]


def _apply_smote(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    sampling_strategy: float | str,
    k_neighbors: int,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Oversample the minority training class on already imputed finite features."""
    if k_neighbors < 1:
        raise ModelPipelineError("smote_k_neighbors must be >= 1")
    min_class_count = min(int((labels == 0).sum()), int((labels == 1).sum()))
    if min_class_count < 2:
        raise ModelPipelineError("SMOTE requires at least 2 samples in the minority class")
    effective_k = min(k_neighbors, min_class_count - 1)
    sampler = SMOTE(
        sampling_strategy=sampling_strategy,
        k_neighbors=effective_k,
        random_state=random_seed,
    )
    try:
        resampled_x, resampled_y = sampler.fit_resample(features, labels)
    except ValueError as error:
        raise ModelPipelineError(f"SMOTE resampling failed: {error}") from error
    return np.asarray(resampled_x, dtype=np.float64), np.asarray(resampled_y, dtype=int)


class DistressClassifier:
    """Predict a binary distress target with explicit class imbalance and fixed preprocessing."""

    def __init__(
        self,
        feature_columns: Sequence[str] = ML_FEATURE_COLUMNS,
        random_seed: int = 42,
        model_type: ModelType = "xgboost",
        imbalance_strategy: ImbalanceStrategy = "class_weight",
        smote_k_neighbors: int = 5,
        smote_sampling_strategy: float | str = "auto",
        **model_params: Any,
    ) -> None:
        """Initialize training-only preprocessing and deterministic tree-model parameters."""
        if model_type not in ("xgboost", "lightgbm", "random_forest"):
            raise ModelPipelineError(f"Unsupported distress classifier model_type: {model_type}")
        if imbalance_strategy not in ("class_weight", "smote"):
            raise ModelPipelineError(f"Unsupported imbalance_strategy: {imbalance_strategy}")
        if smote_k_neighbors < 1:
            raise ModelPipelineError("smote_k_neighbors must be >= 1")
        self.feature_columns = tuple(feature_columns)
        self.model_type: ModelType = model_type
        self.imbalance_strategy: ImbalanceStrategy = imbalance_strategy
        self.smote_k_neighbors = smote_k_neighbors
        self.smote_sampling_strategy: float | str = smote_sampling_strategy
        self.random_seed = random_seed
        self.preprocessor = FinancialPreprocessor(self.feature_columns)
        if model_type == "xgboost":
            self.params: dict[str, Any] = {
                "n_estimators": 150,
                "max_depth": 4,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_lambda": 1.0,
                "eval_metric": "logloss",
                "random_state": random_seed,
                "n_jobs": 1,
                **model_params,
            }
        elif model_type == "lightgbm":
            self.params = {
                "n_estimators": 150,
                "max_depth": 4,
                "num_leaves": 15,
                "learning_rate": 0.05,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_lambda": 1.0,
                "random_state": random_seed,
                "n_jobs": 1,
                "verbose": -1,
                **model_params,
            }
        else:
            self.params = {
                "n_estimators": 200,
                "max_depth": 8,
                "min_samples_leaf": 3,
                "class_weight": "balanced" if imbalance_strategy == "class_weight" else None,
                "random_state": random_seed,
                "n_jobs": 1,
                **model_params,
            }
        self.model_: XGBClassifier | LGBMClassifier | RandomForestClassifier | None = None
        self.optimal_threshold_ = 0.5
        self.calibration_: tuple[float, float] | None = None
        self.train_class_counts_before_: dict[int, int] | None = None
        self.train_class_counts_after_: dict[int, int] | None = None

    def fit(
        self, df_train: pd.DataFrame, target_col: str = "next_is_distressed"
    ) -> "DistressClassifier":
        """Fit on observed training labels and apply the configured imbalance strategy."""
        train, labels = _classification_training(df_train, target_col)
        self.preprocessor.fit(train)
        features = self.preprocessor.transform(train)
        self.train_class_counts_before_ = {
            0: int((labels == 0).sum()),
            1: int((labels == 1).sum()),
        }
        if self.imbalance_strategy == "smote":
            features, labels = _apply_smote(
                features,
                labels,
                sampling_strategy=self.smote_sampling_strategy,
                k_neighbors=self.smote_k_neighbors,
                random_seed=self.random_seed,
            )
        self.train_class_counts_after_ = {
            0: int((labels == 0).sum()),
            1: int((labels == 1).sum()),
        }
        self.scale_pos_weight_ = float((labels == 0).sum() / max((labels == 1).sum(), 1))
        if self.model_type == "xgboost":
            params = {**self.params, "scale_pos_weight": self.scale_pos_weight_}
            self.model_ = XGBClassifier(**params).fit(features, labels)
        elif self.model_type == "lightgbm":
            params = {**self.params, "scale_pos_weight": self.scale_pos_weight_}
            self.model_ = LGBMClassifier(**params).fit(features, labels)
        else:
            self.model_ = RandomForestClassifier(**self.params).fit(features, labels)
        self.optimal_threshold_ = 0.5
        self.calibration_ = None
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Return positive-class probabilities after applying only fitted preprocessing."""
        return self.probabilities_from_features(self.preprocessor.transform(df))

    def probabilities_from_features(self, inputs: np.ndarray) -> np.ndarray:
        """Score fitted features, applying the validation-fitted affine logit if present."""
        margin = self.raw_margin_from_features(inputs)
        affine = getattr(self, "calibration_", None)
        if affine is None:
            return expit(margin)
        slope, intercept = affine
        return expit(slope * margin + intercept)

    def raw_margin_from_features(self, inputs: np.ndarray) -> np.ndarray:
        """Return the uncalibrated log-odds margin on already transformed inputs."""
        if self.model_ is None:
            raise ModelPipelineError("Classifier must be fitted before prediction")
        model_type = getattr(self, "model_type", "xgboost")
        if model_type == "xgboost":
            return np.asarray(self.model_.predict(inputs, output_margin=True), dtype=np.float64)
        if model_type == "lightgbm":
            return np.asarray(self.model_.predict(inputs, raw_score=True), dtype=np.float64)
        proba_matrix = np.asarray(self.model_.predict_proba(inputs), dtype=np.float64)
        proba = np.clip(proba_matrix[:, 1], 1e-7, 1.0 - 1e-7)
        return np.asarray(logit(proba), dtype=np.float64)

    def predict_raw_margin(self, df: pd.DataFrame) -> np.ndarray:
        """Return the model output that raw TreeSHAP contributions reconstruct."""
        return self.raw_margin_from_features(self.preprocessor.transform(df))

    def predict_raw_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Return original class-weighted probabilities without post-hoc calibration."""
        return expit(self.predict_raw_margin(df))

    def fit_calibration(
        self, validation: pd.DataFrame, labels: Sequence[int] | pd.Series | np.ndarray
    ) -> None:
        """Fit a regularized sigmoid on a separate publication-eligible validation window."""
        y = binary_labels(labels)
        margin = self.predict_raw_margin(validation)
        if len(y) != len(margin):
            raise ModelPipelineError("Calibration requires one observed label per feature row")
        offset = math.log(self.scale_pos_weight_)
        if len(np.unique(y)) == 2:
            calibrator = LogisticRegression(random_state=self.params["random_state"])
            calibrator.fit((margin - offset).reshape(-1, 1), y)
            slope = float(calibrator.coef_[0, 0])
            if slope > 0:
                self.calibration_ = (slope, float(calibrator.intercept_[0]) - slope * offset)
                return
        # The weighted logistic population optimum shifts odds by the class weight.
        self.calibration_ = (1.0, -offset)

    def predict(self, df: pd.DataFrame, threshold: float | None = None) -> np.ndarray:
        """Return binary predictions using the validation-selected or caller-specified threshold."""
        cutoff = self.optimal_threshold_ if threshold is None else threshold
        classify_risk_level(cutoff)
        return (self.predict_proba(df) >= cutoff).astype(int)

    def optimize_threshold(
        self,
        X_df: pd.DataFrame,  # noqa: N803
        y_true: Sequence[int] | pd.Series | np.ndarray,
    ) -> float:
        """Favor F1 and precision among thresholds within 0.02 of the best validation F2."""
        labels, probabilities = binary_labels(y_true), self.predict_proba(X_df)
        if len(labels) != len(probabilities):
            raise ModelPipelineError("Validation labels and feature rows must have the same length")
        candidates = []
        thresholds = np.linspace(0.15, 0.85, 71)
        if getattr(self, "calibration_", None) is not None:
            thresholds = np.unique(np.r_[probabilities, thresholds])
        for threshold in thresholds:
            predicted = probabilities >= threshold
            # Labels/probabilities were already validated above. Reusing the binary
            # counts avoids repeatedly validating the same arrays in sklearn metrics.
            positives = int(labels.sum())
            predicted_positives = int(predicted.sum())
            true_positives = int(np.count_nonzero(predicted & (labels == 1)))
            f2_denominator = 4 * positives + predicted_positives
            f1_denominator = positives + predicted_positives
            candidates.append(
                (
                    5 * true_positives / f2_denominator if f2_denominator else 0.0,
                    2 * true_positives / f1_denominator if f1_denominator else 0.0,
                    true_positives / predicted_positives if predicted_positives else 0.0,
                    threshold,
                )
            )
        best_f2 = max(row[0] for row in candidates)
        _, _, _, best = max(
            (row for row in candidates if row[0] >= best_f2 - 0.02),
            key=lambda row: (row[1], row[2], row[0], -abs(row[3] - 0.5), -row[3]),
        )
        self.optimal_threshold_ = float(best)
        return self.optimal_threshold_

    def predict_with_risk_level(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return probability, thresholded label, and fixed risk band for each input row."""
        probabilities = self.predict_proba(df)
        return pd.DataFrame(
            {
                "distress_probability": probabilities,
                "predicted_label": (probabilities >= self.optimal_threshold_).astype(int),
                "risk_level": [classify_risk_level(float(p)) for p in probabilities],
            },
            index=df.index,
        )


class BaselineComparisonSuite:
    """Logistic regression and continuous/rule Altman benchmarks on identical held-out rows."""

    def __init__(
        self,
        feature_columns: Sequence[str] = ML_FEATURE_COLUMNS,
        random_seed: int = 42,
        imbalance_strategy: ImbalanceStrategy = "class_weight",
        smote_k_neighbors: int = 5,
        smote_sampling_strategy: float | str = "auto",
    ) -> None:
        """Initialize the requested median/scaling/logistic training pipeline."""
        if imbalance_strategy not in ("class_weight", "smote"):
            raise ModelPipelineError(f"Unsupported imbalance_strategy: {imbalance_strategy}")
        if smote_k_neighbors < 1:
            raise ModelPipelineError("smote_k_neighbors must be >= 1")
        self.feature_columns = tuple(feature_columns)
        self.random_seed = random_seed
        self.imbalance_strategy: ImbalanceStrategy = imbalance_strategy
        self.smote_k_neighbors = smote_k_neighbors
        self.smote_sampling_strategy: float | str = smote_sampling_strategy
        self._schema = FinancialPreprocessor(self.feature_columns)
        self.logistic_regression = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scaler", RobustScaler()),
                (
                    "clf",
                    LogisticRegression(
                        class_weight="balanced" if imbalance_strategy == "class_weight" else None,
                        max_iter=1000,
                        random_state=random_seed,
                    ),
                ),
            ]
        )
        self.fitted_ = False

    def fit(
        self, df_train: pd.DataFrame, target_col: str = "next_is_distressed"
    ) -> "BaselineComparisonSuite":
        """Train logistic regression on exactly the same observed target horizon as XGBoost."""
        train, labels = _classification_training(df_train, target_col)
        frame = self._schema.frame(train)
        if self.imbalance_strategy == "smote":
            imputer = self.logistic_regression.named_steps["imputer"]
            scaler = self.logistic_regression.named_steps["scaler"]
            clf = self.logistic_regression.named_steps["clf"]
            scaled = scaler.fit_transform(imputer.fit_transform(frame))
            resampled_x, resampled_y = _apply_smote(
                scaled,
                labels,
                sampling_strategy=self.smote_sampling_strategy,
                k_neighbors=self.smote_k_neighbors,
                random_seed=self.random_seed,
            )
            clf.fit(resampled_x, resampled_y)
        else:
            self.logistic_regression.fit(frame, labels)
        self.fitted_ = True
        return self

    def predict_probabilities(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        """Return both continuous risk scores, using numerically stable Altman logistic mapping."""
        if not self.fitted_:
            raise ModelPipelineError("Baselines must be fitted before prediction")
        if "altman_z_score" not in df:
            raise ModelPipelineError("Altman benchmark requires altman_z_score")
        z = (
            pd.to_numeric(df["altman_z_score"], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .to_numpy()
        )
        manufacturing = (
            df["sic_code"].map(is_manufacturing_sic).to_numpy()
            if "sic_code" in df
            else np.ones(len(df), dtype=bool)
        )
        cutoffs = np.where(
            manufacturing, ALTMAN_MANUFACTURING_CUTOFF, ALTMAN_NON_MANUFACTURING_CUTOFF
        )
        margin = cutoffs - np.where(np.isfinite(z), z, cutoffs)
        altman = expit(margin)
        # Preserve the strict rule even when expit rounds a positive margin to 0.5.
        altman = np.where(margin > 0, np.maximum(altman, np.nextafter(0.5, 1)), altman)
        return {
            "logistic_regression": self.logistic_regression.predict_proba(self._schema.frame(df))[
                :, 1
            ],
            "altman_z_baseline": altman,
        }

    def evaluate(
        self, df: pd.DataFrame, y_true: Sequence[int] | pd.Series | np.ndarray
    ) -> dict[str, dict[str, Any]]:
        """Score both baselines using the strict variant-specific Altman rule."""
        scores = self.predict_probabilities(df)
        return {
            name: evaluate_binary_classification(
                y_true,
                values,
                threshold=float(np.nextafter(0.5, 1)) if name == "altman_z_baseline" else 0.5,
            )
            for name, values in scores.items()
        }


CANDIDATE_MODEL_TYPES: tuple[ModelType, ...] = ("xgboost", "lightgbm", "random_forest")


def select_best_classifier(
    candidates: dict[str, DistressClassifier],
    eval_df: pd.DataFrame,
    eval_labels: Sequence[int] | pd.Series | np.ndarray,
) -> tuple[str, DistressClassifier, dict[str, dict[str, Any]]]:
    """Evaluate fitted candidates on identical rows and return the highest-scoring model."""
    if not candidates:
        raise ModelPipelineError("At least one candidate classifier is required for selection")
    y = binary_labels(eval_labels)
    metrics: dict[str, dict[str, Any]] = {}
    for name, clf in candidates.items():
        probs = clf.predict_proba(eval_df)
        metrics[name] = evaluate_binary_classification(y, probs, clf.optimal_threshold_)

    def _score_key(name: str) -> tuple[float, float, float, float]:
        row = metrics[name]
        roc = float(row["roc_auc"]) if row["roc_auc"] is not None else -1.0
        pr = float(row["pr_auc"]) if row["pr_auc"] is not None else -1.0
        f2 = float(row["f2_score"])
        brier = float(row["brier_score"]) if row["brier_score"] is not None else 1.0
        return (roc, pr, f2, -brier)

    best_name = max(candidates, key=_score_key)
    return best_name, candidates[best_name], metrics
