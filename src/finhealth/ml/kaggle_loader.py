"""Leakage-free loader and scale-free ratio normalizer for Kaggle US Company Bankruptcy data."""

from pathlib import Path

import numpy as np
import pandas as pd

from finhealth.core.exceptions import ModelPipelineError
from finhealth.etl.financial_ratios import ALTMAN_MANUFACTURING_CUTOFF
from finhealth.ml.feature_contracts import (
    CORE_BANKRUPTCY_FEATURES,
    MULTI_PERIOD_FEATURES,
    assert_scale_free_features,
)

EPSILON = 1e-9
EQUITY_RATIO_FLOOR = 0.05

REQUIRED_KAGGLE_COLUMNS: tuple[str, ...] = (
    "company_name",
    "status_label",
    "year",
    "X1",
    "X6",
    "X10",
    "X12",
    "X14",
    "X15",
    "X16",
    "X17",
)

# Mapping of Kaggle US Bankruptcy raw columns (X1-X18, excluding X8 market value from ML).
KAGGLE_ACCOUNTING_COLUMNS: dict[str, str] = {
    "X1": "current_assets",
    "X2": "cost_of_goods_sold",
    "X3": "depreciation_amortization",
    "X4": "ebitda",
    "X5": "inventory",
    "X6": "net_income",
    "X7": "accounts_receivable",
    "X10": "total_assets",
    "X11": "long_term_debt",
    "X12": "operating_income",
    "X13": "gross_profit",
    "X14": "current_liabilities",
    "X15": "retained_earnings",
    "X16": "revenues",
    "X17": "total_liabilities",
    "X18": "operating_expenses",
}


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Compute numerator / denominator, returning NaN where denominator <= EPSILON."""
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    valid = num.notna() & den.notna() & np.isfinite(num) & np.isfinite(den) & (den > EPSILON)
    result = pd.Series(np.nan, index=num.index, dtype="float64")
    result.loc[valid] = num.loc[valid] / den.loc[valid]
    return result


def _optional_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a float64 numeric Series for an optional column, or all-NaN if absent."""
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan)


