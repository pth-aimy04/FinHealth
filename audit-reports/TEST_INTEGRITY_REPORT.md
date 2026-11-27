# BÁO CÁO KIỂM ĐỊNH ĐỘ TIN CẬY VÀ TÍNH TOÀN VẸN KIỂM THỬ (TEST INTEGRITY REPORT)

## 1. Thống kê Tổng quan Bộ Kiểm thử (Test Inventory & Execution Summary)

Dữ liệu thống kê dưới đây được trích xuất trực tiếp từ hai lần thực thi độc lập của `pytest 9.2.0` trên môi trường ảo `.venv` (`Python 3.12.14`) trong quá trình audit:

1. **Lần chạy 1 (`audit-reports/logs/pytest_default_basetemp.log`)**: Chạy với đường dẫn tạm mặc định của Windows (`%TEMP%\pytest-of-hp`), nhằm ghi nhận nguyên trạng môi trường máy trạm.
2. **Lần chạy 2 (`audit-reports/logs/pytest_scratch_basetemp.log`)**: Chạy với `--basetemp` và `-o cache_dir` đặt tại thư mục `scratch` có quyền ghi, nhằm loại bỏ rào cản ACL của Windows trên `%TEMP%` và đánh giá chính xác 100% logic của 184 test cases.

| Chỉ số thống kê | Lần chạy 1 (Mặc định `%TEMP%`) | Lần chạy 2 (Writable `--basetemp`) | Bản chụp cũ (`data/artifacts/data-version/pytest.txt`) |
|---|---:|---:|---:|
| **Tổng số test thu thập (Collected)** | **184** | **184** | 182 |
| **Số test thực thi (Executed)** | **184** | **184** | 182 |
| **PASSED** | **119** | **180** | 182 |
| **FAILED** | **3** | **4** | 0 |
| **ERROR (Fixture Setup Blocked)** | **62** | **0** | 0 |
| **SKIPPED** | **0** | **0** | 0 |
| **Thời gian thực thi** | `76.79s` | `136.66s` | `105.94s` |
| **Exit Code** | `1` | `1` | `0` |

> [!IMPORTANT]
> Sự khác biệt giữa bản chụp cũ (`182 passed` trong `data/artifacts/data-version/pytest.txt`) và trạng thái hiện tại của repository (`184 collected`: `180 passed, 4 failed`) xuất phát từ việc sau thời điểm lưu `pytest.txt`, dự án đã được bổ sung thêm 2 unit test mới trong `tests/unit/test_ml_pipeline.py` (`test_lightgbm_and_random_forest_candidates_and_selection` và `test_kaggle_bankruptcy_loader_and_out_of_time_panel`) và huấn luyện lại gói mô hình `v1.2.0`, làm phát sinh lỗi bất đồng bộ dữ liệu `AUD-DATA-001`.

---

## 2. Phân loại Danh mục Kiểm thử & Ranh giới Phụ thuộc (Test Classification & Dependency Boundaries)

Tuân thủ nguyên tắc **No Fake Green Tests**, bảng dưới đây phân tách rõ bản chất từng tệp kiểm thử, loại phụ thuộc thực tế được sử dụng và ranh giới giả lập (mock/stub):

