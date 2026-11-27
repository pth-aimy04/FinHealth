"""Hardened HTKK XML financial statement parser using defusedxml (TT99, TT200, TT133)."""

import re
from dataclasses import dataclass
from datetime import date
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as DefusedET  # type: ignore[import-untyped]
from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]

from finhealth.core.exceptions import EtlProcessingError
from finhealth.etl.accounting_validator import ValidationReport, validate_financial_statement
from finhealth.etl.vn_accounting_mapper import (
    StatementSection,
    VasRegime,
    map_vas_codes_to_normalized,
)

MAX_HTKK_XML_BYTES = 5 * 1024 * 1024  # 5 MB hard upload limit

_BS_CONTAINER_HINTS = (
    "cdkt",
    "b01",
    "bcthtc",
    "bangcandoiketoan",
    "baocaotinhhinhtaichinh",
    "balancesheet",
)
_IS_CONTAINER_HINTS = (
    "kqhdsxkd",
    "kqkd",
    "b02",
    "ketquakinhdoanh",
    "incomestatement",
)
_CF_CONTAINER_HINTS = (
    "lctt",
    "b03",
    "luuchuyentiente",
    "cashflow",
)

_CT_TAG_PATTERN = re.compile(r"^ct(\d{2,3})(?:_.*)?$", re.IGNORECASE)
_VN_DATE_PATTERN = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_ISO_DATE_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_YEAR_PATTERN = re.compile(r"(20\d{2}|199\d)")


@dataclass(frozen=True)
class ParsedHtkkStatement:
    """Normalized statement payload extracted from a Vietnamese HTKK XML filing."""

    accounting_standard: VasRegime
    tax_code: str | None
    company_name: str | None
    fiscal_year: int | None
    fiscal_period: str
    period_end_date: date | None
    raw_codes: dict[StatementSection, dict[str, float | None]]
    normalized_fields: dict[str, float | None]
    validation: ValidationReport


