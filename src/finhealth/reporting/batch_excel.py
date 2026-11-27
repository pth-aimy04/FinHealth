"""Batch Excel template generator, safe read_only upload parser, and ranked export (S03)."""

import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from io import BytesIO
from math import isfinite
from typing import Any

from openpyxl import Workbook, load_workbook  # type: ignore[import-untyped]
from openpyxl.styles import Alignment, Font, PatternFill  # type: ignore[import-untyped]

from finhealth.api.schemas.analytics import LEGAL_DISCLAIMER_VI
from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.batch_models import OrgBatchJob, OrgBatchJobRow
from finhealth.etl.excel_templates import ALLOWED_UNIT_SCALES, _parse_cell_number

MAX_BATCH_FILE_BYTES = 10 * 1024 * 1024  # 10 MB upload ceiling
MAX_BATCH_ROWS = 500
MAX_BATCH_ZIP_ENTRIES = 200
MAX_BATCH_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB zip-bomb ceiling
MAX_BATCH_COMPRESSION_RATIO = 100.0

BATCH_GUIDE_SHEET = "HuongDan"
BATCH_DATA_SHEET = "DanhSachDoanhNghiep"

_VALID_BUSINESS_TYPES = {"manufacturing", "trade_service", "financial_institution"}
_VALID_LISTING_STATUSES = {"listed", "unlisted"}
_VALID_AUDIT_STATUSES = {
    "audited_unqualified",
    "audited_qualified",
    "audited_adverse_disclaimer",
    "unaudited",
}
_VALID_STANDARDS = {"TT99_2025", "TT200_2014", "TT133_2016", "US_GAAP"}

_RISK_TIER_LABELS_VI: dict[str, str] = {
    "STRONG": "Vững mạnh",
    "STABLE": "Ổn định",
    "WATCH": "Cần theo dõi sát",
    "CRITICAL": "Nguy cơ khủng hoảng cao",
}

BATCH_NUMERIC_COLUMNS: tuple[str, ...] = (
    "total_assets",
    "current_assets",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "total_liabilities",
    "current_liabilities",
    "short_term_debt",
    "long_term_debt",
    "accounts_payable",
    "stockholders_equity",
    "retained_earnings",
    "revenues",
    "cost_of_goods_sold",
    "gross_profit",
    "operating_expenses",
    "operating_income",
    "depreciation_amortization",
    "ebitda",
    "interest_expense",
    "net_income",
    "operating_cash_flow",
    "capex",
    "market_value_equity",
)

BATCH_COLUMNS: tuple[tuple[str, str], ...] = (
    ("company_name", "Tên doanh nghiệp *"),
    ("tax_code", "Mã số thuế"),
    ("sector_name", "Ngành nghề"),
    ("business_type", "Loại hình (manufacturing/trade_service/financial_institution)"),
    ("listing_status", "Niêm yết (listed/unlisted)"),
    ("fiscal_year", "Năm tài chính *"),
    ("accounting_standard", "Chuẩn BCTC (TT99_2025/TT200_2014/TT133_2016/US_GAAP)"),
    ("audit_status", "Kiểm toán"),
    ("currency", "Tiền tệ (VND/USD)"),
    ("unit_scale", "Đơn vị (1/1000/1000000/1000000000)"),
    ("total_assets", "Tổng tài sản *"),
    ("current_assets", "Tài sản ngắn hạn"),
    ("cash_and_equivalents", "Tiền và TĐ tiền"),
    ("accounts_receivable", "Phải thu ngắn hạn"),
    ("inventory", "Hàng tồn kho"),
    ("total_liabilities", "Tổng nợ phải trả *"),
    ("current_liabilities", "Nợ ngắn hạn"),
    ("short_term_debt", "Vay ngắn hạn"),
    ("long_term_debt", "Vay dài hạn"),
    ("accounts_payable", "Phải trả người bán"),
    ("stockholders_equity", "Vốn chủ sở hữu *"),
    ("retained_earnings", "Lợi nhuận sau thuế chưa PP"),
    ("revenues", "Doanh thu thuần"),
    ("cost_of_goods_sold", "Giá vốn hàng bán"),
    ("gross_profit", "Lợi nhuận gộp"),
    ("operating_expenses", "Chi phí hoạt động"),
    ("operating_income", "Lợi nhuận thuần HĐKD (EBIT)"),
    ("depreciation_amortization", "Khấu hao TSCĐ"),
    ("ebitda", "EBITDA"),
    ("interest_expense", "Chi phí lãi vay"),
    ("net_income", "Lợi nhuận sau thuế"),
    ("operating_cash_flow", "Lưu chuyển tiền thuần HĐKD (OCF)"),
    ("capex", "Chi đầu tư TSCĐ (CapEx)"),
    ("market_value_equity", "Vốn hóa thị trường (nếu niêm yết)"),
)


