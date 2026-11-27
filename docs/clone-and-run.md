# Bàn giao FinHealth

## Thành phần đã đưa lên GitHub

- Backend Python/FastAPI (`src/finhealth`).
- Alembic migrations 0001–0007, tests và tài liệu backend.
- Cache SEC gốc, bộ dữ liệu Kaggle hiện có, các panel Parquet, mô hình và ảnh biểu đồ.
- `data/seed/financial.sqlite3`: xuất trực tiếp từ SQL Server hiện tại, chỉ có `companies`,
  `financial_statements`, `financial_metrics`, `model_predictions`, `filing_versions`,
  `forecast_evidence`. Giữ ID, số liệu thiếu, đơn vị và provenance trong các bản ghi.

Không bàn giao `.env`, SMTP credentials, `.venv`, `node_modules`, database backup gốc,
tài khoản, password hash, phiên đăng nhập, OTP, watchlist, saved analyses hoặc log riêng.
SQL Server là phần mềm cần cài riêng; Git lưu cấu trúc và snapshot tài chính để khôi phục.

## 1. Clone và cài Python

Dùng Python **3.12 64-bit** để khớp môi trường của model bundle. Máy cần Git và Python.

```powershell
git clone https://github.com/pth-aimy04/FinHealth.git
cd FinHealth
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock -e ".[dev,sqlserver]"
Copy-Item .env.example .env
```

Nếu PowerShell chặn Activate.ps1, gọi trực tiếp `.\.venv\Scripts\python.exe`,
`.\.venv\Scripts\alembic.exe` và `.\.venv\Scripts\uvicorn.exe` thay vì activate.
`requirements.lock` khóa các dependency dự án và mô hình; không dùng đường dẫn package
riêng trên máy người tạo. Không lấy `.env` của người khác để dùng chung mật khẩu.

## 2. SQL Server

Cài SQL Server Developer/Express, SSMS và Microsoft ODBC Driver 17 hoặc 18 for SQL Server
cùng kiến trúc Python. Trong SSMS, kết nối instance của **máy bạn**, dùng Windows
Authentication và chạy `scripts/create_sqlserver_database.sql` để tạo `finhealth_db`
nếu chưa có. Script không xóa hoặc thay thế database có sẵn.

Trong `.env`, sửa tên máy/instance và driver theo kết quả `Get-OdbcDriver`:

```dotenv
DATABASE_URL="mssql+pyodbc://localhost/finhealth_db?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes"
INGESTION_WORKER_ENABLED=false
```

Với SQL Express, hostname có thể là `localhost\SQLEXPRESS`. Đừng dùng tên `ADMIN-PC`
của máy phát triển nếu instance nằm trên máy bạn. Windows Authentication dùng tài khoản
Windows đang chạy Python; tài khoản này phải được cấp quyền tạo bảng và ghi dữ liệu.
`TrustServerCertificate=yes` dành cho SQL Server local với chứng chỉ tự ký.

Từ thư mục gốc, chạy:

```powershell
python -m finhealth.db.handoff restore
alembic current
```

Lệnh restore áp dụng migrations rồi sao chép sáu bảng trong một transaction, giữ nguyên
ID và kiểm tra số dòng. Nó từ chối database đã có dữ liệu tài chính; hãy dùng database
mới, không xóa database đang làm việc để chạy lại. Tài khoản và bảng vận hành được tạo
trống qua migrations. Không import file `.bak` gốc vì có thể chứa thông tin tài khoản.

## 3. Chạy không cần SQL Server (SQLite)

Đổi riêng `DATABASE_URL` trong `.env` rồi chạy cùng lệnh restore:

```dotenv
DATABASE_URL="sqlite:///data/processed/parquet/finhealth.sqlite3"
```

```powershell
python -m finhealth.db.handoff restore
```

Đây là database làm việc riêng. Giữ snapshot `data/seed/financial.sqlite3` nguyên vẹn;
không trỏ ứng dụng trực tiếp vào snapshot vì nó không có bảng tài khoản/vận hành.

## 4. Khởi động và tạo admin riêng

```powershell
python -m finhealth.core.account_cli --help
python -m finhealth.core.account_cli create-admin --email admin@example.com --name "Local Admin"
uvicorn finhealth.api.main:app --host 127.0.0.1 --port 8000
```

Thay email ví dụ bằng email của bạn; CLI hỏi mật khẩu trong terminal.
Mở http://127.0.0.1:8000 và http://127.0.0.1:8000/docs.
Public browsing không cần SMTP. Đăng ký, xác minh và khôi phục tài khoản qua email cần
SMTP thật do người chạy cấu hình trong `.env`; xem `security-and-accounts.md`.

Cache và mô hình đã có nên không cần gọi SEC hoặc huấn luyện lại để chạy dashboard.
Trước bất kỳ lần cập nhật SEC nào, thay `research@example.com` trong `SEC_USER_AGENT`
bằng email được theo dõi. Chỉ bật một ingestion dispatcher cho mỗi danh tính SEC.

## 5. Kiểm tra

```powershell
ruff check .
pytest -v
```

Test SQL Server thật yêu cầu bật `FINHEALTH_SQLSERVER_TEST_ENABLED=1` rõ ràng.
Một số test audit cần snapshot/fixture riêng và sẽ báo skipped nếu không có.
Mô hình joblib chỉ được nạp từ repo/bundle đáng tin cậy.

## Cập nhật snapshot bàn giao

Chỉ chạy khi chủ dữ liệu cho phép chia sẻ. Với `.env` trỏ database nguồn, xuất ra đường
dẫn mới để không ghi đè snapshot hiện tại:

```powershell
python -m finhealth.db.handoff export --snapshot data/seed/financial-next.sqlite3
```

Exporter chỉ đọc sáu bảng trong allowlist. Các bảng cá nhân và bảo mật không được xuất.
