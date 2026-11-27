# LỘ TRÌNH KHẮC PHỤC VÀ CẢI TIẾN KỸ THUẬT (REMEDIATION ROADMAP)

Lộ trình dưới đây được sắp xếp theo thứ tự ưu tiên dựa trên mức độ nghiêm trọng của các phát hiện kiểm định (P1 → P2 → P3), nêu rõ mối quan hệ phụ thuộc, rủi ro khi chỉnh sửa và quy trình xác minh sau khi sửa.

---

## 1. Khắc phục Ngay lập tức — Immediate Fixes (Mức độ ưu tiên: HIGH / P1)

### 1.1. Đồng bộ hóa dữ liệu dự báo `v1.2.0` trong SQLite với gói mô hình `v1.2.0` trên đĩa (`AUD-DATA-001`)
- **Mức ưu tiên**: **P1 (Immediate)**
- **Phụ thuộc**: Không có (Gói mô hình `data/artifacts/models/v1.2.0` và code `src/finhealth/ml/explainer.py` đã đúng).
- **Hành động cụ thể**:
  - Chạy đồng bộ lại dự báo của gói `v1.2.0` vào cơ sở dữ liệu SQLite cục bộ `data/processed/parquet/finhealth.sqlite3`:
    ```powershell
    .\.venv\Scripts\python.exe -m finhealth.ml.train_cli --offline --require-real --model-version v1.2.0 --replace-existing --database-url sqlite:///data/processed/parquet/finhealth.sqlite3
    ```
    *(Hoặc chạy script gọi `sync_company_prediction(session, company.id, bundle)` cho 98 công ty trên `finhealth.sqlite3` bằng bundle `v1.2.0` hiện có để không phải huấn luyện lại).*
- **Rủi ro khi sửa**: Thấp. Cần sao lưu tệp `finhealth.sqlite3` trước khi ghi đè; nếu người dùng cũng đang chạy SQL Server (`ADMIN-PC/finhealth_db`), cần chạy đồng bộ cho cả SQLite lẫn SQL Server để hai DB khớp nhau.
- **Phương pháp xác minh sau sửa**:
  - Chạy `pytest tests/integration/test_dashboard_ui.py tests/integration/test_forensic_audit.py -k "not latency" -v` và xác nhận 3 test đang FAIL (`test_company_features_explanations_and_altman[AAPL]`, `test_company_features_explanations_and_altman[AAL]`, `test_prediction_and_api_parity`) chuyển sang `PASSED`.

### 1.2. Sửa hiển thị đơn vị và nhãn đối soát SHAP trên Frontend khi mô hình là Random Forest (`AUD-FUNC-001`)
- **Mức ưu tiên**: **P1 (Immediate)**
- **Phụ thuộc**: Kết hợp với `AUD-DATA-001` để API trả về `"output_space": "probability"`.
- **Hành động cụ thể**:
  - Trong `frontend/js/app.js:633-638`: Thay nhãn cứng `"Xác suất sigmoid trước hiệu chỉnh"` bằng biểu thức theo `prediction?.output_space === "probability" ? "Xác suất gốc trước hiệu chỉnh" : "Xác suất sigmoid trước hiệu chỉnh"`.
  - Trong `frontend/js/app.js:591, 610` (`printCreditMemo`, `renderDiagnostic`), `frontend/js/charts.js:262, 278, 285` (`renderShapWaterfallChart`) và `frontend/index.html:159`: Hiển thị đơn vị theo `prediction?.output_space === "probability"` (ví dụ `"đóng góp xác suất"` thay vì gắn cứng `"log-odds"`).
- **Rủi ro khi sửa**: Rất thấp (chỉ thay đổi chuỗi hiển thị trên UI dựa trên trường `output_space` đã có sẵn trong schema `PredictionDetailSchema`).
- **Phương pháp xác minh sau sửa**:
  - Kiểm tra tab "Giải thích rủi ro" với mô hình `v1.2.0` (`random_forest`): Giá trị gốc + tổng đóng góp của AAPL hiển thị `0.0722 (xác suất)`, xác suất gốc trước hiệu chỉnh hiển thị `7.218%` (thay vì `51.804%`).