@dataclass(frozen=True)
class ParsedBatchRow:
    """One raw company row extracted from an uploaded batch Excel workbook."""

    row_index: int
    company_name: str
    tax_code: str | None
    sector_name: str | None
    business_type: str
    listing_status: str
    fiscal_year: int | None
    accounting_standard: str
    audit_status: str
    currency: str
    unit_scale: int
    numeric_fields: dict[str, float | None]

    def to_input_json(self) -> dict[str, Any]:
        """Serialize into a JSON-compatible dictionary stored on OrgBatchJobRow."""
        return {
            "company_name": self.company_name,
            "tax_code": self.tax_code,
            "sector_name": self.sector_name,
            "business_type": self.business_type,
            "listing_status": self.listing_status,
            "fiscal_year": self.fiscal_year,
            "accounting_standard": self.accounting_standard,
            "audit_status": self.audit_status,
            "currency": self.currency,
            "unit_scale": self.unit_scale,
            "numeric_fields": dict(self.numeric_fields),
        }


@dataclass(frozen=True)
class ParsedBatchWorkbook:
    """Validated collection of up to 500 company rows from an uploaded batch workbook."""

    rows: list[ParsedBatchRow]


def _guard_batch_xlsx_safety(raw_bytes: bytes) -> None:
    """Reject empty, oversized (>10 MB), malformed, or zip-bomb Excel files before openpyxl."""
    if not raw_bytes:
        raise EtlProcessingError("Tệp Excel trống.")
    if len(raw_bytes) > MAX_BATCH_FILE_BYTES:
        raise EtlProcessingError("Tệp Excel vượt quá giới hạn tối đa 10 MB.")
    try:
        with zipfile.ZipFile(BytesIO(raw_bytes), "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_BATCH_ZIP_ENTRIES:
                raise EtlProcessingError(
                    "Tệp Excel chứa quá nhiều thành phần nén (nghi ngờ zip-bomb)."
                )
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > MAX_BATCH_UNCOMPRESSED_BYTES:
                raise EtlProcessingError(
                    "Dung lượng giải nén của tệp Excel vượt quá giới hạn an toàn."
                )
            ratio = total_uncompressed / max(len(raw_bytes), 1)
            if ratio > MAX_BATCH_COMPRESSION_RATIO:
                raise EtlProcessingError(
                    "Tỷ lệ nén của tệp Excel bất thường (chặn zip-bomb)."
                )
    except zipfile.BadZipFile as exc:
        raise EtlProcessingError("Tệp tải lên không phải định dạng Excel .xlsx hợp lệ.") from exc


def generate_batch_template_bytes() -> bytes:
    """Generate the standardized 2-sheet batch assessment Excel template (<=500 companies)."""
    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    sub_font = Font(italic=True, color="334155")
    sub_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    guide_ws = wb.active
    assert guide_ws is not None
    guide_ws.title = BATCH_GUIDE_SHEET
    guide_ws.append(["Mục", "Hướng dẫn sử dụng biểu mẫu Thẩm định Hàng loạt FinHealth"])
    for cell in guide_ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    guide_rows = [
        ("Giới hạn", "Tối đa 500 doanh nghiệp mỗi tệp và dung lượng tệp ≤ 10 MB (.xlsx)."),
        (
            "Cấu trúc nhập liệu",
            f"Nhập mỗi doanh nghiệp trên 1 dòng trong sheet '{BATCH_DATA_SHEET}' "
            "bắt đầu từ dòng 3 (giữ nguyên dòng 1 mã cột).",
        ),
        (
            "Trường bắt buộc",
            "company_name, fiscal_year, total_assets (>0), total_liabilities, stockholders_equity "
            "(cân đối: Tổng TS = Tổng Nợ + VCSH, dung sai ≤ 0,5%).",
        ),
        (
            "Cô lập lỗi từng dòng",
            "Dòng nhập thiếu hoặc lệch cân đối sẽ được đánh dấu lỗi riêng mà không làm gián đoạn "
            "các doanh nghiệp hợp lệ còn lại trong lô.",
        ),
        (
            "Tổ chức tài chính",
            "Các dòng có business_type='financial_institution' sẽ được ghi nhận trạng thái "
            "loại trừ (không chấm điểm Altman/ML phi tài chính).",
        ),
        ("Miễn trừ pháp lý", LEGAL_DISCLAIMER_VI),
    ]
    for item in guide_rows:
        guide_ws.append(list(item))
    guide_ws.column_dimensions["A"].width = 24
    guide_ws.column_dimensions["B"].width = 96

    data_ws = wb.create_sheet(title=BATCH_DATA_SHEET)
    keys = [col[0] for col in BATCH_COLUMNS]
    labels = [col[1] for col in BATCH_COLUMNS]
    data_ws.append(keys)
    data_ws.append(labels)

    for cell in data_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="left")
    for cell in data_ws[2]:
        cell.font = sub_font
        cell.fill = sub_fill
        cell.alignment = Alignment(horizontal="left", wrap_text=True)

    # One illustrative healthy sample row (in millions VND, 100% balanced).
    sample_row = [
        "Công ty CP Sản xuất Minh An (Mẫu)",
        "0101234567",
        "Sản xuất công nghiệp",
        "manufacturing",
        "unlisted",
        2025,
        "TT99_2025",
        "audited_unqualified",
        "VND",
        1_000_000,
        1_200_000,
        620_000,
        180_000,
        160_000,
        210_000,
        480_000,
        280_000,
        120_000,
        160_000,
        110_000,
        720_000,
        260_000,
        1_450_000,
        920_000,
        530_000,
        290_000,
        240_000,
        65_000,
        305_000,
        22_000,
        175_000,
        210_000,
        55_000,
        None,
    ]
    data_ws.append(sample_row)

    for col_idx in range(1, len(BATCH_COLUMNS) + 1):
        col_letter = data_ws.cell(row=1, column=col_idx).column_letter
        data_ws.column_dimensions[col_letter].width = 22 if col_idx <= 4 else 18

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _parse_int_or_none(raw: Any) -> int | None:
    """Convert an openpyxl cell value into an integer or None."""
    val = _parse_cell_number(raw)
    if val is None:
        return None
    return int(round(val))


