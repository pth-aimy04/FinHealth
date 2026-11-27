# BÁO CÁO KIỂM ĐỊNH BẢO MẬT VÀ QUYỀN RIÊNG TƯ (SECURITY AUDIT REPORT)

## 1. Tổng quan Kiểm định Bảo mật

Quá trình kiểm định bảo mật được tiến hành theo phương pháp phân tích tĩnh toàn diện mã nguồn (Static Application Security Testing - SAST), kiểm tra cấu hình môi trường, đánh giá phụ thuộc (Software Composition Analysis - SCA) và đối chiếu với các bài kiểm thử bảo mật hiện có trong test suite. Tuyệt đối không công bố nội dung secret trong báo cáo và không thực hiện tấn công xâm nhập phá hoại.

---

## 2. Các Cơ chế Phòng vệ Bảo mật Đã Được Xác Minh (`VERIFIED`)

Dự án đã chủ động triển khai nhiều biện pháp bảo vệ an toàn theo chuẩn OWASP / CWE:

1. **Chống SQL Injection & Wildcard Injection (`CWE-89`)**:
   - Toàn bộ truy vấn cơ sở dữ liệu sử dụng SQLAlchemy 2.0 ORM với tham số hóa (parameterized queries).
   - Trong `src/finhealth/api/services.py:100-104`, bộ lọc tìm kiếm chuỗi `q` sử dụng `.contains(query, autoescape=True)` để tự động escape các ký tự đại diện SQL (`%`, `_`, `\`), ngăn chặn tấn công vét cạn hoặc gây nghẽn qua chuỗi tìm kiếm (đã kiểm chứng tại `test_filing_lineage.py:56`).
   - Không có bất kỳ lời gọi `text()` hay `exec_driver_sql()` nào nối chuỗi đầu vào từ người dùng.
2. **Chống Path Traversal & Giới hạn Tệp Tĩnh (`CWE-22`)**:
   - Các route tĩnh `/static` và `/api/v1/figures` sử dụng `DashboardStaticFiles` kế thừa từ `starlette.staticfiles.StaticFiles` (`src/finhealth/api/static.py:10-23`), giới hạn nghiêm ngặt trong hai thư mục `frontend` và `data/artifacts/figures`.
   - Tên phiên bản mô hình (`model_version`) trong `TrainModelRequest` (`src/finhealth/api/schemas/models.py:385`), `save_bundle` (`registry.py:261`) và `ModelRegistryState.initialize` (`dependencies.py:69`) đều được kiểm tra bằng biểu thức chính quy chặt `r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"`, chặn hoàn toàn `..`, `/` và `\`.
   - Đã được kiểm chứng thực thi tại `tests/integration/test_dashboard_ui.py::test_static_roots_are_configurable_and_confined` (truy cập `/static/%2e%2e/private.txt`, `/api/v1/figures/%2e%2e/models/v1.0.0/models.joblib` và `/static/.env` đều trả về `HTTP 404`).
3. **Chống Cross-Site Scripting - XSS trên Giao diện (`CWE-79`)**:
   - Giao diện `frontend/js/app.js`, `charts.js` và `reports.js` định nghĩa hàm `escapeHtml` (`charts.js:6-8`) để mã hóa toàn bộ 5 ký tự nhạy cảm (`&`, `<`, `>`, `"`, `'`) trước khi đưa bất kỳ dữ liệu chuỗi nào từ API (`name`, `ticker`, `cik`, `sector`, `accession`, `source_url`, `tag`) vào `innerHTML`.
   - Liên kết ngoài (`source_url` trong `frontend/js/reports.js:25-27`) được kiểm tra bắt buộc `url?.startsWith("https://")` trước khi render thẻ `<a href=...>`, chặn hoàn toàn giao thức `javascript:` hoặc `data:`.
4. **Chống CSV Formula Injection (`CWE-1236`)**:
   - Module `frontend/js/csv.js:1-8` kiểm tra mọi giá trị văn bản xuất ra tệp CSV bằng biểu thức `/^[\s\uFEFF]*[=+@-]|^[\t\r\n]/u` và tự động chèn dấu nháy đơn dẫn đầu (`'`), ngăn chặn việc thực thi công thức độc hại trong Microsoft Excel / LibreOffice Calc (đã được kiểm chứng bằng Node.js tại `test_v12_compare_and_ui.py:251-291`).
5. **Chống HTTP Header Injection & SSRF qua SEC Client (`CWE-113`, `CWE-918`)**:
   - `Settings.validate_sec_user_agent` (`src/finhealth/core/config.py:51-67`) dùng `re.fullmatch` không cho phép ký tự xuống dòng `\r`, `\n`.
   - `SecEdgarClient` (`src/finhealth/ingestion/sec_client.py:110`) đặt `follow_redirects=False` và chỉ tạo URL từ hằng số `https://data.sec.gov/...` với `cik` đã chuẩn hóa thành đúng 10 chữ số ASCII (`normalize_cik`), ngăn chặn hoàn toàn khả năng bị lợi dụng làm bàn đạp SSRF sang host nội bộ hoặc bị redirect thoát khỏi bộ giới hạn tốc độ.
6. **Bảo vệ Thông tin Nhạy cảm trong Log và Phản hồi Lỗi (`CWE-209`, `CWE-532`)**:
   - `postgres_password` và `admin_token` sử dụng `SecretStr` với `repr=False`; `database_url_override` đặt `repr=False`.
   - `database_error_handler` (`src/finhealth/api/main.py:91-96`) bắt mọi `SQLAlchemyError` và chỉ trả về thông báo chuẩn `{"detail": "Database operation failed", "error_type": "DatabaseError"}` (HTTP 503), không làm lộ chuỗi kết nối hay câu lệnh SQL ra phía client.
   - Trong `src/finhealth/ingestion/jobs.py:100-103`, lỗi khi chạy job chỉ lưu tên lớp ngoại lệ (`type(error).__name__`) vào cột `error_code`.

---

## 3. Các Phát hiện và Điểm yếu Bảo mật Đã Xác nhận

### 3.1. `AUD-SEC-001` — Đứt gãy tích hợp xác thực `ADMIN_TOKEN` giữa Backend và Frontend (Severity: MEDIUM / P2)
- **Trạng thái**: `STATICALLY_CONFIRMED`
- **Vị trí**: `src/finhealth/api/dependencies.py:25-35`, `frontend/js/api.js:43-68, 101-115`
- **Phân tích**:
  - Backend sử dụng `require_write_access` với `hmac.compare_digest` (chống timing attack tốt) để bảo vệ các endpoint thay đổi dữ liệu (`POST /api/v1/companies/{identifier}/analyze`, `POST /api/v1/ingestion/{identifier}`, `GET /api/v1/ingestion/status/{job_id}`, `POST /api/v1/models/train`).
  - Trong môi trường `development` và `test` khi không cấu hình `ADMIN_TOKEN`, các route này mở tự do (đây là thiết kế chủ đích cho môi trường local).
  - Tuy nhiên, khi chuyển sang `staging` hoặc `production` (hoặc khi người vận hành cấu hình `ADMIN_TOKEN` trong `.env`), giao diện web `frontend/js/api.js` hoàn toàn không có khả năng đính kèm header `Authorization: Bearer <token>`, khiến chức năng "Phân tích hồ sơ SEC" trên giao diện bị tê liệt (HTTP 403).
- **Khuyến nghị**:
  - Bổ sung cơ chế nhập token quản trị trên UI (hoặc tắt form gửi request ghi trên UI công khai khi không có quyền quản trị), đồng thời bổ sung thông báo lỗi rõ ràng cho mã HTTP 403 trong `frontend/js/api.js`.

### 3.2. `AUD-SEC-002` — Rủi ro Deserialization từ `joblib.load()` và Cấu hình Cứng CORS (Severity: LOW / P3)
- **Trạng thái**: `STATICALLY_CONFIRMED`
- **Vị trí**: `src/finhealth/ml/registry.py:304-324`, `src/finhealth/api/main.py:68-74`
- **Phân tích**:
  1. **Deserialization (`CWE-502`)**: `joblib.load()` sử dụng giao thức `pickle` của Python. Mặc dù `load_bundle()` có kiểm tra SHA-256 của `models.joblib` đối chiếu với `metadata.json`, cả hai tệp này đều nằm chung trong cùng một thư mục `data/artifacts/models/<version>/`. Nếu một tác nhân độc hại có quyền ghi vào thư mục `data/artifacts/models/`, họ có thể thay thế cả `models.joblib` lẫn mã băm trong `metadata.json` để thực thi mã tùy ý khi ứng dụng khởi động.
  2. **CORS Configuration**: `main.py:70` đặt cứng `allow_origins=["*"] if configured.app_env == "development" else ["http://localhost:3000"]`. Khi triển khai trên tên miền thực tế ở `staging`/`production`, danh sách origin không thể cấu hình qua biến môi trường.
- **Khuyến nghị**:
  - Đảm bảo quyền hệ thống tệp (filesystem permissions) trên thư mục `data/artifacts/models/` chỉ cho phép ghi đối với tiến trình huấn luyện được ủy quyền.
  - Đưa danh sách `cors_allowed_origins` vào lớp `Settings` trong `src/finhealth/core/config.py`.

### 3.3. Kiểm tra Tệp `.env` và Quản lý Secret tại Local Workspace
- **Trạng thái**: `VERIFIED`
- **Quan sát**:
  - Tệp `.gitignore` đã loại trừ đúng `.env` và `.env.*` (chỉ giữ `!.env.example`).
  - Tệp `.env` hiện có trên máy cục bộ chứa các khóa cấu hình (`DATABASE_URL`, `APP_ENV`, `SEC_USER_AGENT`, `POSTGRES_*`, `INGESTION_WORKER_ENABLED`), trong đó mật khẩu PostgreSQL đang dùng giá trị mặc định của môi trường dev (`finhealth_secret` như trong `.env.example`) và `DATABASE_URL` sử dụng Windows Authentication (`Trusted_Connection` / không chứa mật khẩu plaintext) tới instance SQL Server cục bộ.
  - Không phát hiện API key, private key hay token đám mây nào bị rò rỉ trong mã nguồn hoặc trong các tệp log dưới `data/artifacts/`.

---

## 4. Giới hạn Phạm vi Kiểm định Bảo mật

- Không thực hiện quét lỗ hổng CVE trực tuyến vì môi trường kiểm định hoạt động offline; kiểm tra chuỗi cung ứng dựa trên `pip list` và `pip check` trong `.venv` (ghi nhận tại `AUD-OPS-002`).
- Không thực hiện kiểm thử tải từ chối dịch vụ (DoS/flooding) lên tiến trình Uvicorn hoặc cơ sở dữ liệu.
