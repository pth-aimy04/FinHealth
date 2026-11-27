"""Shared fitted financial feature contract without held-out statistic leakage."""

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from finhealth.core.exceptions import ModelPipelineError
from finhealth.etl.feature_engineering import RatioWinsorizer


class FinancialPreprocessor:
    """Training-only winsorization and median imputation with stable feature order."""

    def __init__(
        self, columns: Sequence[str], lower_quantile: float = 0.01, upper_quantile: float = 0.99
    ) -> None:
        """Record the feature schema; do not learn any statistics until fit."""
        if not columns or isinstance(columns, str) or len(set(columns)) != len(columns):
            raise ModelPipelineError("Features must be a nonempty sequence of distinct names")
        self.columns = tuple(columns)
        self.lower_quantile, self.upper_quantile = lower_quantile, upper_quantile
        self.winsorizer: RatioWinsorizer | None = None
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)

    def frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate feature presence and convert infinities to explicitly missing model inputs."""
        missing = set(self.columns) - set(df)
        if missing:
            raise ModelPipelineError(f"Missing feature columns: {sorted(missing)}")
        try:
            return df[list(self.columns)].astype(float).replace([np.inf, -np.inf], np.nan)
        except (ValueError, TypeError) as error:
            raise ModelPipelineError("Model features must be numeric or missing") from error

    def fit(self, df: pd.DataFrame) -> "FinancialPreprocessor":
        """Learn bounds and medians only on training data; empty features use fixed zero."""
        values = self.frame(df)
        if values.empty:
            raise ModelPipelineError("Cannot fit preprocessing on an empty frame")
        available = [column for column in self.columns if values[column].notna().any()]
        self.winsorizer = RatioWinsorizer(available, self.lower_quantile, self.upper_quantile).fit(
            values
        )
        self.imputer.fit(self.winsorizer.transform(values))
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Apply fixed learned bounds/medians, preserving all training feature dimensions."""
        if self.winsorizer is None:
            raise ModelPipelineError("Financial preprocessing must be fitted before transform")
        try:
            values = df[list(self.columns)].to_numpy(dtype=float, copy=True, na_value=np.nan)
        except (KeyError, TypeError, ValueError) as error:
            raise ModelPipelineError(
                "Model inputs must contain all numeric feature columns"
            ) from error
        values[~np.isfinite(values)] = np.nan
        bounds = self.winsorizer.bounds_
        assert bounds is not None
        limits = [bounds.get(column, (-np.inf, np.inf)) for column in self.columns]
        lower, upper = np.asarray(limits).T
        np.clip(values, lower, upper, out=values)
        # Median imputation is a columnwise substitution using the fitted sklearn statistics.
        return np.where(np.isnan(values), self.imputer.statistics_, values)
