"""Finite financial ratios and the explicitly specified book-equity Altman variants."""

import math
from collections.abc import Mapping
from typing import Any

from finhealth.core.constants import US_GAAP_TAG_FALLBACKS

CREDIT_RATIO_COLUMNS = ("cash_ratio", "interest_coverage", "fcf_to_liabilities")
ALTMAN_MANUFACTURING_CUTOFF = 1.81
ALTMAN_NON_MANUFACTURING_CUTOFF = 1.10

def _finite(value: Any) -> float | None:
    """Treat missing and nonfinite numeric inputs as missing rather than usable facts."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _safe_div(
    num: float | None, den: float | None, require_positive_den: bool = False
) -> float | None:
    """Divide finite values, rejecting missing, near-zero, and prohibited denominators."""
    numerator, denominator = _finite(num), _finite(den)
    if numerator is None or denominator is None or abs(denominator) < 1e-9:
        return None
    if require_positive_den and denominator <= 0:
        return None
    result = numerator / denominator
    return result if math.isfinite(result) else None


def compute_altman_z_score(
    stmt: Mapping[str, Any], is_manufacturing: bool = True
) -> dict[str, Any]:
    """Compute the requested Z/Z'' formulas using BOOK equity, not market capitalization.

    This manufacturing formula is the requested book-equity proxy, not an exact
    implementation of the original publicly traded manufacturer model's market X4.
    """
    current_assets, current_liabilities = (
        _finite(stmt.get("current_assets")),
        _finite(stmt.get("current_liabilities")),
    )
    working_capital = (
        current_assets - current_liabilities
        if current_assets is not None and current_liabilities is not None
        else None
    )
    assets = stmt.get("total_assets")
    components = [
        _safe_div(working_capital, assets, True),
        _safe_div(stmt.get("retained_earnings"), assets, True),
        _safe_div(stmt.get("operating_income"), assets, True),
        _safe_div(stmt.get("stockholders_equity"), stmt.get("total_liabilities"), True),
    ]
    weights = [6.56, 3.26, 6.72, 1.05]
    low, high = ALTMAN_NON_MANUFACTURING_CUTOFF, 2.60
    if is_manufacturing:
        components.append(_safe_div(stmt.get("revenues"), assets, True))
        weights = [1.2, 1.4, 3.3, 0.6, 1.0]
        low, high = ALTMAN_MANUFACTURING_CUTOFF, 2.99
    if any(component is None for component in components):
        return {"altman_z_score": None, "altman_zone": None}
    score = sum(
        weight * component
        for weight, component in zip(weights, components, strict=True)
        if component is not None
    )
    if not math.isfinite(score):
        return {"altman_z_score": None, "altman_zone": None}
    zone = "SAFE" if score > high else "GREY" if score >= low else "DISTRESS"
    return {"altman_z_score": score, "altman_zone": zone}


def compute_equity_guards(
    total_assets: float | None, stockholders_equity: float | None
) -> dict[str, float | bool | None]:
    """Expose explicit insolvency flags instead of letting missing ratios hide negative equity."""
    assets = _finite(total_assets)
    equity = _finite(stockholders_equity)
    equity_to_assets = _safe_div(equity, assets, require_positive_den=True)
    return {
        "equity_to_assets": equity_to_assets,
        "is_negative_equity": bool(equity is not None and equity <= 0.0),
        "is_thin_equity": bool(
            equity_to_assets is not None and 0.0 < equity_to_assets < 0.05
        ),
    }


def compute_statement_ratios(
    stmt: Mapping[str, Any], is_manufacturing: bool = True
) -> dict[str, Any]:
    """Compute ratios with positive denominator policies and no implicit imputation."""
    assets, liabilities = stmt.get("total_assets"), stmt.get("total_liabilities")
    equity, revenue = stmt.get("stockholders_equity"), stmt.get("revenues")
    current_assets = _finite(stmt.get("current_assets"))
    current_liabilities = _finite(stmt.get("current_liabilities"))
    working_capital = (
        current_assets - current_liabilities
        if current_assets is not None and current_liabilities is not None
        else None
    )
    diluted = _finite(stmt.get("eps_diluted"))
    meaningful_equity = _finite(equity)
    finite_assets = _finite(assets)
    if (
        meaningful_equity is not None
        and finite_assets is not None
        and finite_assets > 0
        and meaningful_equity / finite_assets < 0.05
    ):
        meaningful_equity = None
    roe = _safe_div(stmt.get("net_income"), meaningful_equity, True)
    leverage = _safe_div(liabilities, meaningful_equity, True)
    cash = stmt.get("cash_and_equivalents")
    cash_source = (stmt.get("field_provenance") or {}).get("cash_and_equivalents", {})
    # Retain the reported inclusive balance, but exclude restricted cash from liquidity.
    if cash_source.get("tag") == US_GAAP_TAG_FALLBACKS["cash_and_equivalents"][1]:
        cash = None
    interest = _safe_div(stmt.get("operating_income"), stmt.get("interest_expense"), True)
    ocf, capex = _finite(stmt.get("operating_cash_flow")), _finite(stmt.get("capex"))
    fcf = ocf - capex if ocf is not None and capex is not None and capex >= 0 else None

    finite_revenue = _finite(revenue)
    cogs = _finite(stmt.get("cost_of_goods_sold"))
    gross_profit = _finite(stmt.get("gross_profit"))
    if gross_profit is None and finite_revenue is not None and cogs is not None:
        gross_profit = finite_revenue - cogs

    operating_income = _finite(stmt.get("operating_income"))
    depreciation = _finite(stmt.get("depreciation_amortization"))
    ebitda = _finite(stmt.get("ebitda"))
    if ebitda is None and operating_income is not None and depreciation is not None:
        ebitda = operating_income + depreciation

    inventory = _finite(stmt.get("inventory"))
    receivables = _finite(stmt.get("accounts_receivable"))
    quick_assets = (
        current_assets - inventory
        if current_assets is not None and inventory is not None
        else None
    )
    receivables_to_revenue = _safe_div(receivables, finite_revenue, True)
    inventory_to_cogs = _safe_div(inventory, cogs, True)
    dso = receivables_to_revenue * 365.0 if receivables_to_revenue is not None else None
    dio = inventory_to_cogs * 365.0 if inventory_to_cogs is not None else None

    short_term_debt = _finite(stmt.get("short_term_debt"))
    long_term_debt = _finite(stmt.get("long_term_debt"))
    short_term_debt_share = _safe_div(short_term_debt, liabilities, True)
    if short_term_debt_share is None and short_term_debt is None:
        short_term_debt_share = _safe_div(current_liabilities, liabilities, True)

    equity_guards = compute_equity_guards(finite_assets, _finite(equity))

    return {
        "roa": _safe_div(stmt.get("net_income"), assets, True),
        "roe": min(3.0, max(-3.0, roe)) if roe is not None else None,
        "eps": diluted if diluted is not None else _finite(stmt.get("eps_basic")),
        "debt_ratio": _safe_div(liabilities, assets, True),
        "debt_to_equity": min(20.0, max(0.0, leverage)) if leverage is not None else None,
        "current_ratio": _safe_div(current_assets, current_liabilities, True),
        "quick_ratio": _safe_div(quick_assets, current_liabilities, True),
        "gross_margin": _safe_div(gross_profit, finite_revenue, True),
        "operating_margin": _safe_div(operating_income, finite_revenue, True),
        "ebitda_margin": _safe_div(ebitda, finite_revenue, True),
        "ebitda_to_assets": _safe_div(ebitda, assets, True),
        "opex_to_revenue": _safe_div(stmt.get("operating_expenses"), finite_revenue, True),
        "ocf_ratio": _safe_div(stmt.get("operating_cash_flow"), liabilities, True),
        "cash_ratio": _safe_div(cash, current_liabilities, True),
        "interest_coverage": min(50.0, max(-20.0, interest)) if interest is not None else None,
        "fcf_to_liabilities": _safe_div(fcf, liabilities, True),
        "working_capital_ratio": _safe_div(working_capital, assets, True),
        "retained_earnings_ratio": _safe_div(stmt.get("retained_earnings"), assets, True),
        "ebit_to_assets": _safe_div(operating_income, assets, True),
        "asset_turnover": _safe_div(finite_revenue, assets, True),
        "short_term_debt_share": short_term_debt_share,
        "long_term_debt_to_assets": _safe_div(long_term_debt, assets, True),
        "inventory_to_assets": _safe_div(inventory, assets, True),
        "receivables_to_revenue": receivables_to_revenue,
        "depreciation_to_assets": _safe_div(depreciation, assets, True),
        "dso": dso,
        "dio": dio,
        **equity_guards,
        **compute_altman_z_score(stmt, is_manufacturing),
    }
