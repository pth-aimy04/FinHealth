# BÁO CÁO TỔNG QUAN KIỂM ĐỊNH KỸ THUẬT ĐỘC LẬP (EXECUTIVE AUDIT REPORT)

## 1. Định danh Dự án & Thông tin Kiểm định

- **Tên dự án**: FinHealth — Corporate Financial Health and Distress Prediction Infrastructure
- **Phiên bản khai báo trong mã nguồn**: `1.3.0` (`pyproject.toml`, `src/finhealth/__init__.py`)
- **Phiên bản gói cài đặt thực tế trong `.venv`**: `0.1.0` (Editable install tại `D:\DATN`, metadata chưa được đồng bộ lại qua `pip install -e .`)
- **Timestamp kiểm định**: `2026-11-20T20:57:06+07:00` đến `2026-11-20T21:16:33+07:00`
- **Project Root**: `d:\DATN`
- **Trạng thái Git / Repository Commit**: **KHÔNG CÓ** (`fatal: not a git repository (or any of the parent directories): .git`). Thư mục dự án không chứa `.git`, không thể xác minh lịch sử commit, branch hoặc trạng thái working tree.
- **Chế độ kiểm định**: **READ-ONLY BY DEFAULT** (Không chỉnh sửa bất kỳ tệp mã nguồn, cấu hình, cơ sở dữ liệu hay gói mô hình nào của dự án).

---

## 2. Phạm vi Kiểm định (Audit Scope)

Cuộc kiểm định bao phủ toàn diện 100% các tệp mã nguồn và cấu hình của dự án (41 tệp Python trong `src/finhealth/`, 18 tệp kiểm thử trong `tests/`, 4 bản migration Alembic trong `migrations/`, 8 tệp giao diện trong `frontend/`, cùng các tệp cấu hình và dữ liệu kiểm định cục bộ trong `data/`):

1. **Architecture & System Design**: Cấu trúc phân lớp (`core`, `db`, `ingestion`, `etl`, `ml`, `api`, `frontend`), hướng phụ thuộc, quản lý trạng thái, cô lập lỗi và thiết kế bất đồng bộ.
2. **Academic & Scientific Correctness**: Xử lý dữ liệu bảng (panel data), chống rò rỉ dữ liệu tương lai (temporal/publication-date purging & embargo), công thức tỷ số tài chính, biến thể Altman Z / Z″, phân tích DuPont 3 nhân tố với phân rã Shapley, phân cụm PCA + K-Means, mô hình phân loại rủi ro (XGBoost, LightGBM, Random Forest), hồi quy kỳ tới (Next-Period Forecaster), hiệu chuẩn xác suất (Platt scaling / affine logit) và giải thích mô hình TreeSHAP.
3. **Functional Correctness**: Logic nghiệp vụ từ trích xuất XBRL SEC EDGAR, đối soát kỳ báo cáo quý/năm, kịch bản stress testing, kho báo cáo phiên bản (`filing_versions`, `forecast_evidence`) đến hiển thị giao diện.
4. **Security & Privacy**: Xác thực/phân quyền (`require_write_access`), bảo vệ chống Path Traversal, SQL Injection, XSS, CSV Formula Injection, an toàn deserialization (`joblib`), cấu hình CORS và quản lý thông tin nhạy cảm (`.env`).
5. **Performance & Scalability**: Độ phức tạp thuật toán, hiệu năng truy vấn SQL, cơ chế caching (`lru_cache`), giới hạn tốc độ (`AsyncRateLimiter`) và độ trễ API thực tế.
6. **Clean Code & Maintainability**: Chất lượng mã nguồn (`ruff`), kiểm tra kiểu tĩnh (`mypy`), tính nhất quán giữa tài liệu và triển khai.
7. **Database & Data Integrity**: Thiết kế lược đồ SQLAlchemy, ràng buộc toàn vẹn (FK, Unique, CheckConstraint), tương thích đa hệ quản trị (SQLite, PostgreSQL, SQL Server) và tính đồng bộ giữa dữ liệu lưu trữ với mô hình đang hoạt động.
8. **Testing & QA Reliability**: Đánh giá 184 test cases, phân loại ranh giới mock/thật, phát hiện test giòn (flaky/brittle) và đối chiếu với các bản chụp kết quả kiểm thử cũ trong `data/artifacts/`.
9. **DevOps, CI/CD & Production Readiness**: Quản lý phụ thuộc, lockfile, Docker Compose, Alembic migrations, khả năng truy vết bản phát hành.
10. **Dependencies, Licenses & Supply Chain**: Kiểm tra môi trường ảo `.venv` (`pip list`, `pip check`).
11. **Documentation & Developer Experience**: Đối chiếu `README.md`, `AGENTS.md`, và các tài liệu con với trạng thái hệ thống thực tế.

