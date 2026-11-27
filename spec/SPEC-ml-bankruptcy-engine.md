# Spec: Leakage-Free ML Bankruptcy Engine, Calibration & Health Scoring (`ml-bankruptcy-engine`) — V1.0

> **Module ID:** `ml-bankruptcy-engine` (xem [capability-map.md](capability-map.md))  
> **Trạng thái:** Đã chốt (Approved — sẵn sàng triển khai)  
> **Phụ thuộc:** `financial-data` (`NormalizedStatementRecord`, `compute_statement_ratios`, cờ `is_negative_equity`)  
> **Phạm vi nghiệp vụ:** M06 (1 Điểm Sức khỏe 0–100 duy nhất & 4 cấp độ), M07 (Dự báo xác suất phá sản 12 tháng & Chỉ báo Độ tin cậy 4 lớp), sửa toàn bộ lỗ hổng ML hiện hữu (rò rỉ nhãn Kaggle, bỏ `eps`/`X8`, calibrate đồng đều 4 mô hình LR/RF/XGB/LGBM, thang PD thực, Cash-Flow Overlay, đồng bộ đa worker).

---

## 1. Objective

Thay thế lõi ML thử nghiệm hiện tại bằng **Core ML Bankruptcy Engine chuẩn Production**:
- Huấn luyện chính trên tập **Kaggle US Bankruptcy (`data/raw/kaggle/american_bankruptcy.csv` — 8.971 DN, 78.682 dòng, 609 ca phá sản Chapter 7/11 thật, 1999–2018)** sau khi **triệt tiêu 100% look-ahead & entity leakage**.
- Chấm điểm công bằng, **không phụ thuộc tiền tệ (VND/USD)** và hoạt động cho cả doanh nghiệp niêm yết lẫn chưa niêm yết/TNHH.
- Tích hợp **Lớp Dòng tiền (Cash-Flow Risk Overlay)** để bù điểm khuyết OCF/Lãi vay của tập Kaggle khi người dùng nhập đủ BCTC 3 biểu mẫu.

### Yêu cầu kỹ thuật & toán học cụ thể
1. **Sửa triệt để Look-Ahead & Entity Leakage trong `src/finhealth/ml/kaggle_loader.py`:**
   - Trong `american_bankruptcy.csv`, cả 609 công ty `status_label == "failed"` bị gắn nhãn `"failed"` ở mọi năm lịch sử.
   - **Quy tắc gán nhãn 1-year-ahead chuẩn (Lombardo et al., 2022):**
     - Với mỗi công ty `status_label == "failed"`, tìm `max_year = max(year)`.
     - Gán **`next_is_bankrupt = 1` CHỈ tại dòng `year == max_year`** (năm tài chính cuối cùng trước sự kiện nộp đơn Chapter 7/11); mọi năm trước đó (`year < max_year`) và mọi dòng của công ty `alive` mang nhãn **`next_is_bankrupt = 0`**.
     - **Kiểm soát phân tách thời gian sạch (Strict Out-of-Time Split):**
       - `Train`: `fiscal_year <= 2014` (~490 sự kiện phá sản)
       - `Validation`: `2015 <= fiscal_year <= 2016` (~62 sự kiện phá sản)
       - `Test`: `fiscal_year >= 2017` (~57 sự kiện phá sản; **0 công ty nào ở tập Test từng có nhãn `1` ở Train hoặc Validation**).
