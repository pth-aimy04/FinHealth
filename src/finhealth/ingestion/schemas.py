"""Validated SEC metadata and SIC division helpers."""

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator

from finhealth.db.repositories import normalize_cik

_SIC_DIVISIONS: tuple[tuple[int, int, str], ...] = (
    (100, 999, "Agriculture, Forestry and Fishing"),
    (1000, 1499, "Mining"),
    (1500, 1799, "Construction"),
    (2000, 3999, "Manufacturing"),
    (4000, 4999, "Transportation, Communications and Utilities"),
    (5000, 5199, "Wholesale Trade"),
    (5200, 5999, "Retail Trade"),
    (6000, 6799, "Finance, Insurance and Real Estate"),
    (7000, 8999, "Services"),
    (9100, 9999, "Public Administration"),
)


def _parse_sic(sic_code: str | int | None) -> int | None:
    """Parse up to four ASCII digits without coercing floats, booleans, or signs."""
    if isinstance(sic_code, bool) or not isinstance(sic_code, (str, int)):
        return None
    value = str(sic_code).strip()
    return int(value) if re.fullmatch(r"[0-9]{1,4}", value) else None


def map_sic_to_sector(sic_code: str | int | None) -> str:
    """Map a SIC code to the requested macro division; unmapped gaps remain Unknown."""
    code = _parse_sic(sic_code)
    if code is not None:
        for lower, upper, sector in _SIC_DIVISIONS:
            if lower <= code <= upper:
                return sector
    return "Unknown"


def is_manufacturing_sic(sic_code: str | int | None) -> bool:
    """Identify SIC 2000 through 3999 for later Altman model selection."""
    code = _parse_sic(sic_code)
    return code is not None and 2000 <= code <= 3999


def is_financial_institution_sic(sic_code: str | int | None) -> bool:
    """Identify the SIC finance, insurance, and real estate division."""
    code = _parse_sic(sic_code)
    return code is not None and 6000 <= code <= 6799


class SecTickerEntry(BaseModel):
    """A normalized entry from SEC's string-indexed ticker dictionary."""

    cik: str
    ticker: str = Field(min_length=1)
    title: str = Field(min_length=1)

    @field_validator("cik", mode="before")
    @classmethod
    def normalize_identifier(cls, value: Any) -> str:
        """Normalize both SEC integer CIKs and explicit string identifiers."""
        return normalize_cik(value)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: Any) -> str:
        """Require a nonempty ticker string and canonicalize casing."""
        if not isinstance(value, str):
            raise ValueError("ticker must be a string")
        return value.strip().upper()

    @classmethod
    def from_sec_raw(cls, raw: dict[str, Any]) -> "SecTickerEntry":
        """Parse the actual cik_str/ticker/title contract without invented aliases."""
        return cls.model_validate(
            {"cik": raw.get("cik_str"), "ticker": raw.get("ticker"), "title": raw.get("title")}
        )


class CompanyMetadata(BaseModel):
    """Company identity and sector attributes extracted from submissions."""

    cik: str
    name: str = Field(min_length=1)
    ticker: str | None = None
    sic_code: str | None = None
    sic_description: str | None = None
    sector: str | None = None
    quarter_report_dates: dict[str, date] | None = None
    amendment_report_dates: dict[str, date] | None = None

    @field_validator("cik", mode="before")
    @classmethod
    def normalize_identifier(cls, value: Any) -> str:
        """Validate and pad the SEC registrant identifier."""
        return normalize_cik(value)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str | None) -> str | None:
        """Normalize optional exchange symbols and preserve absent tickers."""
        return value.strip().upper() if value else None


def sec_report_dates(submissions: dict[str, Any], *forms: str) -> dict[str, date] | None:
    """Index relevant historical accessions by their declared period of report."""
    recent = submissions.get("filings", {}).get("recent")
    if recent is None:
        return None
    return {
        accession: date.fromisoformat(report_date)
        for accession, report_date, form in zip(
            recent["accessionNumber"], recent["reportDate"], recent["form"], strict=True
        )
        if form in forms and report_date
    }