---

## 3. Phương pháp Kiểm định & Môi trường Thực thi

### 3.1. Phương pháp luận
- **Phân tích tĩnh (Static Analysis)**: Đọc và đối chiếu trực tiếp toàn bộ 100% tệp mã nguồn trong repository; chạy `ruff check .` và `mypy src/finhealth`.
- **Xác minh thực thi (Execution-Based Verification)**: Chạy toàn bộ test suite bằng `pytest -v` trên môi trường ảo `.venv` của dự án; truy vấn trực tiếp ở chế độ chỉ đọc (`mode=ro`) đối với cơ sở dữ liệu `data/processed/parquet/finhealth.sqlite3` và đối chiếu với gói mô hình `data/artifacts/models/v1.2.0` cùng `latest.json`.
- **Phản biện chéo (Adversarial Review)**: Kiểm tra từng phát hiện để loại bỏ suy diễn chủ quan, phân biệt rõ lỗi hệ thống thực sự với giới hạn môi trường OS/ACL.

### 3.2. Môi trường thực thi
- **Hệ điều hành**: Windows (`win32`)
- **Python Runtime**:
  - Hệ thống: `Python 3.13.2`
  - Môi trường ảo dự án (`.venv\Scripts\python.exe`): `Python 3.12.14`
- **Công cụ kiểm định trong `.venv`**: `pytest 9.2.0`, `ruff 0.17.5`, `mypy 2.4.1`, `SQLAlchemy 2.0.57`, `FastAPI 0.162.7`, `pydantic 2.14.3`, `scikit-learn 1.9.1`, `xgboost 3.0.0`, `lightgbm 4.7.0`, `shap 0.54.1`, `pandas 3.0.1`, `numpy 2.3.5`.
- **Giới hạn môi trường ghi nhận**:
  1. Thư mục `.pytest_cache` tại gốc dự án và thư mục tạm mặc định `C:\Users\hp\AppData\Local\Temp\pytest-of-hp` bị khóa quyền truy cập bởi Windows ACL (`PermissionError: [WinError 5] Access is denied`), gây ra 62 lỗi `ERROR` ở bước fixture setup (`tmp_path`) khi chạy `pytest -v` với đường dẫn tạm mặc định.
  2. Khi chuyển `--basetemp` và `cache_dir` sang thư mục có quyền ghi, toàn bộ 62 lỗi setup biến mất, cho phép đánh giá chính xác 184/184 test cases.
  3. Không thực hiện truy vấn mạng ra SEC EDGAR thật hoặc kết nối vào SQL Server `ADMIN-PC` nhằm tuân thủ tuyệt đối nguyên tắc Read-Only / Không tác động dịch vụ ngoài.

---

## 4. Tóm tắt Điều hành (Executive Summary)

Dự án **FinHealth** có chất lượng thiết kế kiến trúc và kỹ thuật cốt lõi ở mức tốt: phân tách rõ các tầng (`core`, `db`, `ingestion`, `etl`, `ml`, `api`, `frontend`), không có hiệu ứng phụ khi import (lazy loading), xử lý chuẩn xác ngữ cảnh thời gian của báo cáo XBRL SEC EDGAR, kiểm soát chặt chẽ hiện tượng rò rỉ dữ liệu tương lai (temporal purging và publication-date embargo), và áp dụng các biện pháp phòng vệ an toàn (ràng buộc khóa ngoại đa dialect, chuẩn hóa NaN/Inf thành `null`, chống CSV injection, giới hạn tốc độ SEC).

Tuy nhiên, cuộc kiểm định độc lập đã phát hiện và chứng minh bằng bằng chứng trực tiếp **18 phát hiện kỹ thuật (Findings)**, trong đó có **3 lỗi mức HIGH (P1)**, **6 lỗi mức MEDIUM (P2)**, **6 lỗi mức LOW (P3)** và **3 ghi nhận mức INFO (P4)**. Đáng chú ý nhất:

