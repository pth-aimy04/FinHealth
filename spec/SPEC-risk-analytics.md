# Spec: Corporate Risk Diagnostics, 5 Pillars, Business Drivers & Multi-Period Analytics (`risk-analytics`) — V1.0

> **Module ID:** `risk-analytics` (xem [capability-map.md](capability-map.md))  
> **Trạng thái:** Đã chốt (Approved — sẵn sàng triển khai)  
> **Phụ thuộc:** `financial-data`, `ml-bankruptcy-engine`  
> **Phạm vi nghiệp vụ:** M08 (Altman $Z/Z'/Z''$ + chặn TCTC), M09 (5 Trụ cột & 18–22 tỷ số có chú giải), M10 (Bảng "Điểm Tựa & Điểm Nghẽn Tài Chính" ngôn ngữ tài chính chuẩn xác toán học), M11 (Lịch sử đa kỳ 3–5 năm kể cả DN tổ chức), S01 (Đối chiếu chuẩn ngành từ SEC/cohort), C02 (QoE sẵn có), C03 (So sánh trực diện 2–4 DN + sửa 2 bug `ComparePage`), tuân thủ miễn trừ trách nhiệm NĐ 88/2014/NĐ-CP.

---

## 1. Objective

Cung cấp toàn bộ tầng phân tích tài chính doanh nghiệp xác định (deterministic) kết hợp với kết quả của `ml-bankruptcy-engine`, xuất ra các hợp đồng API giàu ngữ cảnh nghiệp vụ tiếng Việt để giao diện người dùng (và báo cáo PDF) trình bày trực quan mà **không hiển thị bất kỳ con số trơ trọi hay thuật ngữ lập trình/ML nào**.

### Yêu cầu nghiệp vụ cụ thể
1. **Altman Z-Score Chuẩn Quốc tế đủ 3 biến thể ($Z, Z', Z''$) & Chặn Ngành (M08):**
   - Triển khai tường minh 3 công thức chuẩn tại `src/finhealth/etl/financial_ratios.py`:
     - **$Z$ (DN sản xuất đã niêm yết — bắt buộc có `market_value_equity > 0`):** `1.2 X1 + 1.4 X2 + 3.3 X3 + 0.6 (MarketCap / TL) + 1.0 X5`, ngưỡng `< 1.81` (Nguy hiểm), `1.81–2.99` (Vùng xám), `> 2.99` (An toàn). Nếu thiếu `market_value_equity`, tự động hạ xuống $Z'$ kèm ghi chú rõ ràng.
     - **$Z'$ (DN sản xuất chưa niêm yết — dùng vốn sổ sách):** `0.717 X1 + 0.847 X2 + 3.107 X3 + 0.420 (BookEquity / TL) + 0.998 X5`, ngưỡng `< 1.23` (Nguy hiểm), `1.23–2.90` (Vùng xám), `> 2.90` (An toàn).
     - **$Z''$ (DN thương mại/dịch vụ/phi sản xuất & thị trường mới nổi):** `6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 (BookEquity / TL)`, ngưỡng `< 1.10` (Nguy hiểm), `1.10–2.60` (Vùng xám), `> 2.60` (An toàn).
   - **Tự động tắt với Tổ chức Tài chính (`business_type == 'financial_institution'`):** Trả `altman_applicable = False`, `altman_z_score = None`, `altman_unavailable_reason_vi = "Chỉ số Altman Z-Score không áp dụng cho Ngân hàng, Bảo hiểm và Tổ chức tài chính."`
   - Trả kèm `cutoff_low` và `cutoff_high` trực tiếp trong API response để biểu đồ frontend (`AltmanZoneChart`) vẽ đúng ngưỡng động thay vì hardcode `1.81 / 2.99`.
2. **Bức tranh 5 Trụ cột Sức khỏe Tài chính & 20 Chỉ số Cốt lõi (M09):**
   - Nâng cấp `compute_health_pillars()` tại `src/finhealth/etl/corporate_finance.py` từ 4 lên **5 trụ cột rõ ràng** (20 chỉ số, bỏ `AAA..CCC`, dùng trạng thái `STRONG / ADEQUATE / WEAK / CRITICAL / UNAVAILABLE`):
     1. **Khả năng thanh toán ngắn hạn (`liquidity`):** `current_ratio`, `quick_ratio`, `cash_ratio`, `working_capital_ratio`
     2. **Cơ cấu vốn & Áp lực nợ vay (`solvency`):** `debt_ratio`, `equity_to_assets`, `short_term_debt_share`, `interest_coverage`, `retained_earnings_ratio` *(có phạt `0.0` khi `is_negative_equity == True`)*
     3. **Khả năng sinh lời (`profitability`):** `gross_margin`, `operating_margin`, `ebitda_margin`, `roa`, `roe` *(phạt `0.0` khi âm VCSH)*
     4. **Hiệu quả luân chuyển vốn (`efficiency`):** `asset_turnover`, `dso_days` (`accounts_receivable / revenues * 365`), `dio_days` (`inventory / cost_of_goods_sold * 365`)
     5. **Sức mạnh dòng tiền thực (`cash_flow`):** `ocf_ratio` (`OCF / TL`), `fcf_to_liabilities`, `cash_conversion_qoe` (`OCF / NI`)
   - **Từ điển Chú giải Nghiệp vụ (`src/finhealth/etl/metric_catalog.py`):** Mọi chỉ số trả về trong API đều kèm `label_vi`, `pillar`, `unit`, `good_direction`, `reference_range_vi`, `tooltip_vi` (giải thích ý nghĩa kinh tế ngắn gọn), `status` (`GOOD / NEUTRAL / WARNING / CRITICAL / UNAVAILABLE`), `yoy_change` (so kỳ trước) và `peer_position` (so chuẩn ngành — đáp ứng UX Rule #2: không con số trơ trọi).
3. **Bảng Phân tích "Điểm Tựa & Điểm Nghẽn Tài Chính" (M10 — Chính xác Toán học & Ngôn ngữ Tài chính):**
   - Xây dựng dịch vụ `translate_drivers_to_business()` tại `src/finhealth/etl/driver_narrative.py`:
     - Tách riêng tối đa **5 Điểm Tựa (tác động giảm rủi ro — màu xanh)** và **5 Điểm Nghẽn (tác động đẩy rủi ro tăng — màu đỏ)** từ `shap_explanation.contributions`.
     - **Tuyệt đối không quy đổi tuyến tính sai toán từ SHAP log-odds sang "giảm X điểm sức khỏe"**. Thay vào đó, tính:
       - `impact_share_pct`: Tỷ trọng `%` đóng góp tương đối trong tổng `sum(|SHAP|)` của doanh nghiệp đó (`0–100%`, cộng đủ 100%).
       - `impact_strength`: `'VERY_HIGH' | 'HIGH' | 'MODERATE' | 'LOW'` (dựa theo `impact_share_pct` và độ lớn chuẩn hóa).
       - `headline_vi` & `detail_vi`: Câu diễn đạt tiếng Việt nghiệp vụ kèm giá trị thực tế vs ngưỡng tham chiếu (ví dụ: *"Nợ phải trả chiếm 84,2% tổng tài sản (cao hơn ngưỡng an toàn ≤ 60%), là yếu tố đẩy rủi ro tăng mạnh nhất — chiếm 28% mức tác động rủi ro."*).
     - Giữ kèm `technical_attribution` (tên biến gốc, `shap_value`, `output_space` thực tế) trong nhánh phụ chỉ dành cho chế độ kiểm định/Admin, không hiển thị trên UI khách hàng.
4. **Lịch sử Diễn biến Sức khỏe Đa kỳ 3–5 Năm (M11):**
   - Endpoint `GET /api/v1/org/companies/{company_id}/analysis` (và cập nhật `GET /api/v1/companies/{identifier}` cho SEC):
     - Trả chuỗi lịch sử theo năm (`finalized`) gồm: `fiscal_year`, `accounting_standard` (`TT200_2014` nối mượt sang `TT99_2025`), `revenues`, `net_income`, `operating_cash_flow`, `debt_ratio`, `roa`, `altman_z_score`, **`health_score` (0–100)** và **`pd_12m` (%)** của từng năm (được lưu/tính nhất quán theo cùng `active_model_version` để vẽ đồ thị xu hướng 3–5 năm).
5. **So sánh Vị thế Ngành (S01) & So sánh Trực diện 2–4 Doanh nghiệp (C03):**
   - **S01:** Tính phân vị ngành cho cả **DN tổ chức tự nhập** lẫn **DN SEC**, ánh xạ nhóm ngành VSIC ↔ SEC macro-sector cohort (fallback sang toàn thị trường khi ngành có `< 5` mẫu và ghi rõ `benchmark_scope = "sector" | "universe"`), gắn nhãn trực quan tiếng Việt: *"Top 25% tốt nhất ngành"*, *"Ngang mức trung bình ngành"*, *"Thấp hơn trung bình ngành"*.
   - **C03:**
     - Sửa 2 bug hiện có trên SEC Compare: giới hạn UI `ComparePage.tsx` về đúng **2–4 doanh nghiệp** (khớp backend `services.py:829`) và sửa `api.ts:148` gửi đúng query `common_fiscal_year` (số năm nguyên) thay vì `period_policy`.
     - Bổ sung `GET /api/v1/org/companies/compare?ids=1,2,3&common_fiscal_year=...` cho phép so sánh trực diện **2–4 doanh nghiệp trong cùng Workspace Tổ chức** (đặt song song Điểm sức khỏe, PD 12 tháng, Altman Z, 5 trụ cột và các chỉ số cốt lõi).
6. **Khung Pháp lý & Miễn trừ Trách nhiệm (Nghị định 88/2014/NĐ-CP):**
   - Mọi response phân tích (`OrgCompanyAnalysisSchema`, `CompanyFullAnalysisSchema`, `CompareResponseSchema`) đều mang trường `legal_disclaimer_vi` cố định (nêu rõ kết quả là phân tích định lượng nội bộ dựa trên mô hình ML lịch sử, không phải dịch vụ xếp hạng tín nhiệm theo NĐ 88/2014/NĐ-CP và không thay thế quyết định cấp tín dụng/đầu tư).
   - Bỏ nhãn `AAA..CCC` trên các API hướng người dùng cuối mới; dùng 4 nhãn chuẩn `STRONG / STABLE / WATCH / CRITICAL`.

### Boundary Contract cung cấp cho `batch-and-reporting` và `product-ui-governance`
- `CompanyAssessmentView` (Pydantic schema thống nhất cho cả DN Tổ chức và DN SEC):
  - `summary`: `{ health_score, risk_tier, risk_label_vi, pd_12m, confidence, cash_flow_overlay, top_3_takeaways_vi, legal_disclaimer_vi }` (phục vụ **Quy tắc 3 giây**).
  - `altman`: `{ applicable, variant ("Z"|"Z'"|"Z''"), score, zone, cutoff_low, cutoff_high, components, unavailable_reason_vi }`
  - `pillars`: 5 trụ cột + danh sách 20 chỉ số có ngữ cảnh đầy đủ.
  - `drivers`: `{ strengths: list[BusinessDriver] (≤5), bottlenecks: list[BusinessDriver] (≤5) }`
  - `diagnostics`: `dupont`, `quality_of_earnings` (C02), `accounting_checklist`.
  - `history`: chuỗi 3–5 năm có `health_score`, `pd_12m`, `altman_z_score`, doanh thu/lợi nhuận/OCF/nợ.
  - `peer_context`: vị thế ngành S01.

---

## 2. Tech Stack

- Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.0, `finhealth.etl`, `finhealth.ml`.
- Lưu trữ snapshot kết quả chấm điểm cho từng kỳ BCTC tổ chức vào bảng `org_assessments` (đóng băng `model_version`, `rule_version`, `pd_12m`, `health_score`, `risk_tier`, `confidence_json`, `drivers_json` để vẽ lịch sử M11 nhanh và đảm bảo tái lập kiểm toán).

---

## 3. Commands

```powershell
.\.venv\Scripts\ruff.exe check src/finhealth/etl src/finhealth/api
.\.venv\Scripts\mypy.exe src/finhealth
.\.venv\Scripts\pytest.exe -v tests/unit/test_risk_analytics_v2.py tests/unit/test_v12_business_logic.py tests/integration/test_org_analysis_and_compare.py
```

---

## 4. Project Structure

```text
migrations/versions/
  └── 0010_org_assessments_history.py         # Bảng org_assessments lưu snapshot chấm điểm đa kỳ theo org_statement_id & model_version
src/finhealth/db/
  └── org_models.py                           # Thêm ORM OrgAssessment
src/finhealth/etl/
  ├── financial_ratios.py                     # Đủ 3 biến thể Altman Z/Z'/Z'' + ngưỡng động + chặn FI
  ├── corporate_finance.py                    # 5 Trụ cột sức khỏe (20 chỉ số) + phạt âm VCSH + bỏ AAA..CCC ở v2
  ├── metric_catalog.py                       # Từ điển 20 chỉ số tiếng Việt, ngưỡng tham chiếu & tooltip
  └── driver_narrative.py                     # Chuyển TreeSHAP → 2 cột Điểm Tựa & Điểm Nghẽn chuẩn ngôn ngữ tài chính
src/finhealth/api/
  ├── schemas/analytics.py                    # CompanyAssessmentView, BusinessDriver, AltmanView, PillarView, OrgCompareResponse
  ├── services_org.py                         # Orchestrator chấm điểm, lưu lịch sử đa kỳ, so sánh ngành S01 & so sánh 2–4 DN C03
  └── routers/org_analytics.py                # GET /api/v1/org/companies/{id}/analysis, POST .../recompute, GET /api/v1/org/companies/compare
tests/
  ├── unit/test_risk_analytics_v2.py          # Test đủ Z/Z'/Z'', chặn FI, 5 trụ cột, tổng impact_share_pct = 100%, không trừ điểm sai SHAP
  └── integration/test_org_analysis_and_compare.py  # Test lịch sử 3–5 năm, so sánh 2–4 DN tổ chức, cô lập org_id, sửa bug SEC compare
```

---

## 5. Code Style

```python
from typing import Literal

AltmanVariant = Literal["Z", "Z'", "Z''"]


def select_altman_variant(
    *,
    business_type: str,
    listing_status: str,
    has_market_value: bool,
) -> tuple[AltmanVariant | None, float | None, float | None]:
    """Select the economically valid Altman formula and zone cutoffs by firm type."""
    if business_type == "financial_institution":
        return None, None, None
    if business_type == "manufacturing":
        if listing_status == "listed" and has_market_value:
            return "Z", 1.81, 2.99
        return "Z'", 1.23, 2.90
    return "Z''", 1.10, 2.60
```

---

## 6. Testing Strategy

- **Unit tests (`tests/unit/test_risk_analytics_v2.py`):**
  - Kiểm chứng công thức & ngưỡng chính xác của cả 3 biến thể Altman: $Z$ (`1.81/2.99`), $Z'$ (`1.23/2.90`), $Z''$ (`1.10/2.60`), fallback $Z \to Z'$ khi thiếu vốn hóa, và `applicable=False` với ngân hàng/TCTC.
  - Kiểm chứng 5 trụ cột (đủ 20 chỉ số trong `metric_catalog.py`), kiểm tra mọi chỉ số đều có `tooltip_vi` và `status`, và kiểm tra âm VCSH nhận điểm `0.0` (không bỏ trống).
  - Kiểm chứng `driver_narrative.py`: tối đa 5 Điểm Tựa + 5 Điểm Nghẽn, không chứa chuỗi kỹ thuật (`shap_value`, `log_odds`, `_yoy_delta`), tổng `impact_share_pct` của toàn bộ biến bằng `100%` (sai số `< 0.1`).
- **Integration tests (`tests/integration/test_org_analysis_and_compare.py`):**
  - Nạp 4 kỳ liên tiếp (TT200 FY2022–2025 + TT99 FY2026) → kiểm tra `history` trả đủ 4 điểm có `health_score` và `pd_12m` xuyên suốt.
  - So sánh 2–4 DN trong cùng Workspace Tổ chức trả kết quả đúng; truyền >4 DN trả 422; truyền ID của tổ chức khác trả 404.
  - Kiểm tra SEC `GET /api/v1/companies/compare` với `common_fiscal_year=2023` hoạt động đúng sau khi sửa bug query param.

---

## 7. Boundaries

- **Always:**
  - Kèm `legal_disclaimer_vi` trong mọi phản hồi đánh giá rủi ro.
  - Tính `altman` với ngưỡng động `cutoff_low`/`cutoff_high` theo đúng biến thể đã chọn.
- **Ask first:**
  - Thay đổi trọng số giữa 5 trụ cột hoặc ngưỡng tham chiếu của 20 chỉ số trong `metric_catalog.py`.
- **Never:**
  - Không bao giờ hiển thị hoặc trả về chuỗi *"làm giảm X điểm sức khỏe"* bằng cách cộng/trừ tuyến tính SHAP log-odds.
  - Không bao giờ tính Altman Z hoặc ML phi tài chính cho doanh nghiệp có `business_type == "financial_institution"`.

---

## 8. Success Criteria

1. Một doanh nghiệp tổ chức sau khi hoàn tất BCTC (finalized) trả về đầy đủ `CompanyAssessmentView`: 1 Điểm Sức khỏe 0–100, PD 12 tháng, Độ tin cậy 4 lớp, Altman đúng biến thể ($Z/Z'/Z''$), 5 Trụ cột & 20 chỉ số có tooltip/ngữ cảnh ngành S01, bảng 2 cột Điểm Tựa & Điểm Nghẽn tiếng Việt, QoE (C02) và lịch sử 3–5 năm (M11).
2. So sánh 2–4 doanh nghiệp hoạt động chuẩn cho cả DN Tổ chức và DN SEC (đã sửa 2 bug `ComparePage`).
3. Toàn bộ test đơn vị & tích hợp xanh 100%, không hồi quy các kiểm thử DuPont/QoE/Piotroski hiện có.

---

## 9. Out of Scope (Deferred)

- Cảnh báo chuỗi suy giảm ngầm 3 kỳ tự động (S02 — V1.1).
- Chế độ khẩu vị rủi ro Thận trọng / Tiêu chuẩn / Linh hoạt (S05 — V1.1).
- Khung khuyến nghị hạn mức công nợ thương mại (C04 — V1.1).
- Beneish M-Score đầy đủ (C02 nâng cao — V2.0+).
