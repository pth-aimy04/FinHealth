# Spec: Multi-Standard Financial Data, Private Company Directory & VN BCTC Ingestion (`financial-data`) — V1.0

> **Module ID:** `financial-data` (xem [capability-map.md](capability-map.md))  
> **Trạng thái:** Đã chốt (Approved — sẵn sàng triển khai)  
> **Phụ thuộc:** `identity-privacy` (`OrgContext`, `require_org_role`, `organizations.id`)  
> **Phạm vi nghiệp vụ:** M02 (3 DN mẫu VN), M03 (Danh bạ DN tổ chức CRUD), M04 (Nhập BCTC Web 3 biểu mẫu + Lưu nháp + Excel + **Import XML HTKK** chuẩn TT99/2025, TT200/2014, TT133/2016), M05 (Kiểm tra cân đối kế toán & sửa bug âm VCSH), mở rộng schema khoản mục BCTC, duy trì dữ liệu SEC EDGAR cho tab "Thị trường Mỹ (SEC)".

---

## 1. Objective

Xây dựng tầng dữ liệu tài chính hai miền rõ ràng và an toàn:
1. **Miền Doanh nghiệp Riêng của Tổ chức (`org_companies`, `org_financial_statements`):** Cô lập tuyệt đối theo `organization_id`, phục vụ quản lý danh bạ doanh nghiệp Việt Nam/quốc tế và nhập BCTC đa kỳ (3–5 năm) chuẩn kế toán Việt Nam.
2. **Miền Dữ liệu Công khai SEC EDGAR (`companies`, `financial_statements`):** Giữ nguyên khả năng tra cứu tab **"Thị trường Mỹ (SEC)"**, đồng thời mở rộng cột BCTC bổ sung để đồng bộ cấu trúc tỷ số với lõi ML Kaggle US.

### Yêu cầu nghiệp vụ cụ thể
1. **Mở rộng trường BCTC cốt lõi (thống nhất cho cả `OrgFinancialStatement` và `FinancialStatement`):**
   - Bổ sung 9 trường khoản mục còn thiếu so với hiện tại (`db/models.py:103-118`):
     - `cost_of_goods_sold` (Giá vốn hàng bán)
     - `gross_profit` (Lợi nhuận gộp — tự tính `revenues - cost_of_goods_sold` nếu người dùng không nhập, hoặc đối chiếu sai lệch)
     - `operating_expenses` (Tổng chi phí bán hàng & quản lý / chi phí hoạt động)
     - `depreciation_amortization` (Khấu hao TSCĐ & phân bổ)
     - `ebitda` (tự tính `operating_income + depreciation_amortization` khi thiếu)
     - `accounts_receivable` (Các khoản phải thu ngắn hạn)
     - `inventory` (Hàng tồn kho)
     - `accounts_payable` (Phải trả người bán ngắn hạn)
     - `long_term_debt` (Vay và nợ thuê tài chính dài hạn)
     - `short_term_debt` (Vay và nợ thuê tài chính ngắn hạn)
     - `market_value_equity` (Vốn hóa thị trường — tùy chọn, chỉ dùng cho Altman $Z$ của DN sản xuất niêm yết, **tuyệt đối không đưa vào mô hình ML chung**).
2. **Danh bạ Doanh nghiệp Tổ chức (M03):**
   - Bảng `org_companies` gắn `organization_id` (NOT NULL, FK `organizations.id`), gồm:
     - `id`, `organization_id`, `name` (bắt buộc), `tax_code` (MST 10 hoặc 13 chữ số dạng `0123456789` hoặc `0123456789-001`, unique theo cặp `(organization_id, tax_code)` khi không null), `ticker` (tùy chọn), `sector_code` (mã ngành VSIC cấp 1/2), `sector_name`, `business_type` (`'manufacturing' | 'trade_service' | 'financial_institution'`), `listing_status` (`'listed' | 'unlisted'`), `relationship_tag` (`'own_company' | 'customer' | 'supplier' | 'competitor' | 'portfolio' | 'other'`), `archived` (soft-archive), `is_sample` (đánh dấu 3 DN mẫu).
   - **Chặn ngành Tổ chức tài chính (FI Exclusion Gate):** Nếu `business_type == 'financial_institution'` (Ngân hàng, Bảo hiểm, Chứng khoán, Quỹ), hệ thống vẫn cho phép lưu hồ sơ nhưng **gắn cờ `scoring_eligible = False`** và trả về thông báo nghiệp vụ rõ ràng (chặn chấm điểm Altman Z và ML phi tài chính).
   - CRUD đầy đủ: `GET/POST /api/v1/org/companies`, `GET/PATCH/DELETE /api/v1/org/companies/{company_id}` (yêu cầu `viewer` cho GET, `analyst` cho POST/PATCH, `org_admin` cho DELETE vĩnh viễn; `analyst` được archive). Tìm kiếm nhanh theo tên, MST, mã CK, thẻ quan hệ, loại hình.