1. **Sự bất đồng bộ nghiêm trọng về trạng thái dữ liệu và mô hình lưu trữ (`AUD-DATA-001` - HIGH, `AUD-FUNC-001` - HIGH)**:
   - Mô hình đang kích hoạt trong `data/artifacts/models/latest.json` là `v1.2.0` (được tạo lúc `2026-11-20T13:31:09Z`), trong đó bộ phân loại chiến thắng (`selected_model_name`) là **`random_forest`** (có `output_space = "probability"`).
   - Ngược lại, trong cơ sở dữ liệu `data/processed/parquet/finhealth.sqlite3`, 98 bản ghi dự báo của `model_version = 'v1.2.0'` lại được ghi từ một lần chạy trước đó (lúc `2026-11-20 13:20:09Z` – `13:20:24Z`, tức sớm hơn 11 phút so với bundle `v1.2.0` trên đĩa) khi `output_space` vẫn được lưu là **`"log_odds"`** trong khi `base_value` (`~0.4982`) và các đóng góp SHAP lại nằm trên thang xác suất (`probability`).
   - Hệ quả trực tiếp:
     - **3 kiểm thử tích hợp quan trọng bị FAILED** (`test_company_features_explanations_and_altman[AAPL]`, `test_company_features_explanations_and_altman[AAL]`, `test_prediction_and_api_parity`).
     - Giao diện người dùng (`frontend/js/app.js:630-638`) và biểu đồ giải thích (`frontend/js/charts.js:254-288`, `frontend/index.html:159`) hiển thị sai bản chất toán học của SHAP: áp dụng hàm sigmoid `1 / (1 + Math.exp(-summed))` lên tổng xác suất của Random Forest (ví dụ với AAPL: tổng xác suất SHAP là `0.0722` nhưng giao diện tính `sigmoid(0.0722) = 51.8%` và ghi nhãn là `log-odds`).
2. **Vi phạm kiểm tra kiểu tĩnh Mypy (`AUD-CODE-001` - HIGH)**:
   - Dù tệp log cũ `data/artifacts/data-version/mypy.txt` ghi `"Success: no issues found in 60 source files"`, việc chạy thực tế `mypy src/finhealth` trên 61 tệp nguồn hiện tại **FAILED với 9 lỗi trong 4 tệp** (`kaggle_loader.py`, `distress_classifier.py`, `registry.py`, `train_cli.py`) liên quan đến các thay đổi bổ sung LightGBM, Random Forest và Kaggle dataset.
3. **Lỗi hiển thị biểu đồ đường hiệu chuẩn xác suất 07 (`AUD-FUNC-002` - MEDIUM)**:
   - Hàm `reliability_bins()` trong `src/finhealth/ml/evaluator.py:119-127` xuất ra các khóa `"model"`, `"n"`, `"mean_probability"`, `"observed_prevalence"`, nhưng hàm vẽ biểu đồ `_reliability()` trong `src/finhealth/ml/visualization.py:318-325` lại đọc các khóa không tồn tại là `"score"`, `"count"`, `"mean_score"`, `"observed_rate"`. Kết quả là tệp ảnh xuất bản `07_reliability_calibration.png` chỉ có đường chéo tham chiếu `y = x` mà **không hề có bất kỳ dữ liệu thực nghiệm nào được vẽ lên**.

---

## 5. Tổng hợp các Phát hiện Đã Xác minh (Confirmed Findings Summary)

