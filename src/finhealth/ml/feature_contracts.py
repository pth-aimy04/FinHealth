"""Shared scale-free ML feature contracts for V1.0 bankruptcy scoring."""

from collections.abc import Iterable
from typing import Literal

ScoringMode = Literal["single_period", "multi_period"]
RiskTier = Literal["STRONG", "STABLE", "WATCH", "CRITICAL"]
ConfidenceLevel = Literal["HIGH", "MODERATE", "LOW"]

CORE_BANKRUPTCY_FEATURES: tuple[str, ...] = (
    "roa",
    "ebit_to_assets",
    "ebitda_to_assets",
    "gross_margin",
    "operating_margin",
    "opex_to_revenue",
    "asset_turnover",
    "current_ratio",
    "quick_ratio",
    "working_capital_ratio",
    "debt_ratio",
    "short_term_debt_share",
    "long_term_debt_to_assets",
    "retained_earnings_ratio",
    "equity_to_assets",
    "is_negative_equity",
    "inventory_to_assets",
    "receivables_to_revenue",
    "depreciation_to_assets",
)

YOY_DELTA_FEATURES: tuple[str, ...] = (
    "roa_yoy_delta",
    "gross_margin_yoy_delta",
    "debt_ratio_yoy_delta",
    "working_capital_yoy_delta",
    "revenue_growth_yoy",
)

MULTI_PERIOD_FEATURES: tuple[str, ...] = CORE_BANKRUPTCY_FEATURES + YOY_DELTA_FEATURES
ALLOWED_SCALE_FREE_FEATURES: frozenset[str] = frozenset(MULTI_PERIOD_FEATURES)

FORBIDDEN_SCALE_DEPENDENT_FEATURES: frozenset[str] = frozenset(
    {
        "eps",
        "eps_basic",
        "eps_diluted",
        "market_value_equity",
        "total_assets",
        "current_assets",
        "total_liabilities",
        "current_liabilities",
        "stockholders_equity",
        "retained_earnings",
        "revenues",
        "cost_of_goods_sold",
        "gross_profit",
        "operating_expenses",
        "operating_income",
        "depreciation_amortization",
        "ebitda",
        "interest_expense",
        "net_income",
        "operating_cash_flow",
        "cash_and_equivalents",
        "accounts_receivable",
        "inventory",
        "accounts_payable",
        "long_term_debt",
        "short_term_debt",
        "capex",
        *(f"x{idx}" for idx in range(1, 19)),
    }
)


def get_feature_columns(mode: ScoringMode) -> tuple[str, ...]:
    """Return the immutable ordered feature contract for the requested scoring mode."""
    if mode == "single_period":
        return CORE_BANKRUPTCY_FEATURES
    if mode == "multi_period":
        return MULTI_PERIOD_FEATURES
    raise ValueError(f"Unsupported scoring mode: {mode}")


def assert_scale_free_features(columns: Iterable[str]) -> None:
    """Reject currency- or share-scale-dependent features from general bankruptcy models."""
    col_list = list(columns)
    forbidden = sorted(
        col for col in col_list if col.strip().lower() in FORBIDDEN_SCALE_DEPENDENT_FEATURES
    )
    if forbidden:
        raise ValueError(
            "Scale-dependent features are forbidden in the general bankruptcy engine: "
            + ", ".join(forbidden)
        )
    unknown = sorted(set(col_list) - ALLOWED_SCALE_FREE_FEATURES)
    if unknown:
        raise ValueError(
            "Unverified features outside the scale-free bankruptcy contract: "
            + ", ".join(unknown)
        )
