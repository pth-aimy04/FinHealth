# SỔ ĐĂNG KÝ PHÁT HIỆN KIỂM ĐỊNH (FINDINGS REGISTER)

## 1. Bảng Tổng hợp Chính thức (Official Findings Table)

| ID | Category | Severity | Verification Status | Location | Evidence | Impact | Recommendation |
|---|---|---|---|---|---|---|---|
| `AUD-DATA-001` | Database & Data Integrity | **HIGH (P1)** | `REPRODUCED` | `data/processed/parquet/finhealth.sqlite3` (`model_predictions`), `data/artifacts/models/v1.2.0/`, `src/finhealth/ml/explainer.py:73-76`, `tests/integration/test_dashboard_ui.py:128-133`, `tests/integration/test_forensic_audit.py:586,618` | Bản ghi `model_predictions` của `v1.2.0` trong SQLite được tạo lúc `13:20:09Z–13:20:24Z` với `output_space="log_odds"` nhưng `base_value=0.4982` và `contributions` lại thuộc không gian xác suất của Random Forest; trong khi gói `v1.2.0/models.joblib` trên đĩa được tạo lúc `13:31:09Z` và `ShapExplainer` xuất `output_space="probability"`. Làm FAIL 3 integration tests. | Dữ liệu dự báo trong DB không khớp với gói mô hình `v1.2.0` đang phát hành; làm hỏng kiểm thử đối soát SHAP và gây sai lệch diễn giải toán học giữa `raw_margin` (log-odds) và tổng SHAP (xác suất). | Chạy lại quy trình đồng bộ dự báo (`sync_company_prediction` hoặc `train_cli --replace-existing`) để cập nhật toàn bộ 98 dòng `model_predictions` và `forecast_evidence` trong SQLite khớp với bundle `v1.2.0` hiện hành. |
| `AUD-FUNC-001` | Functional & Academic Correctness | **HIGH (P1)** | `VERIFIED` | `frontend/js/app.js:629-638`, `frontend/js/charts.js:254-288`, `frontend/index.html:159` | Khi `output_space === "probability"` (mô hình Random Forest trong `v1.2.0`), `app.js:635` vẫn hiển thị nhãn `"Xác suất sigmoid trước hiệu chỉnh"`; đặc biệt với dữ liệu SQLite hiện tại (`output_space="log_odds"` nhưng giá trị SHAP là xác suất), `app.js:631` tính `1 / (1 + Math.exp(-summed))` trên xác suất `0.07218` ra `51.804%` thay vì `7.218%`. `charts.js:262,278,285` và `index.html:159` gắn cứng đơn vị `"log-odds"` cho mọi biểu đồ SHAP. | Người dùng nhận được thông tin giải thích rủi ro sai lệch về mặt toán học trên tab "Giải thích rủi ro" khi mô hình được chọn là Random Forest. | Cập nhật `charts.js`, `app.js` và `index.html` để hiển thị động đơn vị (`log-odds` hoặc `đóng góp xác suất`) theo `prediction.output_space`, đồng thời đồng bộ lại dữ liệu SQLite. |
| `AUD-CODE-001` | Clean Code & Type Safety | **HIGH (P1)** | `REPRODUCED` | `src/finhealth/ml/kaggle_loader.py:121`, `src/finhealth/ml/distress_classifier.py:157,160`, `src/finhealth/ml/registry.py:144,153,180,210,245`, `src/finhealth/ml/train_cli.py:619` | Chạy `.\.venv\Scripts\python.exe -m mypy src/finhealth` trả về `Found 9 errors in 4 files (checked 61 source files)` với mã thoát `MYPY_EXIT=1`. | Vi phạm cổng kiểm định kiểu tĩnh của dự án; tồn tại các bất tương thích kiểu giữa `ModelType` (`Literal`), `str`, `np.bool_` và kiểu trả về của `XGBClassifier.predict` / `RandomForestClassifier.predict_proba`. | Sửa 9 lỗi kiểu tĩnh trong 4 tệp thuộc module `src/finhealth/ml/` và xác minh lại bằng `mypy src/finhealth`. |
| `AUD-FUNC-002` | Functional & Visualization | **MEDIUM (P2)** | `VERIFIED` | `src/finhealth/ml/evaluator.py:119-127`, `src/finhealth/ml/visualization.py:318-325`, `data/artifacts/figures/07_reliability_calibration.png` | `reliability_bins()` trả về dict với các khóa `model`, `n`, `mean_probability`, `observed_prevalence`, nhưng `_reliability()` trong `visualization.py` lọc theo `row.get("score") == score_kind and row.get("count", 0) > 0` và đọc `row["mean_score"]`, `row["observed_rate"]`. | Điều kiện lọc `subset` trong `_reliability()` luôn rỗng (`[]`), khiến biểu đồ `07_reliability_calibration.png` (cho cả SEC và Kaggle) chỉ vẽ đường chéo tham chiếu `y = x` mà không có bất kỳ điểm dữ liệu thực nghiệm nào. | Sửa `_reliability()` trong `src/finhealth/ml/visualization.py:318-325` để đọc đúng các khóa `model`, `n`, `mean_probability`, `observed_prevalence` và xuất lại biểu đồ số 07. |
| `AUD-SEC-001` | Security & Functional Integration | **MEDIUM (P2)** | `STATICALLY_CONFIRMED` | `src/finhealth/api/dependencies.py:25-35`, `src/finhealth/api/routers/companies.py:80`, `src/finhealth/api/routers/ingestion.py:14`, `frontend/js/api.js:43-68,101-115` | `require_write_access` bắt buộc header `Authorization: Bearer <ADMIN_TOKEN>` khi `app_env` không phải `development`/`test` hoặc khi `admin_token` được cấu hình, nhưng `frontend/js/api.js` không có bất kỳ cơ chế nào để gửi header `Authorization`. | Trong môi trường `staging` hoặc `production` (hoặc khi đặt `ADMIN_TOKEN`), nút "Phân tích hồ sơ SEC" trên giao diện web luôn thất bại với lỗi HTTP 403. | Bổ sung cơ chế xác thực hoặc nhập/gửi bearer token cho các thao tác quản trị trên giao diện khi triển khai ngoài môi trường `development`, hoặc ẩn/vô hiệu hóa form cập nhật SEC đối với người dùng chỉ đọc. |
| `AUD-ARCH-001` | Architecture & State Management | **MEDIUM (P2)** | `STATICALLY_CONFIRMED` | `src/finhealth/api/dependencies.py:57-101`, `src/finhealth/api/main.py:36,59` | `create_app()` gán `app.state.model_registry = _MODEL_STATE` (biến toàn cục cấp module). Trong `ModelRegistryState.initialize()`, nếu `self._initialized` đã là `True`, hàm lập tức `return` mà không kiểm tra `directory` mới có khớp với thư mục đã nạp hay không. | Nếu nhiều instance `FastAPI` được tạo qua `create_app(settings)` trong cùng tiến trình với các `model_path` khác nhau (mà không ghi đè thủ công `app.state.model_registry`), instance sau sẽ âm thầm dùng lại model bundle của instance đầu tiên. | Khởi tạo `ModelRegistryState()` mới bên trong `create_app()` cho từng ứng dụng (hoặc lưu kèm đường dẫn `self._directory` trong `ModelRegistryState` để nạp lại khi `directory` thay đổi). |
| `AUD-TEST-001` | Testing & QA Reliability | **MEDIUM (P2)** | `REPRODUCED` | `tests/integration/test_forensic_audit.py:702-720` | `test_api_latency[/companies]` đo 25 request qua `TestClient` và assert cứng `assert p95 < 50`. Trong lần chạy toàn bộ test suite (`pytest_scratch_basetemp.log`), test này FAILED với `p95 = 59.833860 ms` (median `22.8875 ms`). | Kiểm thử phụ thuộc chặt vào tải CPU/I/O tức thời của máy chạy test, gây ra hiện tượng flaky failure (lúc PASS lúc FAIL) trong cổng kiểm thử tự động. | Tách kiểm thử hiệu năng/độ trễ sang nhóm benchmark riêng (ví dụ dùng pytest marker) hoặc nới ngưỡng kiểm tra chống suy giảm hiệu năng cực đoan (regression guard) phù hợp với môi trường không chuyên dụng. |
| `AUD-OPS-001` | DevOps & Environment | **MEDIUM (P2)** | `REPRODUCED` | `D:\DATN\.pytest_cache`, `C:\Users\hp\AppData\Local\Temp\pytest-of-hp` | Chạy `pytest -v` mặc định gặp `PermissionError: [WinError 5] Access is denied: 'C:\\Users\\hp\\AppData\\Local\\Temp\\pytest-of-hp'`, gây ra 62 lỗi `ERROR` ở bước setup fixture `tmp_path` (`pytest_default_basetemp.log`). | Cổng kiểm thử chuẩn `pytest -v` thất bại hàng loạt trên môi trường hiện tại nếu không truyền tham số `--basetemp` và `-o cache_dir` sang thư mục khác. | Khắc phục quyền sở hữu/ACL của Windows trên thư mục `%TEMP%\pytest-of-hp` và `D:\DATN\.pytest_cache`, hoặc cấu hình `basetemp` / `cache_dir` vào thư mục cục bộ có quyền ghi trong `pyproject.toml`. |
| `AUD-DOC-001` | Documentation & DX | **MEDIUM (P2)** | `VERIFIED` | `README.md:40,113,185,195-204`, `data/artifacts/models/latest.json`, `data/artifacts/models/v1.2.0/BENCHMARK_REPORT.md` | `README.md` tuyên bố gói mô hình active là `v1.1.0` với 80 công ty, 1,234 báo cáo năm, 748 cặp huấn luyện, Brier score `0.058535` và 6 biểu đồ 300-DPI. Thực tế `latest.json` kích hoạt `v1.2.0` (mô hình chính là `random_forest`, 98 công ty, 1,506 báo cáo năm, 900 cặp huấn luyện, Brier `0.048583`, 7 biểu đồ 300-DPI). | Tài liệu hướng dẫn và thông số kiểm định công bố trong `README.md` không phản ánh đúng trạng thái dữ liệu và mô hình đang được phục vụ bởi hệ thống. | Cập nhật `README.md` để phản ánh chính xác phiên bản mô hình `v1.2.0`, quy trình chọn mô hình ứng viên (XGBoost / LightGBM / Random Forest), bộ dữ liệu 98 công ty và 7 biểu đồ xuất bản. |
| `AUD-SEC-002` | Security & Configuration | **LOW (P3)** | `STATICALLY_CONFIRMED` | `src/finhealth/ml/registry.py:304-324`, `src/finhealth/api/main.py:68-74` | `load_bundle()` sử dụng `joblib.load()` (dựa trên `pickle`) sau khi kiểm tra SHA-256 trong `metadata.json` cùng thư mục. Ngoài ra, `CORSMiddleware` đặt cứng `allow_origins=["http://localhost:3000"]` cho mọi môi trường khác `development`. | SHA-256 chỉ chống hỏng tệp (corruption), không chống thực thi mã tùy ý nếu kẻ tấn công có quyền ghi cả `models.joblib` và `metadata.json`. Cấu hình CORS cứng `localhost:3000` không linh hoạt khi triển khai domain thực tế. | Bổ sung biến cấu hình `CORS_ALLOWED_ORIGINS` trong `Settings`; hạn chế chặt quyền ghi hệ thống tệp đối với `data/artifacts/models` hoặc sử dụng chữ ký số (HMAC/public-key) với khóa tách biệt nếu nạp artifact từ kho lưu trữ ngoài. |
| `AUD-PERF-001` | Performance & Scalability | **LOW (P3)** | `STATICALLY_CONFIRMED` | `src/finhealth/api/services.py:388-416,658-689` | Trong `list_company_summaries()`, khi có bất kỳ bộ lọc nào (`filtered == True`) hoặc `offset > 0` hoặc `len(rows) == limit`, hàm gọi `self._annual_metrics(session)` để truy vấn lại toàn bộ danh sách công ty và chỉ số năm trong DB nhằm dựng `CompositeBenchmark` trong Python. | Với quy mô 98 công ty hiện tại độ trễ chỉ khoảng 10–25ms, nhưng khi mở rộng lên hàng chục nghìn doanh nghiệp, việc quét toàn bảng và sắp xếp phân vị trên mỗi request phân trang/lọc sẽ tạo nút thắt cổ chai CPU và I/O. | Cache đối tượng `CompositeBenchmark` theo phiên bản dữ liệu/kỳ báo cáo hoặc tính sẵn điểm `composite_health_score` vào bảng `financial_metrics` khi chạy ETL. |
| `AUD-DATA-002` | Database & Schema Design | **LOW (P3)** | `STATICALLY_CONFIRMED` | `src/finhealth/db/lineage_models.py:12-56`, `migrations/versions/0004_filing_lineage.py:15-28` | `FilingVersion.issuer_key` lưu chuỗi định danh (`sec:0000320193`, `vn:FPT`) không có khóa ngoại liên kết với `companies`; `ForecastEvidence.filing_version_id` khai báo `ForeignKey("filing_versions.id")` nhưng không có `ondelete="CASCADE"` và không có index riêng trên cột `filing_version_id` (chỉ có composite unique constraint). | Dù thiết kế append-only chủ đích giữ lại lịch sử khi xóa dòng ở bảng serving, việc thiếu index hoặc quy tắc xóa rõ ràng trên `ForecastEvidence` có thể gây lỗi khóa ngoại nếu cần dọn dẹp một `FilingVersion`. | Xem xét bổ sung index cho các truy vấn lọc trên `filing_versions` / `forecast_evidence` và tài liệu hóa rõ chính sách lưu trữ vĩnh viễn (immutable append-only) của các bảng lineage. |
| `AUD-ACAD-001` | Academic & Scientific Methodology | **LOW (P3)** | `STATICALLY_CONFIRMED` | `src/finhealth/ml/kaggle_loader.py:40-144`, `src/finhealth/ml/splitter.py:88-90,116-120,163-164` | `load_kaggle_bankruptcy_panel()` gán `period_end_date = YYYY-12-31` và không có cột `filed_date`. Khi chạy qua `build_next_period_panel`, `training_horizon_rows` và `prepare_validation_test`, các bước lọc theo thời điểm công bố (`filed_date` và publication embargo) được bỏ qua, chỉ chia theo `fiscal_year`. | Trên bộ dữ liệu Kaggle, nhãn của năm `train_end_year` (ví dụ 2014, được công bố vào đầu năm 2015) vẫn được dùng trong tập huấn luyện, và tập test không có ngày `threshold_calibration_asof` (`None`). | Ghi chú rõ giới hạn thiếu ngày công bố (`filed_date`) của bộ dữ liệu Kaggle trong `BENCHMARK_REPORT.md` (hiện báo cáo Kaggle vẫn in đoạn văn mẫu về publication embargo của SEC). |
| `AUD-OPS-002` | DevOps & Supply Chain | **LOW (P3)** | `VERIFIED` | `d:\DATN` (root), `pyproject.toml`, `.venv` | 1) Không có thư mục `.git`; 2) `pyproject.toml` dùng ràng buộc `>=` mà không có lockfile; 3) Gói `finhealth` trong `.venv` có metadata version `0.1.0` thay vì `1.3.0`; 4) `pip check` trả về exit code `1` do gói `yfinance 0.2.56` trong `.venv` thiếu 5 dependencies (`beautifulsoup4`, `frozendict`, `platformdirs`, `pytz`, `requests`). | Không thể tái lập chính xác 100% môi trường build trên máy khác từ `pyproject.toml`; `pip check` báo lỗi môi trường; không có quản lý lịch sử mã nguồn qua Git. | Khởi tạo Git repository; xuất lockfile cố định phiên bản các thư viện; gỡ bỏ gói `yfinance` không sử dụng khỏi `.venv`; chạy `pip install -e . --no-deps` để đồng bộ version `1.3.0`. |
| `AUD-CODE-002` | Clean Code & Frontend CSS | **LOW (P3)** | `STATICALLY_CONFIRMED` | `frontend/styles.css:49,59,73,1309` | Có 4 selector CSS chứa khoảng trắng không hợp lệ giữa phần tử và pseudo-class / pseudo-element: `button: disabled` (dòng 49), `button: focus-visible` (dòng 59), `input: :placeholder` (dòng 73), `dialog: :backdrop` (dòng 1309). | Trong CSS chuẩn, khoảng trắng biến selector thành descendant combinator hoặc cú pháp không hợp lệ, khiến style `:disabled`, `:focus-visible` của `<button>`, `::placeholder` của `<input>` và `::backdrop` của `<dialog>` không có hiệu lực đúng như thiết kế. | Xóa khoảng trắng thừa để thành `button:disabled`, `button:focus-visible`, `input::placeholder`, `dialog::backdrop`. |
| `AUD-INFO-001` | Academic & Domain Transparency | **INFO (P4)** | `VERIFIED` | `src/finhealth/ml/splitter.py:39-60`, `src/finhealth/etl/financial_ratios.py:33-74`, `frontend/index.html:162-163,192` | Nhãn mục tiêu phân loại (`is_distressed`) trên dữ liệu SEC là một quy tắc chỉ báo kế toán (proxy rule), không phải dữ liệu phá sản pháp lý (Chapter 7/11); Altman Z cho ngành sản xuất dùng giá trị sổ sách của vốn chủ sở hữu (book equity) cho thành phần X4. | Không phải lỗi phần mềm; dự án đã công bố rất rõ ràng và trung thực các giới hạn này trên giao diện, báo cáo benchmark và docstring. Tuy nhiên người đọc báo cáo học thuật cần lưu ý tính chất tự hồi quy của việc dự báo một chỉ báo tổ hợp từ các tỷ số kế toán kỳ tới. | Duy trì sự minh bạch hiện có; nếu mở rộng nghiên cứu học thuật, có thể bổ sung thực nghiệm đối chiếu với sự kiện phá sản pháp lý thực tế (như đã bước đầu thử nghiệm qua Kaggle dataset). |
| `AUD-INFO-002` | Architecture & Rate Limiting | **INFO (P4)** | `VERIFIED` | `src/finhealth/ingestion/rate_limiter.py:9-45`, `src/finhealth/ingestion/README.md:6-16` | `AsyncRateLimiter` dùng `asyncio.Lock()` và `time.monotonic()` trong phạm vi một event loop duy nhất, và `atomic_write_json` dùng `threading.RLock()` trong phạm vi một tiến trình. | Đáp ứng đúng yêu cầu cho mô hình single-dispatcher hiện tại; không tự động chia sẻ quota nếu chạy nhiều worker process độc lập cùng gọi SEC. | Tuân thủ đúng hướng dẫn vận hành single-dispatcher trong `src/finhealth/ingestion/README.md` khi triển khai thực tế. |
| `AUD-INFO-003` | Testing & Environment Scope | **INFO (P4)** | `NOT_TESTED` | Môi trường kiểm định cục bộ | Kiểm thử giao diện trực quan trên trình duyệt thật (headless browser / Playwright) và kiểm thử kết nối trực tiếp tới PostgreSQL / SQL Server thật không được thực thi trong đợt audit Read-Only này. | Phạm vi xác minh runtime giới hạn ở SQLite, FastAPI `TestClient`, Node.js (cho CSV serializer) và phân tích tĩnh HTML/CSS/JS. | Thực hiện kiểm thử E2E trên trình duyệt và trên hệ quản trị cơ sở dữ liệu đích (PostgreSQL/SQL Server) trong môi trường staging trước khi golive. |

