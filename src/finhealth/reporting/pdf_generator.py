"""Executive A4 Vietnamese PDF report generator (M12) using ReportLab + Matplotlib Agg."""

from datetime import datetime, timezone
from io import BytesIO
from math import isfinite, pi
from pathlib import Path
from threading import Lock
from typing import Any
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from finhealth.api.schemas.analytics import (
    LEGAL_DISCLAIMER_VI,
    BusinessDriverView,
    CompanyAssessmentView,
    MultiPeriodHistoryPointView,
    PillarView,
)

_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_REGULAR = "FinHealthSans"
_FONT_BOLD = "FinHealthSans-Bold"
_FONT_MONO = "FinHealthMono"
_FONT_LOCK = Lock()
_FONTS_REGISTERED = False

_TIER_COLORS: dict[str | None, str] = {
    "STRONG": "#15803D",
    "STABLE": "#1D4ED8",
    "WATCH": "#B45309",
    "CRITICAL": "#B91C1C",
    None: "#475569",
}

_TIER_BG_COLORS: dict[str | None, str] = {
    "STRONG": "#DCFCE7",
    "STABLE": "#DBEAFE",
    "WATCH": "#FEF3C7",
    "CRITICAL": "#FEE2E2",
    None: "#F1F5F9",
}

_CONFIDENCE_LABELS_VI: dict[str, str] = {
    "HIGH": "Cao (Đáng tin cậy)",
    "MODERATE": "Trung bình (Cần đối chiếu thêm)",
    "LOW": "Thấp (Thiếu dữ liệu / Ngoại lệ)",
}

_AUDIT_LABELS_VI: dict[str, str] = {
    "audited_unqualified": "Đã kiểm toán — Chấp nhận toàn phần",
    "audited_qualified": "Đã kiểm toán — Ý kiến ngoại trừ",
    "audited_adverse_disclaimer": "Đã kiểm toán — Trái ngược / Từ chối",
    "unaudited": "Chưa kiểm toán / Tự lập",
}

_BUSINESS_TYPE_LABELS_VI: dict[str, str] = {
    "manufacturing": "Sản xuất",
    "trade_service": "Thương mại & Dịch vụ",
    "financial_institution": "Tổ chức Tài chính (Loại trừ)",
}

_METRIC_STATUS_LABELS_VI: dict[str, str] = {
    "GOOD": "Tốt",
    "NEUTRAL": "Trung bình",
    "WARNING": "Cảnh báo",
    "CRITICAL": "Nguy hiểm",
    "UNAVAILABLE": "Thiếu số liệu",
}


def ensure_valid_pdf_bytes(buffer: BytesIO) -> bytes:
    """Return generated PDF bytes after verifying standard PDF header integrity."""
    payload = buffer.getvalue()
    if not payload.startswith(b"%PDF-"):
        raise RuntimeError("PDF generator did not produce a valid PDF stream")
    return payload


