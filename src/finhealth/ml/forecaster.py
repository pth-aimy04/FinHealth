"""Dedicated next-period XGBoost regressors with train-only feature and target clipping."""

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from finhealth.core.exceptions import ModelPipelineError
from finhealth.etl.feature_engineering import RatioWinsorizer
from finhealth.ml.preprocessing import FinancialPreprocessor
from finhealth.ml.splitter import FORECAST_TARGET_COLUMNS, ML_FEATURE_COLUMNS, training_horizon_rows

LOWER_QUANTILE = 0.025
UPPER_QUANTILE = 0.975


class NextPeriodForecaster:
    """Fit one regressor per indicator using only observed finite training targets."""

    def __init__(
        self,
        feature_columns: Sequence[str] = ML_FEATURE_COLUMNS,
        target_columns: Sequence[str] = FORECAST_TARGET_COLUMNS,
        random_seed: int = 42,
        *,
        allow_missing_targets: bool = False,
        **xgb_params: Any,
    ) -> None:
        """Set deterministic defaults and retain user-provided model hyperparameters."""
        self.feature_columns, self.target_columns = tuple(feature_columns), tuple(target_columns)
        self.allow_missing_targets = allow_missing_targets
        self.preprocessor = FinancialPreprocessor(
            self.feature_columns, LOWER_QUANTILE, UPPER_QUANTILE
        )
        self.params = {
            "n_estimators": 140,
            "max_depth": 3,
            "learning_rate": 0.04,
            "min_child_weight": 3,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "reg_alpha": 0.1,
            "reg_lambda": 1.5,
            "objective": "reg:pseudohubererror",
            "random_state": random_seed,
            "n_jobs": 1,
            **xgb_params,
        }
        self.models_: dict[str, XGBRegressor] = {}
        self.residual_models_: dict[str, XGBRegressor] = {}
        self.blends_: dict[str, tuple[str, float]] = {}
        self.target_winsorizer_: RatioWinsorizer | None = None

    def fit(self, df_train: pd.DataFrame) -> "NextPeriodForecaster":
        """Purge crossing targets and train independent regressors without target imputation."""
        train = training_horizon_rows(df_train)
        targets = [f"next_{column}" for column in self.target_columns]
        if not set(targets).issubset(train):
            raise ModelPipelineError("Forecaster requires next-period target columns")
        target_frame = train[targets].astype(float).replace([np.inf, -np.inf], np.nan)
        active_targets = [col for col in targets if target_frame[col].notna().sum() >= 2]
        if not getattr(self, "allow_missing_targets", False) and len(active_targets) < len(targets):
            raise ModelPipelineError(
                "Every forecast target requires at least two finite training rows"
            )
        if not active_targets:
            raise ModelPipelineError(
                "At least one forecast target requires two finite training rows"
            )
        self.preprocessor.fit(train)
        values = self.preprocessor.transform(train)
        self.target_winsorizer_ = RatioWinsorizer(
            active_targets, LOWER_QUANTILE, UPPER_QUANTILE
        ).fit(target_frame)
        clipped = self.target_winsorizer_.transform(target_frame)
        self.models_, self.residual_models_, self.blends_ = {}, {}, {}
        for column in self.target_columns:
            key = f"next_{column}"
            observed = target_frame[key].notna()
            if observed.sum() < 2:
                continue
            self.models_[column] = self._fit_regressor(
                values[observed.to_numpy()], clipped.loc[observed, key]
            )
            current = self._current(train, column)
            paired = observed.to_numpy() & np.isfinite(current)
            if paired.sum() >= 2:
                delta = clipped.loc[paired, key] - self._clipped_current(current, column)[paired]
                self.residual_models_[column] = self._fit_regressor(values[paired], delta)
                self.blends_[column] = ("residual", 1.0)
        return self

    def _fit_regressor(self, values: np.ndarray, target: pd.Series) -> XGBRegressor:
        """Fit a robust tree ensemble with a base score in the target's units."""
        params = {"base_score": float(target.median()), **self.params}
        return XGBRegressor(**params).fit(values, target)

    def _current(self, df: pd.DataFrame, column: str) -> np.ndarray:
        """Read the reported current value without median imputation."""
        values = df[column] if column in df else pd.Series(np.nan, index=df.index)
        return pd.to_numeric(values, errors="coerce").to_numpy(dtype=float, na_value=np.nan)

    def _clipped_current(self, current: np.ndarray, column: str) -> np.ndarray:
        """Express the residual anchor on the same training-clipped scale as the target."""
        clipper = self.target_winsorizer_
        assert clipper is not None and clipper.bounds_ is not None
        return np.clip(current, *clipper.bounds_[f"next_{column}"])

    def _candidates(
        self, transformed: np.ndarray, current: np.ndarray, column: str
    ) -> dict[str, np.ndarray]:
        """Produce a level forecast and a residual forecast using fixed trained estimators."""
        predictions = {"level": self.models_[column].predict(transformed).astype(float)}
        residual = getattr(self, "residual_models_", {}).get(column)
        if residual is not None:
            predictions["residual"] = self._clipped_current(current, column) + residual.predict(
                transformed
            )
        return predictions

    def tune_shrinkage(self, validation: pd.DataFrame) -> None:
        """Choose a blend by equal-weight validation MAE and RMSE relative to persistence."""
        transformed = self.preprocessor.transform(validation)
        for column in self.target_columns:
            if column not in self.models_:
                continue
            current = self._current(validation, column)
            target = self._current(validation, f"next_{column}")
            paired = np.isfinite(current) & np.isfinite(target)
            if paired.sum() < 2:
                continue
            base = current[paired]
            y = target[paired]
            absolute = np.abs(base - y)
            mae, rmse = absolute.mean(), np.sqrt(np.mean(absolute**2))
            if mae == 0:
                self.blends_[column] = ("level", 0.0)
                continue
            best = (2.0, 0.0, "level")
            for name, candidate in self._candidates(transformed[paired], base, column).items():
                for weight in np.linspace(0.05, 1.0, 20):
                    error = base + weight * (candidate - base) - y
                    score = np.abs(error).mean() / mae + np.sqrt(np.mean(error**2)) / rmse
                    best = min(best, (float(score), float(weight), name))
            self.blends_[column] = (best[2], best[1])

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict all configured next-period indicators with stable column/index alignment."""
        if not self.models_:
            raise ModelPipelineError("Forecaster must be fitted before prediction")
        values = self.preprocessor.transform(df)
        predictions = {}
        for column in self.target_columns:
            if column not in self.models_:
                predictions[f"pred_{column}"] = np.full(len(df), np.nan)
                continue
            current = self._current(df, column)
            candidates = self._candidates(values, current, column)
            method, weight = getattr(self, "blends_", {}).get(column, ("level", 1.0))
            observed = np.isfinite(current)
            result = candidates["level"].copy()
            result[observed] = current[observed] + weight * (
                candidates[method][observed] - current[observed]
            )
            predictions[f"pred_{column}"] = result
        return pd.DataFrame(predictions, index=df.index)