---

## 2. Mô tả Chi tiết Từng Phát hiện (Detailed Findings Analysis)

### `AUD-DATA-001` — Bất đồng bộ giữa gói mô hình `v1.2.0` trên đĩa và dữ liệu dự báo `model_predictions` lưu trong SQLite

- **Lĩnh vực kiểm định**: Database & Data Integrity / Testing & QA Reliability
- **Mức độ nghiêm trọng**: **HIGH (P1)**
- **Trạng thái xác minh**: `REPRODUCED`
- **Thành phần & Vị trí**:
  - `data/processed/parquet/finhealth.sqlite3` (bảng `model_predictions`, `model_version = 'v1.2.0'`)
  - `data/artifacts/models/v1.2.0/metadata.json` và `models.joblib`
  - `src/finhealth/ml/explainer.py:73-76`
  - `tests/integration/test_dashboard_ui.py:113-137`
  - `tests/integration/test_forensic_audit.py:547-625`
- **Bằng chứng trực tiếp**:
  1. Truy vấn trực tiếp `finhealth.sqlite3` (ở chế độ chỉ đọc) cho thấy 98 bản ghi `model_predictions` của phiên bản `v1.2.0` được tạo trong khoảng `2026-11-20 13:20:09.723600` đến `2026-11-20 13:20:24.765962`.
  2. Trong khi đó, tệp `data/artifacts/models/v1.2.0/metadata.json` và `data/artifacts/models/latest.json` ghi nhận gói mô hình `v1.2.0` trên đĩa được tạo lúc `2026-11-20T13:31:09.740691+00:00` (tức là 11 phút sau khi dữ liệu SQLite được ghi).
  3. Trong SQLite, cột `shap_explanations` của `v1.2.0` lưu:
     - Với CIK đầu tiên (`0000001800` - ABT): `base_value = 0.49821111111111127`, `raw_margin = -3.4703795467786223`, `raw_probability = 0.03016687516808507`, nhưng **`output_space = "log_odds"`**.
     - Với `AAPL`: `base_value + sum(contributions) = 0.07218471233571078` (đây chính là xác suất raw của Random Forest), trong khi `raw_margin = logit(0.07218471233571078) = -2.5536043865332405`, nhưng `output_space` trong DB lại là `"log_odds"`.
  4. Khi chạy `pytest`, 3 test tích hợp thất bại:
     - `test_company_features_explanations_and_altman[AAPL]`: `AssertionError: assert 2.6257890988689514 < 1e-05 where 2.6257890988689514 = abs((-2.5536043865332405 - 0.07218471233571078))` (do `prediction.get("output_space")` trong DB là `"log_odds"`, test đi vào nhánh `else` và so sánh `raw_margin` với tổng SHAP trên thang xác suất).
     - `test_company_features_explanations_and_altman[AAL]`: `AssertionError: assert 0.3138853967006634 < 1e-05`.
     - `test_prediction_and_api_parity`: `AssertionError: assert 'log_odds' == 'probability'` khi đối chiếu `stored_shap["output_space"]` trong SQLite với `explanation["output_space"]` được tính trực tiếp từ `bundle` `v1.2.0` (`ShapExplainer` tại `src/finhealth/ml/explainer.py:73-76` trả về `"probability"` cho `RandomForestClassifier`).
