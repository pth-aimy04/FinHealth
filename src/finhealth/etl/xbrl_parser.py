"""Deterministic latest-filing XBRL normalization with per-fact provenance."""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from finhealth.core.constants import SUPPORTED_FORMS, US_GAAP_TAG_FALLBACKS
from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.repositories import normalize_cik

FLOW_FIELDS = frozenset(
    {
        "revenues",
        "net_income",
        "operating_income",
        "operating_cash_flow",
        "eps_basic",
        "eps_diluted",
    }
)
CREDIT_FLOW_FIELDS = frozenset({"interest_expense", "capex"})
CREDIT_FIELDS = CREDIT_FLOW_FIELDS | {"cash_and_equivalents"}
CONSOLIDATED_EQUITY = "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"
MINORITY_INTEREST = "MinorityInterest"
TEMPORARY_EQUITY_TAGS = (
    "TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests",
    "TemporaryEquityCarryingAmountAttributableToParent",
    "RedeemableNoncontrollingInterestEquityCarryingAmount",
)
BALANCE_SCOPE_TAGS = (CONSOLIDATED_EQUITY, MINORITY_INTEREST, *TEMPORARY_EQUITY_TAGS)


class NormalizedStatementRecord(BaseModel):
    """One statement period with nullable accounting values and auditable fact sources."""

    cik: str
    accession_number: str
    form_type: str
    fiscal_year: int
    fiscal_period: str
    period_end_date: date
    filed_date: date
    total_assets: float | None = None
    current_assets: float | None = None
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    stockholders_equity: float | None = None
    retained_earnings: float | None = None
    revenues: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    operating_cash_flow: float | None = None
    eps_basic: float | None = None
    eps_diluted: float | None = None
    cash_and_equivalents: float | None = None
    interest_expense: float | None = None
    capex: float | None = None
    field_provenance: dict[str, dict[str, Any]] = Field(default_factory=dict)


@dataclass(frozen=True)
class _Fact:
    """A validated scalar observation with selection rank and original context."""

    value: float
    tag: str
    unit: str
    priority: int
    duration_rank: int
    end: date
    start: date | None
    filed: date
    accession: str
    fiscal_year: int

    def rank(self) -> tuple[int, int, date, str, date, float]:
        """Prefer tag priority, quarterly duration, then latest filing/accession."""
        return (
            -self.priority,
            -self.duration_rank,
            self.filed,
            self.accession,
            self.start or date.min,
            self.value,
        )

    def provenance(self) -> dict[str, Any]:
        """Serialize source metadata without losing currency, duration, or publication date."""
        return {
            "tag": self.tag,
            "unit": self.unit,
            "currency": "USD",
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat(),
            "filed": self.filed.isoformat(),
            "accn": self.accession,
            "filing_context_fiscal_year": self.fiscal_year,
            "duration_basis": "YTD" if self.duration_rank == 1 else "period",
        }


