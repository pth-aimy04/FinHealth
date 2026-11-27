"""Check credit fact comparability, ratio edge cases and industrial scope."""

from typing import Any

import pytest

from finhealth.core.exceptions import EtlProcessingError
from finhealth.etl.annual import as_reported_annual_payload
from finhealth.etl.financial_ratios import compute_statement_ratios
from finhealth.etl.pipeline import FinancialEtlPipeline
from finhealth.ingestion.schemas import is_financial_institution_sic


@pytest.mark.parametrize(
    ("sic", "excluded"),
    [
        ("5999", False),
        ("6000", True),
        (6799, True),
        (6800, False),
        (None, False),
        ("6e3", False),
    ],
)
def test_industrial_scope(sic: str | int | None, excluded: bool) -> None:
    """Recognize the inclusive SIC range and reject non-industrial ETL."""
    assert is_financial_institution_sic(sic) is excluded
    if excluded:
        with pytest.raises(EtlProcessingError, match="specialized regulatory capital"):
            FinancialEtlPipeline().process_company_facts_payload(
                "320193", {"cik": 320193}, str(sic)
            )
    with pytest.raises(EtlProcessingError, match="PARA ticker"):
        FinancialEtlPipeline().process_company_facts_payload("1826011", {"cik": 1826011}, "7372")


def test_credit_facts_preserve_accession_duration_and_restricted_cash_scope() -> None:
    """Use matching annual flows while excluding later restatements and restricted cash."""
    flow = {
        "form": "10-K",
        "accn": "original",
        "end": "2022-12-31",
        "filed": "2023-02-20",
        "start": "2022-01-01",
        "fy": 2022,
    }
    balance = {key: value for key, value in flow.items() if key != "start"}
    payload: dict[str, Any] = {
        "cik": 320193,
        "facts": {
            "us-gaap": {
                tag: {"units": {"USD": observations}}
                for tag, observations in {
                    "Liabilities": [balance | {"val": 80}],
                    "LiabilitiesCurrent": [balance | {"val": 20}],
                    "OperatingIncomeLoss": [flow | {"val": 25}],
                    "NetCashProvidedByUsedInOperatingActivities": [flow | {"val": 40}],
                    "InterestExpense": [
                        flow | {"start": "2022-02-01", "val": 1},
                        flow | {"accn": "later", "filed": "2024-02-20", "val": 2},
                    ],
                    "InterestAndDebtExpense": [flow | {"val": 5}],
                    "PaymentsToAcquirePropertyPlantAndEquipment": [flow | {"val": 15}],
                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": [
                        balance | {"val": 12},
                    ],
                }.items()
            }
        },
    }
    (row,) = FinancialEtlPipeline().process_company_facts_payload(
        "320193", as_reported_annual_payload(payload), "3571"
    )
    assert row["cash_and_equivalents"] == 12 and row["cash_ratio"] is None
    assert row["interest_coverage"] == 5
    assert row["fcf_to_liabilities"] == 25 / 80
    assert row["field_provenance"]["interest_expense"]["tag"] == "InterestAndDebtExpense"
    assert row["field_provenance"]["interest_expense"]["accn"] == "original"


def test_credit_ratios_keep_missing_and_limit_finite_interest_coverage() -> None:
    """Exercise numerator/denominator signs, missing capex and both coverage bounds."""
    row = {
        "current_liabilities": 20,
        "total_liabilities": 80,
        "cash_and_equivalents": 12,
        "operating_cash_flow": 40,
        "operating_income": 100,
        "interest_expense": 1,
        "capex": 45,
    }
    ratios = compute_statement_ratios(row)
    assert ratios["cash_ratio"] == 0.6
    assert ratios["interest_coverage"] == 50
    assert ratios["fcf_to_liabilities"] == -5 / 80
    assert compute_statement_ratios(row | {"operating_income": -100})["interest_coverage"] == -20
    for denominator in (None, 0, -1):
        changed = compute_statement_ratios(
            row
            | {
                "interest_expense": denominator,
                "current_liabilities": denominator,
                "total_liabilities": denominator,
            }
        )
        assert all(
            changed[name] is None
            for name in ("cash_ratio", "interest_coverage", "fcf_to_liabilities")
        )
    for capex in (None, -1):
        assert compute_statement_ratios(row | {"capex": capex})["fcf_to_liabilities"] is None


def test_credit_fallbacks_nonoperating_interest_and_productive_assets_capex() -> None:
    """Verify official FASB fallbacks for industrial interest expense and CapEx with provenance."""
    flow = {
        "form": "10-K",
        "accn": "0000885639-26-000010",
        "end": "2026-01-31",
        "filed": "2026-03-19",
        "start": "2025-02-02",
        "fy": 2025,
    }
    balance = {key: value for key, value in flow.items() if key != "start"}
    payload: dict[str, Any] = {
        "cik": 885639,
        "facts": {
            "us-gaap": {
                tag: {"units": {"USD": observations}}
                for tag, observations in {
                    "Liabilities": [balance | {"val": 1000}],
                    "LiabilitiesCurrent": [balance | {"val": 250}],
                    "OperatingIncomeLoss": [flow | {"val": 624}],
                    "NetCashProvidedByUsedInOperatingActivities": [flow | {"val": 700}],
                    "InterestExpenseNonoperating": [flow | {"val": 156}],
                    "PaymentsToAcquireProductiveAssets": [flow | {"val": 372}],
                }.items()
            }
        },
    }
    (row,) = FinancialEtlPipeline().process_company_facts_payload(
        "885639", as_reported_annual_payload(payload), "5311"
    )
    assert row["interest_expense"] == 156
    assert row["capex"] == 372
    assert row["interest_coverage"] == pytest.approx(4.0)
    assert row["fcf_to_liabilities"] == pytest.approx((700 - 372) / 1000)
    assert row["field_provenance"]["interest_expense"]["tag"] == "InterestExpenseNonoperating"
    assert row["field_provenance"]["capex"]["tag"] == "PaymentsToAcquireProductiveAssets"
