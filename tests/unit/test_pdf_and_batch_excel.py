"""Unit tests for Vietnamese A4 PDF generation (M12) and Batch Excel engine (S03)."""

from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import matplotlib.pyplot as plt
import pytest
from openpyxl import Workbook, load_workbook  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.api.schemas.analytics import (
    LEGAL_DISCLAIMER_VI,
    AltmanView,
    AssessmentSummaryView,
    BusinessDriverView,
    CashFlowOverlayView,
    CompanyAssessmentView,
    ConfidenceView,
    ContextualMetricView,
    DiagnosticsView,
    DriversSplitView,
    MultiPeriodHistoryPointView,
    OrgCompanyMetaView,
    PeerContextView,
    PillarsOverviewView,
    PillarView,
)
from finhealth.core.exceptions import EtlProcessingError
from finhealth.db.account_models import Organization, User
from finhealth.db.base import Base
from finhealth.db.batch_models import OrgBatchJobRow
from finhealth.db.session import create_db_engine
from finhealth.reporting.batch_excel import (
    BATCH_COLUMNS,
    BATCH_DATA_SHEET,
    BATCH_GUIDE_SHEET,
    MAX_BATCH_FILE_BYTES,
    MAX_BATCH_ROWS,
    generate_batch_export_bytes,
    generate_batch_template_bytes,
    parse_batch_excel_bytes,
    sort_batch_rows_by_risk,
)
from finhealth.reporting.batch_worker import create_batch_job_from_upload, process_batch_job
from finhealth.reporting.pdf_generator import (
    ensure_valid_pdf_bytes,
    generate_company_assessment_pdf,
)


def _sample_pillars(is_negative_equity: bool = False) -> PillarsOverviewView:
    """Build a realistic 5-pillar overview covering 20 contextual metrics."""
    pillar_defs: list[tuple[Any, str, float, float | None, str]] = [
        ("liquidity", "Thanh khoản", 0.20, 78.0, "STRONG"),
        (
            "solvency",
            "Đòn bẩy & An toàn vốn",
            0.25,
            25.0 if is_negative_equity else 72.0,
            "ADEQUATE",
        ),
        ("profitability", "Sinh lời", 0.25, 81.5, "STRONG"),
        ("efficiency", "Hiệu quả hoạt động", 0.15, 68.0, "ADEQUATE"),
        ("cash_flow", "Dòng tiền", 0.15, 75.0, "STRONG"),
    ]
    pillars: list[PillarView] = []
    for p_key, p_label, weight, score, p_status in pillar_defs:
        metrics: list[ContextualMetricView] = []
        for idx in range(4):
            val: float | None = None if (is_negative_equity and idx == 0) else 0.12 + idx * 0.05
            metrics.append(
                ContextualMetricView(
                    key=f"{p_key}_m{idx}",
                    pillar=p_key,
                    label_vi=f"Chỉ số {p_label} #{idx + 1}",
                    value=val,
                    formatted_value_vi="—" if val is None else f"{val * 100:.1f}%",
                    unit="percent",
                    good_direction="higher",
                    reference_range_vi="≥ 10%",
                    tooltip_vi="Giải thích chỉ số tiếng Việt có dấu.",
                    status="UNAVAILABLE" if val is None else "GOOD",
                    score=None if val is None else 75.0,
                    yoy_change=None if val is None else 0.02,
                )
            )
        pillars.append(
            PillarView(
                key=p_key,
                label_vi=p_label,
                description_vi=f"Mô tả trụ cột {p_label}",
                weight=weight,
                score=score,
                status=p_status,  # type: ignore[arg-type]
                observed_metrics=sum(1 for m in metrics if m.value is not None),
                total_metrics=len(metrics),
                metrics=metrics,
            )
        )
    return PillarsOverviewView(
        overall_score=45.0 if is_negative_equity else 75.2,
        overall_status="WEAK" if is_negative_equity else "STRONG",
        is_negative_equity=is_negative_equity,
        pillars=pillars,
    )


