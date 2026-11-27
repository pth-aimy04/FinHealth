"""Chronological panel labels, sequential targets, and out-of-time partitions."""

import numpy as np
import pandas as pd

from finhealth.core.exceptions import ModelPipelineError

RATIO_FEATURE_COLUMNS: tuple[str, ...] = (
    "roa",
    "roe",
    "eps",
    "debt_ratio",
    "debt_to_equity",
    "current_ratio",
    "operating_margin",
    "ocf_ratio",
    "working_capital_ratio",
    "retained_earnings_ratio",
    "ebit_to_assets",
    "asset_turnover",
)
TEMPORAL_FEATURE_COLUMNS: tuple[str, ...] = (
    "roa_yoy_delta",
    "roe_yoy_delta",
    "debt_ratio_yoy_delta",
    "ocf_ratio_yoy_delta",
    "negative_ocf_streak",
)
ML_FEATURE_COLUMNS: tuple[str, ...] = RATIO_FEATURE_COLUMNS + TEMPORAL_FEATURE_COLUMNS
FORECAST_TARGET_COLUMNS: tuple[str, ...] = ("roa", "roe", "eps", "debt_ratio", "ocf_ratio")


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    """Read an optional numeric signal with absent/nonfinite values left missing."""
    values = df[column] if column in df else pd.Series(np.nan, index=df.index)
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)


def derive_distress_label(df: pd.DataFrame) -> pd.Series:
    """Prefer observed binary labels row by row; otherwise use the requested distress proxy."""
    roa = _numeric(df, "roa")
    cash_flow = _numeric(df, "ocf_ratio")
    streak = _numeric(df, "negative_ocf_streak")
    leverage = _numeric(df, "debt_ratio")
    margin = _numeric(df, "operating_margin")
    liquidity = _numeric(df, "current_ratio")
    proxy = (
        ((roa < 0) & ((cash_flow < 0.06) | (streak >= 1)))
        | (((roa < -0.03) | (cash_flow < 0) | (margin < -0.05)) & (leverage > 0.65))
        | ((liquidity < 0.90) & (leverage > 0.75) & ((roa < 0.02) | (cash_flow < 0.08)))
        | (streak >= 2)
    )
    labels = proxy.fillna(False).astype(int)
    for column in ("is_bankrupt", "is_distressed"):
        if column in df:
            observed = df[column].notna()
            if not df.loc[observed, column].isin([0, 1]).all():
                raise ModelPipelineError(f"{column} must contain binary labels or missing values")
            labels.loc[observed] = df.loc[observed, column].astype(int)
    return labels.rename("is_distressed")


