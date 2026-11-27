"""Loader and accounting ratio normalizer for the Kaggle US Company Bankruptcy dataset."""

from pathlib import Path

import numpy as np
import pandas as pd

from finhealth.core.exceptions import ModelPipelineError
from finhealth.etl.financial_ratios import ALTMAN_MANUFACTURING_CUTOFF

EPSILON = 1e-9
EQUITY_RATIO_FLOOR = 0.05

REQUIRED_KAGGLE_COLUMNS: tuple[str, ...] = (
    "company_name",
    "status_label",
    "year",
    "X1",
    "X6",
    "X8",
    "X10",
    "X12",
    "X14",
    "X15",
    "X16",
    "X17",
)


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Compute numerator / denominator, returning NaN where denominator <= EPSILON."""
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    valid = num.notna() & den.notna() & np.isfinite(num) & np.isfinite(den) & (den > EPSILON)
    result = pd.Series(np.nan, index=num.index, dtype="float64")
    result.loc[valid] = num.loc[valid] / den.loc[valid]
    return result


def load_kaggle_bankruptcy_panel(csv_path: Path) -> pd.DataFrame:
    """Load Kaggle US Company Bankruptcy CSV and normalize it to the FinHealth panel schema."""
    if not csv_path.exists():
        raise ModelPipelineError(f"Kaggle bankruptcy dataset not found at {csv_path}")
    raw = pd.read_csv(csv_path)
    missing = [col for col in REQUIRED_KAGGLE_COLUMNS if col not in raw.columns]
    if missing:
        raise ModelPipelineError(f"Kaggle dataset missing required columns: {missing}")

    df = raw.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["company_name", "status_label", "year"]).copy()
    df["fiscal_year"] = df["year"].astype(int)
    df["cik"] = df["company_name"].astype(str)
    df["company_id"] = df["cik"]
    df["ticker"] = df["cik"]
    df["company_name"] = df["cik"]
    df["form_type"] = "10-K"
    df["sic_code"] = "3999"  # Use standard 1.81 manufacturing Altman cutoff with market value X8.
    df["data_source"] = "kaggle_us_bankruptcy"

    total_assets = pd.to_numeric(df["X10"], errors="coerce")
    current_assets = pd.to_numeric(df["X1"], errors="coerce")
    total_liabilities = pd.to_numeric(df["X17"], errors="coerce")
    current_liabilities = pd.to_numeric(df["X14"], errors="coerce")
    retained_earnings = pd.to_numeric(df["X15"], errors="coerce")
    revenues = pd.to_numeric(df["X16"], errors="coerce")
    ebit = pd.to_numeric(df["X12"], errors="coerce")
    net_income = pd.to_numeric(df["X6"], errors="coerce")
    market_value = pd.to_numeric(df["X8"], errors="coerce")
    book_equity = total_assets - total_liabilities

    equity_ok = (
        total_assets.notna()
        & book_equity.notna()
        & (total_assets > EPSILON)
        & (book_equity >= EQUITY_RATIO_FLOOR * total_assets)
    )
    safe_equity = book_equity.where(equity_ok)

    df["total_assets"] = total_assets
    df["total_liabilities"] = total_liabilities
    df["stockholders_equity"] = book_equity
    df["net_income"] = net_income
    df["revenues"] = revenues
    df["operating_income"] = ebit
    df["operating_cash_flow"] = np.nan

    df["roa"] = _safe_ratio(net_income, total_assets)
    df["roe"] = _safe_ratio(net_income, safe_equity).clip(lower=-3.0, upper=3.0)
    df["eps"] = np.nan
    df["debt_ratio"] = _safe_ratio(total_liabilities, total_assets)
    df["debt_to_equity"] = _safe_ratio(total_liabilities, safe_equity).clip(lower=0.0, upper=20.0)
    df["current_ratio"] = _safe_ratio(current_assets, current_liabilities)
    df["operating_margin"] = _safe_ratio(ebit, revenues)
    df["ocf_ratio"] = np.nan
    df["working_capital_ratio"] = _safe_ratio(current_assets - current_liabilities, total_assets)
    df["retained_earnings_ratio"] = _safe_ratio(retained_earnings, total_assets)
    df["ebit_to_assets"] = _safe_ratio(ebit, total_assets)
    df["asset_turnover"] = _safe_ratio(revenues, total_assets)
    df["cash_ratio"] = np.nan
    df["interest_coverage"] = np.nan
    df["fcf_to_liabilities"] = np.nan

    mv_to_liab = _safe_ratio(market_value, total_liabilities)
    altman_valid = (
        df["working_capital_ratio"].notna()
        & df["retained_earnings_ratio"].notna()
        & df["ebit_to_assets"].notna()
        & mv_to_liab.notna()
        & df["asset_turnover"].notna()
    )
    df["altman_z_score"] = np.where(
        altman_valid,
        1.2 * df["working_capital_ratio"]
        + 1.4 * df["retained_earnings_ratio"]
        + 3.3 * df["ebit_to_assets"]
        + 0.6 * mv_to_liab
        + 1.0 * df["asset_turnover"],
        np.nan,
    )
    df["altman_zone"] = pd.Series(
        np.where(
            df["altman_z_score"] < ALTMAN_MANUFACTURING_CUTOFF,
            "DISTRESS",
            np.where(df["altman_z_score"] <= 2.99, "GREY", "SAFE"),
        ),
        index=df.index,
        dtype=object,
    ).where(altman_valid, None)

    df = df.sort_values(["cik", "fiscal_year"], kind="mergesort").drop_duplicates(
        subset=["cik", "fiscal_year"], keep="last"
    ).reset_index(drop=True)
    df["period_end_date"] = pd.to_datetime(df["fiscal_year"].astype(str) + "-12-31")
    grouped = df.groupby("cik", sort=False)
    df["roa_yoy_delta"] = grouped["roa"].diff()
    df["roe_yoy_delta"] = grouped["roe"].diff()
    df["debt_ratio_yoy_delta"] = grouped["debt_ratio"].diff()
    df["ocf_ratio_yoy_delta"] = np.nan
    df["negative_ocf_streak"] = 0

    status_lower = df["status_label"].astype(str).str.strip().str.lower()
    df["is_distressed"] = (status_lower == "failed").astype(int)
    return df