- **Quy trình xác minh**:
  - Chạy lệnh: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_dashboard_ui.py tests/integration/test_forensic_audit.py -v --basetemp=...`
  - Xem log chi tiết tại: `audit-reports/logs/pytest_scratch_basetemp.log`.
- **Expected behavior**: Mọi bản ghi dự báo của `model_version = 'v1.2.0'` trong `finhealth.sqlite3` phải khớp tuyệt đối với kết quả suy luận của gói mô hình `v1.2.0` hiện hành trên đĩa (`output_space = "probability"`).
- **Actual behavior**: Dữ liệu trong `finhealth.sqlite3` là sản phẩm của một phiên bản mã nguồn lúc 13:20Z (trước khi `explainer.py:73-76` được sửa để gán `"output_space": "probability"` cho `RandomForestClassifier`, và khi lần chạy lại lúc 13:31Z ghi vào `"database": "configured database"` tức SQL Server trong `.env` chứ không cập nhật lại tệp `finhealth.sqlite3`).
- **Phân tích nguyên nhân gốc (Root Cause)**:
  - Trong `src/finhealth/ml/train_cli.py:498-501`, hàm `persist_real_panel()` ưu tiên `configured_url = database_url or settings.database_url_override`. Khi tệp `.env` được cấu hình `DATABASE_URL` trỏ sang SQL Server, lần chạy `train_cli` lúc `13:31:09Z` (sau khi sửa `explainer.py`) đã ghi dự báo mới vào SQL Server (`"database": "configured database"` trong `v1.2.0/evaluation_report.json:358`) mà **không cập nhật** tệp cục bộ `data/processed/parquet/finhealth.sqlite3` (vốn vẫn giữ dữ liệu từ lần chạy lúc `13:20Z`).
- **Phạm vi ảnh hưởng**: Toàn bộ 98 dự báo `v1.2.0` trong cơ sở dữ liệu SQLite cục bộ, API `/api/v1/companies/{identifier}` khi chạy trên SQLite, giao diện Giải thích rủi ro và bộ kiểm thử tích hợp của dự án.
- **Khuyến nghị khắc phục**: Chạy đồng bộ lại dữ liệu dự báo của `v1.2.0` vào `data/processed/parquet/finhealth.sqlite3` (ví dụ truyền `--database-url sqlite:///data/processed/parquet/finhealth.sqlite3` khi chạy `train_cli` hoặc gọi `sync_company_prediction` cho 98 công ty trên SQLite với bundle `v1.2.0`).
- **Mức độ tin cậy của kết luận**: **Cao (100% — Có bằng chứng timestamp, dữ liệu DB, mã nguồn và log thực thi test)**.

---

### `AUD-FUNC-001` — Giao diện Giải thích rủi ro (`app.js`, `charts.js`, `index.html`) hiển thị và tính toán sai khi mô hình chính là Random Forest (`output_space = "probability"`)

- **Lĩnh vực kiểm định**: Functional Correctness / Academic & Scientific Correctness
- **Mức độ nghiêm trọng**: **HIGH (P1)**
- **Trạng thái xác minh**: `VERIFIED`
- **Thành phần & Vị trí**:
  - `frontend/js/app.js:628-638`
  - `frontend/js/charts.js:254-288`
  - `frontend/index.html:159`
  - `frontend/js/app.js:590-592`
- **Bằng chứng trực tiếp**:
  1. Trong `frontend/js/app.js:629-638`:
     ```javascript
     const summed = complete ? prediction.base_value + all.reduce((sum, [, value]) => sum + value, 0) : null;
     const finalProbability = finite(summed)
       ? (prediction?.output_space === "probability" ? summed : 1 / (1 + Math.exp(-summed)))
       : null;
     $("shap-reconciliation").innerHTML = [
       `Giá trị gốc <strong>${number(prediction?.base_value, 4)}</strong>`,
       `Giá trị gốc + tổng đóng góp <strong>${number(summed, 4)} ${prediction?.output_space === "probability" ? "(xác suất)" : "log-odds"}</strong>`,
       `Xác suất sigmoid trước hiệu chỉnh <strong>${percent(finalProbability, 3)}</strong>`,
       `Xác suất mô hình công bố <strong>${percent(prediction?.distress_probability, 3)}</strong>`,
     ].map((text) => `<span>${text}</span>`).join("");
     ```
     - Khi đọc dữ liệu từ `finhealth.sqlite3` hiện tại (`output_space = "log_odds"` do lỗi `AUD-DATA-001`), `finalProbability` áp dụng hàm sigmoid `1 / (1 + Math.exp(-summed))` lên `summed = 0.07218` (vốn đã là xác suất của Random Forest), cho ra kết quả sai hoàn toàn là **`51.804%`** thay vì **`7.218%`**.
     - Ngay cả khi `output_space === "probability"`, nhãn thứ 3 ở dòng 636 vẫn ghi cứng là **`"Xác suất sigmoid trước hiệu chỉnh"`** mặc dù Random Forest không hề dùng hàm liên kết sigmoid.
  2. Trong `frontend/js/charts.js:262,278,285`, hàm `renderShapWaterfallChart` gắn cứng chuỗi `"log-odds"` ở `aria-label` và tooltip:
     - Dòng 262: `"Đóng góp rủi ro có dấu của TreeSHAP trên thang log-odds"`
     - Dòng 278: `aria-label="${escapeHtml(vietnamese(row.feature))}, ${number(row.shap_value, 3)} log-odds"`
     - Dòng 285: `<span>Đóng góp ${row.shap_value >= 0 ? "+" : ""}${number(row.shap_value, 5)} log-odds</span>`
  3. Trong `frontend/index.html:159`, tiêu đề phụ của thẻ biểu đồ SHAP ghi cứng: `<span class="muted">Đóng góp có dấu trên thang log-odds</span>`.
  4. Trong `frontend/js/app.js:591-592` (hàm `printCreditMemo` và `renderDiagnostic` dòng 610), biên bản tín dụng in ra cũng ghi cứng đơn vị `log-odds`: `${number(row.shap_value, 4)} log-odds trước hiệu chỉnh`.