3. **3 Hồ sơ Doanh nghiệp Mẫu Trải nghiệm Ngay (M02 — Sample Onboarding):**
   - Cung cấp bộ seed xác định (`src/finhealth/etl/vn_samples.py`) gồm **3 doanh nghiệp Việt Nam giả lập có tính nhất quán kế toán 100% (4 năm tài chính liên tiếp FY2022–FY2025 + FY2026 chuẩn TT99)**:
     1. *Công ty CP Sản xuất Minh An (Mẫu — Vững mạnh)*: Dòng tiền dương, đòn bẩy thấp, biên lợi nhuận ổn định.
     2. *Công ty TNHH Thương mại Hoàng Long (Mẫu — Suy giảm ngầm)*: Doanh thu vẫn tăng nhưng biên lãi gộp thu hẹp 3 năm, phải thu & tồn kho phình nhanh, OCF suy yếu.
     3. *Công ty CP Xây lắp Đại Phát (Mẫu — Nguy cơ khủng hoảng cao)*: Nợ ngắn hạn vượt TSNH, lỗ lũy kế bào mòn VCSH, dòng tiền kinh doanh âm kéo dài.
   - Khi Workspace mới được tạo (hoặc người dùng bấm "Nạp lại 3 hồ sơ mẫu"), cho phép nạp/khởi tạo nhanh 3 DN mẫu (`POST /api/v1/org/samples/seed`, idempotent) để trải nghiệm toàn bộ phân tích trong <30 giây.
4. **Nhập BCTC chuẩn Kế toán Việt Nam — Web, Lưu nháp, Excel & Import XML HTKK (M04):**
   - Bảng `org_financial_statements` gắn `(organization_id, org_company_id, fiscal_year, fiscal_period)`, hỗ trợ:
     - `accounting_standard`: `'TT99_2025' | 'TT200_2014' | 'TT133_2016' | 'IFRS_USGAAP'`
     - `currency`: `'VND' | 'USD'` và `unit_scale`: `1 | 1_000_000 | 1_000_000_000` (Đồng / Triệu đồng / Tỷ đồng — mọi số tiền được chuẩn hóa nội bộ về đơn vị nguyên tệ khi lưu, giữ `display_unit` để hiển thị lại đúng đơn vị người dùng chọn).
     - `audit_status`: `'audited_unqualified' | 'audited_qualified' | 'audited_adverse_disclaimer' | 'unaudited'`
     - `status`: `'draft' | 'finalized'` (hỗ trợ **Lưu nháp** không chặn khi thiếu số liệu; khi chuyển `'finalized'` mới chạy chấm điểm ML/Altman).
     - `source_channel`: `'web_form' | 'excel_upload' | 'htkk_xml' | 'sample'`
   - **Bộ ánh xạ chỉ tiêu VAS 3 chế độ (`src/finhealth/etl/vn_accounting_mapper.py`):**
     - Ánh xạ chuẩn hóa mã số chỉ tiêu của **TT99/2025/TT-BTC** (*Báo cáo tình hình tài chính*, *Báo cáo KQHĐKD*, *Báo cáo LCTT*), **TT200/2014/TT-BTC** (`B01-DN`, `B02-DN`, `B03-DN`) và **TT133/2016/TT-BTC** (`B01a-DNN`/`B01b-DNN`, `B02-DNN`, `B03-DNN`) về cùng một tập trường chuẩn hóa nội bộ — đảm bảo chuỗi đa kỳ FY2022–2025 (TT200) nối mượt với FY2026+ (TT99).
   - **Import file XML HTKK (`POST /api/v1/org/companies/{id}/statements/import-xml`):**
     - Parse tệp `.xml` xuất từ phần mềm kế toán / HTKK chuẩn Tổng cục Thuế bằng `defusedxml` (hoặc parser XML chặn XXE/entity expansion tuyệt đối, giới hạn kích thước file ≤ 5 MB).
     - Tự động nhận diện phiên bản biểu mẫu (`TT200` / `TT133` / `TT99`), MST, kỳ tài chính và trích xuất các mã chỉ tiêu (`100`, `110`, `130`, `140`, `270`, `300`, `310`, `320`, `338`, `400`, `421`, `01`, `10`, `11`, `20`, `23`, `30`, `50`, `60`, LCTT `20`, `21`...) về bản nháp (`draft`) để người dùng kiểm tra trước khi xác nhận.
   - **Biểu mẫu Excel chuẩn (`GET /api/v1/templates/bctc/{standard}` & `POST .../import-excel`):**
     - Xuất file `.xlsx` mẫu theo chuẩn `TT99_2025`, `TT200_2014`, `TT133_2016` có sẵn mã chỉ tiêu và công thức cộng tổng; đọc file upload (≤ 5 MB) bằng `openpyxl` (`data_only=True, read_only=True`).