def _is_label_subtitle_row(row_map: dict[str, Any]) -> bool:
    """Detect the optional Vietnamese human-readable subtitle row (row 2 in template)."""
    name_val = str(row_map.get("company_name") or "").strip().lower()
    year_raw = row_map.get("fiscal_year")
    if "tên doanh nghiệp" in name_val or "ten doanh nghiep" in name_val:
        return True
    return isinstance(year_raw, str) and (
        "năm" in year_raw.lower() or "nam" in year_raw.lower()
    )


def parse_batch_excel_bytes(raw_bytes: bytes) -> ParsedBatchWorkbook:
    """Parse an uploaded batch Excel workbook safely in read_only + data_only mode."""
    _guard_batch_xlsx_safety(raw_bytes)

    wb = load_workbook(BytesIO(raw_bytes), read_only=True, data_only=True)
    try:
        if BATCH_DATA_SHEET in wb.sheetnames:
            ws = wb[BATCH_DATA_SHEET]
        else:
            # Fall back to first non-guide sheet if user renamed the sheet.
            candidates = [s for s in wb.sheetnames if s != BATCH_GUIDE_SHEET]
            if not candidates:
                raise EtlProcessingError(
                    f"Không tìm thấy sheet dữ liệu '{BATCH_DATA_SHEET}' trong tệp Excel."
                )
            ws = wb[candidates[0]]

        row_iter = ws.iter_rows(values_only=True)
        try:
            header_raw = next(row_iter)
        except StopIteration as exc:
            raise EtlProcessingError("Sheet dữ liệu doanh nghiệp đang trống.") from exc

        headers = [str(cell).strip().lower() if cell is not None else "" for cell in header_raw]
        if "company_name" not in headers or "total_assets" not in headers:
            raise EtlProcessingError(
                "Thiếu cột bắt buộc ('company_name', 'total_assets') ở dòng tiêu đề đầu tiên."
            )

        parsed_rows: list[ParsedBatchRow] = []
        excel_row_num = 1
        for raw_row in row_iter:
            excel_row_num += 1
            if not raw_row or all(
                cell is None or (isinstance(cell, str) and not cell.strip())
                for cell in raw_row
            ):
                continue

            row_map = {
                headers[idx]: raw_row[idx]
                for idx in range(min(len(headers), len(raw_row)))
                if headers[idx]
            }
            if excel_row_num == 2 and _is_label_subtitle_row(row_map):
                continue

            if len(parsed_rows) >= MAX_BATCH_ROWS:
                raise EtlProcessingError(
                    f"Tệp Excel vượt quá giới hạn tối đa {MAX_BATCH_ROWS} doanh nghiệp mỗi lô."
                )

            company_name = str(row_map.get("company_name") or "").strip()
            tax_code_raw = row_map.get("tax_code")
            tax_code = str(tax_code_raw).strip()[:20] if tax_code_raw is not None else None
            if tax_code == "":
                tax_code = None

            sector_raw = row_map.get("sector_name")
            sector_name = str(sector_raw).strip()[:120] if sector_raw is not None else None
            if sector_name == "":
                sector_name = None

            btype = str(row_map.get("business_type") or "manufacturing").strip().lower()
            if btype not in _VALID_BUSINESS_TYPES:
                btype = "manufacturing"

            lstatus = str(row_map.get("listing_status") or "unlisted").strip().lower()
            if lstatus not in _VALID_LISTING_STATUSES:
                lstatus = "unlisted"

            fiscal_year = _parse_int_or_none(row_map.get("fiscal_year"))

            std = str(row_map.get("accounting_standard") or "TT99_2025").strip().upper()
            if std not in _VALID_STANDARDS:
                std = "TT99_2025"

            audit = str(row_map.get("audit_status") or "unaudited").strip().lower()
            if audit not in _VALID_AUDIT_STATUSES:
                audit = "unaudited"

            currency = str(row_map.get("currency") or "VND").strip().upper()
            if currency not in ("VND", "USD"):
                currency = "VND"

            raw_scale = _parse_int_or_none(row_map.get("unit_scale"))
            unit_scale = raw_scale if raw_scale in ALLOWED_UNIT_SCALES else 1

            numeric_fields: dict[str, float | None] = {
                col: _parse_cell_number(row_map.get(col)) for col in BATCH_NUMERIC_COLUMNS
            }

            parsed_rows.append(
                ParsedBatchRow(
                    row_index=len(parsed_rows) + 1,
                    company_name=company_name or f"Doanh nghiệp dòng {excel_row_num}",
                    tax_code=tax_code,
                    sector_name=sector_name,
                    business_type=btype,
                    listing_status=lstatus,
                    fiscal_year=fiscal_year,
                    accounting_standard=std,
                    audit_status=audit,
                    currency=currency,
                    unit_scale=unit_scale,
                    numeric_fields=numeric_fields,
                )
            )
    finally:
        wb.close()

    if not parsed_rows:
        raise EtlProcessingError("Không có dòng doanh nghiệp nào để thẩm định trong tệp Excel.")

    return ParsedBatchWorkbook(rows=parsed_rows)


