"""Select annual filing contexts shared by training and serving."""

import logging
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import msgspec

from finhealth.core.constants import US_GAAP_TAG_FALLBACKS
from finhealth.core.exceptions import EtlProcessingError
from finhealth.etl.xbrl_parser import BALANCE_SCOPE_TAGS, FLOW_FIELDS

logger = logging.getLogger(__name__)
_TAG_UNITS = {
    tag: "USD/shares" if field.startswith("eps_") else "USD"
    for field, tags in US_GAAP_TAG_FALLBACKS.items()
    for tag in tags
}
_TAG_UNITS.update(dict.fromkeys(BALANCE_SCOPE_TAGS, "USD"))


class _Observation(msgspec.Struct, gc=False):
    """Hold only fields used by annual context selection and normalization."""

    form: str
    end: str
    filed: str
    accn: str
    val: Any = None
    start: str | None = None
    fy: int | None = None


class _UsdUnits(msgspec.Struct, gc=False):
    """Decode only the supported currency array for accounting facts."""

    observations: list[_Observation] | None = msgspec.field(name="USD", default=None)


class _EpsUnits(msgspec.Struct, gc=False):
    """Decode only the supported per-share currency array for EPS."""

    observations: list[_Observation] | None = msgspec.field(name="USD/shares", default=None)


class _UsdConcept(msgspec.Struct, gc=False):
    """Select the supported accounting units from a SEC concept."""

    units: _UsdUnits


class _EpsConcept(msgspec.Struct, gc=False):
    """Select the supported EPS units from a SEC concept."""

    units: _EpsUnits


if TYPE_CHECKING:
    _Gaap = msgspec.Struct
else:
    _Gaap = msgspec.defstruct(
        "_Gaap",
        [
            (tag, (_UsdConcept if unit == "USD" else _EpsConcept) | None, None)
            for tag, unit in _TAG_UNITS.items()
        ],
    )


class _Facts(msgspec.Struct):
    """Select the US GAAP namespace."""

    us_gaap: _Gaap | None = msgspec.field(name="us-gaap", default=None)


class _CompanyFacts(msgspec.Struct):
    """Identify the registrant and skip unsupported namespaces and tags during decode."""

    cik: int | str
    entity_name: str | None = msgspec.field(name="entityName", default=None)
    facts: _Facts | None = None


@lru_cache(maxsize=8)
def _decode_companyfacts(raw: bytes) -> dict[str, Any]:
    """Decode only supported facts and select annual contexts for identical source bytes."""
    document = msgspec.json.decode(raw, type=_CompanyFacts)
    selected: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {}
    concepts = document.facts.us_gaap if document.facts is not None else None
    if concepts is not None:
        for tag, unit in _TAG_UNITS.items():
            concept = getattr(concepts, tag)
            if concept is None or concept.units.observations is None:
                continue
            selected[tag] = {
                "units": {
                    unit: [
                        {
                            "form": fact.form,
                            "start": fact.start,
                            "end": fact.end,
                            "filed": fact.filed,
                            "accn": fact.accn,
                            "fy": fact.fy if fact.fy is not None else int(fact.end[:4]),
                            "val": fact.val,
                        }
                        for fact in concept.units.observations
                        if fact.form == "10-K"
                    ]
                }
            }
    return as_reported_annual_payload(
        {
            "cik": document.cik,
            "entityName": document.entity_name,
            "facts": {"us-gaap": selected},
        }
    )


def load_annual_companyfacts(path: Path) -> dict[str, Any]:
    """Read current filing bytes and supply the read-only annual projection to ETL."""
    try:
        return _decode_companyfacts(path.read_bytes())
    except (OSError, msgspec.DecodeError, TypeError, ValueError, KeyError) as error:
        raise EtlProcessingError(f"Cannot read SEC companyfacts cache: {path}") from error


def as_reported_annual_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Select first-observed annual filing/accession per period before invoking actual ETL.

    Anchor period ends on annual-duration flow facts, excluding quarterly footnotes
    and later restatements. Missing facts in the selected accession remain missing.
    """
    concepts = payload.get("facts", {}).get("us-gaap", {})
    anchors: dict[str, tuple[str, str]] = {}
    for field in FLOW_FIELDS:
        unit = "USD/shares" if field.startswith("eps_") else "USD"
        for tag in US_GAAP_TAG_FALLBACKS[field]:
            for row in concepts.get(tag, {}).get("units", {}).get(unit, []):
                if row.get("form") != "10-K" or not row.get("start"):
                    continue
                days = (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days
                if not 330 <= days <= 380 or row["filed"] < row["end"]:
                    continue
                identity = (row["filed"], row["accn"])
                end = row["end"]
                if end not in anchors or identity < anchors[end]:
                    anchors[end] = identity
    selected = {}
    calendar_years: dict[int, list[str]] = {}
    for end in anchors:
        calendar_years.setdefault(date.fromisoformat(end).year, []).append(end)
    for year, ends in calendar_years.items():
        if len(ends) > 1:
            logger.warning(
                "Excluding ambiguous annual endpoints for CIK %s, calendar year %s: %s",
                payload.get("cik"),
                year,
                ", ".join(sorted(ends)),
            )
            for end in ends:
                del anchors[end]
    for tag in _TAG_UNITS.keys() & concepts.keys():
        concept = concepts[tag]
        selected[tag] = {
            **concept,
            "units": {
                unit: [
                    row
                    for row in rows
                    if row.get("form") == "10-K"
                    and anchors.get(row.get("end")) == (row.get("filed"), row.get("accn"))
                ]
                for unit, rows in concept.get("units", {}).items()
            },
        }
    return {**payload, "facts": {**payload.get("facts", {}), "us-gaap": selected}}