- **Expected behavior**: Khi mô hình được chọn là Random Forest (`output_space === "probability"`), toàn bộ nhãn giải thích SHAP trên giao diện, tooltip biểu đồ và bản in báo cáo tín dụng phải hiển thị đúng đơn vị đóng góp xác suất, không gắn nhãn `log-odds` hay `"Xác suất sigmoid"`.
- **Actual behavior**: Các thành phần giao diện được viết giả định cố định cho XGBoost (`log-odds`), nên khi gói mô hình `v1.2.0` chọn `random_forest` làm mô hình chiến thắng, các nhãn đơn vị trên UI bị sai lệch so với không gian đầu ra thực tế của TreeSHAP.
- **Phân tích nguyên nhân gốc**: Giai đoạn nâng cấp từ `v1.1.0` (chỉ có XGBoost) lên `v1.2.0` (bổ sung LightGBM và Random Forest) chỉ mới cập nhật một dòng toán tử 3 ngôi trong `app.js:631,635` mà chưa cập nhật đồng bộ `charts.js`, `index.html`, `printCreditMemo` và `renderDiagnostic`.
- **Phạm vi ảnh hưởng**: Tab "Giải thích rủi ro", phần tóm tắt chẩn đoán ở tab "Phân tích công ty" và bản in "Báo cáo rủi ro tín dụng".
- **Khuyến nghị khắc phục**: Sử dụng `prediction?.output_space === "probability"` để điều chỉnh động nhãn đơn vị (ví dụ `"đóng góp xác suất"` vs `"log-odds"`, `"Xác suất gốc trước hiệu chỉnh"` vs `"Xác suất sigmoid trước hiệu chỉnh"`) tại tất cả các vị trí nêu trên.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Xác minh trực tiếp từ mã nguồn JS/HTML và dữ liệu đầu ra)**.

---

### `AUD-CODE-001` — Kiểm tra kiểu tĩnh `mypy src/finhealth` thất bại với 9 lỗi trong 4 tệp

- **Lĩnh vực kiểm định**: Clean Code & Maintainability / Static Type Safety
- **Mức độ nghiêm trọng**: **HIGH (P1)**
- **Trạng thái xác minh**: `REPRODUCED`
- **Thành phần & Vị trí**:
  - `src/finhealth/ml/kaggle_loader.py:121`
  - `src/finhealth/ml/distress_classifier.py:157,160`
  - `src/finhealth/ml/registry.py:144,153,180,210,245`
  - `src/finhealth/ml/train_cli.py:619`
- **Bằng chứng trực tiếp**:
  Lệnh thực thi: `.\.venv\Scripts\python.exe -m mypy src/finhealth`
  Kết quả trả về (`MYPY_EXIT=1`, lưu tại `audit-reports/logs/ruff_and_mypy.log`):
  ```text
  src\finhealth\ml\kaggle_loader.py:121: error: No overload variant of "where" matches argument types "Series[bool]", "None", "ndarray[tuple[Any, ...], dtype[Any]]"  [call-overload]
  src\finhealth\ml\distress_classifier.py:157: error: Item "list[Any]" of "Any | ndarray[tuple[Any, ...], dtype[Any]] | list[Any]" has no attribute "astype"  [union-attr]
  src\finhealth\ml\distress_classifier.py:160: error: No overload variant of "__getitem__" of "list" matches argument type "tuple[slice[None, None, None], int]"  [call-overload]
  src\finhealth\ml\registry.py:144: error: Argument 1 to "select_best_classifier" has incompatible type "dict[Literal['xgboost', 'lightgbm', 'random_forest'], DistressClassifier]"; expected "dict[str, DistressClassifier]"  [arg-type]
  src\finhealth\ml\registry.py:153: error: Argument 1 to "select_best_classifier" has incompatible type "dict[Literal['xgboost', 'lightgbm', 'random_forest'], DistressClassifier]"; expected "dict[str, DistressClassifier]"  [arg-type]
  src\finhealth\ml\registry.py:180: error: Cannot infer value of type parameter "KT" of <dict>  [misc]
  src\finhealth\ml\registry.py:210: error: Invalid index type "str" for "dict[Literal['xgboost', 'lightgbm', 'random_forest'], dict[str, Any]]"; expected type "Literal['xgboost', 'lightgbm', 'random_forest']"  [index]
  src\finhealth\ml\registry.py:245: error: Argument "candidates" to "ModelArtifactBundle" has incompatible type "dict[Literal['xgboost', 'lightgbm', 'random_forest'], DistressClassifier]"; expected "dict[str, DistressClassifier] | None"  [arg-type]
  src\finhealth\ml\train_cli.py:619: error: Incompatible types in assignment (expression has type "numpy.bool[builtins.bool]", variable has type "builtins.bool")  [assignment]
  Found 9 errors in 4 files (checked 61 source files)
  ```
- **Expected behavior**: `mypy src/finhealth` phải hoàn tất với `0 errors` như được cam kết trong mục Verification của `README.md:229`.
- **Actual behavior**: Thất bại với 9 lỗi trong 4 tệp (lưu ý tệp log cũ `data/artifacts/data-version/mypy.txt` chỉ kiểm tra 60 tệp trước khi tệp thứ 61 là `kaggle_loader.py` và các thay đổi đa mô hình được thêm vào).
- **Phân tích nguyên nhân gốc**:
  1. Trong `registry.py:114-119`, comprehension `{model_name: ... for model_name in CANDIDATE_MODEL_TYPES}` được suy diễn kiểu là `dict[ModelType, DistressClassifier]`. Do `dict` trong Python bất biến (invariant) theo kiểu khóa `KT`, nó không tương thích với `dict[str, DistressClassifier]` trong chữ ký hàm `select_best_classifier` và `ModelArtifactBundle.candidates`.
  2. Trong `distress_classifier.py:157,160`, `XGBClassifier.predict()` và `RandomForestClassifier.predict_proba()` có kiểu trả về union bao gồm `list[Any]` trong type hints của thư viện, cần ép kiểu qua `np.asarray(...)` trước khi gọi `.astype()` hoặc slicing 2 chiều `[:, 1]`.
  3. Trong `kaggle_loader.py:121`, `np.where(~altman_valid, None, ...)` truyền `None` vào numpy typing stub mới (`numpy 2.3.5`).
  4. Trong `train_cli.py:619`, biến `real_only` được khai báo trước đó ở nhánh `if` là `bool` (`real_only = False`), nhưng ở nhánh `else` lại gán kết quả của `panel["data_source"].eq("cached_sec").all()` có kiểu `np.bool_`.
- **Phạm vi ảnh hưởng**: Cổng kiểm tra kiểu tĩnh (`mypy`) của dự án.
- **Khuyến nghị khắc phục**:
  - Chú thích rõ `candidates: dict[str, DistressClassifier] = ...` và `candidate_test_metrics: dict[str, dict[str, Any]] = ...` trong `registry.py`.
  - Bọc `np.asarray(..., dtype=np.float64)` trong `distress_classifier.py:157,160`.
  - Dùng `bool(panel["data_source"].eq("cached_sec").all())` trong `train_cli.py:619`.
  - Dùng `pd.Series(..., index=df.index).where(altman_valid, None)` trong `kaggle_loader.py:121`.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Xác minh bằng thực thi trình kiểm tra kiểu `mypy`)**.

---

### `AUD-FUNC-002` — Biểu đồ `07_reliability_calibration.png` bị vẽ rỗng do bất đồng bộ tên khóa dữ liệu giữa `evaluator.py` và `visualization.py`

- **Lĩnh vực kiểm định**: Functional Correctness / Visualization
- **Mức độ nghiêm trọng**: **MEDIUM (P2)**
- **Trạng thái xác minh**: `VERIFIED`
- **Thành phần & Vị trí**:
  - `src/finhealth/ml/evaluator.py:107-129`
  - `src/finhealth/ml/visualization.py:308-337`
  - `data/artifacts/figures/07_reliability_calibration.png`
  - `data/artifacts/figures_kaggle-v1.2.0/07_reliability_calibration.png`
- **Bằng chứng trực tiếp**:
  1. Tại `src/finhealth/ml/evaluator.py:118-127`, hàm `reliability_bins()` tạo danh sách các dict với cấu trúc khóa:
     ```python
     {
         "model": name,
         "lower": bucket / 10,
         "upper": (bucket + 1) / 10,
         "n": int(mask.sum()),
         "positives": int(y[mask].sum()),
         "mean_probability": float(scores[mask].mean()),
         "observed_prevalence": float(y[mask].mean()),
     }
     ```
     (Cấu trúc này cũng được xác nhận trong `data/artifacts/models/v1.2.0/evaluation_report.json:656-836`).
  2. Tuy nhiên, tại `src/finhealth/ml/visualization.py:317-325`, phương thức `_reliability()` lại truy cập:
     ```python
     subset = [
         row
         for row in bins
         if row.get("score") == score_kind and row.get("count", 0) > 0
     ]
     if subset:
         xs = [row["mean_score"] for row in subset]
         ys = [row["observed_rate"] for row in subset]
         axis.plot(xs, ys, f"{marker}-", color=color, label=label, linewidth=2)
     ```
  3. Vì không có phần tử nào trong `bins` có khóa `"score"` hay `"count"`, danh sách `subset` luôn rỗng (`[]`). Biểu đồ được lưu ra đĩa chỉ có duy nhất đường tham chiếu nét đứt `y = x` ở dòng 312.
  4. Hơn nữa, trong `tests/integration/test_dashboard_ui.py:20-27`, hằng số `FIGURES` chỉ liệt kê 6 biểu đồ đầu (`01` đến `06`), bỏ sót biểu đồ `07_reliability_calibration.png`.