def _sample_assessment(
    *,
    business_type: str = "manufacturing",
    is_negative_equity: bool = False,
    include_history: bool = True,
) -> CompanyAssessmentView:
    """Build a valid CompanyAssessmentView fixture covering normal, edge, and FI cases."""
    is_fi = business_type == "financial_institution"
    history: list[MultiPeriodHistoryPointView] = []
    if include_history:
        for idx, yr in enumerate((2022, 2023, 2024, 2025)):
            history.append(
                MultiPeriodHistoryPointView(
                    statement_id=100 + idx,
                    fiscal_year=yr,
                    fiscal_period="FY",
                    accounting_standard="TT200_2014" if yr < 2025 else "TT99_2025",
                    currency="VND",
                    audit_status="audited_unqualified",
                    revenues=1000.0 + idx * 120.0,
                    net_income=90.0 + idx * 15.0,
                    operating_cash_flow=110.0 + idx * 12.0,
                    total_assets=1200.0 + idx * 80.0,
                    total_liabilities=500.0 + idx * 20.0,
                    stockholders_equity=-50.0 if is_negative_equity else 700.0 + idx * 60.0,
                    debt_ratio=0.42,
                    roa=0.09,
                    current_ratio=2.1,
                    altman_variant=None if is_fi else "Z'",
                    altman_z_score=None if is_fi else 3.15 + idx * 0.1,
                    altman_zone=None if is_fi else "SAFE",
                    health_score=None if is_fi else 72.0 + idx * 2.5,
                    pd_12m=None if is_fi else max(0.005, 0.025 - idx * 0.004),
                    risk_tier=None if is_fi else "STRONG",
                )
            )

    mode: Any = "excluded" if is_fi else ("multi_period" if include_history else "single_period")
    summary = AssessmentSummaryView(
        scoring_eligible=not is_fi,
        scoring_mode=mode,
        model_version="excluded-fi" if is_fi else "v2.0.0-kaggle",
        health_score=None if is_fi else (38.5 if is_negative_equity else 82.4),
        risk_tier=None if is_fi else ("CRITICAL" if is_negative_equity else "STRONG"),
        risk_label_vi=(
            "Không áp dụng (Tổ chức tài chính)"
            if is_fi
            else ("Nguy cơ khủng hoảng cao" if is_negative_equity else "Vững mạnh")
        ),
        pd_12m=None if is_fi else (0.145 if is_negative_equity else 0.0085),
        confidence=None
        if is_fi
        else ConfidenceView(
            level="HIGH",
            input_completeness=0.95,
            is_ood=False,
            ood_features=[],
            ensemble_spread=0.012,
            audit_status="audited_unqualified",
            reasons_vi=["BCTC đã kiểm toán chấp nhận toàn phần.", "Dữ liệu đầy đủ 95%."],
        ),
        cash_flow_overlay=None
        if is_fi
        else CashFlowOverlayView(
            triggered=is_negative_equity,
            flags=["negative_ocf_streak"] if is_negative_equity else [],
            reasons_vi=(
                ["Dòng tiền kinh doanh âm kéo dài cần giám sát chặt."]
                if is_negative_equity
                else []
            ),
            original_tier="WATCH" if is_negative_equity else "STRONG",
            adjusted_tier="CRITICAL" if is_negative_equity else "STRONG",
        ),
        top_3_takeaways_vi=[
            "Sức khỏe tài chính ổn định với biên lợi nhuận cải thiện liên tục.",
            "Thanh khoản ngắn hạn duy trì trên ngưỡng an toàn 2,0 lần.",
            "Cần theo dõi vòng quay hàng tồn kho trong mùa cao điểm.",
        ],
        unavailable_reason_vi=(
            "Mô hình không áp dụng cho Ngân hàng, Bảo hiểm và Tổ chức tài chính." if is_fi else None
        ),
        legal_disclaimer_vi=LEGAL_DISCLAIMER_VI,
    )

    altman = AltmanView(
        applicable=not is_fi,
        variant=None if is_fi else "Z'",
        score=None if is_fi else 3.45,
        zone=None if is_fi else "SAFE",
        zone_label_vi=None if is_fi else "Vùng an toàn",
        cutoff_low=None if is_fi else 1.23,
        cutoff_high=None if is_fi else 2.90,
        unavailable_reason_vi=(
            "Loại trừ Tổ chức tài chính theo chuẩn Altman." if is_fi else None
        ),
    )

    drivers = DriversSplitView(
        strengths=[]
        if is_fi
        else [
            BusinessDriverView(
                factor_code="roa",
                label_vi="Tỷ suất sinh lời trên tài sản (ROA)",
                pillar="profitability",
                side="STRENGTH",
                observed_value=0.11,
                formatted_value_vi="11,0%",
                reference_range_vi="≥ 8%",
                impact_share_pct=55.0,
                impact_strength="HIGH",
                impact_strength_label_vi="Tác động mạnh",
                headline_vi="Hiệu quả sử dụng tài sản vượt trội so với trung bình ngành",
                detail_vi="ROA đạt 11,0% tạo bộ đệm lợi nhuận bền vững.",
            )
        ],
        bottlenecks=[]
        if is_fi
        else [
            BusinessDriverView(
                factor_code="debt_ratio",
                label_vi="Tỷ số Nợ trên Tổng tài sản",
                pillar="solvency",
                side="BOTTLENECK",
                observed_value=0.68,
                formatted_value_vi="68,0%",
                reference_range_vi="≤ 60%",
                impact_share_pct=45.0,
                impact_strength="MODERATE",
                impact_strength_label_vi="Tác động vừa",
                headline_vi="Áp lực đòn bẩy nợ cần kiểm soát chi phí lãi vay",
                detail_vi="Tỷ lệ nợ ở mức 68,0%.",
            )
        ],
        total_impact_share_pct=0.0 if is_fi else 100.0,
    )

    return CompanyAssessmentView(
        company=OrgCompanyMetaView(
            id=42,
            organization_id=7,
            name="Công ty CP Sản xuất & Thương mại Minh An — Việt Nam",
            tax_code="0101234567",
            ticker="MAN",
            sector_code="C",
            sector_name="Công nghiệp chế biến, chế tạo",
            business_type=business_type,
            listing_status="unlisted",
            relationship_tag="customer",
            is_sample=True,
            fiscal_year=2025,
            accounting_standard="TT99_2025",
            currency="VND",
        ),
        summary=summary,
        altman=altman,
        pillars=_sample_pillars(is_negative_equity=is_negative_equity),
        drivers=drivers,
        diagnostics=DiagnosticsView(
            dupont={"roe": 0.16},
            quality_of_earnings={"status": "STRONG", "cash_conversion_ratio": 1.18},
            accounting_checklist={"passed": True},
        ),
        history=history,
        peer_context=PeerContextView(
            benchmark_scope="sector",
            mapped_sector="Manufacturing",
            cohort_size=12,
            summary_label_vi="Top 25% tốt nhất ngành",
            metrics={},
        ),
        legal_disclaimer_vi=LEGAL_DISCLAIMER_VI,
    )


