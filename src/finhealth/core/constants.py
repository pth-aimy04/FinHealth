"""Canonical US-GAAP concept candidates, ordered by preference.

Names refer to the us-gaap namespace in the official FASB taxonomy:
https://xbrl.fasb.org/us-gaap/2025/elts/us-gaap-2025.xsd
Legacy revenue tags are retained for historical filings. Including assessed
tax changes the revenue basis: downstream ETL must preserve tag provenance
and enforce comparable periods, units, and accounting scope.
"""

RANDOM_SEED: int = 42
# This registrant reused PARA after the historical Paramount ticker ceased trading.
EXCLUDED_INDUSTRIAL_CIKS = frozenset({"0001826011"})

US_GAAP_TAG_FALLBACKS: dict[str, tuple[str, ...]] = {
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "stockholders_equity": ("StockholdersEquity",),
    "revenues": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss",),
    "operating_income": ("OperatingIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "retained_earnings": ("RetainedEarningsAccumulatedDeficit",),
    "eps_basic": ("EarningsPerShareBasic",),
    "eps_diluted": ("EarningsPerShareDiluted",),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "interest_expense": (
        "InterestExpense",
        "InterestAndDebtExpense",
        "InterestExpenseNonoperating",
        "InterestExpenseDebt",
    ),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
}

SUPPORTED_FORMS: tuple[str, ...] = ("10-K", "10-Q")
