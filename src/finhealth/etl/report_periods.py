"""Reporting-only period arithmetic with explicit missing-data reasons."""

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from finhealth.etl.financial_ratios import _finite, _safe_div

FLOWS = ("revenues", "operating_income", "net_income", "operating_cash_flow")


def _flow(record: dict[str, Any], name: str) -> tuple[float | None, dict[str, Any]]:
    """Read a normalized flow and its source context."""
    return _finite(record.get(name)), record.get("provenance", {}).get(name, {})


def _basis(source: dict[str, Any]) -> tuple[str | None, ...]:
    """Keep tag and accounting line changes out of period arithmetic."""
    return tuple(source.get(key) for key in ("unit", "currency", "tag", "form", "line"))


def _fourth_quarter(
    amount: float | None, source: dict[str, Any], field: str, index: int,
    by_period: dict[int, dict[str, Any]],
) -> tuple[float | None, list[dict[str, Any]]]:
    """Subtract Q1–Q3 from a compatible full-year fact with contiguous fiscal dates."""
    if amount is None or not source.get("unit") or source.get("duration_basis") != "period":
        return None, []
    quarters = [by_period.get(index - lag, {}).get("flows", {}).get(field, {}) for lag in (3, 2, 1)]
    comparable = [_comparable(by_period.get(index - lag, {}), field, source) for lag in (3, 2, 1)]
    if any(value is None for value in comparable):
        return None, []
    inputs = [quarter["sources"][0] for quarter in quarters]
    fiscal_start, fiscal_end = source.get("start"), source.get("end")
    if not fiscal_start or not fiscal_end or fiscal_start != inputs[0].get("start"):
        return None, []
    previous = date.fromisoformat(fiscal_start) - timedelta(days=1)
    for normalized, quarter in zip(quarters, inputs, strict=True):
        end = quarter.get("end")
        if not end or (quarter.get("filed") or "9999") >= (source.get("filed") or ""):
            return None, []
        closing = date.fromisoformat(end)
        if normalized.get("start") != (previous + timedelta(days=1)).isoformat():
            return None, []
        if not 70 <= (closing - previous).days <= 110:
            return None, []
        previous = closing
    if not 70 <= (date.fromisoformat(fiscal_end) - previous).days <= 110:
        return None, []
    result = _finite(amount - sum(value for value in comparable if value is not None))
    return result, [source, *inputs]


def _quarter_start(
    source: dict[str, Any], end: str, previous: dict[str, Any] | None,
) -> str | None:
    """Identify a quarter interval after deaccumulating its source flow."""
    start = source.get("start")
    if source.get("duration_basis") == "YTD" and previous:
        prior_end = previous.get("period_end")
        if prior_end:
            start = (date.fromisoformat(str(prior_end)) + timedelta(days=1)).isoformat()
    if not start or not 70 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 110:
        return None
    return str(start)


def _consecutive_window(observations: list[dict[str, Any]]) -> bool:
    """Reject four-quarter totals when actual intervals contain gaps or overlaps."""
    if any(row.get("value") is None or not row.get("start") for row in observations):
        return False
    return all(
        later["start"] == (date.fromisoformat(earlier["end"]) + timedelta(days=1)).isoformat()
        for earlier, later in zip(observations, observations[1:], strict=False)
    )