def build_next_period_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Shift within company/form groups and invalidate gaps or ambiguous fiscal periods."""
    identity = "company_id" if "company_id" in df else "cik"
    required = {identity, "form_type", "fiscal_year", "period_end_date", *FORECAST_TARGET_COLUMNS}
    if df.empty or not required.issubset(df.columns):
        raise ModelPipelineError(f"Panel is empty or missing columns: {sorted(required - set(df))}")
    result = df.copy(deep=True)
    result["period_end_date"] = pd.to_datetime(result["period_end_date"], errors="raise")
    if result[[identity, "form_type", "fiscal_year", "period_end_date"]].isna().any().any():
        raise ModelPipelineError("Panel keys must be non-null")
    if not result["form_type"].isin(["10-K", "10-Q"]).all():
        raise ModelPipelineError("Panel supports only 10-K and 10-Q forms")
    if result.duplicated([identity, "form_type", "fiscal_year", "period_end_date"]).any():
        raise ModelPipelineError(
            "Duplicate company/form/period rows make target alignment ambiguous"
        )
    if ((pd.to_numeric(result["fiscal_year"], errors="coerce") % 1) != 0).any():
        raise ModelPipelineError("fiscal_year must be an integer")
    result["is_distressed"] = derive_distress_label(result)
    result = result.sort_values([identity, "form_type", "fiscal_year", "period_end_date"])
    groups = result.groupby([identity, "form_type"], sort=False)
    for column in (*FORECAST_TARGET_COLUMNS, "is_distressed", "fiscal_year"):
        result[f"next_{column}"] = groups[column].shift(-1)
    next_end = groups["period_end_date"].shift(-1)
    result["next_period_end_date"] = next_end
    if "filed_date" in result:
        result["filed_date"] = pd.to_datetime(result["filed_date"])
        result["next_filed_date"] = pd.to_datetime(groups["filed_date"].shift(-1))
    annual = result["form_type"].eq("10-K")
    valid = annual & result["next_fiscal_year"].eq(result["fiscal_year"] + 1)
    if (~annual).any():
        if "fiscal_period" not in result:
            raise ModelPipelineError("Quarterly panels require fiscal_period Q1..Q4")
        quarter = result["fiscal_period"].map({"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4})
        if quarter.loc[~annual].isna().any():
            raise ModelPipelineError("Quarterly periods must be Q1..Q4")
        ordinal = result["fiscal_year"] * 4 + quarter
        next_ordinal = ordinal.groupby([result[identity], result["form_type"]]).shift(-1)
        valid |= ~annual & next_ordinal.eq(ordinal + 1)
    valid &= (next_end - result["period_end_date"]).dt.days.between(1, 400)
    if "next_filed_date" in result:
        valid &= result["next_filed_date"] > result["filed_date"]
    for column in (*FORECAST_TARGET_COLUMNS, "is_distressed", "fiscal_year"):
        result.loc[~valid, f"next_{column}"] = np.nan
    result.loc[~valid, "next_period_end_date"] = pd.NaT
    return result


def training_horizon_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Purge shifted targets beyond the maximum feature-year boundary of a training split."""
    if "next_fiscal_year" in df and "fiscal_year" in df:
        boundary = df.attrs.get("train_end_year", df["fiscal_year"].max())
        mask = df["next_fiscal_year"] <= boundary
        if "next_filed_date" in df:
            mask &= pd.to_datetime(df["next_filed_date"]) <= pd.Timestamp(int(boundary), 12, 31)
            if "filed_date" in df:
                mask &= pd.to_datetime(df["next_filed_date"]) > pd.to_datetime(df["filed_date"])
        result = df.loc[mask].copy()
        result.attrs["train_end_year"] = boundary
        return result
    return df.copy()


class TemporalSplitter:
    """Partition current feature years; target-horizon purging is a separate required step."""

    def split(
        self, df: pd.DataFrame, train_end_year: int, val_end_year: int | None = None
    ) -> dict[str, pd.DataFrame]:
        """Return independent train/optional validation/test frames with strict time separation."""
        if df.empty or "fiscal_year" not in df or df["fiscal_year"].isna().any():
            raise ModelPipelineError("Temporal split requires nonempty, non-null fiscal_year data")
        if val_end_year is not None and val_end_year <= train_end_year:
            raise ModelPipelineError("val_end_year must be later than train_end_year")
        result = {"train": df.loc[df["fiscal_year"] <= train_end_year].copy()}
        boundary = train_end_year if val_end_year is None else val_end_year
        if val_end_year is not None:
            result["val"] = df.loc[
                df["fiscal_year"].between(train_end_year + 1, val_end_year)
            ].copy()
        result["test"] = df.loc[df["fiscal_year"] > boundary].copy()
        if result["train"].empty or result["test"].empty:
            raise ModelPipelineError("Temporal split must contain nonempty train and test sets")
        if result["train"]["fiscal_year"].max() >= result["test"]["fiscal_year"].min():
            raise ModelPipelineError("Training and test years overlap")
        return result


def prepare_validation_test(
    validation: pd.DataFrame, test: pd.DataFrame, validation_end_year: int
) -> tuple[pd.DataFrame, pd.DataFrame, str | None]:
    """Calibrate on observable annual targets, embargoing test origins before their publication.

    Annual t+1 labels are admitted through December of validation year +2.
    This excludes excessively late comparative observations. The latest admitted
    label publication is the calibration timestamp; test feature filings before
    that timestamp cannot be scored with the selected threshold.
    """
    observed = validation.dropna(subset=["next_is_distressed"]).copy()
    held_out = test.copy()
    if "next_filed_date" not in observed or "filed_date" not in held_out:
        return observed, held_out, None
    dates = pd.to_datetime(observed["next_filed_date"])
    observed = observed.loc[dates <= pd.Timestamp(validation_end_year + 2, 12, 31)]
    if observed.empty:
        raise ModelPipelineError(
            "Validation has no labels observable within its publication window"
        )
    calibration = pd.to_datetime(observed["next_filed_date"]).max()
    held_out = held_out.loc[pd.to_datetime(held_out["filed_date"]) >= calibration].copy()
    return observed, held_out, calibration.isoformat()