5. **Trợ lý Kiểm tra Cân đối Kế toán & Sửa Bug Âm VCSH (M05):**
   - Module `src/finhealth/etl/accounting_validator.py` kiểm tra tức thì (trên cả Web Form, Excel, XML):
     - **Lỗi cứng (Error — cảnh báo đỏ tại dòng lệch):**
       - `|total_assets - (total_liabilities + stockholders_equity)| > max(1.0, 0.005 * total_assets)` (lệch cân đối Tài sản – Nguồn vốn > 0,5%).
       - `current_assets > total_assets` hoặc `current_liabilities > total_liabilities`.
       - `cash_and_equivalents > current_assets`, `inventory > current_assets`, `accounts_receivable > current_assets`.
       - `short_term_debt > current_liabilities` hoặc `long_term_debt > (total_liabilities - current_liabilities)` (khi có đủ số liệu).
     - **Cảnh báo nghiệp vụ (Warning — vàng, cho phép tiếp tục):**
       - Doanh nghiệp bị **âm vốn chủ sở hữu** (`stockholders_equity <= 0`) hoặc đệm vốn mỏng (`stockholders_equity / total_assets < 0.05`).
       - `gross_profit` lệch quá 1% so với `revenues - cost_of_goods_sold`.
       - Lợi nhuận sau thuế dương nhưng `operating_cash_flow` âm sâu.
   - **Sửa triệt để Bug Âm VCSH ở `src/finhealth/etl/financial_ratios.py` & `corporate_finance.py`:**
     - Bảo lưu chính sách trả `None` cho `roe` và `debt_to_equity` khi `equity / assets < 0.05` (không chia số âm/gần 0 gây nổ tỷ số).
     - **Bổ sung cờ tường minh:** `is_negative_equity: bool` (`stockholders_equity <= 0`) và `is_thin_equity: bool` (`0 < equity / assets < 0.05`) + tỷ số không bị nổ mẫu số `equity_to_assets = stockholders_equity / total_assets` (luôn hữu hạn ngay cả khi âm!).
     - Sửa dead code tại `corporate_finance.py:355`: khi `is_negative_equity == True`, điểm thành phần `debt_to_equity` và `roe` trong trụ cột Sức khỏe bắt buộc nhận **`0.0` điểm** thay vì bị bỏ qua khỏi trung bình trụ cột.

### Boundary Contract cung cấp cho các module phía sau
- `NormalizedStatementRecord` (TypedDict / Pydantic model chuẩn hóa dùng chung cho cả `OrgFinancialStatement`, `FinancialStatement` SEC và `kaggle_loader.py`): chứa đủ 25 trường khoản mục thô + `is_manufacturing`, `is_financial_institution`, `listing_status`, `audit_status`, `accounting_standard`, `currency`.
- `ValidationReport`: `{ is_balanced: bool, errors: list[FieldCheckIssue], warnings: list[FieldCheckIssue] }`.
- `compute_statement_ratios(stmt, is_manufacturing=...)` trả đủ bộ tỷ số mở rộng + `is_negative_equity`, `is_thin_equity`, `equity_to_assets`.