| ID | Lĩnh vực | Mức độ | Trạng thái | Tóm tắt vấn đề |
|---|---|---|---|---|
| `AUD-DATA-001` | Database & Data Integrity | **HIGH (P1)** | `REPRODUCED` | Bất đồng bộ giữa gói mô hình `v1.2.0` trên đĩa (`output_space="probability"`, tạo lúc 13:31Z) và dữ liệu `model_predictions` trong SQLite (`output_space="log_odds"` gắn với giá trị SHAP xác suất của Random Forest, tạo lúc 13:20Z), làm FAIL 3 integration tests. |
| `AUD-FUNC-001` | Functional & Academic | **HIGH (P1)** | `VERIFIED` | Giao diện Giải thích rủi ro (`app.js`, `charts.js`, `index.html`) tính sai xác suất đối soát SHAP (áp dụng hàm sigmoid lên tổng xác suất) và gắn cứng nhãn `log-odds` khi mô hình được chọn là Random Forest. |
| `AUD-CODE-001` | Clean Code & Type Safety | **HIGH (P1)** | `REPRODUCED` | `mypy src/finhealth` thất bại với 9 lỗi kiểu tĩnh trong 4 tệp thuộc module `ml`, trái ngược với log báo cáo cũ trong `data/artifacts/data-version/mypy.txt`. |
| `AUD-FUNC-002` | Functional & Visualization | **MEDIUM (P2)** | `VERIFIED` | Sai lệch tên khóa dữ liệu giữa `evaluator.reliability_bins` và `visualization.EvaluationPlotGenerator._reliability` khiến biểu đồ `07_reliability_calibration.png` bị rỗng (không có đường dữ liệu Raw và Calibrated). |
| `AUD-SEC-001` | Security & Privacy | **MEDIUM (P2)** | `STATICALLY_CONFIRMED` | Khi `APP_ENV` là `staging` hoặc `production`, frontend (`frontend/js/api.js`) không có cơ chế gửi header `Authorization: Bearer <ADMIN_TOKEN>`, khiến các thao tác cập nhật/phân tích SEC từ giao diện web chắc chắn bị từ chối `HTTP 403`. |
| `AUD-ARCH-001` | Architecture & Concurrency | **MEDIUM (P2)** | `STATICALLY_CONFIRMED` | Biến toàn cục `_MODEL_STATE` được chia sẻ mặc định giữa các instance `create_app()`; phương thức `initialize()` dừng sớm nếu `_initialized == True`, gây rủi ro dùng sai model path khi khởi tạo nhiều app instance với `Settings` khác nhau mà không gán lại `app.state.model_registry`. |
| `AUD-TEST-001` | Testing & QA Reliability | **MEDIUM (P2)** | `REPRODUCED` | Kiểm thử hiệu năng `test_api_latency[/companies]` đặt ngưỡng cứng `P95 < 50ms` ngay trong bộ test chức năng và bị FAIL (`P95 = 59.83ms`) khi hệ thống chịu tải I/O. |
| `AUD-OPS-001` | DevOps & Environment | **MEDIUM (P2)** | `REPRODUCED` | Quyền truy cập hệ thống tệp (Windows ACL) bị khóa trên `D:\DATN\.pytest_cache` và `%TEMP%\pytest-of-hp`, làm 62 test bị `ERROR` ở bước khởi tạo fixture `tmp_path` nếu chạy `pytest` không kèm `--basetemp`. |
| `AUD-DOC-001` | Documentation Divergence | **MEDIUM (P2)** | `VERIFIED` | `README.md` và các bản chụp kiểm định trong `data/artifacts/` lỗi thời so với trạng thái thực tế của hệ thống (phiên bản mô hình `v1.1.0` vs `v1.2.0`, số lượng công ty 80 vs 98, số báo cáo 1,234 vs 1,506, số lượng biểu đồ 6 vs 7). |
| `AUD-SEC-002` | Security & Supply Chain | **LOW (P3)** | `STATICALLY_CONFIRMED` | Rủi ro bảo mật tiềm ẩn khi nạp gói mô hình qua `joblib.load()` (pickle deserialization) nếu thư mục `data/artifacts/models` bị ghi đè bởi tiến trình không tin cậy, và cấu hình CORS cứng `http://localhost:3000` ở môi trường ngoài `development`. |
| `AUD-PERF-001` | Performance & Scalability | **LOW (P3)** | `STATICALLY_CONFIRMED` | Truy vấn danh sách doanh nghiệp (`list_company_summaries`) nạp lại toàn bộ bảng chỉ số năm qua `_annual_metrics(session)` trên mỗi trang phân trang hoặc khi có bộ lọc để tính phân vị `CompositeBenchmark` trong bộ nhớ Python. |
| `AUD-DATA-002` | Database & Schema Design | **LOW (P3)** | `STATICALLY_CONFIRMED` | Bảng `filing_versions` lưu `issuer_key` dạng chuỗi (`sec:<cik>`, `vn:<ticker>`) không có khóa ngoại (FK) tham chiếu tới bảng `companies`, và `forecast_evidence.filing_version_id` không khai báo `ondelete="CASCADE"`. |
| `AUD-ACAD-001` | Academic & Methodology | **LOW (P3)** | `STATICALLY_CONFIRMED` | Khi huấn luyện trên bộ dữ liệu Kaggle (`kaggle_loader.py`), cột `filed_date` không tồn tại nên cơ chế cắt ngưỡng ngày công bố (`training_horizon_rows` và `prepare_validation_test` embargo) bị bỏ qua, chỉ phân chia theo `fiscal_year`. |
| `AUD-OPS-002` | DevOps & Supply Chain | **LOW (P3)** | `VERIFIED` | Dự án không có kho lưu trữ Git (`.git`), không có lockfile cố định phiên bản (`requirements.lock` / `uv.lock` / `poetry.lock`), metadata gói `finhealth` trong `.venv` vẫn ở `0.1.0` (so với `1.3.0`), và `.venv` chứa gói ngoại lai `yfinance 0.2.56` bị thiếu 5 dependencies làm `pip check` thất bại (exit code 1). |
| `AUD-CODE-002` | Clean Code & Frontend CSS | **LOW (P3)** | `STATICALLY_CONFIRMED` | Tệp `frontend/styles.css` chứa 4 selector viết sai cú pháp CSS do có khoảng trắng sau dấu hai chấm (`button: disabled`, `button: focus-visible`, `input: :placeholder`, `dialog: :backdrop`), khiến trình duyệt bỏ qua các quy tắc định dạng này. |
| `AUD-INFO-001` | Academic Transparency | **INFO (P4)** | `VERIFIED` | Các giả định học thuật (nhãn khó khăn tài chính là proxy kế toán chứ không phải phá sản pháp lý; Altman X4 của dữ liệu SEC dùng giá trị sổ sách của vốn chủ sở hữu) được tài liệu hóa minh bạch trong code, API và UI. |
| `AUD-INFO-002` | Architecture & Rate Limit | **INFO (P4)** | `VERIFIED` | Bộ giới hạn tốc độ `AsyncRateLimiter` điều phối trong phạm vi một tiến trình/event loop đơn lẻ; giới hạn này đã được ghi chú rõ trong `src/finhealth/ingestion/README.md`. |
| `AUD-INFO-003` | Testing & QA Coverage | **INFO (P4)** | `NOT_TESTED` | Kiểm thử hiển thị trực quan trên trình duyệt thực tế (visual browser rendering) và kiểm thử tích hợp trực tiếp với PostgreSQL / SQL Server thật không được thực thi trong phạm vi audit Read-Only offline. |