- **Expected behavior**: Biểu đồ `07_reliability_calibration.png` phải hiển thị hai đường thực nghiệm `Trước hiệu chuẩn (Raw)` và `Sau hiệu chuẩn (Calibrated)` từ dữ liệu `test_reliability_bins`.
- **Actual behavior**: Biểu đồ chỉ có khung trục và đường chéo lý tưởng `y = x`, hoàn toàn không có đường dữ liệu của mô hình.
- **Phân tích nguyên nhân gốc**: Người phát triển viết hàm `_reliability()` trong `visualization.py` sử dụng tên cột hiển thị của bảng ASCII trong `train_cli.py:361` (`Score`, `Mean score`, `Observed rate`) thay vì tên khóa JSON thực tế do `evaluator.reliability_bins()` sinh ra (`model`, `n`, `mean_probability`, `observed_prevalence`).
- **Phạm vi ảnh hưởng**: Biểu đồ nghiên cứu số 07 trên giao diện web ("Mô hình và phân nhóm") và trong thư mục `data/artifacts/figures/`.
- **Khuyến nghị khắc phục**: Sửa `visualization.py:319-324` để dùng `row.get("model") == score_kind and row.get("n", 0) > 0`, `row["mean_probability"]` và `row["observed_prevalence"]`. Bổ sung kiểm thử trong `test_visualization_and_cli.py` để xác minh biểu đồ có chứa các đường dữ liệu được vẽ.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Đối chiếu trực tiếp mã nguồn và cấu trúc JSON)**.

---

### `AUD-SEC-001` — Giao diện người dùng không hỗ trợ gửi `Authorization: Bearer <ADMIN_TOKEN>` cho các route ghi khi chạy ở `staging` / `production`

- **Lĩnh vực kiểm định**: Security & Privacy / Functional Integration
- **Mức độ nghiêm trọng**: **MEDIUM (P2)**
- **Trạng thái xác minh**: `STATICALLY_CONFIRMED`
- **Thành phần & Vị trí**:
  - `src/finhealth/api/dependencies.py:25-35`
  - `src/finhealth/api/routers/companies.py:78-81`
  - `src/finhealth/api/routers/ingestion.py:14`
  - `frontend/js/api.js:43-68,101-115`
- **Bằng chứng trực tiếp**:
  1. Backend bảo vệ tất cả các route ghi (`POST /api/v1/companies/{identifier}/analyze`, `POST /api/v1/ingestion/{identifier}`, `GET /api/v1/ingestion/status/{job_id}`, `POST /api/v1/models/train`) bằng dependency `require_write_access`:
     ```python
     def require_write_access(
         request: Request, settings: Annotated[Settings, Depends(get_settings)],
     ) -> None:
         expected = settings.admin_token.get_secret_value() if settings.admin_token else None
         if expected is None and settings.app_env in ("development", "test"):
             return
         supplied = request.headers.get("Authorization", "")
         if not expected or not compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
             raise HTTPException(403, "Write access requires the configured administrator token")
     ```
  2. Tuy nhiên, trong `frontend/js/api.js:43-52`, hàm `request()` chỉ gửi header `Accept: "application/json"` và `Content-Type: "application/json"`. Không có trường nhập token trên UI, cũng không có logic đính kèm header `Authorization`.
  3. Ngoài ra, trong `frontend/js/api.js:34-40`, mã lỗi HTTP `403` không được định nghĩa thông báo tiếng Việt cụ thể trong hàm `errorMessage()`, nên nếu bị từ chối quyền, UI chỉ hiện thông báo chung `"Không hoàn thành được yêu cầu (HTTP 403)."`.
- **Expected behavior**: Khi triển khai ở `staging`/`production` (hoặc khi cấu hình `ADMIN_TOKEN`), người quản trị sử dụng nút "Phân tích hồ sơ SEC" trên dashboard phải có phương thức cung cấp token xác thực, hoặc nút này phải yêu cầu xác thực rõ ràng.
- **Actual behavior**: Mọi thao tác bấm nút "Phân tích hồ sơ SEC" trên giao diện web trong môi trường `staging`/`production` (hoặc trong `development` nếu có đặt `ADMIN_TOKEN`) đều bị từ chối với lỗi HTTP 403.
- **Phân tích nguyên nhân gốc**: Cơ chế `require_write_access` được thêm vào backend để bảo vệ các route ghi, nhưng phía client (`frontend/js/api.js` và `index.html`) chưa được cập nhật tương ứng.
- **Phạm vi ảnh hưởng**: Tính năng cập nhật và phân tích hồ sơ SEC trực tiếp từ giao diện web trong môi trường triển khai có bật bảo mật.
- **Khuyến nghị khắc phục**: Bổ sung hộp thoại/trường nhập Admin Token (lưu trong `sessionStorage` của trình duyệt) khi gọi `api.analyze()`, kèm thông báo lỗi rõ ràng cho mã HTTP 403 trong `frontend/js/api.js`.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Xác nhận trực tiếp từ mã nguồn backend và frontend)**.

---

### `AUD-ARCH-001` — Chia sẻ biến toàn cục `_MODEL_STATE` giữa các instance `create_app()` và bỏ qua việc nạp lại khi `model_path` thay đổi

- **Lĩnh vực kiểm định**: Architecture & System Design / State Management
- **Mức độ nghiêm trọng**: **MEDIUM (P2)**
- **Trạng thái xác minh**: `STATICALLY_CONFIRMED`
- **Thành phần & Vị trí**:
  - `src/finhealth/api/dependencies.py:37-101`
  - `src/finhealth/api/main.py:36,59`
- **Bằng chứng trực tiếp**:
  1. Tại `src/finhealth/api/dependencies.py:101`, `_MODEL_STATE = ModelRegistryState()` được khởi tạo ở cấp module.
  2. Tại `src/finhealth/api/main.py:59`, hàm factory `create_app(settings)` gán trực tiếp singleton này cho mọi ứng dụng: `app.state.model_registry = _MODEL_STATE`.
  3. Trong `ModelRegistryState.initialize(self, directory: Path)` (`dependencies.py:57-61`):
     ```python
     def initialize(self, directory: Path) -> None:
         with self._lock:
             if self._initialized:
                 return
     ```
     Hàm không lưu lại `directory` nào đã được dùng để khởi tạo. Nếu `_MODEL_STATE` đã được khởi tạo một lần (hoặc `set()` đã được gọi), mọi lời gọi `initialize(new_directory)` sau đó đều bị bỏ qua hoàn toàn.
  4. Chính các tác giả test đã phải tự né lỗi này bằng cách ghi đè thủ công `app.state.model_registry = ModelRegistryState()` ở hầu hết các test tích hợp (`test_api_endpoints.py:73`, `test_dashboard_ui.py:39`, `test_forensic_audit.py:108`, `test_v12_compare_and_ui.py:49`).
- **Expected behavior**: Mỗi ứng dụng tạo bởi `create_app(settings)` cần có trạng thái cô lập theo `settings.model_path` của chính nó, hoặc `initialize(directory)` phải kiểm tra xem `directory` được yêu cầu có khớp với `directory` đã nạp hay không.
- **Actual behavior**: `_MODEL_STATE` dùng chung toàn cục và khóa cứng sau lần `initialize` đầu tiên.
- **Phân tích nguyên nhân gốc**: Thiết kế muốn hỗ trợ hàm tiện ích `set_active_model_bundle()` ở cấp module nhưng lại gắn cùng một instance `_MODEL_STATE` vào `create_app()` mà không kiểm tra sự thay đổi của `directory`.
- **Phạm vi ảnh hưởng**: Các kịch bản khởi tạo nhiều app instance với cấu hình `Settings` khác nhau trong cùng một tiến trình Python.
- **Khuyến nghị khắc phục**: Lưu `self._directory: Path | None = None` trong `ModelRegistryState` và nạp lại khi `self._directory != directory.resolve()`, hoặc tạo mới `ModelRegistryState()` trong `create_app()`.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Xác nhận trực tiếp từ mã nguồn)**.

---

### `AUD-TEST-001` — Kiểm thử độ trễ `test_api_latency[/companies]` đặt ngưỡng thời gian cứng gây lỗi Flaky Test

- **Lĩnh vực kiểm định**: Testing & QA Reliability / Performance Testing
- **Mức độ nghiêm trọng**: **MEDIUM (P2)**
- **Trạng thái xác minh**: `REPRODUCED`
- **Thành phần & Vị trí**:
  - `tests/integration/test_forensic_audit.py:702-720`
- **Bằng chứng trực tiếp**:
  Trong lần chạy toàn bộ 184 test (`audit-reports/logs/pytest_scratch_basetemp.log`), test `tests/integration/test_forensic_audit.py::test_api_latency[/companies]` bị **FAILED**:
  ```text
  _, p95 = _timing(f"D GET /api/v1{path}", get, 25)
  > assert p95 < 50
  E assert 59.833860024809795 < 50
  Captured stdout call:
  BENCHMARK|D GET /api/v1/companies|25|22.887500|59.833860|0.693332
  ```
  Trong khi độ trễ trung vị (median) chỉ là `22.89 ms`, giá trị phân vị thứ 95 (`P95`) trên 25 mẫu (tương ứng mẫu chậm thứ 2 trong 25 lần gọi liên tiếp) đạt `59.83 ms`, vượt ngưỡng cứng `50 ms` do dao động lập lịch CPU/I/O của hệ điều hành Windows.