---

## 2. Tech Stack

- **Backend:** Python 3.10+, SQLAlchemy 2.0, Alembic, Pydantic v2, FastAPI.
- **Thư viện mới cần bổ sung vào `pyproject.toml`:**
  - `openpyxl>=3.1.2` (đọc/ghi biểu mẫu Excel `.xlsx` chuẩn TT99/TT200/TT133 và hỗ trợ Batch S03).
  - `defusedxml>=0.7.1` (parse file XML HTKK an toàn chống tấn công XXE/Billion Laughs).
  - `python-multipart>=0.0.9` (nhận `UploadFile` trong FastAPI cho Excel/XML).
- **Frontend:** React 19, `react-hook-form` + `zod` (đã có trong `frontend/package.json`).

---

## 3. Commands

```powershell
# Lint, typecheck & tests tập trung cho financial-data
.\.venv\Scripts\ruff.exe check src/finhealth/etl src/finhealth/db src/finhealth/api
.\.venv\Scripts\mypy.exe src/finhealth
.\.venv\Scripts\pytest.exe -v tests/unit/test_vn_accounting_and_validation.py tests/unit/test_etl_pipeline.py tests/integration/test_org_companies_and_statements.py

# Migration
.\.venv\Scripts\alembic.exe upgrade head
```

---

## 4. Project Structure

```text
migrations/versions/
  └── 0009_org_companies_and_extended_statements.py  # Bảng org_companies, org_financial_statements;
                                                     # bổ sung cột mở rộng vào financial_statements
src/finhealth/db/
  ├── models.py                                      # Thêm cột mở rộng cho FinancialStatement (nullable)
  └── org_models.py                                  # ORM OrgCompany, OrgFinancialStatement
src/finhealth/etl/
  ├── financial_ratios.py                            # Mở rộng tỷ số (Gross Margin, Quick Ratio, DSO, DIO,
  │                                                  # EBITDA Margin, ST Debt Share, Equity/Assets, cờ âm VCSH)
  ├── accounting_validator.py                        # Bộ kiểm tra cân đối kế toán & lỗi cấu trúc từng dòng
  ├── vn_accounting_mapper.py                        # Ánh xạ mã chỉ tiêu TT99/2025, TT200/2014, TT133/2016
  ├── htkk_xml_parser.py                             # Parser file XML HTKK an toàn (defusedxml)
  ├── excel_templates.py                             # Tạo template .xlsx & parse upload .xlsx (openpyxl)
  └── vn_samples.py                                  # 3 bộ hồ sơ DN mẫu VN đa kỳ 100% cân đối
src/finhealth/api/
  ├── schemas/org_financials.py                      # Pydantic StrictInput cho OrgCompany, Statement, ValidationReport
  └── routers/org_companies.py                       # CRUD công ty, BCTC draft/finalized, upload Excel/XML, seed mẫu
tests/
  ├── unit/test_vn_accounting_and_validation.py      # Kiểm thử XML HTKK, Excel, mapper TT99/TT200/TT133,
  │                                                  # cân đối kế toán, bug âm VCSH
  └── integration/test_org_companies_and_statements.py  # CRUD cô lập org_id, RBAC viewer/analyst/admin, draft→finalized
```

---

## 5. Code Style

```python
from finhealth.etl.financial_ratios import _finite, _safe_div


def compute_equity_guards(
    total_assets: float | None, stockholders_equity: float | None
) -> dict[str, float | bool | None]:
    """Expose explicit insolvency flags instead of letting missing ratios hide negative equity."""
    assets = _finite(total_assets)
    equity = _finite(stockholders_equity)
    equity_to_assets = _safe_div(equity, assets, require_positive_den=True)
    return {
        "equity_to_assets": equity_to_assets,
        "is_negative_equity": bool(equity is not None and equity <= 0.0),
        "is_thin_equity": bool(
            equity_to_assets is not None and 0.0 < equity_to_assets < 0.05
        ),
    }
```

---

## 6. Testing Strategy