def _balance_fallback(
    fields: dict[str, _Fact], scope: dict[str, _Fact], anchor: _Fact
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    """Derive missing balance facts only with period- and filing-aligned equity scope."""
    values = {field: fact.value for field, fact in fields.items()}
    sources = {field: fact.provenance() for field, fact in fields.items()}
    assets = values.get("total_assets")
    if assets is None or ("total_liabilities" in values) == ("stockholders_equity" in values):
        return values, sources
    missing = "total_liabilities" if "total_liabilities" not in values else "stockholders_equity"
    other = "stockholders_equity" if missing == "total_liabilities" else "total_liabilities"
    if any(
        (fields[name].accession, fields[name].filed) != (anchor.accession, anchor.filed)
        for name in ("total_assets", other)
    ):
        return values, sources
    if any(scope[tag].value != 0 for tag in TEMPORARY_EQUITY_TAGS if tag in scope):
        return values, sources
    minority = scope.get(MINORITY_INTEREST)
    consolidated = scope.get(CONSOLIDATED_EQUITY)
    adjustment: dict[str, Any] = {}
    if missing == "total_liabilities" and consolidated is not None:
        values[missing] = assets - consolidated.value
        adjustment = {"input": consolidated.provenance(), "value": consolidated.value}
        identity = "total_assets - consolidated_equity"
    elif minority is not None:
        values[missing] = assets - values[other] - minority.value
        adjustment = {"input": minority.provenance(), "value": minority.value}
        identity = f"total_assets - {other} - minority_interest"
    elif consolidated is None:
        values[missing] = assets - values[other]
        identity = f"total_assets - {other}"
        adjustment = {"assumption": "no noncontrolling interests"}
    else:
        return values, sources
    sources[missing] = {"derived": identity, **adjustment}
    return values, sources


def _candidate(field: str, tag: str, priority: int, row: dict[str, Any]) -> _Fact | None:
    """Validate a supported fact and discard subperiods or unusable scalar values."""
    try:
        end = date.fromisoformat(row["end"])
        filed = date.fromisoformat(row["filed"])
        start = date.fromisoformat(row["start"]) if row.get("start") else None
        value = row.get("val")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        value = float(value)
        if not math.isfinite(value):
            return None
        duration_rank = 0
        if field in CREDIT_FLOW_FIELDS and start is None:
            return None
        if field == "cash_and_equivalents" and start is not None:
            return None
        if field in FLOW_FIELDS | CREDIT_FLOW_FIELDS and start is not None:
            days = (end - start).days
            if row["form"] == "10-K" and not 330 <= days <= 380:
                return None
            if row["form"] == "10-Q" and not 70 <= days <= 110:
                if field != "operating_cash_flow" or not 110 < days <= 380:
                    return None
                duration_rank = 1
        accession = row["accn"]
        if not isinstance(accession, str) or not accession:
            raise ValueError("Missing accession number")
        fiscal_year = row.get("fy", end.year)
        if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int):
            raise ValueError("Fiscal context year must be an integer")
        return _Fact(
            value,
            tag,
            "USD/shares" if field.startswith("eps_") else "USD",
            priority,
            duration_rank,
            end,
            start,
            filed,
            accession,
            fiscal_year,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise EtlProcessingError(f"Malformed supported XBRL observation for {tag}") from error


class SecXbrlParser:
    """Resolve comparative periods independently of the filing-context fy field."""

    def amendments(
        self, payload: dict[str, Any], report_dates: dict[str, date],
    ) -> list[NormalizedStatementRecord]:
        """Normalize only actual amendment accession facts at their declared report end."""
        records = []
        concepts = payload.get("facts", {}).get("us-gaap", {})
        supported = {tag for tags in US_GAAP_TAG_FALLBACKS.values() for tag in tags}
        supported.update(BALANCE_SCOPE_TAGS)
        for accession, end in report_dates.items():
            selected = {}
            for tag in supported & concepts.keys():
                units = {}
                for unit, facts in concepts[tag]["units"].items():
                    rows = [
                        {**row, "form": row["form"].removesuffix("/A")}
                        for row in facts
                        if row.get("form") in ("10-K/A", "10-Q/A")
                        and row.get("accn") == accession and row.get("end") == end.isoformat()
                    ]
                    if rows:
                        units[unit] = rows
                if units:
                    selected[tag] = {"units": units}
            if not selected:
                continue
            for record in self.parse({
                "cik": payload["cik"], "facts": {"us-gaap": selected},
            }, quarter_report_dates={accession: end}):
                facts = {key: {**value, "source_form": record.form_type + "/A"}
                         for key, value in record.field_provenance.items()
                         if value.get("accn") == accession}
                if not facts:
                    continue
                records.append(record.model_copy(update={
                    "field_provenance": facts,
                    **{key: None for key in US_GAAP_TAG_FALLBACKS if key not in facts},
                }))
        return records

    def parse(
        self, payload: dict[str, Any], *, exclude_ambiguous: bool = False,
        quarter_report_dates: dict[str, date] | None = None,
    ) -> list[NormalizedStatementRecord]:
        """Normalize USD facts into chronological latest-filing statement records."""
        try:
            cik = normalize_cik(payload["cik"])
            concepts = payload.get("facts", {}).get("us-gaap", {})
            if not isinstance(concepts, dict):
                raise ValueError("us-gaap must be an object")
            grouped: dict[tuple[str, str, date], dict[str, _Fact]] = defaultdict(dict)
            credit: dict[tuple[str, str, date, date, str, date | None], dict[str, _Fact]] = (
                defaultdict(dict)
            )
            balance_scope: dict[tuple[str, date, date, str], dict[str, _Fact]] = defaultdict(dict)
            for tag in BALANCE_SCOPE_TAGS:
                for row in concepts.get(tag, {}).get("units", {}).get("USD", []):
                    form = row.get("form")
                    if form in SUPPORTED_FORMS and not row.get("start"):
                        fact = _candidate(tag, tag, 0, row)
                        if (
                            fact and form == "10-Q" and quarter_report_dates is not None
                            and quarter_report_dates.get(fact.accession) != fact.end
                        ):
                            continue
                        if fact is not None:
                            balance_scope[form, fact.end, fact.filed, fact.accession][tag] = fact
            for field, tags in US_GAAP_TAG_FALLBACKS.items():
                unit = "USD/shares" if field.startswith("eps_") else "USD"
                for priority, tag in enumerate(tags):
                    rows = concepts.get(tag, {}).get("units", {}).get(unit, [])
                    if not isinstance(rows, list):
                        raise ValueError(f"{tag} unit observations must be an array")
                    for row in rows:
                        if not isinstance(row, dict):
                            raise ValueError(f"{tag} observation must be an object")
                        form = row.get("form")
                        if form not in SUPPORTED_FORMS:
                            continue
                        period = "FY" if form == "10-K" else row.get("fp")
                        if period not in ("FY", "Q1", "Q2", "Q3", "Q4") or (
                            form == "10-Q" and period == "FY"
                        ):
                            continue
                        fact = _candidate(field, tag, priority, row)
                        if fact is None:
                            continue
                        if (
                            form == "10-Q" and quarter_report_dates is not None
                            and quarter_report_dates.get(fact.accession) != fact.end
                        ):
                            continue
                        fields = (
                            credit[(form, period, fact.end, fact.filed, fact.accession, fact.start)]
                            if field in CREDIT_FIELDS
                            else grouped[(form, period, fact.end)]
                        )
                        if field not in fields or fact.rank() > fields[field].rank():
                            fields[field] = fact
            records: list[NormalizedStatementRecord] = []
            natural_keys: set[tuple[int, str, str]] = set()
            ambiguous_keys: set[tuple[int, str, str]] = set()
            for (form, period, end), fields in sorted(
                grouped.items(), key=lambda x: (x[0][2], x[0][0])
            ):
                anchor = max(fields.values(), key=lambda f: (f.filed, f.accession, f.tag))
                year = end.year
                if form == "10-Q" and quarter_report_dates is not None:
                    year = anchor.fiscal_year
                elif form == "10-Q" and period == "Q1" and end.month >= 10:
                    # Never reuse a later comparative filing's fy beyond the adjacent year.
                    year = anchor.fiscal_year if anchor.fiscal_year == end.year + 1 else end.year
                key = (year, period, form)
                if key in natural_keys:
                    if exclude_ambiguous:
                        ambiguous_keys.add(key)
                        continue
                    raise EtlProcessingError(
                        f"Ambiguous fiscal calendar produces duplicate key: {key}"
                    )
                natural_keys.add(key)
                context = (form, period, end, anchor.filed, anchor.accession)
                aligned_credit = dict(credit.get((*context, None), {}))
                flow_starts = {
                    fact.start
                    for field, fact in fields.items()
                    if field in FLOW_FIELDS
                    and fact.start is not None
                    and (fact.filed, fact.accession) == (anchor.filed, anchor.accession)
                    and fact.duration_rank == 0
                }
                if len(flow_starts) == 1:
                    aligned_credit.update(credit.get((*context, next(iter(flow_starts))), {}))
                values, sources = _balance_fallback(
                    {**fields, **aligned_credit},
                    balance_scope.get((form, end, anchor.filed, anchor.accession), {}),
                    anchor,
                )
                records.append(
                    NormalizedStatementRecord(
                        cik=cik,
                        accession_number=anchor.accession,
                        form_type=form,
                        fiscal_year=year,
                        fiscal_period=period,
                        period_end_date=end,
                        filed_date=anchor.filed,
                        field_provenance=sources,
                        **values,
                    )
                )
            return [
                row
                for row in records
                if (row.fiscal_year, row.fiscal_period, row.form_type) not in ambiguous_keys
            ]
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise EtlProcessingError("Invalid SEC companyfacts structure") from error