def sort_batch_rows_by_risk(rows: Sequence[OrgBatchJobRow]) -> list[OrgBatchJobRow]:
    """Rank batch rows by pd_12m descending (highest risk first), then excluded/failed."""

    def _sort_key(row: OrgBatchJobRow) -> tuple[int, float, int]:
        if row.status == "succeeded" and row.pd_12m is not None and isfinite(row.pd_12m):
            return (0, -float(row.pd_12m), row.row_index)
        if row.status == "excluded":
            return (1, 0.0, row.row_index)
        return (2, 0.0, row.row_index)

    return sorted(rows, key=_sort_key)


def generate_batch_export_bytes(
    job: OrgBatchJob,
    rows: Sequence[OrgBatchJobRow],
) -> bytes:
    """Export a 2-sheet Excel summary & risk-ranked results workbook for a batch job."""
    ranked = sort_batch_rows_by_risk(rows)
    wb = Workbook()

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    section_font = Font(bold=True, color="0F172A")

    # Sheet 1: Portfolio Summary
    summary_ws = wb.active
    assert summary_ws is not None
    summary_ws.title = "TomTatDanhMuc"
    summary_ws.append(["Chỉ tiêu tổng hợp", "Giá trị"])
    for cell in summary_ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    tier_counts: dict[str, int] = {"STRONG": 0, "STABLE": 0, "WATCH": 0, "CRITICAL": 0}
    pds: list[float] = []
    scores: list[float] = []
    excluded_count = 0
    for row in ranked:
        if row.status == "excluded":
            excluded_count += 1
        elif row.status == "succeeded":
            if row.risk_tier in tier_counts:
                tier_counts[row.risk_tier] += 1
            if row.pd_12m is not None and isfinite(row.pd_12m):
                pds.append(float(row.pd_12m))
            if row.health_score is not None and isfinite(row.health_score):
                scores.append(float(row.health_score))

    avg_pd = sum(pds) / len(pds) if pds else None
    avg_health = sum(scores) / len(scores) if scores else None

    summary_rows: list[tuple[str, Any]] = [
        ("Mã lô (Job ID)", job.id),
        ("Tên tệp nguồn", job.filename),
        ("Trạng thái xử lý", job.status),
        ("Phiên bản mô hình", job.model_version or "—"),
        ("Tổng số doanh nghiệp", job.total_rows),
        ("Chấm điểm thành công", job.succeeded_rows),
        ("Loại trừ (Tổ chức tài chính)", excluded_count),
        ("Dòng lỗi dữ liệu", job.failed_rows),
        ("PD 12 tháng trung bình (%)", round(avg_pd * 100.0, 2) if avg_pd is not None else None),
        ("Điểm Sức khỏe trung bình", round(avg_health, 2) if avg_health is not None else None),
        ("Nhóm Vững mạnh (STRONG)", tier_counts["STRONG"]),
        ("Nhóm Ổn định (STABLE)", tier_counts["STABLE"]),
        ("Nhóm Cần theo dõi sát (WATCH)", tier_counts["WATCH"]),
        ("Nhóm Nguy cơ cao (CRITICAL)", tier_counts["CRITICAL"]),
        ("Miễn trừ pháp lý", LEGAL_DISCLAIMER_VI),
    ]
    for label, val in summary_rows:
        summary_ws.append([label, val])
        summary_ws.cell(row=summary_ws.max_row, column=1).font = section_font

    summary_ws.column_dimensions["A"].width = 34
    summary_ws.column_dimensions["B"].width = 76

    # Sheet 2: Ranked Results
    res_ws = wb.create_sheet(title="KetQuaXepHang")
    res_headers = [
        "Hạng rủi ro",
        "Dòng gốc",
        "Tên doanh nghiệp",
        "Mã số thuế",
        "Năm TC",
        "Trạng thái",
        "PD 12 tháng (%)",
        "Điểm Sức khỏe",
        "Nhóm rủi ro",
        "Độ tin cậy",
        "Altman Z",
        "Điểm nghẽn hàng đầu",
        "Thanh toán NH",
        "Nợ / Tổng TS",
        "ROA (%)",
        "Ghi chú lỗi",
    ]
    res_ws.append(res_headers)
    for cell in res_ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="left")

    rank_counter = 0
    for row in ranked:
        if row.status == "succeeded":
            rank_counter += 1
            rank_val: int | None = rank_counter
        else:
            rank_val = None
        result_meta = row.result_json or {}
        ratios = result_meta.get("ratios") or {}
        altman_score = result_meta.get("altman_z_score")
        roa_val = ratios.get("roa")

        res_ws.append(
            [
                rank_val,
                row.row_index,
                row.company_name,
                row.tax_code,
                row.fiscal_year,
                row.status,
                round(row.pd_12m * 100.0, 2) if row.pd_12m is not None else None,
                round(row.health_score, 2) if row.health_score is not None else None,
                _RISK_TIER_LABELS_VI.get(row.risk_tier or "", row.risk_tier),
                row.confidence_level,
                round(float(altman_score), 2) if isinstance(altman_score, (int, float)) else None,
                row.top_bottleneck_vi,
                round(float(ratios["current_ratio"]), 2)
                if isinstance(ratios.get("current_ratio"), (int, float))
                else None,
                round(float(ratios["debt_ratio"]), 4)
                if isinstance(ratios.get("debt_ratio"), (int, float))
                else None,
                round(float(roa_val) * 100.0, 2) if isinstance(roa_val, (int, float)) else None,
                row.error_message,
            ]
        )

    widths = [12, 10, 32, 16, 10, 12, 16, 15, 22, 12, 12, 42, 14, 14, 12, 46]
    for idx, width in enumerate(widths, start=1):
        col_letter = res_ws.cell(row=1, column=idx).column_letter
        res_ws.column_dimensions[col_letter].width = width

    out = BytesIO()
    wb.save(out)
    return out.getvalue()