---

## 6. Các Phát hiện Nghi ngờ / Chưa xác minh (Suspected / Unverified Findings)

- **Tương thích runtime với SQL Server (`ADMIN-PC/finhealth_db`)**: Tệp `.env` hiện tại trỏ `DATABASE_URL` tới instance SQL Server cục bộ `ADMIN-PC/finhealth_db`, và tệp `data/artifacts/data-version/live-qa.json` ghi nhận một lần chạy trước đó với 80 công ty và model `v1.1.0`. Do tuân thủ nguyên tắc Read-Only và không tác động vào dịch vụ cơ sở dữ liệu ngoài, trạng thái hiện thời của database `finhealth_db` trên SQL Server được ghi nhận là `NOT_TESTED`. Tuy nhiên, nếu SQL Server vẫn đang lưu dữ liệu của model `v1.1.0` trong khi `latest.json` trên đĩa đã chuyển sang `v1.2.0`, ứng dụng khi khởi động với `.env` sẽ gặp hiện tượng lệch phiên bản giữa model đang active (`v1.2.0`) và các dự báo lưu trong SQL Server (`v1.1.0`) (`SUSPECTED`).

---

## 7. Đánh giá Mức độ Sẵn sàng Vận hành (Production Readiness Assessment)

Dựa trên bằng chứng thực nghiệm thu thập được:

