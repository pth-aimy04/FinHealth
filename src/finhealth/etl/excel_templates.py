"""Vietnamese BCTC Excel template generator and safe openpyxl upload parser."""

import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook  # type: ignore[import-untyped]
from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore[import-untyped]

from finhealth.core.exceptions import EtlProcessingError
from finhealth.etl.accounting_validator import ValidationReport, validate_financial_statement
from finhealth.etl.financial_ratios import _finite
from finhealth.etl.vn_accounting_mapper import (
    REGIME_METADATA,
    StatementSection,
    VasRegime,
    get_regime_spec,
    map_normalized_to_vas_codes,
    map_vas_codes_to_normalized,
    normalize_vas_regime,
)

MAX_EXCEL_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB compressed upload limit
MAX_EXCEL_ZIP_ENTRIES = 200
MAX_EXCEL_UNCOMPRESSED_BYTES = 25 * 1024 * 1024  # 25 MB zip-bomb ceiling
MAX_EXCEL_COMPRESSION_RATIO = 100.0

META_SHEET = "ThongTinChung"
SECTION_SHEETS: dict[StatementSection, str] = {
    "bs": "CanDoiKeToan",
    "is": "KetQuaKinhDoanh",
    "cf": "LuuChuyenTienTe",
}
ALLOWED_UNIT_SCALES = {1, 1_000, 1_000_000, 1_000_000_000}


@dataclass(frozen=True)
class ParsedExcelStatement:
    """Normalized statement extracted from an uploaded FinHealth BCTC Excel template."""

    accounting_standard: VasRegime
    fiscal_year: int | None
    fiscal_period: str
    currency: str
    unit_scale: int
    audit_status: str
    raw_codes: dict[StatementSection, dict[str, float | None]]
    normalized_fields: dict[str, float | None]
    validation: ValidationReport