- **Unit tests (`tests/unit/test_vn_accounting_and_validation.py`):**
  - Test kiểm tra cân đối kế toán phát hiện đúng dòng lệch (`Assets != Liabilities + Equity`, `CA > TA`, `Cash > CA`, `Inventory > CA`).
  - Test doanh nghiệp âm VCSH (`equity = -50`, `assets = 1000`): xác nhận `is_negative_equity == True`, `equity_to_assets == -0.05`, `roe is None`, `debt_to_equity is None`, và điểm trụ cột Solvency không bị thổi phồng.
  - Test round-trip tạo file Excel mẫu → điền số liệu → parse lại khớp 100% cho cả 3 chế độ `TT99_2025`, `TT200_2014`, `TT133_2016`.
  - Test parse file XML HTKK mẫu (TT200, TT133, TT99) + test **từ chối payload XXE độc hại** và file > 5 MB.
  - Test 3 DN mẫu VN trong `vn_samples.py` đều vượt qua `accounting_validator` với 0 lỗi cân đối.
- **Integration tests (`tests/integration/test_org_companies_and_statements.py`):**
  - CRUD `OrgCompany` + `OrgFinancialStatement` có cô lập `organization_id` và kiểm tra RBAC (`viewer` bị 403 khi POST/PATCH/DELETE).
  - Test chặn chấm điểm ML/Altman với `business_type == "financial_institution"`.
  - Test chuyển trạng thái `draft → finalized`, đơn vị tiền tệ (Đồng / Triệu / Tỷ) và lưu lịch sử đa kỳ (FY2022–FY2026).

---

## 7. Boundaries

- **Always:**
  - Dùng `defusedxml` (không dùng `xml.etree.ElementTree` trực tiếp trên file người dùng tải lên) và kiểm tra giới hạn kích thước tệp (≤ 5 MB) trước khi đọc toàn bộ vào RAM.
  - Bảo toàn giá trị thiếu là `None` (không bao giờ tự động ép về `0`).
  - Giữ tương thích ngược 100% với bảng `companies` & `financial_statements` của SEC EDGAR (mọi cột mới đều `nullable=True`).
- **Ask first:**
  - Thay đổi quy tắc ngưỡng dung sai cân đối kế toán (mặc định 0,5% tổng tài sản).
- **Never:**
  - Không bao giờ trộn dữ liệu `org_financial_statements` của khách hàng vào bảng SEC công khai hoặc tập huấn luyện ML.
  - Không bao giờ chấp nhận mẫu số bằng 0 hoặc âm ở `_safe_div` hay trả `inf`/`NaN`.

---

## 8. Success Criteria

1. Người dùng (vai trò `analyst`/`org_admin`) tạo được doanh nghiệp trong Workspace (MST, ngành VSIC, niêm yết/chưa niêm yết, thẻ quan hệ), lưu nháp BCTC 3 biểu mẫu, và nạp thành công cả file **Excel chuẩn** lẫn **XML HTKK** cho **TT99/2025**, **TT200/2014**, **TT133/2016**.
2. Bộ kiểm tra cân đối kế toán chỉ đích danh khoản mục sai lệch khi nhập lỗi; doanh nghiệp âm VCSH trả đúng cờ `is_negative_equity=True` và không bị thổi phồng điểm trụ cột hay điền trung vị giả.
3. Nạp 3 hồ sơ DN mẫu Việt Nam thành công trong 1 click (`POST /api/v1/org/samples/seed`), idempotent, 0 lỗi cân đối kế toán.
4. Dữ liệu SEC EDGAR hiện tại (tab "Thị trường Mỹ (SEC)") tiếp tục hoạt động nguyên vẹn, không vỡ bất kỳ test hồi quy nào.

---

## 9. Out of Scope (Deferred)

- Trích xuất tự động từ file PDF kiểm toán OCR/IDP (W03 — V2.0+).
- Tích hợp API tra cứu tự động trạng thái MST Tổng cục Thuế / cổng dữ liệu thương mại có phí (V1.1/V2.0).
- Đồng bộ tự động BCTC doanh nghiệp niêm yết Việt Nam (HOSE/HNX/UPCoM) từ nhà cung cấp dữ liệu thị trường (V1.1).
