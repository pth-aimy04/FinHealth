"""Append evidence without modifying a previously published financial observation."""

import re
from hashlib import sha256
from json import dumps
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.core.constants import US_GAAP_TAG_FALLBACKS
from finhealth.db.lineage_models import FilingVersion, ForecastEvidence

if TYPE_CHECKING:
    from finhealth.db.models import FinancialStatement, ModelPrediction


def fingerprint(value: dict[str, Any]) -> str:
    """Hash a deterministic JSON representation and reject nonfinite values."""
    payload = dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
    return sha256(payload.encode()).hexdigest()


def archive_statement(
    session: Session, cik: str, statement: "FinancialStatement", kind: str
) -> FilingVersion:
    """Preserve the selected facts and their original accession exactly as stored."""
    issuer = f"sec:{cik}"
    facts = {
        "values": {name: getattr(statement, name) for name in US_GAAP_TAG_FALLBACKS},
        "provenance": statement.field_provenance or {},
    }
    identity = {
        "accession": statement.accession_number,
        "form_type": statement.form_type,
        "fiscal_year": statement.fiscal_year,
        "fiscal_period": statement.fiscal_period,
        "period_end": statement.period_end_date,
        "published_on": statement.filed_date,
        "scope": "sec_selected_context",
    }
    digest = fingerprint({**identity, **facts})
    found = session.scalar(
        select(FilingVersion).where(
            FilingVersion.issuer_key == issuer, FilingVersion.fingerprint == digest
        )
    )
    if found is not None:
        if kind == "sec_quarter_confirmed" and found.capture_kind != kind:
            found.capture_kind = kind
        return found
    accession = statement.accession_number
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession.replace('-', '')}/{accession}-index.htm"
        if re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession)
        else None
    )
    version = FilingVersion(
        issuer_key=issuer, fingerprint=digest, facts=facts, source_url=url,
        capture_kind=kind, **identity,
    )
    session.add(version)
    session.flush()
    return version


def archive_forecast(
    session: Session,
    version: FilingVersion,
    prediction: "ModelPrediction",
    reported: dict[str, Any] | None = None,
    fitted: dict[str, Any] | None = None,
) -> ForecastEvidence:
    """Record the actual evidence, marking legacy input vectors as unverified."""
    outputs = {
        column.name: getattr(prediction, column.name)
        for column in prediction.__table__.columns
        if column.name.startswith("pred_") or column.name in {
            "target_fiscal_year", "target_fiscal_period", "distress_probability",
            "risk_level", "shap_explanations",
        }
    }
    identity = {"reported": reported, "fitted": fitted, "outputs": outputs}
    digest = fingerprint(identity)
    found = session.scalar(
        select(ForecastEvidence).where(
            ForecastEvidence.filing_version_id == version.id,
            ForecastEvidence.model_version == prediction.model_version,
            ForecastEvidence.fingerprint == digest,
        )
    )
    if found is not None:
        return found
    record = ForecastEvidence(
        filing_version_id=version.id, model_version=prediction.model_version,
        fingerprint=digest, reported_inputs=reported, fitted_inputs=fitted, outputs=outputs,
        input_status="verified_inputs" if fitted is not None else "legacy_unverified",
    )
    session.add(record)
    return record


def backfill_legacy_evidence(session: Session) -> None:
    """Capture legacy rows as known at migration time, without claiming original inputs."""
    from finhealth.db.models import Company, FinancialStatement, ModelPrediction

    versions = {
        statement.id: archive_statement(session, cik, statement, "legacy_snapshot")
        for statement, cik in session.execute(
            select(FinancialStatement, Company.cik).join(Company)
        ).all()
    }
    for prediction in session.scalars(select(ModelPrediction)):
        archive_forecast(session, versions[prediction.source_statement_id], prediction)
    session.flush()
    from finhealth.api.services import invalidate_benchmark_cache

    invalidate_benchmark_cache(session)