def _ensure_fonts_registered() -> None:
    """Lazily register bundled Unicode TTF fonts once per process."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    with _FONT_LOCK:
        if _FONTS_REGISTERED:
            return
        regular_path = _FONTS_DIR / "DejaVuSans.ttf"
        bold_path = _FONTS_DIR / "DejaVuSans-Bold.ttf"
        mono_path = _FONTS_DIR / "DejaVuSansMono.ttf"
        if not regular_path.is_file() or not bold_path.is_file():
            raise RuntimeError(
                f"Missing bundled Unicode fonts in {_FONTS_DIR}; expected DejaVuSans*.ttf"
            )
        pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(regular_path)))
        pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(bold_path)))
        if mono_path.is_file():
            pdfmetrics.registerFont(TTFont(_FONT_MONO, str(mono_path)))
        registerFontFamily(
            _FONT_REGULAR,
            normal=_FONT_REGULAR,
            bold=_FONT_BOLD,
            italic=_FONT_REGULAR,
            boldItalic=_FONT_BOLD,
        )
        _FONTS_REGISTERED = True


def _safe_text(value: Any, fallback: str = "—") -> str:
    """Escape dynamic text for ReportLab Paragraph XML markup."""
    if value is None:
        return fallback
    text = str(value).strip()
    return escape(text) if text else fallback


def _fmt_pct(value: float | None, decimals: int = 2) -> str:
    """Format a 0..1 ratio as a Vietnamese percentage string."""
    if value is None or not isfinite(value):
        return "—"
    return f"{value * 100:.{decimals}f}%".replace(".", ",")


def _fmt_num(value: float | None, decimals: int = 2) -> str:
    """Format a finite float with Vietnamese decimal comma."""
    if value is None or not isfinite(value):
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",")


def _fmt_yoy(value: float | None, unit: str) -> str:
    """Format a YoY delta cleanly according to metric unit."""
    if value is None or not isfinite(value):
        return "—"
    sign = "+" if value > 0 else ""
    if unit == "percent":
        return f"{sign}{value * 100:.1f} đpt".replace(".", ",")
    if unit == "days":
        return f"{sign}{value:.0f} ngày"
    return f"{sign}{value:.2f}".replace(".", ",")


def _render_radar_chart_png(pillars: list[PillarView]) -> BytesIO | None:
    """Render the 5-pillar radar chart as a 200 DPI PNG using Matplotlib Agg."""
    if not pillars:
        return None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [p.label_vi for p in pillars]
    scores = [
        float(p.score) if p.score is not None and isfinite(p.score) else 0.0
        for p in pillars
    ]
    n = len(labels)
    angles = [idx / float(n) * 2.0 * pi for idx in range(n)]
    angles_closed = angles + angles[:1]
    scores_closed = scores + scores[:1]

    fig = plt.figure(figsize=(4.4, 3.6), dpi=200)
    try:
        plt.rcParams["font.family"] = "DejaVu Sans"
        ax: Any = fig.add_subplot(111, polar=True)
        ax.set_theta_offset(pi / 2)
        ax.set_theta_direction(-1)

        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(["25", "50", "75", "100"], fontsize=7, color="#64748B")
        ax.set_xticks(angles)
        ax.set_xticklabels(labels, fontsize=8, fontweight="bold", color="#0F172A")
        ax.grid(color="#CBD5E1", linestyle="--", linewidth=0.6)
        ax.spines["polar"].set_color("#94A3B8")

        ax.plot(angles_closed, scores_closed, color="#1D4ED8", linewidth=2.0)
        ax.fill(angles_closed, scores_closed, color="#3B82F6", alpha=0.22)
        ax.scatter(angles, scores, color="#1E3A8A", s=24, zorder=5)

        fig.tight_layout(pad=1.0)
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        buf.seek(0)
        return buf
    finally:
        plt.close(fig)


def _render_history_chart_png(
    history: list[MultiPeriodHistoryPointView],
) -> BytesIO | None:
    """Render a multi-period Health Score & PD 12m trajectory PNG with Matplotlib Agg."""
    valid_points = [
        pt
        for pt in history
        if (pt.health_score is not None and isfinite(pt.health_score))
        or (pt.pd_12m is not None and isfinite(pt.pd_12m))
    ]
    if len(valid_points) < 2:
        return None

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    years = [str(pt.fiscal_year) for pt in valid_points]
    health_vals = [
        float(pt.health_score) if pt.health_score is not None else float("nan")
        for pt in valid_points
    ]
    pd_vals = [
        float(pt.pd_12m) * 100.0 if pt.pd_12m is not None else float("nan")
        for pt in valid_points
    ]

    fig, ax1 = plt.subplots(figsize=(6.8, 2.5), dpi=200)
    try:
        plt.rcParams["font.family"] = "DejaVu Sans"
        x_pos = list(range(len(years)))

        line1 = ax1.plot(
            x_pos,
            health_vals,
            color="#1D4ED8",
            marker="o",
            linewidth=2.0,
            label="Điểm Sức khỏe (0–100)",
        )
        ax1.set_ylim(0, 105)
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(years, fontsize=8, color="#0F172A")
        ax1.set_ylabel("Điểm Sức khỏe", fontsize=8, color="#1D4ED8")
        ax1.tick_params(axis="y", labelsize=8, labelcolor="#1D4ED8")
        ax1.grid(axis="y", color="#E2E8F0", linestyle="--", linewidth=0.6)

        ax2 = ax1.twinx()
        line2 = ax2.plot(
            x_pos,
            pd_vals,
            color="#DC2626",
            marker="s",
            linestyle="--",
            linewidth=1.8,
            label="Xác suất rủi ro 12T (%)",
        )
        max_pd = max((v for v in pd_vals if isfinite(v)), default=10.0)
        ax2.set_ylim(0, max(12.0, max_pd * 1.25))
        ax2.set_ylabel("PD 12 tháng (%)", fontsize=8, color="#DC2626")
        ax2.tick_params(axis="y", labelsize=8, labelcolor="#DC2626")

        lines = line1 + line2
        labels = [str(ln.get_label()) for ln in lines]
        ax1.legend(lines, labels, loc="upper left", fontsize=7.5, frameon=True)
        ax1.set_title("Diễn biến Điểm Sức khỏe & Xác suất Rủi ro qua các kỳ", fontsize=9, pad=8)

        fig.tight_layout(pad=0.8)
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        buf.seek(0)
        return buf
    finally:
        plt.close(fig)


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create consistent Vietnamese typography styles for the A4 report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "FinHealthTitle",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#FFFFFF"),
        ),
        "subtitle": ParagraphStyle(
            "FinHealthSubtitle",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#E2E8F0"),
        ),
        "h2": ParagraphStyle(
            "FinHealthH2",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=6,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "FinHealthBody",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=8.5,
            leading=12.5,
            textColor=colors.HexColor("#1E293B"),
        ),
        "body_bold": ParagraphStyle(
            "FinHealthBodyBold",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=8.5,
            leading=12.5,
            textColor=colors.HexColor("#0F172A"),
        ),
        "small": ParagraphStyle(
            "FinHealthSmall",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=7.5,
            leading=10.5,
            textColor=colors.HexColor("#475569"),
        ),
        "kpi_label": ParagraphStyle(
            "FinHealthKpiLabel",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
        ),
        "kpi_value": ParagraphStyle(
            "FinHealthKpiValue",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=17,
            leading=21,
            textColor=colors.HexColor("#0F172A"),
            alignment=TA_CENTER,
        ),
        "table_hdr": ParagraphStyle(
            "FinHealthTableHdr",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#FFFFFF"),
            alignment=TA_LEFT,
        ),
        "table_cell": ParagraphStyle(
            "FinHealthTableCell",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=7.2,
            leading=9.8,
            textColor=colors.HexColor("#1E293B"),
        ),
        "table_cell_right": ParagraphStyle(
            "FinHealthTableCellRight",
            parent=base["Normal"],
            fontName=_FONT_REGULAR,
            fontSize=7.2,
            leading=9.8,
            textColor=colors.HexColor("#1E293B"),
            alignment=TA_RIGHT,
        ),
    }


def _driver_cell_paragraph(
    drivers: list[BusinessDriverView],
    styles: dict[str, ParagraphStyle],
    empty_text: str,
) -> Paragraph:
    """Format up to 5 Strength or Bottleneck items into one rich Paragraph."""
    if not drivers:
        return Paragraph(_safe_text(empty_text), styles["small"])
    lines: list[str] = []
    for item in drivers[:5]:
        share = _fmt_num(item.impact_share_pct, 1)
        lines.append(
            f"<b>• {_safe_text(item.label_vi)}</b> ({_safe_text(item.formatted_value_vi)}, "
            f"tỷ trọng {share}%): {_safe_text(item.headline_vi)}"
        )
    return Paragraph("<br/>".join(lines), styles["body"])


def generate_company_assessment_pdf(
    assessment: CompanyAssessmentView,
    *,
    generated_at: datetime | None = None,
    assessment_ref: str | None = None,
) -> bytes:
    """Generate a 3-page A4 Vietnamese PDF report from a CompanyAssessmentView."""
    _ensure_fonts_registered()
    styles = _build_styles()
    timestamp = generated_at or datetime.now(timezone.utc)
    ts_str = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ref_code = assessment_ref or f"FH-{assessment.company.id}-{assessment.company.fiscal_year or 0}"
    disclaimer = assessment.summary.legal_disclaimer_vi or LEGAL_DISCLAIMER_VI
    model_version = assessment.summary.model_version

    buffer = BytesIO()
    page_w, _page_h = A4
    margin_x = 15 * mm
    usable_w = page_w - 2 * margin_x

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin_x,
        rightMargin=margin_x,
        topMargin=16 * mm,
        bottomMargin=24 * mm,
        title=f"Báo cáo Thẩm định Tài chính - {assessment.company.name}",
        author="FinHealth",
    )

    def _draw_footer(canvas_obj: Any, doc_obj: Any) -> None:
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas_obj.setLineWidth(0.6)
        canvas_obj.line(margin_x, 19.5 * mm, page_w - margin_x, 19.5 * mm)

        canvas_obj.setFont(_FONT_BOLD, 6.8)
        canvas_obj.setFillColor(colors.HexColor("#334155"))
        meta_line = (
            f"Mô hình: {model_version}  |  Trích xuất: {ts_str}  |  Mã hồ sơ: {ref_code}"
        )
        canvas_obj.drawString(margin_x, 16 * mm, meta_line)
        canvas_obj.drawRightString(page_w - margin_x, 16 * mm, f"Trang {doc_obj.page}")

        canvas_obj.setFont(_FONT_REGULAR, 6.2)
        canvas_obj.setFillColor(colors.HexColor("#64748B"))
        # Wrap legal disclaimer cleanly across 2 lines at bottom margin.
        words = disclaimer.split()
        line1_parts: list[str] = []
        line2_parts: list[str] = []
        for word in words:
            candidate = " ".join(line1_parts + [word])
            if pdfmetrics.stringWidth(candidate, _FONT_REGULAR, 6.2) <= usable_w:
                line1_parts.append(word)
            else:
                line2_parts.append(word)
        canvas_obj.drawString(margin_x, 11.8 * mm, " ".join(line1_parts))
        if line2_parts:
            canvas_obj.drawString(margin_x, 8.6 * mm, " ".join(line2_parts))
        canvas_obj.restoreState()

    story: list[Any] = []
    comp = assessment.company
    summ = assessment.summary
    altman = assessment.altman

    # =========================================================================
    # PAGE 1 — EXECUTIVE SUMMARY
    # =========================================================================
    banner_table = Table(
        [
            [
                Paragraph("BÁO CÁO THẨM ĐỊNH SỨC KHỎE TÀI CHÍNH DOANH NGHIỆP", styles["title"]),
            ],
            [
                Paragraph(
                    f"Đơn vị được thẩm định: <b>{_safe_text(comp.name)}</b>  |  "
                    f"Kỳ BCTC: <b>{_safe_text(comp.fiscal_year)}</b>  |  "
                    f"Chuẩn kế toán: <b>{_safe_text(comp.accounting_standard)}</b>",
                    styles["subtitle"],
                )
            ],
        ],
        colWidths=[usable_w],
    )
    banner_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (0, 0), 9),
                ("BOTTOMPADDING", (0, 1), (0, 1), 9),
            ]
        )
    )
    story.append(banner_table)
    story.append(Spacer(1, 4 * mm))

    latest_audit = (
        assessment.history[-1].audit_status
        if assessment.history
        else (summ.confidence.audit_status if summ.confidence else "unaudited")
    )
    meta_rows = [
        [
            Paragraph("<b>Tên doanh nghiệp</b>", styles["small"]),
            Paragraph(_safe_text(comp.name), styles["body"]),
            Paragraph("<b>MST / Mã CK</b>", styles["small"]),
            Paragraph(
                _safe_text(
                    " / ".join(p for p in (comp.tax_code, comp.ticker) if p) or None
                ),
                styles["body"],
            ),
        ],
        [
            Paragraph("<b>Ngành nghề</b>", styles["small"]),
            Paragraph(_safe_text(comp.sector_name or comp.sector_code), styles["body"]),
            Paragraph("<b>Loại hình</b>", styles["small"]),
            Paragraph(
                _safe_text(_BUSINESS_TYPE_LABELS_VI.get(comp.business_type, comp.business_type)),
                styles["body"],
            ),
        ],
        [
            Paragraph("<b>Chuẩn BCTC & Tiền tệ</b>", styles["small"]),
            Paragraph(
                f"{_safe_text(comp.accounting_standard)} ({_safe_text(comp.currency, 'VND')})",
                styles["body"],
            ),
            Paragraph("<b>Trạng thái kiểm toán</b>", styles["small"]),
            Paragraph(
                _safe_text(_AUDIT_LABELS_VI.get(latest_audit, latest_audit)),
                styles["body"],
            ),
        ],
    ]
    meta_table = Table(
        meta_rows,
        colWidths=[usable_w * 0.20, usable_w * 0.30, usable_w * 0.20, usable_w * 0.30],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1. Tóm tắt Điều hành (Executive Summary)", styles["h2"]))

    if not summ.scoring_eligible or comp.business_type == "financial_institution":
        excl_reason = (
            summ.unavailable_reason_vi
            or altman.unavailable_reason_vi
            or "Mô hình đánh giá rủi ro phá sản doanh nghiệp phi tài chính không áp dụng "
            "cho Ngân hàng, Bảo hiểm và Tổ chức tài chính."
        )
        excl_box = Table(
            [
                [
                    Paragraph(
                        "<b>THÔNG BÁO LOẠI TRỪ TỔ CHỨC TÀI CHÍNH</b><br/>"
                        f"{_safe_text(excl_reason)}",
                        styles["body"],
                    )
                ]
            ],
            colWidths=[usable_w],
        )
        excl_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                    ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#D97706")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(excl_box)
        story.append(Spacer(1, 3 * mm))
    else:
        tier_hex = _TIER_COLORS.get(summ.risk_tier, "#475569")
        tier_bg = _TIER_BG_COLORS.get(summ.risk_tier, "#F1F5F9")
        score_txt = (
            f"{_fmt_num(summ.health_score, 1)} / 100" if summ.health_score is not None else "—"
        )
        pd_txt = _fmt_pct(summ.pd_12m, 2)
        conf_lvl = summ.confidence.level if summ.confidence else "LOW"
        conf_txt = _CONFIDENCE_LABELS_VI.get(conf_lvl, conf_lvl)
        completeness_txt = (
            _fmt_pct(summ.confidence.input_completeness, 0) if summ.confidence else "—"
        )

        kpi_table = Table(
            [
                [
                    Paragraph("ĐIỂM SỨC KHỎE TỔNG HỢP", styles["kpi_label"]),
                    Paragraph("XÁC SUẤT RỦI RO 12 THÁNG (PD)", styles["kpi_label"]),
                    Paragraph("ĐỘ TIN CẬY ĐÁNH GIÁ (4 LỚP)", styles["kpi_label"]),
                ],
                [
                    Paragraph(
                        f"<font color='{tier_hex}'>{score_txt}</font><br/>"
                        f"<font size='8.5' color='{tier_hex}'><b>"
                        f"{_safe_text(summ.risk_label_vi)}</b></font>",
                        styles["kpi_value"],
                    ),
                    Paragraph(
                        f"<font color='{tier_hex}'>{pd_txt}</font><br/>"
                        f"<font size='8' color='#475569'>Chế độ: "
                        f"{_safe_text(summ.scoring_mode)}</font>",
                        styles["kpi_value"],
                    ),
                    Paragraph(
                        f"<font size='10.5'><b>{_safe_text(conf_txt)}</b></font><br/>"
                        f"<font size='8' color='#475569'>Đầy đủ dữ liệu: {completeness_txt}</font>",
                        styles["kpi_value"],
                    ),
                ],
            ],
            colWidths=[usable_w / 3.0] * 3,
        )
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 1), colors.HexColor(tier_bg)),
                    ("BACKGROUND", (1, 0), (2, 1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (0, 1), 1.0, colors.HexColor(tier_hex)),
                    ("BOX", (1, 0), (1, 1), 0.6, colors.HexColor("#CBD5E1")),
                    ("BOX", (2, 0), (2, 1), 0.6, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(kpi_table)
        story.append(Spacer(1, 3 * mm))

        # Altman Z / Z' / Z'' box
        if altman.applicable and altman.score is not None:
            alt_text = (
                f"<b>Thước đo Altman ({_safe_text(altman.variant)}):</b> "
                f"Điểm = <b>{_fmt_num(altman.score, 2)}</b>  |  "
                f"Phân vùng: <b>{_safe_text(altman.zone_label_vi or altman.zone)}</b>  |  "
                f"Ngưỡng cảnh báo / an toàn: {_fmt_num(altman.cutoff_low, 2)} / "
                f"{_fmt_num(altman.cutoff_high, 2)}"
            )
            if altman.fallback_note_vi:
                alt_text += f"<br/><i>Ghi chú: {_safe_text(altman.fallback_note_vi)}</i>"
        else:
            alt_text = (
                "<b>Thước đo Altman:</b> Chưa khả dụng — "
                f"{_safe_text(altman.unavailable_reason_vi, 'Thiếu khoản mục cấu thành.')}"
            )
        alt_table = Table([[Paragraph(alt_text, styles["body"])]], colWidths=[usable_w])
        alt_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#93C5FD")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(alt_table)
        story.append(Spacer(1, 3 * mm))

    # Confidence reasons (4-layer details)
    if summ.confidence and summ.confidence.reasons_vi:
        conf_lines = "<br/>".join(
            f"• {_safe_text(reason)}" for reason in summ.confidence.reasons_vi[:4]
        )
        story.append(Paragraph("<b>Chi tiết Độ tin cậy 4 lớp:</b>", styles["body_bold"]))
        story.append(Paragraph(conf_lines, styles["small"]))
        story.append(Spacer(1, 2.5 * mm))

    # Top 3 Takeaways
    story.append(Paragraph("3 Nhận định Trọng tâm", styles["h2"]))
    takeaways = summ.top_3_takeaways_vi or [
        "Chưa đủ dữ liệu để tổng hợp nhận định điều hành cho kỳ này."
    ]
    takeaway_rows = [
        [Paragraph(f"<b>{idx}.</b> {_safe_text(item)}", styles["body"])]
        for idx, item in enumerate(takeaways[:3], start=1)
    ]
    tk_table = Table(takeaway_rows, colWidths=[usable_w])
    tk_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("LINEBEFORE", (0, 0), (0, -1), 3.0, colors.HexColor("#1D4ED8")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tk_table)

    # =========================================================================
    # PAGE 2 — 5 PILLARS RADAR, STRENGTHS & BOTTLENECKS, CASH FLOW / QoE
    # =========================================================================
    story.append(PageBreak())
    story.append(
        Paragraph("2. Phân tích 5 Trụ cột Tài chính & Điểm Tựa / Điểm Nghẽn", styles["h2"])
    )

    radar_buf = _render_radar_chart_png(assessment.pillars.pillars)
    pillar_rows: list[list[Any]] = [
        [
            Paragraph("Trụ cột", styles["table_hdr"]),
            Paragraph("Trọng số", styles["table_hdr"]),
            Paragraph("Điểm", styles["table_hdr"]),
            Paragraph("Trạng thái", styles["table_hdr"]),
        ]
    ]
    for p in assessment.pillars.pillars:
        pillar_rows.append(
            [
                Paragraph(_safe_text(p.label_vi), styles["table_cell"]),
                Paragraph(_fmt_pct(p.weight, 0), styles["table_cell_right"]),
                Paragraph(_fmt_num(p.score, 1), styles["table_cell_right"]),
                Paragraph(_safe_text(p.status), styles["table_cell"]),
            ]
        )
    pillar_summary_tbl = Table(
        pillar_rows,
        colWidths=[usable_w * 0.22, usable_w * 0.09, usable_w * 0.08, usable_w * 0.11],
    )
    pillar_summary_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    if radar_buf is not None:
        radar_img = Image(radar_buf, width=usable_w * 0.48, height=70 * mm, kind="proportional")
        radar_grid = Table(
            [[radar_img, pillar_summary_tbl]],
            colWidths=[usable_w * 0.49, usable_w * 0.51],
        )
        radar_grid.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(radar_grid)
    else:
        story.append(pillar_summary_tbl)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Điểm Tựa & Điểm Nghẽn Tài Chính", styles["h2"]))

    drivers_tbl = Table(
        [
            [
                Paragraph("ĐIỂM TỰA TÀI CHÍNH (TÍCH CỰC)", styles["table_hdr"]),
                Paragraph("ĐIỂM NGHẼN TÀI CHÍNH (RỦI RO)", styles["table_hdr"]),
            ],
            [
                _driver_cell_paragraph(
                    assessment.drivers.strengths,
                    styles,
                    "Chưa ghi nhận điểm tựa nổi bật trong kỳ này.",
                ),
                _driver_cell_paragraph(
                    assessment.drivers.bottlenecks,
                    styles,
                    "Không ghi nhận điểm nghẽn rủi ro nghiêm trọng.",
                ),
            ],
        ],
        colWidths=[usable_w * 0.5, usable_w * 0.5],
    )
    drivers_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#15803D")),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#B91C1C")),
                ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#F0FDF4")),
                ("BACKGROUND", (1, 1), (1, 1), colors.HexColor("#FEF2F2")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(drivers_tbl)
    story.append(Spacer(1, 4 * mm))

    # Cash-Flow Overlay & QoE
    story.append(Paragraph("Cảnh báo Dòng tiền & Chất lượng Lợi nhuận (QoE)", styles["h2"]))
    overlay_notes: list[str] = []
    if assessment.pillars.is_negative_equity:
        overlay_notes.append(
            "• <b>Cảnh báo Âm Vốn chủ sở hữu:</b> Doanh nghiệp có VCSH ≤ 0; "
            "các chỉ số đòn bẩy và ROE bị phạt về 0 điểm theo chuẩn thẩm định."
        )
    if summ.cash_flow_overlay and summ.cash_flow_overlay.triggered:
        for reason in summ.cash_flow_overlay.reasons_vi:
            overlay_notes.append(f"• <b>Cảnh báo dòng tiền / kiểm toán:</b> {_safe_text(reason)}")
    qoe_data = assessment.diagnostics.quality_of_earnings or {}
    qoe_status = qoe_data.get("status") or qoe_data.get("label") or qoe_data.get("assessment")
    qoe_ratio = qoe_data.get("cash_conversion_ratio") or qoe_data.get("ocf_to_net_income")
    if qoe_status or qoe_ratio is not None:
        overlay_notes.append(
            f"• <b>Chất lượng lợi nhuận (QoE):</b> Trạng thái: {_safe_text(qoe_status)}  |  "
            f"Tỷ lệ chuyển hóa tiền (OCF/LNST): "
            f"{_fmt_num(float(qoe_ratio), 2) if isinstance(qoe_ratio, (int, float)) else '—'}"
        )
    if not overlay_notes:
        overlay_notes.append(
            "• Không phát sinh cảnh báo dòng tiền bất thường hay ngoại lệ kiểm toán trọng yếu."
        )

    qoe_box = Table(
        [[Paragraph("<br/>".join(overlay_notes), styles["body"])]],
        colWidths=[usable_w],
    )
    qoe_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#F59E0B")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(qoe_box)

    # =========================================================================
    # PAGE 3 — 20-METRIC TABLE & MULTI-PERIOD HISTORY CHART
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("3. Bảng 20 Chỉ số Tài chính Cốt lõi & Diễn biến Đa kỳ", styles["h2"]))

    metric_rows: list[list[Any]] = [
        [
            Paragraph("Trụ cột", styles["table_hdr"]),
            Paragraph("Chỉ số tài chính", styles["table_hdr"]),
            Paragraph("Giá trị", styles["table_hdr"]),
            Paragraph("Biến động YoY", styles["table_hdr"]),
            Paragraph("Ngưỡng / Vị thế ngành", styles["table_hdr"]),
            Paragraph("Trạng thái", styles["table_hdr"]),
        ]
    ]
    for pillar in assessment.pillars.pillars:
        for metric in pillar.metrics:
            peer_txt = (
                metric.peer_position.position_label_vi
                if metric.peer_position is not None
                else metric.reference_range_vi
            )
            metric_rows.append(
                [
                    Paragraph(_safe_text(pillar.label_vi), styles["table_cell"]),
                    Paragraph(_safe_text(metric.label_vi), styles["table_cell"]),
                    Paragraph(_safe_text(metric.formatted_value_vi), styles["table_cell_right"]),
                    Paragraph(
                        _fmt_yoy(metric.yoy_change, metric.unit),
                        styles["table_cell_right"],
                    ),
                    Paragraph(_safe_text(peer_txt), styles["table_cell"]),
                    Paragraph(
                        _safe_text(_METRIC_STATUS_LABELS_VI.get(metric.status, metric.status)),
                        styles["table_cell"],
                    ),
                ]
            )

    metrics_tbl = Table(
        metric_rows,
        colWidths=[
            usable_w * 0.16,
            usable_w * 0.25,
            usable_w * 0.11,
            usable_w * 0.12,
            usable_w * 0.25,
            usable_w * 0.11,
        ],
        repeatRows=1,
    )
    metrics_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(metrics_tbl)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Diễn biến Đa kỳ (3–5 năm)", styles["h2"]))
    history_buf = _render_history_chart_png(assessment.history)
    if history_buf is not None:
        hist_img = Image(history_buf, width=usable_w, height=56 * mm, kind="proportional")
        story.append(hist_img)
    else:
        story.append(
            Paragraph(
                "Chưa đủ dữ liệu đa kỳ (cần tối thiểu 2 kỳ báo cáo đã chốt có điểm đánh giá) "
                "để hiển thị biểu đồ xu hướng.",
                styles["small"],
            )
        )

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return ensure_valid_pdf_bytes(buffer)