def test_pdf_generator_vietnamese_full_report_and_no_figure_leak() -> None:
    """Full VN assessment renders valid >10KB PDF with embedded TTF and closes all figures."""
    assessment = _sample_assessment(include_history=True)
    pdf_bytes = generate_company_assessment_pdf(
        assessment,
        generated_at=datetime(2026, 3, 15, 9, 30, tzinfo=timezone.utc),
        assessment_ref="UNIT-42-2025",
    )
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 10_000
    assert b"DejaVuSans" in pdf_bytes
    assert plt.get_fignums() == []


def test_pdf_generator_handles_negative_equity_none_and_missing_history() -> None:
    """PDF generator safely handles negative equity, None values, and empty history."""
    assessment = _sample_assessment(is_negative_equity=True, include_history=False)
    pdf_bytes = generate_company_assessment_pdf(assessment)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 10_000
    assert plt.get_fignums() == []


def test_pdf_generator_financial_institution_exclusion() -> None:
    """Financial institution report renders cleanly without Altman/ML scores."""
    assessment = _sample_assessment(business_type="financial_institution", include_history=False)
    pdf_bytes = generate_company_assessment_pdf(assessment)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 10_000
    assert plt.get_fignums() == []


def test_ensure_valid_pdf_bytes_rejects_invalid_stream() -> None:
    """ensure_valid_pdf_bytes raises RuntimeError when bytes do not start with %PDF-."""
    with pytest.raises(RuntimeError, match="valid PDF"):
        ensure_valid_pdf_bytes(BytesIO(b"not a pdf"))


def _make_batch_workbook_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Build an in-memory .xlsx workbook matching the FinHealth batch column schema."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = BATCH_DATA_SHEET
    headers = [col[0] for col in BATCH_COLUMNS]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(col) for col in headers])
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def test_batch_template_round_trip() -> None:
    """Generated batch Excel template opens with openpyxl and parses back cleanly."""
    tpl_bytes = generate_batch_template_bytes()
    wb = load_workbook(BytesIO(tpl_bytes), read_only=True)
    try:
        assert BATCH_GUIDE_SHEET in wb.sheetnames
        assert BATCH_DATA_SHEET in wb.sheetnames
    finally:
        wb.close()

    parsed = parse_batch_excel_bytes(tpl_bytes)
    assert len(parsed.rows) == 1
    assert "Minh An" in parsed.rows[0].company_name
    assert parsed.rows[0].fiscal_year == 2025
    assert parsed.rows[0].numeric_fields["total_assets"] == 1_200_000.0