| Tệp kiểm thử | Số test items | Phân loại kiểm thử | Phụ thuộc thật được sử dụng (Real Dependencies) | Ranh giới Mock / Stub / Monkeypatch | Đánh giá độ tin cậy |
|---|---:|---|---|---|---|
| `tests/unit/test_core_config.py` | 30 | Unit Test | Pydantic `BaseSettings`, parser `.env` thật, tệp `.env.example` thật. | `monkeypatch` biến môi trường và `chdir(tmp_path)` để cô lập với `.env` của máy dev. | **Rất tốt**: Kiểm chứng đầy đủ cả biên hợp lệ và bất hợp lệ (NaN, Inf, CRLF header injection). |
| `tests/unit/test_core_logging.py` | 6 | Unit Test | Python `logging`, `StreamHandler`, `StringIO`, cây ngoại lệ `FinHealthError`. | Không dùng mock. | **Rất tốt**: Kiểm tra tính lũy đẳng (idempotency) và không nhân bản handler. |
| `tests/unit/test_db_session.py` | 4 | Unit + DB Engine Test | SQLite engine thật, SQLAlchemy `Session` thật, `PRAGMA foreign_keys=ON`. | `monkeypatch` hàm `_default_session_factory` để trỏ vào SQLite in-memory thay vì DB mặc định. | **Rất tốt**: Kiểm chứng commit, rollback khi exception và rollback khi generator đóng sớm. |
| `tests/unit/test_db_repositories.py` | 18 | Unit + Relational Integrity Test | SQLite in-memory thật với đầy đủ DDL constraints, FK cascades, JSON columns. | Không dùng mock. | **Xuất sắc**: Kiểm tra cả qua Repository lẫn chèn trực tiếp ORM để chứng minh DB constraint thực sự chặn dữ liệu sai. |
| `tests/unit/test_sec_ingestion.py` | 13 | Unit + Transport Boundary Test | `SecEdgarClient` thật, `AsyncRateLimiter` thật (`time.monotonic`, `asyncio.sleep`), đọc/ghi đĩa nguyên tử thật (`atomic_write_json`). | Chỉ thay tầng mạng ngoài bằng `httpx.MockTransport` trả về JSON fixture hoặc lỗi HTTP (403, 404, 429, 503, timeout); 1 test dùng `monkeypatch.setattr(Path, "replace", ...)` để giả lập lỗi OS khi rename file. | **Rất tốt**: Mock đúng ở biên HTTP/OS ngoài; kiểm chứng cả khoảng cách thời gian thực thi $\ge 0.099\text{s}$ giữa các request. |
| `tests/unit/test_etl_pipeline.py` | 13 | Unit + File/DB I/O Test | `SecXbrlParser`, công thức tỷ số, Altman Z/Z″, `RatioWinsorizer`, SQLite thật, PyArrow Parquet thật. | 1 test dùng `monkeypatch` trên `builtins.__import__` để giả lập môi trường thiếu `pyspark` và kiểm tra cơ chế fallback sang PyArrow. | **Xuất sắc**: Kiểm tra đối soát số học chính xác và chống rò rỉ tập test vào Winsorizer. |
| `tests/unit/test_ml_pipeline.py` | 12 | Unit + Real Estimator Test | `XGBClassifier`, `LGBMClassifier`, `RandomForestClassifier`, `XGBRegressor`, `LogisticRegression`, `PCA`, `KMeans`, `shap.TreeExplainer`, `joblib` thật trên dữ liệu panel tổng hợp (24 công ty × 5 năm). | Không dùng mock. | **Xuất sắc**: Không mock model hay SHAP; kiểm tra bất biến `base_value + sum(shap) == raw_margin`. |
| `tests/unit/test_stage66_remediation.py` | 5 | Unit Test | `compute_statement_ratios`, `FinancialHealthClusterer`, `build_benchmark_panel`, `as_reported_annual_payload`, `prepare_validation_test`. | Không dùng mock. | **Rất tốt**: Kiểm chứng ngưỡng đệm vốn chủ sở hữu 5%, chuẩn hóa phương sai đơn vị và publication embargo. |
| `tests/unit/test_stage67.py` | 2 | Unit Test | `derive_distress_label`, `evaluate_multitarget_regression`, `RatioWinsorizer`. | Không dùng mock. | **Rất tốt**: Chứng minh nhãn proxy hoàn toàn độc lập với cột `altman_z_score`. |
| `tests/unit/test_stage8_credit.py` | 8 | Unit Test | `FinancialEtlPipeline`, `as_reported_annual_payload`, `compute_statement_ratios`. | Không dùng mock. | **Rất tốt**: Kiểm chứng loại trừ SIC 6000–6799, CIK `0001826011`, và loại trừ tiền bị hạn chế (`restricted cash`) khỏi `cash_ratio`. |
| `tests/unit/test_v12_business_logic.py` | 7 | Unit Test | `compute_dupont`, `dupont_bridge` (Shapley 6 hoán vị), `compute_quality_of_earnings`, `compute_accounting_checklist`, `CompositeBenchmark`. | Không dùng mock. | **Xuất sắc**: Đối chiếu kết quả phân rã Shapley 3 nhân tố với công thức đóng giải tích đến sai số $< 10^{-12}$. |
| `tests/unit/test_visualization_and_cli.py` | 2 | Integration / CLI Test | Chạy toàn bộ `train_cli.main(["--offline", ...])`, tạo 7 file PNG 300-DPI thật, kiểm tra header ảnh qua `PIL.Image`, đọc lại Parquet và bundle. | Không dùng mock. | **Tốt, nhưng còn lỗ hổng kiểm tra nội dung biểu đồ 07**: Kiểm tra kích thước ảnh, DPI và độ lệch chuẩn pixel (`std > 10`), nhưng không phát hiện được biểu đồ `07_reliability_calibration.png` chỉ có đường tham chiếu `y = x` mà thiếu đường dữ liệu mô hình (`AUD-FUNC-002`). |
| `tests/integration/test_api_endpoints.py` | 10 | Integration Test | FastAPI `TestClient`, SQLAlchemy + SQLite thật, ETL thật, ML training & inference thật. | Chỉ thay mạng SEC bằng `httpx.MockTransport` với 3 tệp JSON fixture của Apple. | **Rất tốt**: Kiểm tra cả trigger lỗi DB để chứng minh rollback toàn bộ giao dịch. |
| `tests/integration/test_dashboard_ui.py` | 19 | Integration Test (Real Local Artifacts) | FastAPI `TestClient`, cơ sở dữ liệu `data/processed/parquet/finhealth.sqlite3` thật (chế độ `ro`), gói mô hình `v1.2.0` thật, tệp frontend và PNG thật. | Không dùng mock. | **2 test FAILED** (`test_company_features_explanations_and_altman[AAPL]` và `[AAL]`) do phát hiện đúng lỗi bất đồng bộ dữ liệu `AUD-DATA-001`. Ngoài ra danh sách `FIGURES` trong test chỉ kiểm tra 6 ảnh, thiếu ảnh 07. |
| `tests/integration/test_db_migrations.py` | 3 | Integration / DDL Compilation Test | Alembic `command.upgrade("head")` và `downgrade("base")` thật trên SQLite; `compare_metadata`; biên dịch SQL offline cho PostgreSQL và SQL Server. | `monkeypatch` biến môi trường `DATABASE_URL` cho test biên dịch SQL PostgreSQL offline. | **Tốt**: Đảm bảo 4 bản migration khớp 100% với `Base.metadata`. Lưu ý: PostgreSQL và SQL Server chỉ được kiểm tra biên dịch DDL offline (`sql=True`), chưa chạy trên DB server thật. |
| `tests/integration/test_filing_lineage.py` | 7 | Integration Test | FastAPI `TestClient`, SQLite thật, `FilingVersion`, `ForecastEvidence`, `IngestionRun`, dữ liệu thí điểm Việt Nam (`VN:FPT`, `VN:HPG`), `quarterly_series`. | Không dùng mock. | **Rất tốt**: Kiểm chứng truy vấn `as_of`, cảnh báo thay đổi số liệu sửa đổi (`report_alerts`) và cơ chế claim/retry của hàng đợi ingestion. |
| `tests/integration/test_forensic_audit.py` | 17 | Forensic & Performance Integration Test | Toàn bộ 98 tệp raw SEC JSON thật, `sec_real_panel.parquet` (1,506 dòng), `finhealth.sqlite3` thật, gói mô hình `v1.2.0` thật, huấn luyện kiểm chứng hoán vị nhãn (`target_permutation`). | Không dùng mock. | **2 test FAILED**: `test_prediction_and_api_parity` (phát hiện đúng lỗi `AUD-DATA-001`) và `test_api_latency[/companies]` (flaky do ngưỡng cứng `P95 < 50ms` - `AUD-TEST-001`). |
| `tests/integration/test_v12_compare_and_ui.py` | 8 | Integration & Cross-Runtime Test | FastAPI `TestClient` trên `finhealth.sqlite3` thật, `sqlite3.backup`, Alembic migration thật, gọi tiến trình `node` thật để chạy `frontend/js/csv.js`. | Không dùng mock. | **Xuất sắc**: Chạy trực tiếp module ES `frontend/js/csv.js` bằng Node.js để kiểm chứng RFC 4180 và chống CSV Formula Injection. |