2. **Bộ đặc trưng 100% Không thứ nguyên (Scale-Free Feature Contract — khai thác đủ `X1–X18` bỏ `X8`):**
   - **Loại bỏ hoàn toàn** `eps` (phụ thuộc USD/cổ phiếu, lỗi trên Công ty TNHH & VND) và `X8` (vốn hóa thị trường, không tồn tại ở DN chưa niêm yết) khỏi bộ đặc trưng ML tổng quát.
   - **Tập đặc trưng 1 kỳ (`CORE_BANKRUPTCY_FEATURES` — 16 đặc trưng, đều tính được từ `X1–X18` và từ BCTC TT99/TT200/TT133):**
     1. `roa` (`net_income / total_assets`)
     2. `ebit_to_assets` (`operating_income / total_assets`)
     3. `ebitda_to_assets` (`ebitda / total_assets`)
     4. `gross_margin` (`gross_profit / revenues`)
     5. `operating_margin` (`operating_income / revenues`)
     6. `opex_to_revenue` (`operating_expenses / revenues`)
     7. `asset_turnover` (`revenues / total_assets`)
     8. `current_ratio` (`current_assets / current_liabilities`)
     9. `quick_ratio` (`(current_assets - inventory) / current_liabilities`)
     10. `working_capital_ratio` (`(current_assets - current_liabilities) / total_assets`)
     11. `debt_ratio` (`total_liabilities / total_assets`)
     12. `short_term_debt_share` (`current_liabilities / total_liabilities`)
     13. `long_term_debt_to_assets` (`long_term_debt / total_assets`)
     14. `retained_earnings_ratio` (`retained_earnings / total_assets`)
     15. `equity_to_assets` (`stockholders_equity / total_assets` — **hữu hạn ngay cả khi âm VCSH, thay cho `debt_to_equity` bị missing khi âm vốn!**)
     16. `is_negative_equity` (`1.0` nếu `stockholders_equity <= 0`, ngược lại `0.0`)
     - *(Bổ sung tùy chọn đã kiểm chứng từ `X5`, `X7`, `X3`: `inventory_to_assets`, `receivables_to_revenue`, `depreciation_to_assets` — tổng 19 đặc trưng không thứ nguyên).*
   - **Tách 2 chế độ suy luận rõ ràng (tránh suy giảm do thiếu năm trước):**
     - **Chế độ Đơn kỳ (`single_period`):** Huấn luyện & chạy trên 19 đặc trưng không thứ nguyên kỳ hiện tại (không có cột YoY bị `NaN` → không bị điền trung vị giả!).
     - **Chế độ Đa kỳ (`multi_period`, khi có ≥2 năm liên tiếp):** Bổ sung 5 đặc trưng biến thiên YoY (`roa_yoy_delta`, `gross_margin_yoy_delta`, `debt_ratio_yoy_delta`, `working_capital_yoy_delta`, `revenue_growth_yoy`). Hệ thống tự động chọn mô hình `multi_period` nếu DN có dữ liệu kỳ trước hợp lệ, ngược lại gọi `single_period`.
3. **Huấn luyện & Hiệu chuẩn Đồng đều Cả 4 Mô hình (LR, RF, XGBoost, LightGBM):**
   - Cả 4 mô hình (`logistic_regression`, `random_forest`, `xgboost`, `lightgbm`) đều được huấn luyện bằng **cùng preprocessor fit trên tập Train**, **cùng chiến lược mất cân bằng** và **đều đi qua Platt Calibration (`fit_calibration`) trên tập Validation (2015–2016)** để mọi xác suất đầu ra nằm trên **cùng thang xác suất thực** (loại bỏ lỗi LR Brier `0.249` do chưa hiệu chuẩn).
   - **Suy luận Ensemble có trọng số kiểm định (Validation-Weighted Ensemble):**
     - Trọng số $w_m$ chọn trên tập Validation (ưu tiên Brier Score / Log-Loss thấp nhất, hoặc mô hình top-1 + 3 mô hình phụ dùng để tính độ bất đồng).
     - Xuất ra **1 Xác suất Nguy cơ Phá sản 12 tháng duy nhất** `pd_12m` ($\in [0, 1]$) đã hiệu chuẩn.
   - **Giữ nguyên TreeSHAP chính xác:** Tính local SHAP trên mô hình cây chính (`xgboost` hoặc `lightgbm` đạt Validation tốt nhất) với `shap_reconstruction_error < 1e-5`, ghi rõ `output_space` thực tế (không hardcode nhãn sai).