- **Expected behavior**: Bộ kiểm thử tự động (`pytest -v`) phải có tính tất định (deterministic), không bị FAIL ngẫu nhiên bởi nhiễu lập lịch CPU của hệ điều hành.
- **Actual behavior**: Việc trộn lẫn micro-benchmark có ngưỡng mili-giây thấp (`< 50ms` trên 25 mẫu) vào bộ kiểm thử chức năng dẫn đến kết quả không ổn định.
- **Phân tích nguyên nhân gốc**: Trên 25 mẫu, phân vị P95 bị quyết định bởi chỉ 1–2 lần gọi bị trùng nhịp garbage collection hoặc I/O của OS. Bản thân `README.md:236-237` cũng thừa nhận: *"Response times are measured on the local machine and are affected by CPU load, filesystem cache and tracing."*
- **Phạm vi ảnh hưởng**: Độ tin cậy và tính ổn định của cổng kiểm thử `pytest -v`.
- **Khuyến nghị khắc phục**: Tách các test đo thời gian thực thi sang một suite benchmark riêng hoặc kiểm tra theo `median < 50` và `p95 < 150` để tránh false-negative do nhiễu hệ điều hành.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Đã tái hiện trực tiếp trong quá trình thực thi)**.

---

### `AUD-OPS-001` — Lỗi từ chối quyền truy cập hệ thống tệp (Windows ACL PermissionError) trên `.pytest_cache` và `%TEMP%\pytest-of-hp`

- **Lĩnh vực kiểm định**: DevOps, Environment & Local Workflow
- **Mức độ nghiêm trọng**: **MEDIUM (P2)**
- **Trạng thái xác minh**: `REPRODUCED`
- **Thành phần & Vị trí**:
  - `D:\DATN\.pytest_cache`
  - `C:\Users\hp\AppData\Local\Temp\pytest-of-hp`
- **Bằng chứng trực tiếp**:
  1. Khi quét thư mục dự án: `Get-ChildItem : Access to the path 'D:\DATN\.pytest_cache' is denied.`
  2. Khi chạy `pytest -v` với thư mục tạm mặc định (`audit-reports/logs/pytest_default_basetemp.log`), toàn bộ 62 test có sử dụng fixture `tmp_path` đều bị `ERROR` tại bước setup:
     `PermissionError: [WinError 5] Access is denied: 'C:\\Users\\hp\\AppData\\Local\\Temp\\pytest-of-hp'`
  3. Khi chỉ định `--basetemp` và `-o cache_dir` sang thư mục có quyền ghi (`audit-reports/logs/pytest_scratch_basetemp.log`), toàn bộ 62 lỗi `ERROR` này được giải quyết hoàn toàn (0 errors).
- **Expected behavior**: Lệnh chuẩn `pytest -v` chạy từ thư mục gốc phải truy cập được thư mục cache và thư mục tạm để thực thi toàn bộ test suite.
- **Actual behavior**: Thư mục `.pytest_cache` và `%TEMP%\pytest-of-hp` đã được tạo trước đó bởi một tiến trình chạy dưới quyền tài khoản/elevated context khác trên Windows, khiến user hiện tại bị từ chối quyền đọc/ghi.
- **Phân tích nguyên nhân gốc**: Xung đột quyền ACL giữa các phiên làm việc (ví dụ chạy terminal với quyền Administrator trước đó rồi chạy lại với quyền user thường hoặc sandboxed agent).
- **Phạm vi ảnh hưởng**: Trải nghiệm phát triển cục bộ và khả năng chạy lệnh `pytest -v` mặc định không tham số.
- **Khuyến nghị khắc phục**: Đặt lại quyền ACL (hoặc xóa bằng quyền Administrator) đối với `D:\DATN\.pytest_cache` và `C:\Users\hp\AppData\Local\Temp\pytest-of-hp`; có thể cấu hình `cache_dir = ".venv/pytest-cache"` trong `pyproject.toml`.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Đã tái hiện và chứng minh bằng đối chứng thực nghiệm)**.

---

### `AUD-DOC-001` — Sự sai lệch giữa tài liệu `README.md` và trạng thái thực tế của mô hình/dữ liệu phiên bản 1.3.0 (`v1.2.0`)

- **Lĩnh vực kiểm định**: Documentation & Developer Experience / Requirement & Claim Validation
- **Mức độ nghiêm trọng**: **MEDIUM (P2)**
- **Trạng thái xác minh**: `VERIFIED`
- **Thành phần & Vị trí**:
  - `README.md:40, 113, 185, 195-209, 253`
  - `data/artifacts/models/latest.json`
  - `data/artifacts/models/v1.2.0/BENCHMARK_REPORT.md`
  - `data/processed/parquet/finhealth.sqlite3`
- **Bằng chứng trực tiếp**:
  Đối chiếu trực tiếp giữa tuyên bố trong `README.md` và thực tế hệ thống:
  1. **Phiên bản mô hình đang hoạt động**: `README.md:40,185` ghi *"The active local bundle is `data/artifacts/models/v1.1.0`"* và *"Product version 1.3.0 serves the existing v1.1.0 model."* Thực tế `data/artifacts/models/latest.json` trỏ tới **`"model_version": "v1.2.0"`** và các bài test trong `test_dashboard_ui.py:105,109,123` cũng kiểm tra cứng `model_version == "v1.2.0"`.
  2. **Quy mô dữ liệu kiểm định**: `README.md:195-200` ghi *"Stage 8 uses 1,234 annual statements from 80 cached issuers. The supervised sample contains 748 strictly forward filing pairs. Calibration and forecast blend selection use 79 FY2022 observations. The embargoed classification test has 80 labeled observations, including 10 positives. Brier score changes from 0.072606 to 0.058535... maximum raw TreeSHAP margin error is `2.10688449e-06`."* Thực tế trong `finhealth.sqlite3`, `sec_real_panel.parquet` và `v1.2.0/BENCHMARK_REPORT.md`: hệ thống đang có **1,506 báo cáo năm từ 98 doanh nghiệp**, **900 cặp huấn luyện**, **97 quan sát validation**, **98 quan sát test có nhãn (15 ca dương)**, mô hình được chọn là **`random_forest`** với Brier score `0.048583` và sai số TreeSHAP `1.03216047e-15`.
  3. **Số lượng biểu đồ xuất bản**: `README.md:113,234` ghi *"six original 300-DPI figures"* và *"all six publication figures"*. Thực tế `PLOT_FILENAMES` trong `visualization.py:27-35` và `FIGURES` trong `frontend/js/app.js:38-46` có **7 biểu đồ** (đã bổ sung `07_reliability_calibration.png`).
  4. **Số lượng điểm PCA**: `README.md:254` ghi *"all 81 PCA points"*, thực tế có **98 điểm PCA**.
- **Expected behavior**: Tài liệu `README.md` phải khớp với dữ liệu, gói mô hình đang kích hoạt và các kiểm thử tích hợp của phiên bản hiện tại.
- **Actual behavior**: Mã nguồn, dữ liệu SQLite/Parquet, model bundle và integration tests đã được nâng cấp lên `v1.2.0` (98 công ty, 7 biểu đồ, đa mô hình), nhưng `README.md` vẫn giữ các con số thống kê của `v1.1.0` (80 công ty, 6 biểu đồ).
- **Phân tích nguyên nhân gốc**: Cập nhật mã nguồn và chạy lại huấn luyện `v1.2.0` nhưng chưa cập nhật phần thuyết minh benchmark trong `README.md`.
- **Phạm vi ảnh hưởng**: Tính nhất quán của tài liệu kỹ thuật và báo cáo học thuật.
- **Khuyến nghị khắc phục**: Cập nhật các số liệu trong `README.md` theo đúng báo cáo `data/artifacts/models/v1.2.0/BENCHMARK_REPORT.md`.
- **Mức độ tin cậy của kết luận**: **Cao (100% — Đối chiếu trực tiếp từng con số giữa README, JSON, Parquet và SQLite)**.

---

### `AUD-SEC-002` — Rủi ro tiềm ẩn từ `joblib.load()` (pickle deserialization) và cấu hình cứng CORS ở môi trường ngoài `development`

- **Lĩnh vực kiểm định**: Security & Privacy
- **Mức độ nghiêm trọng**: **LOW (P3)**
- **Trạng thái xác minh**: `STATICALLY_CONFIRMED`
- **Thành phần & Vị trí**:
  - `src/finhealth/ml/registry.py:304-324`
  - `src/finhealth/api/main.py:68-74`
- **Bằng chứng trực tiếp**:
  1. `load_bundle(bundle_dir)` kiểm tra SHA-256 của `models.joblib` so với trường `"sha256"` trong `metadata.json` nằm ngay cùng thư mục `bundle_dir`, sau đó gọi `joblib.load(path)` (sử dụng Python `pickle`). Bản thân `src/finhealth/ml/README.md:48-50` đã ghi nhận rất rõ: *"Load only trusted local joblib artifacts: a checksum provides corruption detection, not authentication or safe deserialization."*
  2. Tại `src/finhealth/api/main.py:68-74`:
     ```python
     app.add_middleware(
         CORSMiddleware,
         allow_origins=["*"] if configured.app_env == "development" else ["http://localhost:3000"],
         allow_credentials=False,
         allow_methods=["GET", "POST", "OPTIONS"],
         allow_headers=["*"],
     )
     ```
     Khi `app_env` là `staging` hoặc `production`, `allow_origins` bị gắn cứng là `["http://localhost:3000"]` mà không thể cấu hình qua `.env`.