def compute_scale_free_features_from_statements(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all 19 core scale-free ratios and 5 YoY deltas from raw statement columns.

    All outputs are strictly dimensionless (currency-invariant). Monetary raw columns,
    share counts, EPS, and market capitalization (X8) are excluded from the feature set.
    """
    assert_scale_free_features(CORE_BANKRUPTCY_FEATURES)
    assert_scale_free_features(MULTI_PERIOD_FEATURES)

    out = df.copy()
    total_assets = _optional_numeric(out, "total_assets")
    current_assets = _optional_numeric(out, "current_assets")
    total_liabilities = _optional_numeric(out, "total_liabilities")
    current_liabilities = _optional_numeric(out, "current_liabilities")
    retained_earnings = _optional_numeric(out, "retained_earnings")
    revenues = _optional_numeric(out, "revenues")
    ebit = _optional_numeric(out, "operating_income")
    net_income = _optional_numeric(out, "net_income")
    depreciation = _optional_numeric(out, "depreciation_amortization")
    ebitda = _optional_numeric(out, "ebitda")
    inventory = _optional_numeric(out, "inventory")
    accounts_receivable = _optional_numeric(out, "accounts_receivable")
    long_term_debt = _optional_numeric(out, "long_term_debt")
    gross_profit = _optional_numeric(out, "gross_profit")
    operating_expenses = _optional_numeric(out, "operating_expenses")
    cogs = _optional_numeric(out, "cost_of_goods_sold")

    if gross_profit.isna().all() and revenues.notna().any() and cogs.notna().any():
        gross_profit = revenues - cogs
    if ebitda.isna().all() and ebit.notna().any() and depreciation.notna().any():
        ebitda = ebit + depreciation

    if "stockholders_equity" in out.columns:
        book_equity = _optional_numeric(out, "stockholders_equity")
        fallback_equity = total_assets - total_liabilities
        book_equity = book_equity.where(book_equity.notna(), fallback_equity)
    else:
        book_equity = total_assets - total_liabilities
        out["stockholders_equity"] = book_equity

    # 19 dimensionless core bankruptcy features (CORE_BANKRUPTCY_FEATURES).
    out["roa"] = _safe_ratio(net_income, total_assets)
    out["ebit_to_assets"] = _safe_ratio(ebit, total_assets)
    out["ebitda_to_assets"] = _safe_ratio(ebitda, total_assets)
    out["gross_margin"] = _safe_ratio(gross_profit, revenues)
    out["operating_margin"] = _safe_ratio(ebit, revenues)
    out["opex_to_revenue"] = _safe_ratio(operating_expenses, revenues)
    out["asset_turnover"] = _safe_ratio(revenues, total_assets)
    out["current_ratio"] = _safe_ratio(current_assets, current_liabilities)
    out["quick_ratio"] = _safe_ratio(current_assets - inventory, current_liabilities)
    out["working_capital_ratio"] = _safe_ratio(current_assets - current_liabilities, total_assets)
    out["debt_ratio"] = _safe_ratio(total_liabilities, total_assets)
    out["short_term_debt_share"] = _safe_ratio(current_liabilities, total_liabilities)
    out["long_term_debt_to_assets"] = _safe_ratio(long_term_debt, total_assets)
    out["retained_earnings_ratio"] = _safe_ratio(retained_earnings, total_assets)
    out["equity_to_assets"] = _safe_ratio(book_equity, total_assets)
    out["is_negative_equity"] = pd.Series(
        np.where(book_equity.notna(), (book_equity <= 0.0).astype(float), np.nan),
        index=out.index,
        dtype="float64",
    )
    out["inventory_to_assets"] = _safe_ratio(inventory, total_assets)
    out["receivables_to_revenue"] = _safe_ratio(accounts_receivable, revenues)
    out["depreciation_to_assets"] = _safe_ratio(depreciation, total_assets)

    # 5 consecutive-year YoY delta features (YOY_DELTA_FEATURES).
    id_col = (
        "cik"
        if "cik" in out.columns
        else ("company_id" if "company_id" in out.columns else None)
    )
    if id_col is not None and "fiscal_year" in out.columns:
        grouped = out.groupby(id_col, sort=False)
        consecutive = grouped["fiscal_year"].diff().eq(1)
        prev_revenues = grouped["revenues"].shift(1) if "revenues" in out.columns else pd.Series(
            np.nan, index=out.index, dtype="float64"
        )
        out["roa_yoy_delta"] = grouped["roa"].diff().where(consecutive)
        out["gross_margin_yoy_delta"] = grouped["gross_margin"].diff().where(consecutive)
        out["debt_ratio_yoy_delta"] = grouped["debt_ratio"].diff().where(consecutive)
        out["working_capital_yoy_delta"] = grouped["working_capital_ratio"].diff().where(
            consecutive
        )
        out["revenue_growth_yoy"] = _safe_ratio(revenues - prev_revenues, prev_revenues).where(
            consecutive
        )
    else:
        for col in (
            "roa_yoy_delta",
            "gross_margin_yoy_delta",
            "debt_ratio_yoy_delta",
            "working_capital_yoy_delta",
            "revenue_growth_yoy",
        ):
            if col not in out.columns:
                out[col] = np.nan

    return out


def load_kaggle_bankruptcy_panel(csv_path: Path) -> pd.DataFrame:
    """Load Kaggle US Company Bankruptcy CSV with leakage-free 1-year-ahead bankruptcy labels.

    For every company with ``status_label == 'failed'``, ``next_is_bankrupt`` is set to ``1``
    exclusively on the company's final observed fiscal year (``year == max_year``). All earlier
    years of failed companies and all rows of ``alive`` companies receive ``next_is_bankrupt = 0``.
    """
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
    df["sic_code"] = "3999"
    df["data_source"] = "kaggle_us_bankruptcy"

    # Sort and deduplicate before computing YoY deltas and per-company max_year labels.
    df = (
        df.sort_values(["cik", "fiscal_year"], kind="mergesort")
        .drop_duplicates(subset=["cik", "fiscal_year"], keep="last")
        .reset_index(drop=True)
    )
    df["period_end_date"] = pd.to_datetime(df["fiscal_year"].astype(str) + "-12-31")

    for raw_col, canonical_col in KAGGLE_ACCOUNTING_COLUMNS.items():
        df[canonical_col] = _optional_numeric(df, raw_col)

    total_assets = df["total_assets"]
    total_liabilities = df["total_liabilities"]
    net_income = df["net_income"]
    book_equity = total_assets - total_liabilities
    df["stockholders_equity"] = book_equity
    df["operating_cash_flow"] = np.nan

    # Compute all 19 scale-free core features and 5 YoY delta features (no X8, no EPS).
    df = compute_scale_free_features_from_statements(df)

    # Legacy compatibility columns for clustering/forecasting/Altman baseline evaluation.
    equity_ok = (
        total_assets.notna()
        & book_equity.notna()
        & (total_assets > EPSILON)
        & (book_equity >= EQUITY_RATIO_FLOOR * total_assets)
    )
    safe_equity = book_equity.where(equity_ok)
    df["roe"] = _safe_ratio(net_income, safe_equity).clip(lower=-3.0, upper=3.0)
    df["eps"] = np.nan
    df["debt_to_equity"] = _safe_ratio(total_liabilities, safe_equity).clip(lower=0.0, upper=20.0)
    df["ocf_ratio"] = np.nan
    df["cash_ratio"] = np.nan
    df["interest_coverage"] = np.nan
    df["fcf_to_liabilities"] = np.nan

    # Altman Z baseline (retained only for benchmark comparison, never as an ML feature).
    market_value = _optional_numeric(df, "X8")
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

    grouped = df.groupby("cik", sort=False)
    consecutive = grouped["fiscal_year"].diff().eq(1)
    df["roe_yoy_delta"] = grouped["roe"].diff().where(consecutive)
    df["ocf_ratio_yoy_delta"] = np.nan
    df["negative_ocf_streak"] = 0

    # Leakage-free 1-year-ahead bankruptcy label: ONLY year == max_year for failed companies.
    status_lower = df["status_label"].astype(str).str.strip().str.lower()
    max_year_by_company = grouped["fiscal_year"].transform("max")
    df["next_is_bankrupt"] = (
        (status_lower == "failed") & (df["fiscal_year"] == max_year_by_company)
    ).astype(int)
    df["is_distressed"] = df["next_is_bankrupt"]
    return df