def test_batch_worker_isolates_2_bad_rows_of_10_and_ranks_pd_desc() -> None:
    """10-company batch with 8 valid + 2 bad rows completes 8 ranked by pd_12m descending."""
    rows_data: list[dict[str, Any]] = []
    # 8 valid companies with progressively weaker solvency/profitability so PD varies.
    for idx in range(8):
        debt_frac = 0.25 + idx * 0.09
        assets = 1000.0
        liabilities = round(assets * debt_frac, 2)
        equity = round(assets - liabilities, 2)
        net_inc = 150.0 - idx * 35.0
        ocf = 160.0 - idx * 30.0
        rows_data.append(
            {
                "company_name": f"Công ty Hợp lệ #{idx + 1}",
                "tax_code": f"01000000{idx:02d}",
                "sector_name": "Sản xuất",
                "business_type": "manufacturing",
                "listing_status": "unlisted",
                "fiscal_year": 2025,
                "accounting_standard": "TT99_2025",
                "audit_status": "audited_unqualified",
                "currency": "VND",
                "unit_scale": 1_000_000,
                "total_assets": assets,
                "current_assets": 450.0,
                "cash_and_equivalents": 120.0,
                "accounts_receivable": 110.0,
                "inventory": 120.0,
                "total_liabilities": liabilities,
                "current_liabilities": round(liabilities * 0.55, 2),
                "stockholders_equity": equity,
                "retained_earnings": round(equity * 0.4, 2),
                "revenues": 900.0,
                "cost_of_goods_sold": 600.0,
                "gross_profit": 300.0,
                "operating_expenses": 150.0,
                "operating_income": net_inc + 20.0,
                "interest_expense": 15.0 + idx * 5.0,
                "net_income": net_inc,
                "operating_cash_flow": ocf,
            }
        )

    # Row 9: total_assets <= 0 (hard validation error)
    rows_data.append(
        {
            "company_name": "Công ty Lỗi Tài Sản Âm",
            "fiscal_year": 2025,
            "total_assets": 0.0,
            "total_liabilities": 100.0,
            "stockholders_equity": -100.0,
        }
    )
    # Row 10: balance sheet mismatch (TA != TL + E)
    rows_data.append(
        {
            "company_name": "Công ty Lỗi Lệch Cân Đối",
            "fiscal_year": 2025,
            "total_assets": 1000.0,
            "total_liabilities": 400.0,
            "stockholders_equity": 100.0,
        }
    )

    xlsx_bytes = _make_batch_workbook_bytes(rows_data)
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(
            email="analyst@example.com",
            display_name="Analyst",
            role="user",
            password_hash="stub-hash",
            email_verified=True,
        )
        org = Organization(name="Org Test", slug="org-test")
        db.add_all([user, org])
        db.commit()

        job = create_batch_job_from_upload(
            db,
            org_id=org.id,
            user_id=user.id,
            filename="batch_10_companies.xlsx",
            raw_bytes=xlsx_bytes,
        )
        assert job.status == "queued"
        assert job.total_rows == 10

        completed = process_batch_job(db, job_id=job.id, model_registry=None)
        assert completed.status == "completed"
        assert completed.processed_rows == 10
        assert completed.succeeded_rows == 8
        assert completed.failed_rows == 2

        rows = list(
            db.scalars(select(OrgBatchJobRow).where(OrgBatchJobRow.job_id == job.id)).all()
        )
        ranked = sort_batch_rows_by_risk(rows)
        succeeded = [r for r in ranked if r.status == "succeeded"]
        failed = [r for r in ranked if r.status == "failed"]

        assert len(succeeded) == 8
        assert len(failed) == 2
        pds = [r.pd_12m for r in succeeded]
        assert all(pd is not None for pd in pds)
        assert pds == sorted(pds, reverse=True)  # type: ignore[type-var]
        assert all(r.error_message and len(r.error_message) > 5 for r in failed)

        # Verify Excel export opens cleanly with openpyxl and preserves ranking.
        export_bytes = generate_batch_export_bytes(completed, rows)
        wb = load_workbook(BytesIO(export_bytes), read_only=True, data_only=True)
        try:
            assert "TomTatDanhMuc" in wb.sheetnames
            assert "KetQuaXepHang" in wb.sheetnames
            res_ws = wb["KetQuaXepHang"]
            exported_rows = list(res_ws.iter_rows(min_row=2, values_only=True))
            assert len(exported_rows) == 10
            exported_pds = [r[6] for r in exported_rows[:8]]
            assert exported_pds == sorted(exported_pds, reverse=True)
        finally:
            wb.close()
    engine.dispose()


def test_batch_excel_safety_limits() -> None:
    """Parser enforces 10 MB size ceiling, 500-row cap, and valid zip format."""
    with pytest.raises(EtlProcessingError, match="10 MB"):
        parse_batch_excel_bytes(b"x" * (MAX_BATCH_FILE_BYTES + 1))

    with pytest.raises(EtlProcessingError, match="Excel .xlsx"):
        parse_batch_excel_bytes(b"not-a-zip-file")

    too_many = [
        {"company_name": f"Co {i}", "fiscal_year": 2025, "total_assets": 100.0}
        for i in range(MAX_BATCH_ROWS + 1)
    ]
    with pytest.raises(EtlProcessingError, match=str(MAX_BATCH_ROWS)):
        parse_batch_excel_bytes(_make_batch_workbook_bytes(too_many))