def quarterly_series(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return quarter-only flows, same-quarter growth, and four-quarter sums."""
    by_period: dict[int, dict[str, Any]] = {}
    raw: dict[int, dict[str, Any]] = {}
    explicit_q4 = {row["fiscal_year"] for row in records if row["fiscal_period"] == "Q4"}
    for record in sorted(records, key=lambda row: row["period_end"]):
        if record.get("values"):
            record = {**record, **record["values"]}
        quarter = record["fiscal_period"]
        year = record["fiscal_year"]
        annual = quarter == "FY" and year not in explicit_q4
        if annual:
            quarter = "Q4"
        if quarter not in ("Q1", "Q2", "Q3", "Q4"):
            continue
        index = year * 4 + int(quarter[1]) - 1
        if index in raw:
            raise ValueError("Ambiguous quarter in the selected reporting scope")
        raw[index] = record
        periods: dict[str, Any] = {}
        for field in FLOWS:
            amount, source = _flow(record, field)
            reason = None
            sources = [source] if source else []
            period_end = str(record["period_end"])
            quarter_start = _quarter_start(source, period_end, None)
            if annual:
                amount, sources = _fourth_quarter(amount, source, field, index, by_period)
                reason = "incomplete_fiscal_year" if amount is None else None
                quarter_start = _quarter_start(
                    {**source, "duration_basis": "YTD"}, period_end, by_period.get(index - 1),
                )
            elif amount is None:
                reason = "missing_source"
            elif source.get("duration_basis") == "YTD" and quarter != "Q1":
                prior, prior_source = _flow(raw.get(index - 1, {}), field)
                aligned = (
                    prior is not None
                    and prior_source.get("duration_basis") in (
                        ("period", "YTD") if quarter == "Q2" else ("YTD",)
                    )
                    and source.get("start") is not None
                    and source.get("start") == prior_source.get("start")
                    and source.get("unit") and _basis(source) == _basis(prior_source)
                    and bool(source.get("filed") and prior_source.get("filed"))
                    and source["filed"] > prior_source["filed"]
                    and source.get("end") == str(record["period_end"])
                    and prior_source.get("end") == str(raw[index - 1]["period_end"])
                )
                if aligned and prior is not None:
                    amount = _finite(amount - prior)
                    if amount is None:
                        reason = "nonfinite_result"
                    sources.append(prior_source)
                    quarter_start = _quarter_start(source, period_end, by_period.get(index - 1))
                    if quarter_start is None:
                        amount, reason = None, "incompatible_quarter_interval"
                else:
                    amount, reason = None, "incompatible_ytd"
            elif (source.get("duration_basis") not in ("period", "YTD") or not source.get("unit")
                  or source.get("end") != str(record["period_end"])):
                amount, reason = None, "missing_period_basis"
            elif source.get("start") and quarter_start is None:
                amount, reason = None, "incompatible_quarter_interval"
            unit = source.get("unit")
            older = _comparable(by_period.get(index - 4, {}), field, source)
            prior = _comparable(by_period.get(index - 1, {}), field, source)
            window = [
                _comparable(by_period.get(index - lag, {}), field, source)
                for lag in (3, 2, 1)
            ] + [amount]
            intervals = [
                by_period.get(index - lag, {}).get("flows", {}).get(field, {})
                for lag in (3, 2, 1)
            ] + [{"value": amount, "start": quarter_start, "end": period_end}]
            complete = all(value is not None for value in window) and _consecutive_window(intervals)
            ttm = _finite(sum(value for value in window if value is not None)) if complete else None
            periods[field] = {
                "value": amount, "reason": reason, "sources": sources, "unit": unit,
                "start": quarter_start, "end": period_end,
                "yoy_change": _finite(amount - older)
                if amount is not None and older is not None else None,
                "qoq_change": _finite(amount - prior)
                if amount is not None and prior is not None else None,
                "yoy_growth": _safe_div(amount - older, older, True)
                if amount is not None and older is not None else None,
                "qoq_growth": _safe_div(amount - prior, prior, True)
                if amount is not None and prior is not None else None,
                "ttm": ttm,
                "ttm_reason": (None if ttm is not None else "nonfinite_result") if complete
                else "requires_four_observed_consecutive_quarters",
            }
        if annual and not any(flow["value"] is not None for flow in periods.values()):
            continue
        by_period[index] = {
            "fiscal_year": year, "fiscal_period": quarter, "period_end": record["period_end"],
            "flows": periods,
        }
    return list(by_period.values())


def _comparable(row: dict[str, Any], field: str, source: dict[str, Any]) -> float | None:
    """Use an earlier flow only if its reported unit matches."""
    observation = row.get("flows", {}).get(field, {})
    sources = observation.get("sources", [])
    if not sources or not source.get("unit") or _basis(source) != _basis(sources[0]):
        return None
    return _finite(observation.get("value"))