### 1.3. Khắc phục 9 lỗi kiểm tra kiểu tĩnh Mypy trong `src/finhealth/ml/` (`AUD-CODE-001`)
- **Mức ưu tiên**: **P1 (Immediate)**
- **Phụ thuộc**: Không có.
- **Hành động cụ thể**:
  1. `src/finhealth/ml/registry.py:114`: Khai báo kiểu tường minh `candidates: dict[str, DistressClassifier] = { ... }` và tại dòng 174 khai báo `candidate_test_metrics: dict[str, dict[str, Any]] = { ... }` (giải quyết 5 lỗi trong `registry.py`).
  2. `src/finhealth/ml/distress_classifier.py:157, 160`: Dùng `np.asarray(self.model_.predict(inputs, output_margin=True), dtype=np.float64)` và `np.asarray(self.model_.predict_proba(inputs), dtype=np.float64)[:, 1]` (giải quyết 2 lỗi trong `distress_classifier.py`).
  3. `src/finhealth/ml/kaggle_loader.py:121`: Thay `np.where(~altman_valid, None, ...)` bằng `pd.Series(np.where(altman_valid["altman_z_score"] < ALTMAN_MANUFACTURING_CUTOFF, "DISTRESS", ...), index=df.index).where(altman_valid, None)` hoặc tương đương (giải quyết 1 lỗi trong `kaggle_loader.py`).
  4. `src/finhealth/ml/train_cli.py:619`: Bọc `real_only = bool(panel["data_source"].eq("cached_sec").all())` (giải quyết 1 lỗi trong `train_cli.py`).
- **Rủi ro khi sửa**: Rất thấp (các thay đổi chỉ làm rõ kiểu dữ liệu cho trình kiểm tra tĩnh mà không thay đổi hành vi toán học).
- **Phương pháp xác minh sau sửa**:
  - Chạy `.\.venv\Scripts\python.exe -m mypy src/finhealth` và `.\.venv\Scripts\python.exe -m ruff check .` đều phải trả về exit code `0` (`Success: no issues found in 61 source files`).

---

## 2. Khắc phục Ngắn hạn — Short-Term Fixes (Mức độ ưu tiên: MEDIUM / P2)

### 2.1. Sửa lỗi vẽ biểu đồ rỗng `07_reliability_calibration.png` (`AUD-FUNC-002`)
- **Mức ưu tiên**: **P2 (Short-Term)**
- **Phụ thuộc**: Nên thực hiện trước hoặc cùng lúc với lần chạy lại `train_cli` của `AUD-DATA-001` để xuất lại tệp PNG số 07.
- **Hành động cụ thể**:
  - Trong `src/finhealth/ml/visualization.py:317-325`, sửa tên khóa trong `_reliability()`:
    - Thay `row.get("score") == score_kind and row.get("count", 0) > 0` bằng `row.get("model") == score_kind and row.get("n", 0) > 0`.
    - Thay `row["mean_score"]` bằng `row["mean_probability"]`.
    - Thay `row["observed_rate"]` bằng `row["observed_prevalence"]`.
  - Bổ sung `"07_reliability_calibration.png"` vào tuple `FIGURES` trong `tests/integration/test_dashboard_ui.py:20-27`.
- **Rủi ro khi sửa**: Rất thấp.
- **Phương pháp xác minh sau sửa**:
  - Kiểm tra đối tượng `axis.lines` trong unit test của `_reliability()` phải có $\ge 3$ đường (1 đường tham chiếu `y=x` + đường `raw` + đường `calibrated`) và kiểm tra tệp ảnh `data/artifacts/figures/07_reliability_calibration.png` được tạo lại.

### 2.2. Khôi phục quyền ACL cho `.pytest_cache` và `%TEMP%\pytest-of-hp` & Ổn định hóa test độ trễ (`AUD-OPS-001`, `AUD-TEST-001`)
- **Mức ưu tiên**: **P2 (Short-Term)**
- **Phụ thuộc**: Quyền quản trị máy trạm Windows cục bộ (đối với ACL).
- **Hành động cụ thể**:
  - Trên máy Windows cục bộ, chạy PowerShell (Administrator) để xóa hoặc cấp lại quyền cho `D:\DATN\.pytest_cache` và `C:\Users\hp\AppData\Local\Temp\pytest-of-hp`; hoặc thêm `cache_dir = ".venv/pytest-cache"` vào `[tool.pytest.ini_options]` trong `pyproject.toml`.
  - Trong `tests/integration/test_forensic_audit.py:720`, điều chỉnh ngưỡng kiểm tra độ trễ `test_api_latency` (ví dụ `assert median < 40 and p95 < 120`) để tránh lỗi flaky khi chạy toàn bộ test suite trên máy cá nhân.
- **Rủi ro khi sửa**: Thấp.
- **Phương pháp xác minh sau sửa**:
  - Chạy lệnh chuẩn `pytest -v` (không cần truyền `--basetemp`) đạt `184 passed, 0 failed, 0 errors`.