- **Expected behavior**: Cho phép cấu hình danh sách CORS origins qua biến môi trường khi triển khai thực tế; đảm bảo thư mục `data/artifacts/models` chỉ được ghi bởi tài khoản dịch vụ tin cậy.
- **Actual behavior**: `allow_origins` bị hardcode cho môi trường non-development.
- **Phân tích nguyên nhân gốc**: Giả định môi trường chạy cục bộ trong giai đoạn phát triển.
- **Phạm vi ảnh hưởng**: Khả năng cấu hình CORS khi triển khai cross-origin ở production và an toàn nạp mô hình.
- **Khuyến nghị khắc phục**: Thêm trường `cors_allowed_origins: list[str]` vào `Settings` trong `src/finhealth/core/config.py`.
- **Mức độ tin cậy của kết luận**: **Cao (100%)**.

---

### `AUD-PERF-001` — Nạp lại toàn bộ bảng chỉ số năm trong `_annual_metrics()` trên mỗi truy vấn lọc/phân trang danh sách công ty

- **Lĩnh vực kiểm định**: Performance & Scalability
- **Mức độ nghiêm trọng**: **LOW (P3)**
- **Trạng thái xác minh**: `STATICALLY_CONFIRMED`
- **Thành phần & Vị trí**:
  - `src/finhealth/api/services.py:388-416, 658-689`
- **Bằng chứng trực tiếp**:
  Trong `FinancialAnalysisService.list_company_summaries()` (`services.py:675-685`):
  ```python
  cohort = (
      [
          row
          for row in rows
          if row["cik"] not in EXCLUDED_INDUSTRIAL_CIKS
          and not is_financial_institution_sic(row["sic_code"])
      ]
      if not filtered and offset == 0 and len(rows) < limit
      else self._annual_metrics(session)
  )
  benchmark = CompositeBenchmark.from_rows(cohort)
  ```
  Mỗi khi người dùng nhập bộ lọc trên giao diện (`q`, `risk_level`, `cluster_id`, `min_roa`, ...) hoặc phân trang (`offset > 0`), API thực hiện một truy vấn thứ hai `self._annual_metrics(session)` dùng correlated subquery `latest_annual_statement_id()` quét toàn bộ các công ty trong DB, đưa về Python để sắp xếp và tính phân vị `CompositeBenchmark`.
- **Expected behavior**: Với tập dữ liệu lớn, điểm `CompositeBenchmark` không nên yêu cầu quét và sắp xếp lại toàn bộ vũ trụ doanh nghiệp trên mỗi request lọc.
- **Actual behavior**: Tính toán lại `CompositeBenchmark` trên toàn bộ tập doanh nghiệp cho mỗi request có bộ lọc.
- **Phân tích nguyên nhân gốc**: Thiết kế muốn giữ nguyên phân vị đối chiếu của từng công ty so với toàn ngành/toàn thị trường ngay cả khi danh sách hiển thị đang bị lọc. Đây là quyết định nghiệp vụ đúng đắn, nhưng việc không cache `CompositeBenchmark` hoặc không lưu sẵn điểm vào DB làm tăng chi phí mỗi request.
- **Phạm vi ảnh hưởng**: Độ trễ của endpoint `GET /api/v1/companies` khi có tham số lọc hoặc khi quy mô dữ liệu tăng lớn.
- **Khuyến nghị khắc phục**: Lưu sẵn hoặc cache đối tượng `CompositeBenchmark` trong bộ nhớ ứng dụng và chỉ làm mới khi có giao dịch ghi (`analyze`, `train`, `backfill`).
- **Mức độ tin cậy của kết luận**: **Cao (100%)**.

---

### `AUD-DATA-002` — Thiếu khóa ngoại (FK) từ `filing_versions.issuer_key` và thiếu quy tắc `ondelete` trên `forecast_evidence.filing_version_id`

- **Lĩnh vực kiểm định**: Database & Data Integrity
- **Mức độ nghiêm trọng**: **LOW (P3)**
- **Trạng thái xác minh**: `STATICALLY_CONFIRMED`
- **Thành phần & Vị trí**:
  - `src/finhealth/db/lineage_models.py:12-56`
- **Bằng chứng trực tiếp**:
  - Trong `src/finhealth/db/lineage_models.py:48`:
    `filing_version_id: Mapped[int] = mapped_column(ForeignKey("filing_versions.id"))`
    Không khai báo `ondelete="CASCADE"` hoặc `ondelete="RESTRICT"` rõ ràng (khác với các bảng trong `models.py` luôn khai báo `ondelete="CASCADE"`).
  - Bảng `filing_versions` liên kết với doanh nghiệp qua chuỗi `issuer_key` (`"sec:0000320193"`, `"vn:FPT"`) mà không có FK tới `companies.cik` (do bảng `filing_versions` chứa cả dữ liệu thí điểm Việt Nam `vn:FPT`, `vn:HPG` vốn không nằm trong bảng `companies` của SEC).
- **Expected behavior**: Các ràng buộc tham chiếu giữa `forecast_evidence` và `filing_versions` nên được định nghĩa chính sách xóa/giữ rõ ràng.
- **Actual behavior**: Mặc định theo hành vi `NO ACTION`/`RESTRICT` của RDBMS khi xóa `FilingVersion` nếu đã có `ForecastEvidence`.
- **Phân tích nguyên nhân gốc**: Các bảng trong `lineage_models.py` được thiết kế theo mô hình append-only (chỉ thêm mới, không bao giờ xóa bản ghi lịch sử ngay cả khi bản ghi ở bảng serving `financial_statements` bị xóa hoặc cách ly).
- **Phạm vi ảnh hưởng**: Quản trị dữ liệu dài hạn trên bảng `filing_versions` và `forecast_evidence`.
- **Khuyến nghị khắc phục**: Khai báo tường minh `ondelete="CASCADE"` hoặc chú thích rõ bất biến append-only không cho phép xóa `FilingVersion`.
- **Mức độ tin cậy của kết luận**: **Cao (100%)**.

---

### `AUD-ACAD-001` — Bộ dữ liệu Kaggle không có ngày công bố (`filed_date`) nên bỏ qua bước publication-date embargo

- **Lĩnh vực kiểm định**: Academic & Scientific Correctness
- **Mức độ nghiêm trọng**: **LOW (P3)**
- **Trạng thái xác minh**: `STATICALLY_CONFIRMED`
- **Thành phần & Vị trí**:
  - `src/finhealth/ml/kaggle_loader.py:134`
  - `src/finhealth/ml/splitter.py:116-120, 163-164`
  - `data/artifacts/models/kaggle-v1.2.0/BENCHMARK_REPORT.md:3,25,148`
- **Bằng chứng trực tiếp**:
  1. Bộ dữ liệu Kaggle (`american_bankruptcy.csv`) chỉ cung cấp năm tài chính (`year`), không có ngày nộp báo cáo (`filed_date`). `load_kaggle_bankruptcy_panel()` gán `period_end_date = YYYY-12-31` và không tạo cột `filed_date`.
  2. Trong `prepare_validation_test()` (`splitter.py:163-164`):
     ```python
     if "next_filed_date" not in observed or "filed_date" not in held_out:
         return observed, held_out, None
     ```
     Do đó, trên dữ liệu Kaggle, `threshold_calibration_asof` là `None` (`N/A`), và các quan sát năm `2014` (có nhãn mục tiêu ở năm `2015`) vẫn nằm trong tập `supervised` khi `train_end_year = 2014`? Kiểm tra `training_horizon_rows()` (`splitter.py:115`):
     `mask = df["next_fiscal_year"] <= boundary` -> các dòng có `fiscal_year = 2013` và `next_fiscal_year = 2014` được giữ lại, còn dòng `fiscal_year = 2014` (`next_fiscal_year = 2015`) đã bị loại bỏ đúng theo `next_fiscal_year <= 2014`! Tuy nhiên, vì không có `filed_date`, một báo cáo năm 2014 (thực tế công bố vào đầu năm 2015) vẫn được coi là biết tại cuối năm 2014.
  3. Ngoài ra, trong `data/artifacts/models/kaggle-v1.2.0/BENCHMARK_REPORT.md:3`, văn bản báo cáo tự động vẫn in câu: *"Synthetic rows are simulated accounting records, not actual SEC issuers... Labels are a financial distress proxy, not observed bankruptcy outcomes"*, trong khi Kaggle dataset thực chất là dữ liệu doanh nghiệp Mỹ phá sản thực tế (`status_label == "failed"`) chứ không phải dữ liệu mô phỏng (synthetic) hay nhãn proxy.
- **Expected behavior**: Báo cáo `BENCHMARK_REPORT.md` sinh ra cho `--dataset kaggle` nên mô tả đúng bản chất dữ liệu Kaggle (nhãn phá sản quan sát được từ Kaggle, không có ngày nộp hồ sơ `filed_date`) thay vì in thông điệp của tập dữ liệu mô phỏng (synthetic).
- **Actual behavior**: `train_cli.py:691-697` chỉ kiểm tra `if real_only:` (tức `data_source == "cached_sec"`), nên khi chạy với `dataset == "kaggle"` (`real_only == False`), báo cáo in nhầm lời giải thích của tập `synthetic_benchmark`.
- **Phân tích nguyên nhân gốc**: Nhánh tạo văn bản báo cáo trong `train_cli.py:691-697` chưa tách riêng trường hợp `dataset == "kaggle"`.
- **Phạm vi ảnh hưởng**: Nội dung thuyết minh trong tệp `data/artifacts/models/kaggle-v1.2.0/BENCHMARK_REPORT.md`.
- **Khuyến nghị khắc phục**: Cập nhật phần sinh văn bản thuyết minh trong `train_cli.py:690-703` để phân biệt rõ 3 nguồn: `cached_sec`, `kaggle_us_bankruptcy` và `synthetic_benchmark`.
- **Mức độ tin cậy của kết luận**: **Cao (100%)**.

