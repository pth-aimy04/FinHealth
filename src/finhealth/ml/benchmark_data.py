"""Explicitly synthetic accounting-consistent benchmark corpus passed through the real XBRL ETL."""

from typing import Any

import numpy as np
import pandas as pd

from finhealth.core.constants import US_GAAP_TAG_FALLBACKS
from finhealth.etl.pipeline import FinancialEtlPipeline


def build_benchmark_panel(random_seed: int = 42, n_companies: int = 80) -> pd.DataFrame:
    """Generate 2016–2023 synthetic regimes with stochastic transitions, not real issuer claims.

    Outcomes are sampled from a nonlinear financial risk process, independent of
    Altman thresholds. Neither outcomes nor metrics are hardcoded or real issuer claims.
    """
    rng = np.random.default_rng(random_seed)
    rows: list[dict[str, Any]] = []
    for company in range(n_companies):
        cik = str(9000000000 + company)
        regime_weights = [0.48, 0.32, 0.12, 0.08]
        regime = int(rng.choice(4, p=regime_weights))
        assets = float(rng.uniform(100e6, 5e9))
        concepts: dict[str, Any] = {}
        outcomes: dict[int, int] = {}
        for year in range(2016, 2024):
            if rng.random() < 0.18:
                regime = int(rng.choice(4, p=regime_weights))
            assets *= float(rng.uniform(0.94, 1.12))
            debt_ratio = float(
                np.clip([0.25, 0.48, 0.72, 0.90][regime] + rng.normal(0, 0.035), 0.1, 0.94)
            )
            roa = [0.16, 0.07, 0.005, -0.13][regime] + rng.normal(0, 0.025)
            if year == 2020:
                roa -= 0.03
            liabilities = assets * debt_ratio
            current_liabilities = liabilities * float(rng.uniform(0.25, 0.5))
            current_ratio = max(0.2, [2.6, 1.6, 1.05, 0.65][regime] + rng.normal(0, 0.18))
            cyclical_stress = (1 if year == 2020 else 0) + float(rng.uniform(0, 0.3))
            roa -= 0.03 * debt_ratio**2 * cyclical_stress
            net_income = assets * roa
            eps = net_income / float(assets / rng.uniform(10, 80))
            values = {
                "total_assets": assets,
                "total_liabilities": liabilities,
                "stockholders_equity": assets - liabilities,
                "current_assets": current_liabilities * current_ratio,
                "current_liabilities": current_liabilities,
                "retained_earnings": assets
                * ([0.45, 0.22, 0.015, -0.25][regime] + rng.normal(0, 0.04)),
                "revenues": assets * max(0.15, [1.5, 1.1, 0.85, 0.6][regime] + rng.normal(0, 0.12)),
                "net_income": net_income,
                "operating_income": net_income + assets * 0.025,
                "operating_cash_flow": liabilities
                * ([0.4, 0.2, 0.025, -0.18][regime] + rng.normal(0, 0.04)),
                "eps_basic": eps * 1.01,
                "eps_diluted": eps,
            }
            cash_negative = values["operating_cash_flow"] < 0
            logit = (
                -3.0
                + 3.2 * debt_ratio**2
                + 1.3 * (roa < 0)
                + 0.7 * cash_negative
                + 0.8 * cash_negative * debt_ratio
                + 0.4 * cyclical_stress
            )
            outcomes[year] = int(rng.random() < 1 / (1 + np.exp(-logit)))
            for field, value in values.items():
                tag = US_GAAP_TAG_FALLBACKS[field][0]
                unit = "USD/shares" if field.startswith("eps_") else "USD"
                observation = {
                    "end": f"{year}-12-31",
                    "filed": f"{year + 1}-02-15",
                    "fy": year,
                    "fp": "FY",
                    "form": "10-K",
                    "accn": f"synthetic-{company:04d}-{year}",
                    "val": float(value),
                }
                if field in {
                    "revenues",
                    "net_income",
                    "operating_income",
                    "operating_cash_flow",
                    "eps_basic",
                    "eps_diluted",
                }:
                    observation["start"] = f"{year}-01-01"
                concepts.setdefault(tag, {"units": {unit: []}})["units"][unit].append(observation)
        payload = {
            "cik": cik,
            "entityName": f"Synthetic benchmark company {company:03d}",
            "facts": {"us-gaap": concepts},
        }
        sic = ("3571", "5411", "4213", "7372")[company % 4]
        records = FinancialEtlPipeline().process_company_facts_payload(cik, payload, sic)
        for row in records:
            row.update(
                company_id=f"benchmark:{company:03d}",
                data_source="synthetic_benchmark",
                company_name=payload["entityName"],
                sic_code=sic,
                is_distressed=outcomes[row["fiscal_year"]],
            )
        rows.extend(records)
    return pd.DataFrame(rows)
