# Spec: Asynchronous Batch Excel Assessment & Executive PDF Reporting (`batch-and-reporting`) — V1.0

> **Module ID:** `batch-and-reporting` (xem [capability-map.md](capability-map.md))  
> **Trạng thái:** Đã chốt (Approved — sẵn sàng triển khai)  
> **Phụ thuộc:** `risk-analytics` (`CompanyAssessmentView`, `OrgAssessment`, `OrgContext`)  
> **Phạm vi nghiệp vụ:** M12 (Xuất Báo cáo Thẩm định Tài chính chuẩn PDF chuyên nghiệp), S03 (Thẩm định Hàng loạt qua file Excel chạy nền bất đồng bộ + xếp hạng rủi ro + xuất bảng tổng hợp Excel).

---

## 1. Objective

Cung cấp 2 đầu ra thương mại trọng yếu giúp đội ngũ tài chính, thẩm định tín dụng và mua hàng sử dụng FinHealth trong quy trình phê duyệt thực tế:
1. **Xuất Báo cáo Thẩm định Tài chính chuẩn PDF (M12):** Tài liệu trình ký đẹp, tiếng Việt có dấu hoàn chỉnh (font Be Vietnam Pro / Noto Sans), đóng băng phiên bản mô hình & miễn trừ trách nhiệm pháp lý.
2. **Thẩm định Hàng loạt qua Excel (S03):** Tải lên 1 file Excel chứa tối đa 500 doanh nghiệp, xử lý nền bất đồng bộ (không chặn request API), xếp hạng ưu tiên rủi ro từ cao xuống thấp và cho tải về file Excel kết quả tổng hợp.

