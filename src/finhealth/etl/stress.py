"""A static balance sheet and income statement sensitivity model."""

from collections.abc import Mapping
from typing import Any

from finhealth.core.exceptions import EtlProcessingError
from finhealth.etl.financial_ratios import _finite

SCENARIO_ASSUMPTIONS = (
    "The operating margin shock is additive. A 25% marginal tax rate applies to "
    "incremental operating earnings, with other income and interest costs held fixed.",
    "Financing changes scale reported total and current liabilities together. "
    "Retained earnings and book equity move by the after-tax earnings impact. "
    "Assets absorb the sum of both changes, preserving the original balance sheet residual.",
    "The OCF shock applies its percentage to the absolute reported OCF. "
    "The independent OCF shock changes cash flow without specifying a working capital "
    "or financing bridge. Observed cash, current assets and capex are held fixed. "
    "The balance sheet asset adjustment is assigned to noncurrent assets.",
    "Shares are held fixed. EPS uses shares implied by reported earnings and EPS "
    "when they are available and have matching signs.",
)


def stress_statement(
    statement: Mapping[str, Any],
    *,
    revenue_shock_pct: float,
    operating_margin_delta_pct: float,
    debt_change_pct: float,
    ocf_shock_pct: float,
) -> dict[str, Any]:
    """Return a hypothetical copy with consistent changes in assets and claims on assets."""
    result = dict(statement)
    revenue = _finite(statement.get("revenues"))
    operating = _finite(statement.get("operating_income"))
    earnings_delta = 0.0
    if revenue_shock_pct or operating_margin_delta_pct:
        if revenue is None or revenue <= 0 or operating is None:
            raise EtlProcessingError("Revenue and operating income are required for margin shocks")
        result["revenues"] = revenue * (1 + revenue_shock_pct)
        result["operating_income"] = (operating / revenue + operating_margin_delta_pct) * result[
            "revenues"
        ]
        earnings_delta = 0.75 * (result["operating_income"] - operating)
    if earnings_delta:
        net_income = _finite(statement.get("net_income"))
        for name in ("net_income", "stockholders_equity", "retained_earnings"):
            value = _finite(statement.get(name))
            result[name] = value + earnings_delta if value is not None else None
        for name in ("eps_basic", "eps_diluted"):
            eps = _finite(statement.get(name))
            result[name] = (
                eps * (1 + earnings_delta / net_income)
                if net_income and eps is not None and eps / net_income > 0
                else None
            )
    funding_delta = 0.0
    if debt_change_pct:
        liabilities = _finite(statement.get("total_liabilities"))
        if liabilities is None or liabilities < 0:
            raise EtlProcessingError("Nonnegative total liabilities are required for a debt shock")
        funding_delta = liabilities * debt_change_pct
        result["total_liabilities"] = liabilities + funding_delta
        current = _finite(statement.get("current_liabilities"))
        if current is not None:
            result["current_liabilities"] = current * (1 + debt_change_pct)
    if ocf_shock_pct:
        ocf = _finite(statement.get("operating_cash_flow"))
        if ocf is None:
            raise EtlProcessingError("Reported operating cash flow is required for an OCF shock")
        result["operating_cash_flow"] = ocf + abs(ocf) * ocf_shock_pct
    if earnings_delta or funding_delta:
        assets = _finite(statement.get("total_assets"))
        current_assets = _finite(statement.get("current_assets"))
        if assets is None:
            raise EtlProcessingError("Reported assets are required for this balance sheet shock")
        result["total_assets"] = assets + funding_delta + earnings_delta
        if result["total_assets"] <= 0 or (
            current_assets is not None and result["total_assets"] < current_assets
        ):
            raise EtlProcessingError(
                "Scenario exhausts noncurrent assets under the stated funding assumptions"
            )
    provenance = statement.get("field_provenance")
    if provenance:
        result["field_provenance"] = {
            name: source
            if result.get(name) == statement.get(name)
            else {"derived": "stress scenario", "baseline_source": source}
            for name, source in provenance.items()
        }
    return result