4. **Chỉ báo Độ tin cậy Đánh giá 4 Lớp (M07 — thay cho công thức đồng thuận ngây thơ):**
   - Tính `confidence_level: Literal["HIGH", "MODERATE", "LOW"]` và `confidence_reasons: list[str]` từ 4 tiêu chí tường minh:
     1. **Độ đầy đủ đầu vào (`input_completeness`):** Tỷ lệ trường cốt lõi quan sát được (không bị thiếu/impute). `< 70%` → hạ xuống `LOW`; `70%–90%` → tối đa `MODERATE`.
     2. **Phát hiện ngoài phân phối (`is_ood`, `ood_features`):** Đối chiếu với biên phân vị `[1%, 99%]` của tập Train (`feature_ood_bounds`). Có `>= 3` đặc trưng OOD → hạ ít nhất 1 bậc.
     3. **Độ bất đồng giữa 4 mô hình đã hiệu chuẩn (`ensemble_std` / `ensemble_spread`):** Tính độ lệch chuẩn & khoảng rộng $\max(\hat{p}_m) - \min(\hat{p}_m)$ sau Platt calibration. Nếu khoảng rộng vượt ngưỡng kiểm định (ví dụ `> 0.08`) → hạ 1 bậc và ghi rõ lý do.
     4. **Chất lượng nguồn BCTC (`audit_status`):** Nếu `'unaudited'` → tối đa `MODERATE`; nếu `'audited_adverse_disclaimer'` → ghi cờ cảnh báo nghiêm trọng.
5. **Thang Phân vùng PD Thực, Lớp Dòng tiền (Cash-Flow Overlay) & Quy đổi Đơn điệu sang 1 Điểm Sức khỏe 0–100 Duy nhất (M06):**
   - **4 Cấp độ Cảnh báo (phù hợp base rate phá sản thật ~1%/năm):**
     - `STRONG` (**Vững mạnh** — Xanh lá): `pd_effective < 0.01` (`< 1%`) → Điểm Sức khỏe **`80–100`**
     - `STABLE` (**Ổn định** — Xanh dương): `0.01 <= pd_effective < 0.03` (`1%–3%`) → Điểm Sức khỏe **`60–79.9`**
     - `WATCH` (**Cần theo dõi sát** — Vàng cam): `0.03 <= pd_effective < 0.08` (`3%–8%`) → Điểm Sức khỏe **`35–59.9`**
     - `CRITICAL` (**Nguy cơ khủng hoảng cao** — Đỏ): `pd_effective >= 0.08` (`≥ 8%`) → Điểm Sức khỏe **`0–34.9`**
   - **Quy đổi đơn điệu (Piecewise Monotonic Log-Odds Mapping):** `health_score = map_pd_to_health_score(pd_effective)` đảm bảo **100% nhất quán** — không bao giờ xảy ra mâu thuẫn điểm cao mà PD cao.
   - **Lớp Dòng tiền Bổ trợ (`CashFlowOverlay`):** Vì Kaggle không có OCF & Lãi vay, khi BCTC người dùng có OCF / Lãi vay:
     - Nếu `negative_ocf_streak >= 2` HOẶC (`interest_coverage < 1.0` và `operating_cash_flow < 0`) HOẶC `audit_status == 'audited_adverse_disclaimer'` → gắn `cash_flow_overlay_triggered = True`, nâng tối thiểu mức cảnh báo lên `WATCH` (nếu đang `STRONG`/`STABLE`) và ghi rõ lý do nghiệp vụ (không âm thầm sửa sai lệch `pd_12m` gốc của mô hình).
6. **Đồng bộ Đa Worker & Khắc phục Lỗi Nền:**
   - Thay cache/registry đơn tiến trình bằng cơ chế kiểm tra `latest.json` (`mtime_ns` + `sha256` manifest) tự động reload an toàn trên mọi worker Gunicorn/Uvicorn khi xuất bản bundle mới, không cần khởi động lại server.
   - Sửa kiểm tra so sánh float trong `tests/integration/test_forensic_audit.py:709` sang `pytest.approx(..., rel=1e-12, abs=1e-12)` để hết lỗi ULP `2e-17` giữa các phiên bản XGBoost.

### Boundary Contract cung cấp cho các module phía sau
- `BankruptcyAssessmentResult`:
  - `model_version: str`, `scoring_mode: Literal["single_period", "multi_period"]`
  - `pd_12m: float` (calibrated), `risk_tier: Literal["STRONG", "STABLE", "WATCH", "CRITICAL"]`, `health_score: float` (`0..100`, đơn điệu với `pd_12m` + overlay)
  - `confidence: ConfidenceAssessment` (`level`, `input_completeness`, `is_ood`, `ood_features`, `ensemble_spread`, `reasons_vi`)
  - `cash_flow_overlay: CashFlowOverlayResult` (`triggered`, `flags`, `adjusted_tier`)
  - `shap_explanation: dict[str, Any]` (`output_space`, `base_value`, `top_drivers`, `contributions`, `model_name`)