---

## 3. Phân tích Chi tiết các Kiểm thử Thất bại (Failed & Blocked Tests Analysis)

### 3.1. Các test FAILED do lỗi thực tế trong dữ liệu/hệ thống (3 tests)
1. `tests/integration/test_dashboard_ui.py::test_company_features_explanations_and_altman[AAPL]`
   - **Kết quả**: `FAILED` (`AssertionError: assert 2.6257890988689514 < 1e-05`)
   - **Nguyên nhân**: Xem `AUD-DATA-001`. Bản ghi dự báo `v1.2.0` của AAPL trong `finhealth.sqlite3` lưu `output_space = "log_odds"` nhưng `base_value` và `contributions` là xác suất của `RandomForestClassifier` (tổng = `0.0721847`), không khớp với `raw_margin` (`-2.553604`).
2. `tests/integration/test_dashboard_ui.py::test_company_features_explanations_and_altman[AAL]`
   - **Kết quả**: `FAILED` (`AssertionError: assert 0.3138853967006634 < 1e-05`)
   - **Nguyên nhân**: Tương tự trên đối với mã `AAL` (`raw_margin = 1.055766` so với tổng xác suất SHAP `0.741881`).
3. `tests/integration/test_forensic_audit.py::test_prediction_and_api_parity`
   - **Kết quả**: `FAILED` (`AssertionError: assert 'log_odds' == 'probability'`)
   - **Nguyên nhân**: Xem `AUD-DATA-001`. Dữ liệu `shap_explanations` lưu trong `finhealth.sqlite3` có `"output_space": "log_odds"`, trong khi chạy suy luận trực tiếp từ gói `v1.2.0` hiện tại trả về `"output_space": "probability"`.