- **Trạng thái hiện tại**: **CHƯA SẴN SÀNG CHO PRODUCTION (NOT PRODUCTION-READY)** ở trạng thái nguyên bản hiện tại nếu chưa khắc phục các lỗi P1 và P2.
- **Lý do cốt lõi**:
  1. Dữ liệu dự báo và giải thích SHAP của phiên bản mô hình đang kích hoạt (`v1.2.0`) trong cơ sở dữ liệu SQLite bị lệch trạng thái với chính artifact `v1.2.0` và với logic hiển thị của frontend (`AUD-DATA-001`, `AUD-FUNC-001`), dẫn đến 3 kiểm thử tích hợp thất bại và hiển thị sai số liệu đối soát xác suất trên giao diện Giải thích rủi ro.
  2. Kiểm tra kiểu tĩnh `mypy src/finhealth` đang thất bại với 9 lỗi (`AUD-CODE-001`).
  3. Biểu đồ xuất bản số 07 (`07_reliability_calibration.png`) đang bị vẽ rỗng do sai tên trường dữ liệu (`AUD-FUNC-002`).
  4. Luồng phân tích/cập nhật dữ liệu SEC từ giao diện người dùng không thể hoạt động trong môi trường `staging`/`production` khi bật `ADMIN_TOKEN` vì thiếu cơ chế truyền token ở frontend (`AUD-SEC-001`).
  5. Không có quản lý phiên bản Git và không có lockfile để đảm bảo khả năng tái lập bản dựng (reproducible build) (`AUD-OPS-002`).

---

## 8. Giới hạn của Cuộc Kiểm định (Major Limitations)

1. **Không có lịch sử Git**: Repository không có thư mục `.git`, do đó không thể kiểm chứng lịch sử thay đổi, tác giả commit hoặc thời điểm phát sinh các bản sửa đổi giữa `v1.1.0` và `v1.2.0`.
2. **Không kết nối dịch vụ mạng / DB bên ngoài**: Không gửi request thực tế tới máy chủ `sec.gov` và không kết nối trực tiếp vào dịch vụ SQL Server `ADMIN-PC` hay PostgreSQL container để đảm bảo tính cô lập và an toàn tuyệt đối.
3. **Không kiểm thử giao diện trên trình duyệt headless**: Đánh giá frontend dựa trên phân tích tĩnh 100% mã nguồn HTML/CSS/JS và kiểm thử tích hợp HTTP/static qua FastAPI `TestClient`.

---

## 9. Khuyến nghị Hành động Tiếp theo (Recommended Next Actions)

1. **Khắc phục ngay lập tức (Immediate / P1)**:
   - Đồng bộ lại dữ liệu dự báo trong `finhealth.sqlite3` với gói mô hình `v1.2.0` (hoặc sửa `ShapExplainer` và `frontend/js/app.js` + `charts.js` để xử lý đồng nhất cả hai không gian đầu ra `log_odds` và `probability`).
   - Sửa 9 lỗi kiểu tĩnh trong `src/finhealth/ml/` để `mypy src/finhealth` đạt `0 errors`.
2. **Khắc phục ngắn hạn (Short-term / P2)**:
   - Đồng bộ tên khóa dữ liệu trong `EvaluationPlotGenerator._reliability()` khớp với `reliability_bins()` và tạo lại biểu đồ `07_reliability_calibration.png`.
   - Khôi phục quyền ACL cho thư mục `.pytest_cache` và `%TEMP%\pytest-of-hp` trên máy cục bộ; tách các kiểm thử benchmark độ trễ (`test_api_latency`) ra khỏi ngưỡng fail cứng hoặc điều chỉnh ngưỡng phù hợp.
   - Bổ sung cơ chế nhập/gửi `ADMIN_TOKEN` trên giao diện hoặc xác thực phiên cho các route ghi khi chạy ở `staging`/`production`.
   - Cập nhật `README.md` khớp với trạng thái gói mô hình `v1.2.0` và bộ dữ liệu 98 doanh nghiệp / 1,506 báo cáo năm.
3. **Cải thiện trung và dài hạn (Medium & Long-term / P3)**:
   - Khởi tạo Git repository, tạo lockfile cho dependencies, dọn dẹp các gói ngoại lai trong `.venv` và cài đặt lại `pip install -e ".[dev]"` để đồng bộ version `1.3.0`.
   - Sửa 4 lỗi cú pháp selector trong `frontend/styles.css`.