---

## 2. Tech Stack

- Python 3.10+, `numpy`, `pandas`, `scikit-learn`, `xgboost`, `lightgbm`, `shap`, `scipy`, `joblib`, `pyarrow`.
- `RANDOM_SEED = 42` xuyên suốt mọi thành phần ngẫu nhiên (tuân thủ `AGENTS.md`).

---

## 3. Commands

```powershell
# Huấn luyện & xuất bản gói mô hình Kaggle sạch (v2.0.0-kaggle) không leakage
.\.venv\Scripts\python.exe -m finhealth.ml.train_cli --dataset kaggle --model-version v2.0.0-kaggle

# Lint, typecheck & tests ML
.\.venv\Scripts\ruff.exe check src/finhealth/ml tests/unit/test_ml_bankruptcy_v2.py
.\.venv\Scripts\mypy.exe src/finhealth/ml
.\.venv\Scripts\pytest.exe -v tests/unit/test_ml_bankruptcy_v2.py tests/unit/test_ml_pipeline.py
```

---

## 4. Project Structure

```text
src/finhealth/ml/
  ├── kaggle_loader.py              # Sửa nhãn 1-year-ahead (chỉ year==max_year), mở khóa đủ 19 tỷ số scale-free từ X1-X18 (bỏ X8/eps)
  ├── feature_contracts.py          # Định nghĩa CORE_BANKRUPTCY_FEATURES (19) & MULTI_PERIOD_FEATURES (24) dùng chung
  ├── distress_classifier.py        # Platt calibration cho CẢ 4 mô hình (gồm LogisticRegression), ensemble calibration,
  │                                 # map_pd_to_health_score() & classify_bankruptcy_tier()
  ├── confidence.py                 # Bộ đánh giá Độ tin cậy 4 lớp + CashFlowOverlay
  ├── registry.py                   # Lưu cả 2 pipeline (single_period + multi_period) & 4 calibrated models trong bundle;
  │                                 # reload đa worker an toàn theo latest.json mtime/hash
  ├── explainer.py                  # TreeSHAP chính xác gắn đúng output_space & model_name
  └── train_cli.py                  # Hỗ trợ --dataset kaggle (clean 1Y) và --dataset sec; xuất BENCHMARK_REPORT.md
data/artifacts/models/
  └── v2.0.0-kaggle/                # Artifact mới sạch leakage, kiểm chứng out-of-time 2017–2018
tests/
  └── unit/test_ml_bankruptcy_v2.py # Kiểm thử 0% entity/look-ahead leakage, scale invariance (VND = USD),
                                    # tính đơn điệu PD↔HealthScore, calibration cả 4 mô hình, confidence 4 lớp
```

---

## 5. Code Style

```python
import math
from typing import Literal

RiskTier = Literal["STRONG", "STABLE", "WATCH", "CRITICAL"]


def classify_bankruptcy_tier(pd_12m: float) -> RiskTier:
    """Map calibrated 12-month bankruptcy probability to credit-aligned risk tiers."""
    if not math.isfinite(pd_12m) or not 0.0 <= pd_12m <= 1.0:
        raise ValueError("pd_12m must be finite and within [0, 1]")
    if pd_12m < 0.01:
        return "STRONG"
    if pd_12m < 0.03:
        return "STABLE"
    if pd_12m < 0.08:
        return "WATCH"
    return "CRITICAL"


def map_pd_to_health_score(pd_12m: float) -> float:
    """Convert calibrated PD monotonically onto [0, 100] aligned with the four risk bands."""
    if not math.isfinite(pd_12m) or not 0.0 <= pd_12m <= 1.0:
        raise ValueError("pd_12m must be finite and within [0, 1]")
    if pd_12m < 0.01:
        return round(100.0 - 20.0 * (pd_12m / 0.01), 2)
    if pd_12m < 0.03:
        return round(80.0 - 20.0 * ((pd_12m - 0.01) / 0.02), 2)
    if pd_12m < 0.08:
        return round(60.0 - 25.0 * ((pd_12m - 0.03) / 0.05), 2)
    tail = min(1.0, math.log1p((pd_12m - 0.08) / 0.08) / math.log1p((1.0 - 0.08) / 0.08))
    return round(max(0.0, 35.0 * (1.0 - tail)), 2)
```