### 3.2. Test FAILED do ngưỡng hiệu năng giòn (Flaky Latency Threshold - 1 test)
4. `tests/integration/test_forensic_audit.py::test_api_latency[/companies]`
   - **Kết quả**: `FAILED` (`AssertionError: assert 59.833860024809795 < 50`)
   - **Nguyên nhân**: Xem `AUD-TEST-001`. Trong Lần chạy 1 (khi 62 test bị skip ở setup nên tải hệ thống nhẹ hơn), test này `PASSED`. Trong Lần chạy 2 (khi chạy đủ 184 test bao gồm huấn luyện ML và xuất ảnh 300-DPI), P95 của 25 lần gọi `/api/v1/companies` là `59.83 ms` (median `22.89 ms`), vượt ngưỡng cứng `50 ms`.

### 3.3. Các test bị BLOCKED (ERROR) khi dùng thư mục `%TEMP%` mặc định (62 tests)
- Trong Lần chạy 1 (`pytest_default_basetemp.log`), 62 test sử dụng fixture `tmp_path` của pytest bị chặn tại bước setup bởi `PermissionError: [WinError 5] Access is denied: 'C:\\Users\\hp\\AppData\\Local\\Temp\\pytest-of-hp'` (`AUD-OPS-001`).
- Khi cung cấp `--basetemp` hợp lệ trong Lần chạy 2 (`pytest_scratch_basetemp.log`), **cả 62 test này đều thực thi thành công và đạt `PASSED` 100%**.

---

## 4. Đánh giá Rủi ro "Fake-Green" & Giới hạn Độ phủ (Fake-Green Risks & Coverage Limitations)