def _guard_xlsx_zip_safety(raw_bytes: bytes) -> None:
    """Reject oversized uploads, non-ZIP payloads, and ZIP-bomb archives before openpyxl."""
    if not raw_bytes:
        raise EtlProcessingError("Tệp Excel trống.")
    if len(raw_bytes) > MAX_EXCEL_UPLOAD_BYTES:
        raise EtlProcessingError(
            f"Tệp Excel vượt quá giới hạn tối đa {MAX_EXCEL_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    try:
        with zipfile.ZipFile(BytesIO(raw_bytes), "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_EXCEL_ZIP_ENTRIES:
                raise EtlProcessingError(
                    "Tệp Excel chứa quá nhiều thành phần nén (nghi ngờ zip-bomb)."
                )
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > MAX_EXCEL_UNCOMPRESSED_BYTES:
                raise EtlProcessingError(
                    "Dung lượng giải nén của tệp Excel vượt quá giới hạn an toàn."
                )
            ratio = total_uncompressed / max(len(raw_bytes), 1)
            if ratio > MAX_EXCEL_COMPRESSION_RATIO:
                raise EtlProcessingError(
                    "Tỷ lệ nén của tệp Excel bất thường (chặn zip-bomb)."
                )
    except zipfile.BadZipFile as exc:
        raise EtlProcessingError("Tệp tải lên không phải định dạng Excel .xlsx hợp lệ.") from exc


def generate_bctc_template_bytes(
    standard: str,
    *,
    fiscal_year: int = 2025,
    fiscal_period: str = "FY",
    currency: str = "VND",
    unit_scale: int = 1_000_000,
    audit_status: str = "unaudited",
    prefill: Mapping[str, Any] | None = None,
) -> bytes:
    """Generate a standardized multi-sheet Excel template for TT99, TT200, or TT133."""
    regime = normalize_vas_regime(standard)
    if unit_scale not in ALLOWED_UNIT_SCALES:
        raise EtlProcessingError(
            f"Đơn vị tỷ lệ không hợp lệ: {unit_scale}. Chỉ chấp nhận 1, 1000, 1000000, 1000000000."
        )

    specs = get_regime_spec(regime)
    meta = REGIME_METADATA[regime]
    prefill_codes = (
        map_normalized_to_vas_codes(regime, prefill, unit_scale=unit_scale)
        if prefill is not None
        else {"bs": {}, "is": {}, "cf": {}}
    )

    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")

    meta_ws = wb.active
    assert meta_ws is not None
    meta_ws.title = META_SHEET
    meta_ws.append(["Truong", "GiaTri", "MoTa"])
    for cell in meta_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="left")

    meta_rows = [
        ("accounting_standard", regime, meta["title_vi"]),
        ("fiscal_year", fiscal_year, "Năm tài chính (1990-2100)"),
        ("fiscal_period", fiscal_period, "Kỳ báo cáo (FY, Q1, Q2, Q3, Q4)"),
        ("currency", currency, "Đơn vị tiền tệ (VND hoặc USD)"),
        ("unit_scale", unit_scale, "Tỷ lệ đơn vị (1=Đồng, 1000000=Triệu, 1000000000=Tỷ)"),
        ("audit_status", audit_status, "Tình trạng kiểm toán"),
    ]
    for row in meta_rows:
        meta_ws.append(list(row))
    meta_ws.column_dimensions["A"].width = 24
    meta_ws.column_dimensions["B"].width = 22
    meta_ws.column_dimensions["C"].width = 56

    for section in ("bs", "is", "cf"):
        sec_key: StatementSection = section
        ws = wb.create_sheet(title=SECTION_SHEETS[sec_key])
        ws.append(["MaSo", "ChiTieu", "GiaTri", "TruongChuanHoa"])
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="left")

        for item in specs:
            if item.section != sec_key:
                continue
            val = prefill_codes[sec_key].get(item.code)
            ws.append([item.code, item.label_vi, val, item.field_name])
            ws.cell(row=ws.max_row, column=3).number_format = "#,##0.00"

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 54
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 28

    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def _parse_cell_number(raw: Any) -> float | None:
    """Convert an openpyxl cell value into a finite float or None."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return _finite(raw)
    if isinstance(raw, str):
        cleaned = raw.strip().replace(",", "").replace(" ", "")
        if not cleaned or cleaned in ("-", "--", "N/A"):
            return None
        try:
            return _finite(float(cleaned))
        except ValueError:
            return None
    return None


def parse_bctc_excel_bytes(
    raw_bytes: bytes,
    *,
    override_standard: str | None = None,
    override_unit_scale: int | None = None,
) -> ParsedExcelStatement:
    """Parse an uploaded BCTC Excel file safely in read_only + data_only mode."""
    _guard_xlsx_zip_safety(raw_bytes)

    wb = load_workbook(BytesIO(raw_bytes), read_only=True, data_only=True)
    try:
        meta_values: dict[str, Any] = {}
        if META_SHEET in wb.sheetnames:
            meta_ws = wb[META_SHEET]
            for row in meta_ws.iter_rows(min_row=2, max_col=2, values_only=True):
                if row and row[0] is not None:
                    meta_values[str(row[0]).strip()] = row[1]

        raw_standard = override_standard or str(
            meta_values.get("accounting_standard") or "TT99_2025"
        )
        regime = normalize_vas_regime(raw_standard)

        raw_scale = override_unit_scale or meta_values.get("unit_scale") or 1
        try:
            unit_scale = int(float(raw_scale))
        except (TypeError, ValueError) as exc:
            raise EtlProcessingError(
                f"Đơn vị tỷ lệ trong file Excel không hợp lệ: {raw_scale!r}"
            ) from exc
        if unit_scale not in ALLOWED_UNIT_SCALES:
            raise EtlProcessingError(
                f"Đơn vị tỷ lệ {unit_scale} không được hỗ trợ. "
                "Chỉ chấp nhận 1, 1000, 1000000, 1000000000."
            )

        fiscal_year: int | None = None
        raw_year = meta_values.get("fiscal_year")
        if raw_year is not None:
            try:
                parsed_year = int(float(raw_year))
                if 1990 <= parsed_year <= 2100:
                    fiscal_year = parsed_year
            except (TypeError, ValueError):
                fiscal_year = None

        fiscal_period = str(meta_values.get("fiscal_period") or "FY").strip().upper() or "FY"
        currency = str(meta_values.get("currency") or "VND").strip().upper()
        if currency not in ("VND", "USD"):
            currency = "VND"
        audit_status = str(meta_values.get("audit_status") or "unaudited").strip()
        if audit_status not in (
            "audited_unqualified",
            "audited_qualified",
            "audited_adverse_disclaimer",
            "unaudited",
        ):
            audit_status = "unaudited"

        raw_codes: dict[StatementSection, dict[str, float | None]] = {"bs": {}, "is": {}, "cf": {}}
        for sec_key, sheet_name in SECTION_SHEETS.items():
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, max_col=3, values_only=True):
                if not row or row[0] is None:
                    continue
                code = str(row[0]).strip()
                if not code:
                    continue
                val = _parse_cell_number(row[2] if len(row) > 2 else None)
                if val is not None:
                    raw_codes[sec_key][code] = val
    finally:
        wb.close()

    if not any(raw_codes.values()):
        raise EtlProcessingError(
            "Không tìm thấy dữ liệu chỉ tiêu tài chính hợp lệ trong tệp Excel tải lên."
        )

    normalized = map_vas_codes_to_normalized(
        regime,
        bs_codes=raw_codes["bs"],
        is_codes=raw_codes["is"],
        cf_codes=raw_codes["cf"],
        unit_scale=unit_scale,
    )
    validation = validate_financial_statement(normalized)

    return ParsedExcelStatement(
        accounting_standard=regime,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        currency=currency,
        unit_scale=unit_scale,
        audit_status=audit_status,
        raw_codes=raw_codes,
        normalized_fields=normalized,
        validation=validation,
    )
