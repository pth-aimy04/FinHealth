"""Group-isolated backward-looking trajectories and training-only quantile clipping."""

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import pandas as pd

from finhealth.core.exceptions import EtlProcessingError
from finhealth.etl.financial_ratios import _finite


def compute_temporal_features(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Compute previous-period deltas and OCF streaks separately by company and form.

    The required *_yoy_delta names represent t minus t-1, including for quarterly
    records; they do not imply a four-quarter lag or interpolate missing periods.
    """
    ordered = sorted(
        records,
        key=lambda row: (
            row.get("period_end_date", date(int(row["fiscal_year"]), 12, 31)),
            row.get("form_type", "10-K"),
            str(row.get("company_id", row.get("cik", ""))),
        ),
    )
    previous: dict[tuple[Any, str], dict[str, Any]] = {}
    result: list[dict[str, Any]] = []
    for original in ordered:
        row = dict(original)
        key = (row.get("company_id", row.get("cik")), row.get("form_type", "10-K"))
        last = previous.get(key, {})
        for metric in ("roa", "roe", "debt_ratio", "ocf_ratio"):
            current, prior = _finite(row.get(metric)), _finite(last.get(metric))
            delta = current - prior if current is not None and prior is not None else None
            row[f"{metric}_yoy_delta"] = _finite(delta)
        ocf = _finite(row.get("operating_cash_flow"))
        row["negative_ocf_streak"] = (
            last.get("negative_ocf_streak", 0) + 1 if (ocf is not None and ocf < 0) else 0
        )
        previous[key] = row
        result.append(row)
    return result


class RatioWinsorizer:
    """Learn finite numeric quantiles on training data and reuse fixed bounds."""

    def __init__(
        self,
        columns: Sequence[str],
        lower_quantile: float = 0.01,
        upper_quantile: float = 0.99,
    ) -> None:
        """Validate quantile order and retain a defensive immutable column specification."""
        if not 0 <= lower_quantile < upper_quantile <= 1:
            raise ValueError("Require 0 <= lower_quantile < upper_quantile <= 1")
        if isinstance(columns, str) or len(set(columns)) != len(columns):
            raise ValueError("columns must be a sequence of distinct column names")
        self.columns = tuple(columns)
        self.lower_quantile, self.upper_quantile = lower_quantile, upper_quantile
        self.bounds_: dict[str, tuple[float, float]] | None = None

    def fit(self, df: pd.DataFrame) -> "RatioWinsorizer":
        """Learn bounds only from this training frame, rejecting unlearnable columns."""
        if df.empty:
            raise EtlProcessingError("Cannot fit winsorizer on an empty training frame")
        bounds: dict[str, tuple[float, float]] = {}
        for column in self.columns:
            if column not in df or not pd.api.types.is_numeric_dtype(df[column]):
                raise EtlProcessingError(f"Missing or nonnumeric training column: {column}")
            finite = df[column].dropna()
            if finite.empty or not all(math.isfinite(value) for value in finite):
                raise EtlProcessingError(f"Training column has no usable finite bounds: {column}")
            low, high = finite.quantile([self.lower_quantile, self.upper_quantile])
            bounds[column] = (float(low), float(high))
        self.bounds_ = bounds
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a clipped copy without recomputing bounds or changing missing values."""
        if self.bounds_ is None:
            raise EtlProcessingError("RatioWinsorizer must be fitted before transform")
        result = df.copy(deep=True)
        for column, (low, high) in self.bounds_.items():
            if column not in result or not pd.api.types.is_numeric_dtype(result[column]):
                raise EtlProcessingError(f"Missing or nonnumeric transform column: {column}")
            result[column] = result[column].clip(low, high)
        return result