### 4.1. Đánh giá các mẫu Fake-Green
- **Không có hiện tượng mock chính hàm đang test**: Tất cả 18 tệp test đều gọi code thật của hệ thống. Việc dùng `httpx.MockTransport` trong `test_sec_ingestion.py` và `test_api_endpoints.py` là đúng chuẩn kiểm thử biên mạng ngoài.
- **Chất lượng Assertion cao**: Các kiểm thử trong `test_forensic_audit.py` và `test_v12_business_logic.py` thực hiện tính toán độc lập từ dữ liệu thô và so sánh với sai số tuyệt đối $< 10^{-12}$ hoặc $< 10^{-7}$. Thậm chí chính các assertion nghiêm ngặt này đã giúp phát hiện ngay lỗi bất đồng bộ `AUD-DATA-001` khi chạy audit độc lập.
- **Một điểm mù (False-Positive / Weak Assertion) đã phát hiện**:
  - Trong `tests/unit/test_visualization_and_cli.py:52-61`, bài test kiểm tra 7 tệp ảnh PNG bằng cách đo kích thước tệp (`> 20000` bytes), độ phân giải (`min(image.size) > 800`), DPI (`~300`) và độ lệch chuẩn màu (`std() > 10`). Vì một biểu đồ chỉ có khung trục, tiêu đề, chú thích và đường chéo nét đứt `y = x` vẫn có kích thước `> 20KB` và `std() > 10`, bài test này đã **PASSED giả tạo (false green)** đối với tệp `07_reliability_calibration.png` mặc dù hàm `_reliability()` không vẽ bất kỳ điểm dữ liệu nào của mô hình lên biểu đồ (`AUD-FUNC-002`).
  - Trong `tests/integration/test_dashboard_ui.py:20-27`, danh sách `FIGURES` chỉ liệt kê 6 tệp ảnh đầu tiên, chưa cập nhật tệp thứ 7 (`07_reliability_calibration.png`).

### 4.2. Giới hạn độ phủ kiểm thử (Coverage Limitations)
1. **Giao diện người dùng (Frontend JS/CSS/HTML)**:
   - Hanya `frontend/js/csv.js` được thực thi trực tiếp qua Node.js trong pytest.
   - Các tệp `frontend/js/app.js`, `frontend/js/charts.js`, `frontend/js/reports.js`, `frontend/js/api.js`, `frontend/js/vi.js` và `frontend/styles.css` chỉ được kiểm tra việc phục vụ tệp tĩnh (`HTTP 200`, MIME type) chứ không có automated test chạy DOM/JS trong pytest. Do đó lỗi hiển thị nhãn SHAP của Random Forest (`AUD-FUNC-001`), lỗi thiếu header `Authorization` (`AUD-SEC-001`) và lỗi cú pháp CSS (`AUD-CODE-002`) không bị bộ pytest phát hiện.
2. **Tương thích Runtime với PostgreSQL và SQL Server**:
   - Module `src/finhealth/db/copy_sqlite_to_sqlserver.py` và các câu truy vấn SQL phức tạp trong `services.py` / `reporting.py` chưa có integration test chạy trực tiếp trên PostgreSQL hoặc SQL Server engine thật trong bộ pytest mặc định (chỉ có test biên dịch chuỗi DDL trong `test_db_migrations.py`).

---

## 5. Tham chiếu Lệnh Thực thi và Tệp Log Bằng chứng

| STT | Lệnh thực thi | Thư mục làm việc | Exit Code | Tệp Log Bằng chứng |
|---:|---|---|---:|---|
| 1 | `.\.venv\Scripts\python.exe -m ruff check .` | `d:\DATN` | `0` | `audit-reports/logs/ruff_and_mypy.log` |
| 2 | `.\.venv\Scripts\python.exe -m mypy src/finhealth` | `d:\DATN` | `1` | `audit-reports/logs/ruff_and_mypy.log` |
| 3 | `.\.venv\Scripts\python.exe -m pytest -v -o cache_dir=$env:TEMP\finhealth_pytest_cache` | `d:\DATN` | `1` | `audit-reports/logs/pytest_default_basetemp.log` |
| 4 | `.\.venv\Scripts\python.exe -m pytest -v --basetemp="...\scratch\pytest_tmp" -o cache_dir="...\scratch\pytest_cache"` | `d:\DATN` | `1` | `audit-reports/logs/pytest_scratch_basetemp.log` |