def _local_name(tag: str) -> str:
    """Strip any XML namespace prefix from an element tag."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _parse_numeric_text(text: str | None) -> float | None:
    """Parse a Vietnamese/HTKK numeric string into a finite float or None."""
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned or cleaned in ("-", "--", "N/A", "null"):
        return None
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.replace(" ", "")
    # Handle comma-formatted numbers (e.g. "1,234,567" or "1,234,567.50")
    if "," in cleaned and "." in cleaned or cleaned.count(",") > 1:
        cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") == 1:
        left, right = cleaned.split(",")
        if len(right) == 3 and left.lstrip("-").isdigit() and right.isdigit():
            cleaned = left + right
        else:
            cleaned = f"{left}.{right}"
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -abs(value) if negative else value


def _parse_date_text(text: str | None) -> date | None:
    """Parse dd/mm/yyyy or yyyy-mm-dd dates emitted by HTKK."""
    if not text:
        return None
    cleaned = text.strip()
    vn_match = _VN_DATE_PATTERN.match(cleaned)
    if vn_match:
        day, month, year = int(vn_match.group(1)), int(vn_match.group(2)), int(vn_match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None
    iso_match = _ISO_DATE_PATTERN.match(cleaned)
    if iso_match:
        year, month, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _detect_section(tag_name: str) -> StatementSection | None:
    """Classify an XML container tag into BS, IS, or CF section when recognizable."""
    lowered = re.sub(r"[^a-z0-9]", "", tag_name.lower())
    if any(hint in lowered for hint in _BS_CONTAINER_HINTS):
        return "bs"
    if any(hint in lowered for hint in _IS_CONTAINER_HINTS):
        return "is"
    if any(hint in lowered for hint in _CF_CONTAINER_HINTS):
        return "cf"
    return None


def _detect_regime(
    form_code: str | None,
    form_name: str | None,
    raw_codes: dict[StatementSection, dict[str, float | None]],
    fiscal_year: int | None,
) -> VasRegime:
    """Infer TT99_2025, TT200_2014, or TT133_2016 from HTKK metadata and line codes."""
    combined = f"{form_code or ''} {form_name or ''}".upper()
    if "TT99" in combined or "99/2025" in combined or "TT99_2025" in combined:
        return "TT99_2025"
    if (
        "TT133" in combined
        or "133/2016" in combined
        or "B01A-DNN" in combined
        or "B01B-DNN" in combined
        or "B02-DNN" in combined
        or (form_code and form_code.strip() in ("406", "685"))
    ):
        return "TT133_2016"
    if (
        "TT200" in combined
        or "200/2014" in combined
        or "B01-DN" in combined
        or (form_code and form_code.strip() in ("405", "684"))
    ):
        return "TT200_2014"

    # Fallback by inspecting unique indicator codes
    bs_keys = set(raw_codes["bs"].keys())
    is_keys = set(raw_codes["is"].keys())
    if bs_keys.intersection({"316", "336", "417"}) or "24" in is_keys:
        return "TT133_2016"
    if fiscal_year is not None and fiscal_year >= 2026:
        return "TT99_2025"
    return "TT200_2014"


def _extract_element_numeric_value(elem: Element) -> float | None:
    """Extract the current-period numeric value from an indicator element or its children."""
    for attr in ("soCuoiNam", "namNay", "value", "giaTri"):
        if attr in elem.attrib:
            parsed = _parse_numeric_text(elem.attrib[attr])
            if parsed is not None:
                return parsed

    direct = _parse_numeric_text(elem.text)
    if direct is not None:
        return direct

    preferred_children = ("socuoinam", "namnay", "giatri", "sotien", "value")
    for child in elem:
        cname = _local_name(child.tag).lower()
        if cname in preferred_children:
            parsed = _parse_numeric_text(child.text)
            if parsed is not None:
                return parsed
    return None


def _walk_sections(
    elem: Element,
    current_section: StatementSection | None,
    raw_codes: dict[StatementSection, dict[str, float | None]],
) -> None:
    """Recursively collect indicator codes grouped by BS, IS, and CF sections."""
    name = _local_name(elem.tag)
    detected = _detect_section(name)
    section = detected or current_section

    if section is not None:
        lower_name = name.lower()
        if lower_name in ("chitieu", "item", "lineitem"):
            code = elem.attrib.get("maSo") or elem.attrib.get("code")
            if code:
                val = _extract_element_numeric_value(elem)
                if val is not None:
                    raw_codes[section][code.strip()] = val
        else:
            match = _CT_TAG_PATTERN.match(name)
            # Ignore explicit prior-year comparative tags (e.g. ct100_soDauNam, ct10_namTruoc)
            if match and not any(
                prior in lower_name for prior in ("sodaunam", "namtruoc", "kytruoc", "prior")
            ):
                val = _extract_element_numeric_value(elem)
                if val is not None:
                    raw_codes[section][match.group(1)] = val

    for child in elem:
        _walk_sections(child, section, raw_codes)


def parse_htkk_xml_bytes(
    raw_bytes: bytes,
    *,
    override_standard: str | None = None,
    unit_scale: int = 1,
) -> ParsedHtkkStatement:
    """Safely parse an HTKK XML financial statement upload with XXE and size guards."""
    if not raw_bytes:
        raise EtlProcessingError("Tệp XML HTKK trống.")
    if len(raw_bytes) > MAX_HTKK_XML_BYTES:
        raise EtlProcessingError(
            f"Tệp XML vượt quá giới hạn tối đa {MAX_HTKK_XML_BYTES // (1024 * 1024)} MB."
        )

    try:
        root = DefusedET.fromstring(
            raw_bytes,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except DefusedXmlException as exc:
        raise EtlProcessingError(
            "Tệp XML bị từ chối vì chứa thực thể/DTD không an toàn (chặn XXE)."
        ) from exc
    except Exception as exc:
        raise EtlProcessingError(f"Không thể phân tích tệp XML HTKK: {exc}") from exc

    tax_code: str | None = None
    company_name: str | None = None
    form_code: str | None = None
    form_name: str | None = None
    ky_kkhai: str | None = None
    kieu_ky: str | None = None
    end_date_text: str | None = None

    for elem in root.iter():
        lname = _local_name(elem.tag).lower()
        text = (elem.text or "").strip()
        if not text:
            continue
        if lname == "mst" and tax_code is None:
            tax_code = text
        elif lname in ("tennnt", "tendn", "companyname") and company_name is None:
            company_name = text
        elif lname == "matkhai" and form_code is None:
            form_code = text
        elif lname == "tentkhai" and form_name is None:
            form_name = text
        elif lname == "kykkhai" and ky_kkhai is None:
            ky_kkhai = text
        elif lname == "kieuky" and kieu_ky is None:
            kieu_ky = text
        elif lname in ("kykkhaidenngay", "denngay", "ngayketthuc") and end_date_text is None:
            end_date_text = text

    period_end_date = _parse_date_text(end_date_text)
    fiscal_year: int | None = None
    if period_end_date is not None:
        fiscal_year = period_end_date.year
    elif ky_kkhai:
        year_match = _YEAR_PATTERN.search(ky_kkhai)
        if year_match:
            fiscal_year = int(year_match.group(1))

    fiscal_period = "FY"
    if kieu_ky and kieu_ky.upper() == "Q" and ky_kkhai:
        q_match = re.search(r"Q([1-4])|0?([1-4])/\d{4}", ky_kkhai.upper())
        if q_match:
            q_num = q_match.group(1) or q_match.group(2)
            fiscal_period = f"Q{q_num}"

    raw_codes: dict[StatementSection, dict[str, float | None]] = {"bs": {}, "is": {}, "cf": {}}
    _walk_sections(root, None, raw_codes)

    if not any(raw_codes.values()):
        raise EtlProcessingError(
            "Không tìm thấy chỉ tiêu BCTC hợp lệ (CĐKT/KQHĐKD/LCTT) trong tệp XML HTKK."
        )

    regime: VasRegime
    if override_standard is not None:
        from finhealth.etl.vn_accounting_mapper import normalize_vas_regime

        regime = normalize_vas_regime(override_standard)
    else:
        regime = _detect_regime(form_code, form_name, raw_codes, fiscal_year)

    normalized = map_vas_codes_to_normalized(
        regime,
        bs_codes=raw_codes["bs"],
        is_codes=raw_codes["is"],
        cf_codes=raw_codes["cf"],
        unit_scale=unit_scale,
    )
    validation = validate_financial_statement(normalized)

    return ParsedHtkkStatement(
        accounting_standard=regime,
        tax_code=tax_code,
        company_name=company_name,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        period_end_date=period_end_date,
        raw_codes=raw_codes,
        normalized_fields=normalized,
        validation=validation,
    )