---

### `AUD-OPS-002` — Thiếu quản lý phiên bản Git (`.git`), thiếu lockfile, lệch metadata version `0.1.0` vs `1.3.0` và lỗi `pip check` trong `.venv`

- **Lĩnh vực kiểm định**: DevOps, CI/CD & Dependencies / Supply Chain
- **Mức độ nghiêm trọng**: **LOW (P3)**
- **Trạng thái xác minh**: `VERIFIED`
- **Thành phần & Vị trí**:
  - Thư mục gốc `d:\DATN`
  - `pyproject.toml:7, 10-42`
  - Môi trường ảo `.venv`
- **Bằng chứng trực tiếp**:
  1. Chạy `git status` trả về: `fatal: not a git repository (or any of the parent directories): .git`.
  2. Không có bất kỳ tệp lockfile nào (`requirements.txt`, `requirements.lock`, `uv.lock`, `poetry.lock`) trong repository; `pyproject.toml` chỉ khai báo cận dưới (`>=`).
  3. Chạy `.\.venv\Scripts\python.exe -m pip list` cho thấy gói `finhealth` được cài editable ở version `0.1.0`, trong khi `pyproject.toml` và `src/finhealth/__init__.py` là `1.3.0`.
  4. Chạy `.\.venv\Scripts\python.exe -m pip check` thất bại với mã thoát `1`:
     ```text
     yfinance 0.2.56 requires beautifulsoup4, which is not installed.
     yfinance 0.2.56 requires frozendict, which is not installed.
     yfinance 0.2.56 requires platformdirs, which is not installed.
     yfinance 0.2.56 requires pytz, which is not installed.
     yfinance 0.2.56 requires requests, which is not installed.
     PIP_CHECK_EXIT=1
     ```
- **Expected behavior**: Repository phải được quản lý bằng Git, có lockfile để đảm bảo tính tái lập của môi trường, và `pip check` trên `.venv` phải đạt exit code `0`.
- **Actual behavior**: Thiếu `.git`, thiếu lockfile, và `.venv` chứa các gói dư thừa (`yfinance`, `Django`, `peewee`, `opencv-python`, ...) trong đó `yfinance` bị thiếu dependency.
- **Phân tích nguyên nhân gốc**: Môi trường `.venv` đã từng được cài thêm các gói thử nghiệm ngoài `pyproject.toml` và dự án được sao chép/giải nén mà không kèm thư mục `.git`.
- **Phạm vi ảnh hưởng**: Tính tái lập bản dựng (build reproducibility) và quản lý cấu hình.
- **Khuyến nghị khắc phục**: Khởi tạo Git, xuất lockfile từ danh sách phụ thuộc chuẩn của `finhealth`, gỡ `yfinance` khỏi `.venv` và chạy lại `pip install -e ".[dev]"`.
- **Mức độ tin cậy của kết luận**: **Cao (100%)**.

---

### `AUD-CODE-002` — Lỗi cú pháp selector CSS trong `frontend/styles.css`

- **Lĩnh vực kiểm định**: Clean Code & Maintainability / Frontend Presentation
- **Mức độ nghiêm trọng**: **LOW (P3)**
- **Trạng thái xác minh**: `STATICALLY_CONFIRMED`
- **Thành phần & Vị trí**:
  - `frontend/styles.css:49, 59, 73, 1309`
- **Bằng chứng trực tiếp**:
  Trích xuất trực tiếp từ `frontend/styles.css`:
  - Dòng 49: `button: disabled {` (thừa khoảng trắng sau dấu `:`)
  - Dòng 59: `button: focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,svg [tabindex]:focus-visible {` (selector đầu tiên `button: focus-visible` thừa khoảng trắng sau dấu `:`)
  - Dòng 73: `input: :placeholder {` (thừa khoảng trắng giữa hai dấu `:`)
  - Dòng 1309: `dialog: :backdrop {` (thừa khoảng trắng giữa hai dấu `:`)
- **Expected behavior**: Các pseudo-class và pseudo-element phải viết liền không có khoảng trắng (`button:disabled`, `button:focus-visible`, `input::placeholder`, `dialog::backdrop`).
- **Actual behavior**: Do có khoảng trắng, trình duyệt hiểu `button: disabled` là selector không hợp lệ (invalid selector); tương tự với `input: :placeholder` và `dialog: :backdrop`. Lưu ý đối với dòng 59, trong CSS selector list, một selector con bị lỗi cú pháp có thể làm trình duyệt bỏ qua cả rule-set `:focus-visible` nếu không dùng forgiving selector list.
- **Phân tích nguyên nhân gốc**: Lỗi định dạng tự động (auto-formatter) trên tệp CSS.
- **Phạm vi ảnh hưởng**: Giao diện hiển thị của trạng thái focus bàn phím (accessibility outline), nút bị vô hiệu hóa (`:disabled`), màu chữ placeholder và nền mờ (`::backdrop`) của hộp thoại phóng to biểu đồ.
- **Khuyến nghị khắc phục**: Xóa khoảng trắng thừa tại 4 dòng trên trong `frontend/styles.css`.
- **Mức độ tin cậy của kết luận**: **Cao (100%)**.

---

### `AUD-INFO-001` — Ghi nhận về tính chất chỉ báo kế toán (Distress Proxy) và biến thể Altman Z theo vốn chủ sở hữu sổ sách

- **Lĩnh vực kiểm định**: Academic & Scientific Correctness
- **Mức độ nghiêm trọng**: **INFO (P4)**
- **Trạng thái xác minh**: `VERIFIED`
- **Thành phần & Vị trí**:
  - `src/finhealth/ml/splitter.py:39-60`
  - `src/finhealth/etl/financial_ratios.py:33-74`
- **Bằng chứng trực tiếp**:
  - Trên dữ liệu SEC EDGAR (vốn không chứa nhãn phá sản pháp lý), hàm `derive_distress_label()` gán nhãn `is_distressed = 1` dựa trên tổ hợp ngưỡng của `roa`, `ocf_ratio`, `negative_ocf_streak`, `debt_ratio`, `operating_margin` và `current_ratio` tại kỳ `t+1`.
  - Hàm `compute_altman_z_score()` sử dụng `stockholders_equity / total_liabilities` (giá trị sổ sách) với hệ số `0.6` cho nhóm sản xuất (`SIC 2000–3999`) và hệ số Z″ (`6.56, 3.26, 6.72, 1.05`) cho nhóm phi sản xuất.
  - Mọi tài liệu, docstring và giao diện của dự án đều công bố rõ đây là *"fundamentals-based forward distress proxy"* và *"book-equity proxy"*, không tuyên bố là xác suất phá sản thực tế trên thị trường.
- **Khuyến nghị**: Giữ nguyên sự minh bạch này trong báo cáo nghiên cứu.

---

### `AUD-INFO-002` — Giới hạn phạm vi đơn tiến trình của `AsyncRateLimiter`

- **Lĩnh vực kiểm định**: Architecture & System Design / SEC Access Policy
- **Mức độ nghiêm trọng**: **INFO (P4)**
- **Trạng thái xác minh**: `VERIFIED`
- **Thành phần & Vị trí**:
  - `src/finhealth/ingestion/rate_limiter.py:9-45`
  - `src/finhealth/ingestion/README.md:6-16`
- **Bằng chứng trực tiếp**:
  `AsyncRateLimiter` điều phối tốc độ tối đa $\le 10$ requests/giây trong phạm vi một `asyncio` event loop và được chia sẻ giữa các request trong cùng một tiến trình FastAPI thông qua `app.state.sec_limiter`. Tài liệu `src/finhealth/ingestion/README.md` đã quy định rõ chỉ được bật một dispatcher (`INGESTION_WORKER_ENABLED=true`) cho mỗi danh tính SEC.
- **Khuyến nghị**: Nếu mở rộng hệ thống sang kiến trúc đa worker hoặc đa máy chủ cùng gọi SEC EDGAR, cần chuyển bộ giới hạn tốc độ sang cơ chế phân tán (ví dụ Redis token bucket).

---

### `AUD-INFO-003` — Giới hạn kiểm thử trực quan trình duyệt và hệ quản trị cơ sở dữ liệu ngoài trong phạm vi Read-Only Audit

- **Lĩnh vực kiểm định**: Testing & QA Reliability
- **Mức độ nghiêm trọng**: **INFO (P4)**
- **Trạng thái xác minh**: `NOT_TESTED`
- **Thành phần & Vị trí**:
  - Giao diện trình duyệt (`frontend/`)
  - Kết nối runtime tới PostgreSQL và SQL Server
- **Bằng chứng trực tiếp**:
  Trong quá trình audit độc lập ở chế độ Read-Only, các kiểm thử DDL cho PostgreSQL và SQL Server được xác minh ở mức biên dịch SQL offline (`test_postgresql_offline_migration_sql`, `test_sqlserver_offline_migration_uses_one_cascade_path`), và logic JS của CSV được xác minh qua Node.js runtime (`test_csv_escaping_formula_protection_and_signed_numbers`). Việc kết nối trực tiếp tới máy chủ SQL Server/PostgreSQL đang chạy và render trực quan trên trình duyệt headless được ghi nhận là `NOT_TESTED`.
- **Khuyến nghị**: Chạy kiểm thử E2E trên trình duyệt và cơ sở dữ liệu đích sau khi hoàn tất khắc phục các phát hiện P1/P2.
