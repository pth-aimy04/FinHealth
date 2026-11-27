"""Read versioned filing evidence and compute reporting-only accounting summaries."""

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finhealth.api.services import FinancialAnalysisService
from finhealth.core.exceptions import SecResourceNotFoundError
from finhealth.db.lineage_models import FilingVersion, ForecastEvidence
from finhealth.db.models import Company, FinancialMetric, FinancialStatement
from finhealth.db.repositories import latest_annual_statement_id
from finhealth.etl.financial_ratios import _safe_div
from finhealth.etl.report_periods import quarterly_series


def _issuer_key(session: Session, identifier: str) -> str:
    """Resolve SEC symbols or an explicit national issuer key."""
    if identifier.upper().startswith("VN:"):
        return "vn:" + identifier[3:].upper()
    return f"sec:{FinancialAnalysisService().resolve_company(session, identifier).cik}"


def _filing(row: FilingVersion) -> dict[str, Any]:
    """Serialize a report with its factual source and explicit missing values."""
    values = dict(row.facts["values"])
    provenance = dict(row.facts["provenance"])
    return {
        "id": row.id, "issuer_key": row.issuer_key, "accession": row.accession,
        "form_type": row.form_type, "scope": row.scope, "fiscal_year": row.fiscal_year,
        "fiscal_period": row.fiscal_period, "period_end": row.period_end,
        "published_on": row.published_on, "captured_at": row.captured_at,
        "capture_kind": row.capture_kind, "source_url": row.source_url,
        "fingerprint": row.fingerprint,
        **row.facts, "values": values, "provenance": provenance,
        "missing_reasons": {
            name: "no_selected_fact" for name, value in row.facts["values"].items() if value is None
        },
    }


def _reported_ratios(
    values: dict[str, Any], provenance: dict[str, Any],
) -> dict[str, float | None]:
    """Compute only ratios supported by the selected report's accounting inputs."""
    return {
        "debt_ratio": _safe_div(values.get("total_liabilities"), values.get("total_assets"), True),
        "net_margin": _matched_flow_ratio(values, provenance, "net_income", "revenues"),
        "cash_conversion": _matched_flow_ratio(
            values, provenance, "operating_cash_flow", "net_income",
        ),
    }


def _matched_flow_ratio(
    values: dict[str, Any], provenance: dict[str, Any], numerator: str, denominator: str,
) -> float | None:
    """Divide flows only when the disclosed duration, currency and accession agree."""
    left, right = provenance.get(numerator, {}), provenance.get(denominator, {})
    if not left.get("unit") or any(
        left.get(key) != right.get(key)
        for key in ("unit", "currency", "start", "end", "duration_basis", "accn", "filed")
    ):
        return None
    return _safe_div(values.get(numerator), values.get(denominator), True)


def list_reports(
    identifier: str, db: Session,
    as_of: date | None = None, period_kind: str | None = None,
) -> dict[str, Any]:
    """Read available versions published by the cutoff, newest disclosure first per period."""
    issuer = _issuer_key(db, identifier)
    query = select(FilingVersion).where(FilingVersion.issuer_key == issuer)
    if issuer.startswith("sec:"):
        query = query.where(
            (FilingVersion.form_type != "10-Q")
            | FilingVersion.capture_kind.in_(("sec_quarter_confirmed", "sec_amendment"))
        )
    if as_of is not None:
        query = query.where(FilingVersion.published_on <= as_of)
    if period_kind is not None:
        query = query.where(FilingVersion.form_type == period_kind)
    cutoff = as_of.isoformat() if as_of is not None else None
    versions = [_filing(row) for row in db.scalars(
        query.order_by(FilingVersion.period_end.desc(), FilingVersion.published_on.desc(),
                       FilingVersion.id.desc())
    )]
    if not versions and issuer.startswith("vn:") and db.scalar(
        select(FilingVersion.id).where(FilingVersion.issuer_key == issuer).limit(1)
    ) is None:
        raise SecResourceNotFoundError("Unknown Vietnamese pilot issuer")
    for version in versions:
        if cutoff is not None:
            for key, source in list(version["provenance"].items()):
                filed = source.get("filed")
                if isinstance(filed, str) and filed > cutoff:
                    version["values"][key] = None
                    version["missing_reasons"][key] = "fact_published_after_cutoff"
                    del version["provenance"][key]
        version["ratios"] = _reported_ratios(version["values"], version["provenance"])
    latest_periods: dict[tuple[int, str], dict[str, Any]] = {}
    for version in versions:
        if version["capture_kind"] != "sec_amendment":
            latest_periods.setdefault((version["fiscal_year"], version["fiscal_period"]), version)
    return {
        "issuer_key": issuer, "as_of": as_of, "versions": versions,
        "quarterly_series": quarterly_series(list(latest_periods.values())),
    }