---

## 6. Testing Strategy

- **Unit tests (`tests/unit/test_ml_bankruptcy_v2.py`):**
  - **Chứng minh 0% Leakage trên `american_bankruptcy.csv`:**
    - Xác nhận đúng 609 dòng có `next_is_bankrupt == 1` (mỗi công ty `failed` đúng 1 dòng tại `year == max_year`).
    - Xác nhận `set(train[train.next_is_bankrupt==1].cik).isdisjoint(set(test[test.next_is_bankrupt==1].cik))` == `True`.
  - **Bất biến đơn vị tiền tệ (Currency Scale-Invariance):** Nhân toàn bộ khoản mục BCTC lên `25_000` (USD → VND) hoặc `1_000_000` → xác suất `pd_12m`, `health_score`, `risk_tier` và `top_drivers` phải **giống hệt nhau sai số `< 1e-9`**.
  - **Tính đơn điệu PD ↔ Health Score:** Quét 1.000 mốc PD từ `0.0` đến `1.0` → xác nhận `health_score` giảm nghiêm ngặt và không bao giờ lệch phân vùng màu sắc.
  - **Calibration đồng đều 4 mô hình:** Xác nhận `logistic_regression`, `random_forest`, `xgboost`, `lightgbm` đều có `calibration_ is not None` và `mean_predicted_prob` trên Validation nằm gần `prevalence` (không lệch kiểu `0.495 vs 0.013`).
  - **Độ tin cậy 4 lớp & Cash-Flow Overlay:** Kiểm thử đủ các trường hợp thiếu trường (`<70%`), OOD (`>=3` biến), bất đồng ensemble cao, chưa kiểm toán, và OCF âm 2 năm liên tiếp.

---

## 7. Boundaries

- **Always:**
  - Fit Winsorization, Imputation, Scaling và Platt Calibration **chỉ trên tập Train/Validation tương ứng**, tuyệt đối không chạm tập Test.
  - Đảm bảo sai số tái dựng TreeSHAP `< 1e-5` trước khi xuất bản bundle.
  - Propagate `RANDOM_SEED = 42` cho toàn bộ model và kiểm chứng khả năng tái lập.
- **Ask first:**
  - Thay đổi mốc phân vùng PD (`1% / 3% / 8%`) hoặc trọng số cố định của ensemble.
- **Never:**
  - Không bao giờ đưa biến có thứ nguyên tiền tệ (`eps`, `total_assets` thô, `market_value`) vào mô hình phân loại chung.
  - Không bao giờ gắn nhãn `1` cho các năm lịch sử `year < max_year` của công ty phá sản.

---

## 8. Success Criteria

1. Gói mô hình `v2.0.0-kaggle` huấn luyện thành công trên `american_bankruptcy.csv` với **0% entity/look-ahead leakage**, đầy đủ 4 mô hình được Platt-calibrate đồng đều, lưu cả 2 chế độ `single_period` và `multi_period`, xuất đầy đủ `BENCHMARK_REPORT.md` và biểu đồ kiểm định (ROC/PR/Calibration/SHAP).
2. Test bất biến đơn vị tiền tệ (USD vs VND vs Tỷ VND) cho kết quả khớp tuyệt đối (`< 1e-9`).
3. Điểm Sức khỏe `0–100` và 4 cấp độ rủi ro đồng biến 100%, không còn mâu thuẫn với xác suất phá sản 12 tháng.
4. Sửa dứt điểm lỗi ULP `test_training_latency_and_saved_scores` và loại bỏ import thừa ở `tests/integration/test_v12_compare_and_ui.py` khi đến bước dọn dẹp test.

---

## 9. Out of Scope (Deferred)

- Huấn luyện trên tập dữ liệu phá sản nội địa Việt Nam (chưa có nguồn dữ liệu sự kiện phá sản/vỡ nợ VN cấp phép ở V1.0).
- Dự báo xác suất phá sản đa kỳ hạn 2–3 năm (W04 — V3.0).
- Tối ưu hóa lộ trình cải thiện định lượng Counterfactual bảo toàn cân đối kế toán kép (W01 — V2.0+).