### Yêu cầu nghiệp vụ cụ thể
1. **Xuất Báo cáo Thẩm định PDF phía Server (M12):**
   - Endpoint:
     - `GET /api/v1/org/companies/{company_id}/report.pdf?fiscal_year=...` (yêu cầu `viewer` trong tổ chức).
     - `GET /api/v1/companies/{identifier}/report.pdf` (cho DN trên tab "Thị trường Mỹ (SEC)", yêu cầu đăng nhập để chống lạm dụng CPU).
   - **Cấu trúc Báo cáo PDF (3–4 trang chuẩn A4):**
     - **Trang 1 — Tóm tắt Điều hành (Executive Summary):** Tên DN, MST/Mã CK, Ngành, Kỳ BCTC, Chuẩn kế toán (TT99/TT200/TT133/US GAAP), Trạng thái kiểm toán, Điểm Sức khỏe tổng hợp `0–100` & huy hiệu 4 màu, Xác suất Nguy cơ Phá sản 12 tháng (%), Chỉ báo Độ tin cậy 4 lớp, Thước đo Altman ($Z/Z'/Z''$), 3 nhận định trọng tâm nhất.
     - **Trang 2 — 5 Trụ cột & Điểm Tựa / Điểm Nghẽn:** Biểu đồ Radar 5 trụ cột (nhúng SVG/PNG sắc nét), bảng 2 cột Xanh–Đỏ (Điểm Tựa & Điểm Nghẽn Tài Chính), cảnh báo Dòng tiền / QoE (nếu có).
     - **Trang 3 — Bảng 20 Chỉ số Cốt lõi & Diễn biến Đa kỳ:** Bảng đối chiếu 20 chỉ số kèm Kỳ trước, Vị thế ngành và Trạng thái; biểu đồ xu hướng sức khỏe 3–5 năm (nếu có ≥2 kỳ).
     - **Chân trang mọi trang (Auditability & Pháp lý):** Ngày giờ trích xuất, `model_version`, mã định danh bản chụp (`assessment_id`), và dòng miễn trừ trách nhiệm theo **Nghị định 88/2014/NĐ-CP**.
   - **Công nghệ render PDF không lệ thuộc trình duyệt nặng:** Dùng **`weasyprint`** (HTML + CSS + SVG nhúng → PDF vector chất lượng cao, hỗ trợ hoàn hảo tiếng Việt UTF-8; nếu môi trường Windows thiếu GTK/Pango runtime thì cung cấp fallback thuần Python bằng **`reportlab`** với font TrueType Unicode nhúng trong repo để 100% chạy được trên cả Linux Docker lẫn Windows local!). *Chiến lược cụ thể: dùng **ReportLab + Matplotlib/SVG-to-PNG** làm engine mặc định 100% đa nền tảng (Windows/Linux/CI không cần cài thư viện hệ thống GTK/Cairo), thiết kế layout A4 chuẩn doanh nghiệp.*
2. **Thẩm định Hàng loạt qua Excel bất đồng bộ (S03):**
   - **Tải biểu mẫu Excel Batch (`GET /api/v1/org/batch/template.xlsx`):** File `.xlsx` mẫu gồm 1 sheet hướng dẫn + 1 sheet nhập liệu nhiều doanh nghiệp (mỗi dòng 1 DN: Tên, MST, Ngành, Loại hình, Niêm yết, Năm, Trạng thái kiểm toán + các cột khoản mục BCTC cốt lõi).
   - **Tải lên & tạo Job chạy nền (`POST /api/v1/org/batch/jobs` — yêu cầu `analyst`):**
     - Kiểm tra file `.xlsx` (≤ 10 MB, tối đa 500 dòng doanh nghiệp), tạo bản ghi `org_batch_jobs` (`status='queued'`, `total_rows`, `processed_rows`, `failed_rows`, gắn `organization_id` và `created_by`).
     - Trả ngay `202 Accepted` kèm `job_id`.
     - **Xử lý nền bất đồng bộ (DB-backed job queue / Background worker):** Kế thừa mô hình worker bền vững đang có của `src/finhealth/ingestion/jobs.py` (DB-backed queue chạy an toàn trên SQLite/PostgreSQL/SQL Server, không bắt buộc cài Redis để chạy local, và sẵn sàng mở rộng sang Redis/ARQ ở production).
     - Từng dòng được chạy qua `accounting_validator` + `ml-bankruptcy-engine` + `risk-analytics` (dòng lỗi dữ liệu được ghi rõ nguyên nhân lỗi mà **không làm sập cả lô**).
     - Kết quả sắp xếp theo thứ tự **`pd_12m` giảm dần** (ưu tiên công ty rủi ro cao nhất lên đầu).
   - **Theo dõi tiến độ & xem bảng kết quả (`GET /api/v1/org/batch/jobs`, `GET /api/v1/org/batch/jobs/{job_id}` — yêu cầu `viewer`):** Hiển thị trạng thái (`queued | running | completed | failed`), tiến độ `processed_rows / total_rows`, phân bổ 4 mức rủi ro và bảng xếp hạng.
   - **Xuất bảng tổng hợp Excel (`GET /api/v1/org/batch/jobs/{job_id}/export.xlsx` — yêu cầu `viewer`):** Sheet 1: Tóm tắt danh mục (phân bổ 4 nhóm rủi ro, PD trung bình, Điểm sức khỏe trung bình); Sheet 2: Danh sách doanh nghiệp xếp hạng rủi ro kèm các chỉ số chính, Điểm nghẽn hàng đầu, Độ tin cậy và ghi chú lỗi dòng (nếu có).

---

## 2. Tech Stack

- **PDF Engine:** `reportlab>=4.2.0` (thuần Python, chạy ổn định trên Windows + Linux Docker không cần GTK, nhúng font TTF tiếng Việt từ `frontend/node_modules/@fontsource/be-vietnam-pro` hoặc lưu bản font chính thức SIL OFL trong `src/finhealth/reporting/fonts/`).
- **Excel Engine:** `openpyxl>=3.1.2` (dùng chung với `financial-data`).
- **Biểu đồ nhúng PDF:** `matplotlib>=3.8.0` (đã có sẵn trong `pyproject.toml`, xuất PNG 200 DPI với backend `Agg` phi giao diện).
- **Rate limit:** Tận dụng `consume_limit` ở `src/finhealth/api/security.py` để chống spam xuất PDF / batch.

---

## 3. Commands

```powershell
.\.venv\Scripts\ruff.exe check src/finhealth/reporting src/finhealth/api/routers/reporting_v2.py
.\.venv\Scripts\mypy.exe src/finhealth
.\.venv\Scripts\pytest.exe -v tests/unit/test_pdf_and_batch_excel.py tests/integration/test_batch_jobs_and_pdf_api.py
```

---

## 4. Project Structure

```text
migrations/versions/
  └── 0011_org_batch_jobs.py                  # Bảng org_batch_jobs và org_batch_job_rows (gắn organization_id)
src/finhealth/db/
  └── batch_models.py                         # ORM OrgBatchJob, OrgBatchJobRow
src/finhealth/reporting/
  ├── __init__.py
  ├── fonts/                                  # Font BeVietnamPro TTF (SIL OFL) hỗ trợ đầy đủ dấu tiếng Việt
  ├── pdf_generator.py                        # Tạo PDF A4 3–4 trang (Executive Summary, Radar, 2 cột Drivers, 20 chỉ số, Disclaimer)
  ├── batch_excel.py                          # Tạo template batch .xlsx, parse upload .xlsx, xuất báo cáo tổng hợp .xlsx
  └── batch_worker.py                         # Xử lý lô nền an toàn, cập nhật tiến độ & cô lập lỗi từng dòng
src/finhealth/api/
  ├── schemas/batch_reporting.py              # BatchJobSummary, BatchJobDetail, BatchRowResult
  └── routers/reporting_v2.py                 # Endpoint PDF report & Batch Excel CRUD/export
tests/
  ├── unit/test_pdf_and_batch_excel.py        # Kiểm thử sinh bytes PDF hợp lệ (%PDF-1.), chứa tiếng Việt không lỗi font,
  │                                           # round-trip Excel batch & sắp xếp rủi ro giảm dần
  └── integration/test_batch_jobs_and_pdf_api.py  # Kiểm thử cô lập org_id, RBAC, upload file lỗi, rate limit, tải PDF & Excel
```

---

## 5. Code Style

```python
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def ensure_valid_pdf_bytes(buffer: BytesIO) -> bytes:
    """Return generated PDF bytes after verifying standard PDF header integrity."""
    payload = buffer.getvalue()
    if not payload.startswith(b"%PDF-"):
        raise RuntimeError("PDF generator did not produce a valid PDF stream")
    return payload
```

---

## 6. Testing Strategy

- **Unit tests (`tests/unit/test_pdf_and_batch_excel.py`):**
  - Sinh PDF từ dữ liệu mẫu VN (có đầy đủ tiếng Việt có dấu, 5 trụ cột, lịch sử 4 năm, và cả trường hợp DN bị âm VCSH hoặc thiếu dữ liệu kỳ trước) → kiểm tra header `%PDF-`, kích thước > 10 KB, không crash khi có `None`.
  - Sinh PDF cho DN `financial_institution` → kiểm tra không in điểm Altman Z/ML và có ghi chú loại trừ.
  - Batch Excel: kiểm tra đọc file 10 DN gồm 8 dòng hợp lệ + 2 dòng sai cấu trúc (ví dụ `total_assets <= 0`) → 8 dòng chấm thành công và xếp thứ tự `pd_12m` giảm dần, 2 dòng lỗi có thông báo rõ ràng; file `.xlsx` xuất ra mở đọc lại được bằng `openpyxl`.
- **Integration tests (`tests/integration/test_batch_jobs_and_pdf_api.py`):**
  - Upload Excel batch trả `202`, job chạy xong trả `completed`, `viewer` xem & tải `.xlsx` được nhưng bị `403` khi upload job mới; tổ chức khác gọi `job_id` nhận `404`.
  - Tải PDF `GET /api/v1/org/companies/{id}/report.pdf` trả `200`, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="..."`; tổ chức khác gọi nhận `404`.

---

## 7. Boundaries

- **Always:**
  - Dùng `matplotlib.use("Agg")` (không phụ thuộc GUI display) và đóng `plt.close(fig)` ngay sau khi xuất PNG vào `BytesIO` để không rò rỉ RAM trên server.
  - Giới hạn file upload batch ≤ 10 MB và ≤ 500 dòng; dùng `openpyxl(..., read_only=True, data_only=True)` chống zip-bomb / memory exhaustion.
  - Luôn in `model_version`, ngày trích xuất và điều khoản miễn trừ trách nhiệm NĐ 88/2014/NĐ-CP vào chân trang PDF.
- **Ask first:**
  - Tăng giới hạn tối đa số dòng mỗi lô batch (> 500) hoặc chuyển đổi sang hạ tầng Redis/Celery bắt buộc.
- **Never:**
  - Không bao giờ để 1 dòng Excel lỗi làm fail toàn bộ batch job.
  - Không bao giờ lưu tệp PDF tạm không dọn rác ra thư mục gốc dự án hoặc phục vụ qua static mount công khai.

---

## 8. Success Criteria

1. Tải báo cáo PDF từ API/UI cho cả DN Tổ chức và DN SEC trong `< 3 giây`, hiển thị tiếng Việt có dấu sắc nét, đầy đủ 4 khối thông tin (Executive Summary, 5 Trụ cột + Điểm Tựa/Điểm Nghẽn, Bảng 20 chỉ số + Lịch sử, Miễn trừ pháp lý).
2. Upload file Excel 50 doanh nghiệp xử lý nền hoàn tất, xếp hạng ưu tiên rủi ro chính xác, xử lý êm dòng lỗi và tải về bảng Excel tổng hợp mở chuẩn trên Microsoft Excel / Google Sheets.
3. Cô lập hoàn toàn theo `organization_id` và tuân thủ phân quyền RBAC (`viewer` vs `analyst`).

---

## 9. Out of Scope (Deferred)

- Chia sẻ báo cáo trực tuyến qua liên kết có mật khẩu & thời hạn (C05 — V2.0+).
- Gửi email tự động đính kèm PDF theo lịch định kỳ (V1.1/V2.0).
- Ký số điện tử (Digital Signature / CA) lên file PDF (V2.0+).