### 2.3. Bổ sung hỗ trợ xác thực `ADMIN_TOKEN` trên Frontend & Cập nhật `README.md` (`AUD-SEC-001`, `AUD-DOC-001`)
- **Mức ưu tiên**: **P2 (Short-Term)**
- **Phụ thuộc**: Không có.
- **Hành động cụ thể**:
  - Trong `frontend/js/api.js`: Hỗ trợ gửi header `Authorization: Bearer <token>` (lấy từ `sessionStorage` hoặc hộp thoại nhập token khi server trả về `HTTP 403`) cho hàm `api.analyze()`, và bổ sung thông báo tiếng Việt cho mã `403` trong `errorMessage()`.
  - Trong `README.md`: Cập nhật thông tin phiên bản mô hình active từ `v1.1.0` lên `v1.2.0`, số lượng doanh nghiệp từ 80 lên 98 (1,506 báo cáo năm), các chỉ số Brier / ROC-AUC / TreeSHAP error theo `data/artifacts/models/v1.2.0/BENCHMARK_REPORT.md`, và số lượng biểu đồ từ 6 lên 7.
- **Rủi ro khi sửa**: Thấp.
- **Phương pháp xác minh sau sửa**:
  - Kiểm thử tích hợp với `app_env="production"` và `admin_token` được cấu hình; đối chiếu mọi con số trong `README.md` với `v1.2.0/evaluation_report.json`.

---

## 3. Cải tiến Kiến trúc, Hiệu năng và Nợ Kỹ thuật Dài hạn — Medium & Long-Term Improvements (P2 / P3)

### 3.1. Cô lập trạng thái `ModelRegistryState` theo từng Application Instance (`AUD-ARCH-001`)
- **Mức ưu tiên**: **P2 (Architectural Improvement)**
- **Hành động cụ thể**:
  - Trong `src/finhealth/api/dependencies.py`, lưu `self._directory: Path | None = None` trong `ModelRegistryState.initialize(directory)` để nếu `directory.resolve() != self._directory` thì nạp lại bundle từ thư mục mới; hoặc khởi tạo `ModelRegistryState()` riêng cho mỗi `create_app()`.
- **Phương pháp xác minh**: Viết unit test khởi tạo 2 app `create_app(settings_a)` và `create_app(settings_b)` với 2 thư mục model khác nhau mà không cần gán tay `app.state.model_registry`.

### 3.2. Cache `CompositeBenchmark` và cấu hình CORS động (`AUD-PERF-001`, `AUD-SEC-002`)
- **Mức ưu tiên**: **P3 (Performance & Security Hardening)**
- **Hành động cụ thể**:
  - Cache kết quả `CompositeBenchmark` cho tập doanh nghiệp năm mới nhất và chỉ xóa cache khi có giao dịch ghi (`analyze`, `train`, `backfill`).
  - Thêm `cors_allowed_origins: list[str] = ["http://localhost:3000"]` vào `Settings` (`src/finhealth/core/config.py`).

### 3.3. Sửa cú pháp CSS, văn bản báo cáo Kaggle và chuẩn hóa môi trường DevOps (`AUD-CODE-002`, `AUD-ACAD-001`, `AUD-OPS-002`, `AUD-DATA-002`)
- **Mức ưu tiên**: **P3 (Maintainability & DevOps)**
- **Hành động cụ thể**:
  - Xóa khoảng trắng thừa trong 4 selector CSS tại `frontend/styles.css:49,59,73,1309` (`button:disabled`, `button:focus-visible`, `input::placeholder`, `dialog::backdrop`).
  - Cập nhật `src/finhealth/ml/train_cli.py:690-703` để khi `dataset == "kaggle"`, tệp `BENCHMARK_REPORT.md` mô tả đúng nguồn dữ liệu Kaggle thay vì in thông điệp của dữ liệu `synthetic_benchmark`.
  - Khởi tạo Git (`git init`), tạo tệp lockfile cố định phiên bản phụ thuộc, gỡ gói `yfinance` bị thiếu dependency khỏi `.venv` và chạy `pip install -e ".[dev]"` để đồng bộ metadata gói `finhealth` lên `1.3.0`.
- **Phương pháp xác minh**:
  - `git status` hoạt động bình thường; `.\.venv\Scripts\python.exe -m pip check` trả về `No broken requirements found` (exit code 0); `pip show finhealth` hiển thị `Version: 1.3.0`.