def report_alerts(
    identifier: str, db: Session, as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Derive explainable notices from the recorded, in-scope disclosure versions."""
    reports = list_reports(identifier, db, as_of)
    alerts = []
    last: dict[tuple[str, str, date], dict[str, Any]] = {}
    for version in reversed(reports["versions"]):
        identity = (version["scope"], version["form_type"], version["period_end"])
        previous = last.get(identity)
        if previous and previous["accession"] != version["accession"]:
            changed = sorted(
                key for key in version["values"].keys() & previous["values"].keys()
                if version["values"][key] is not None and previous["values"][key] is not None
                and _comparable_sources(
                    version["provenance"].get(key, {}), previous["provenance"].get(key, {}),
                )
                and version["values"][key] != previous["values"][key]
            )
            if changed:
                alerts.append({
                    "rule": "disclosed_values_changed", "rule_version": 1,
                    "previous_filing_id": previous["id"], "filing_id": version["id"],
                    "published_on": version["published_on"], "changed_fields": changed,
                    "source_url": version["source_url"],
                })
        last[identity] = version
    return list(reversed(alerts))


def _comparable_sources(current: dict[str, Any], previous: dict[str, Any]) -> bool:
    """Require matching units, concept identity and duration for amendment alerts."""
    return bool(current.get("unit")) and all(
        current.get(key) == previous.get(key)
        for key in ("unit", "currency", "tag", "form", "line", "start", "duration_basis")
    )


def list_forecast_evidence(
    filing_id: int, db: Session,
) -> list[dict[str, Any]]:
    """Expose the saved input evidence without rebuilding legacy predictions."""
    if db.get(FilingVersion, filing_id) is None:
        raise SecResourceNotFoundError("Unknown filing version")
    return [
        {
            "id": row.id, "filing_version_id": row.filing_version_id,
            "model_version": row.model_version, "input_status": row.input_status,
            "reported_inputs": row.reported_inputs, "fitted_inputs": row.fitted_inputs,
            "outputs": row.outputs, "fingerprint": row.fingerprint,
        }
        for row in db.scalars(select(ForecastEvidence).where(
            ForecastEvidence.filing_version_id == filing_id
        ).order_by(ForecastEvidence.id.desc()))
    ]


def data_quality(db: Session) -> dict[str, Any]:
    """Count observed values separately from the total annual snapshot."""
    metrics = {key: getattr(FinancialMetric, key) for key in (
        "roa", "roe", "debt_ratio", "current_ratio", "ocf_ratio", "interest_coverage",
        "fcf_to_liabilities", "altman_z_score",
    )}
    counts = db.execute(select(
        func.count(FinancialStatement.id).label("report_count"),
        *(func.count(column).label(key) for key, column in metrics.items()),
    ).select_from(FinancialStatement).outerjoin(
        FinancialMetric, FinancialMetric.statement_id == FinancialStatement.id
    ).where(FinancialStatement.id.in_(select(latest_annual_statement_id()).select_from(Company))))
    row = counts.mappings().one()
    return {"report_count": row["report_count"], "observed": {key: row[key] for key in metrics}}
