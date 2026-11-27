# Task Checklist: FinHealth Production — V1.0

> Theo dõi tiến độ triển khai theo [tasks/plan.md](plan.md) và 6 đặc tả trong [spec/capability-map.md](../spec/capability-map.md).  
> Quy ước kích thước: **XS** (1 file) · **S** (1–2 files) · **M** (3–5 files). Không có task nào vượt quá ~5 files chính.

---

## WAVE 0 — Foundation, Migrations & Shared Contracts (Sequential — Lead Agent)

### Task T01: Dọn dẹp baseline, cập nhật dependencies và gỡ bỏ `web/` cũ
- **Status:** `[x]`
- **Lane:** `Wave 0 / lead-architect`
- **Description:** Cập nhật `pyproject.toml` bổ sung các gói cần thiết cho V1.0 (`openpyxl>=3.1.2`, `defusedxml>=0.7.1`, `python-multipart>=0.0.9`, `reportlab>=4.2.0`), dọn 2 lỗi nền có sẵn (`F401` import thừa `json` ở `tests/integration/test_v12_compare_and_ui.py:3` và so sánh float ULP bằng `pytest.approx` ở `tests/integration/test_forensic_audit.py:709`), đồng thời xóa bỏ thư mục `web/` lỗi thời.
- **Acceptance criteria:**
  - [x] `pip install -e ".[dev]"` cài đủ `openpyxl`, `defusedxml`, `python-multipart`, `reportlab` không xung đột.
  - [x] Thư mục `web/` đã được xóa hoàn toàn; không còn tham chiếu hỏng tới `web/`.
  - [x] `ruff check .` trả 0 lỗi và `test_training_latency_and_saved_scores` xanh với dung sai `1e-12`.
- **Verification:**
  - [x] `.\.venv\Scripts\ruff.exe check .`
  - [x] `.\.venv\Scripts\pytest.exe -v tests/integration/test_forensic_audit.py -k test_training_latency_and_saved_scores`
- **Dependencies:** None
- **Files likely touched:**
  - `pyproject.toml`
  - `tests/integration/test_v12_compare_and_ui.py`
  - `tests/integration/test_forensic_audit.py`
  - `web/` *(delete)*
- **Estimated scope:** Medium (3–4 targets)

### Task T02: Khóa chuỗi Migration `0008–0011`, ORM models và Boundary Contracts dùng chung
- **Status:** `[x]`
- **Lane:** `Wave 0 / lead-architect`
- **Description:** Tạo trọn bộ schema DB V1.0 qua 4 migration nối tiếp tương thích SQLite/PostgreSQL/SQL Server (`0008_organizations_rbac_and_privacy.py`, `0009_org_companies_and_extended_statements.py`, `0010_org_assessments_history.py`, `0011_org_batch_jobs.py`), định nghĩa đầy đủ ORM models (`account_models.py`, `org_models.py`, `batch_models.py`, `models.py`) và khóa 2 hợp đồng biên (`OrgContext`/`require_org_role` trong `security.py` và `CORE_BANKRUPTCY_FEATURES` trong `ml/feature_contracts.py`).
- **Acceptance criteria:**
  - [x] `alembic upgrade head` tạo đủ bảng `organizations`, `organization_members`, `organization_invites`, `organization_audit_logs`, `org_companies`, `org_financial_statements`, `org_assessments`, `org_batch_jobs`, `org_batch_job_rows`; chuyển `admin_audit_logs.actor_id` sang `nullable=True` (`ON DELETE SET NULL`); backfill default org cho user hiện có.
  - [x] `test_migration_upgrade_matches_metadata_and_downgrade`, `test_postgresql_offline_migration_sql`, và `test_sqlserver_offline_migration_uses_one_cascade_path` đều xanh 100%.
  - [x] `OrgContext`, `require_org_role` và `CORE_BANKRUPTCY_FEATURES` có type annotation đầy đủ, `mypy` xanh 100%.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/integration/test_db_migrations.py`
  - [x] `.\.venv\Scripts\mypy.exe src/finhealth/db src/finhealth/api/security.py src/finhealth/ml/feature_contracts.py`
- **Dependencies:** T01
- **Files likely touched:**
  - `migrations/versions/0008_organizations_rbac_and_privacy.py`
  - `migrations/versions/0009_org_companies_and_extended_statements.py`
  - `migrations/versions/0010_org_assessments_history.py`
  - `migrations/versions/0011_org_batch_jobs.py`
  - `src/finhealth/db/{account_models,org_models,batch_models,models}.py`
  - `src/finhealth/api/security.py`
  - `src/finhealth/ml/feature_contracts.py`
- **Estimated scope:** Medium-Large (split commit if needed: migrations + models, then contracts)

### Checkpoint W0: Sau T01–T02 (Cổng mở Wave 1 Song Song)
- [x] `.\.venv\Scripts\ruff.exe check .` → 0 lỗi
- [x] `.\.venv\Scripts\mypy.exe src/finhealth` → 0 lỗi
- [x] `.\.venv\Scripts\pytest.exe -v` → 0 failed
- [x] Sẵn sàng tách 4 nhánh/worktree độc lập cho Lane A, B, C, D

---

## WAVE 1 — 4 Backend Lanes Song Song (Parallel Coding Agents)

### [Lane A — `identity-privacy`] Task T03: Organization Workspace & RBAC API
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane A (agent-identity)`
- **Description:** Triển khai `src/finhealth/api/routers/organizations.py` (tạo tổ chức, giới hạn 5 org/user & 50 thành viên/org, chuyển `active_org_id` lưu server-side trong `UserSession`, mời thành viên bằng mã 1 lần băm SHA-256 72h, chấp nhận lời mời kiểm khớp email, đổi vai trò `org_admin`/`analyst`/`viewer`, chặn gỡ `org_admin` cuối cùng, xem `organization_audit_logs`) và cập nhật `workspace.py` cô lập `/me/*` theo `OrgContext.organization.id` + kiểm tra RBAC.
- **Acceptance criteria:**
  - [x] `viewer` xem được dữ liệu tổ chức nhưng bị `403` trên mọi thao tác ghi; thành viên tổ chức khác nhận `403`/`404` (chống IDOR).
  - [x] Không thể hạ cấp hoặc xóa `org_admin` cuối cùng của tổ chức (`409`).
  - [x] Lời mời không thể bị tài khoản khác email chấp nhận (`403`) và hết hạn sau 72h.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_org_rbac_invariants.py tests/integration/test_organizations_and_privacy.py -k "org or rbac or invite"`
- **Dependencies:** T02
- **Files likely touched:**
  - `src/finhealth/api/schemas/accounts.py`
  - `src/finhealth/api/routers/organizations.py`
  - `src/finhealth/api/routers/workspace.py`
  - `tests/unit/test_org_rbac_invariants.py`
- **Estimated scope:** Medium (4 files)

### [Lane A — `identity-privacy`] Task T04: Data Privacy Luật 91/2025/QH15 & Auto-Personal Org
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane A (agent-identity)`
- **Description:** Cập nhật `src/finhealth/api/routers/accounts.py`: giữ nguyên invariant `VerifyOtpInput.new_password` khi xác thực email, tự động khởi tạo Workspace mặc định (`is_personal=True`, vai trò `org_admin`) khi verify email xong; bổ sung `job_title` vào profile; triển khai `GET /api/v1/auth/me/export` (xuất dữ liệu cá nhân JSON) và `POST /api/v1/auth/delete-account` (yêu cầu mật khẩu + OTP, chặn `409` nếu là `org_admin` duy nhất của org còn thành viên khác, ngược lại thu hồi phiên và xóa cứng toàn bộ PII/workspace riêng).
- **Acceptance criteria:**
  - [x] Verify email mới tự động tạo đúng 1 Workspace cá nhân; `test_verification_cannot_preserve_attacker_selected_password` tiếp tục xanh.
  - [x] `GET /api/v1/auth/me/export` chỉ chứa dữ liệu của user đăng nhập, không rò rỉ dữ liệu user khác.
  - [x] `POST /api/v1/auth/delete-account` thu hồi session ngay lập tức (cookie cũ trả `401`) và xóa sạch bản ghi `users` + dữ liệu riêng (giữ `admin_audit_logs` với `actor_id=NULL`).
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/integration/test_accounts_and_admin.py tests/integration/test_organizations_and_privacy.py`
- **Dependencies:** T03
- **Files likely touched:**
  - `src/finhealth/api/routers/accounts.py`
  - `src/finhealth/api/schemas/accounts.py`
  - `tests/integration/test_organizations_and_privacy.py`
- **Estimated scope:** Medium (3 files)

---

### [Lane B — `financial-data`] Task T05: Tỷ số Mở rộng, Sửa Bug Âm VCSH, Validator Cân đối & VAS Mapper
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane B (agent-financial-data)`
- **Description:** Mở rộng `financial_ratios.py` tính thêm Gross Margin, Quick Ratio, DSO, DIO, EBITDA Margin, Short-Term Debt Share, `equity_to_assets`, `is_negative_equity`, `is_thin_equity` (không phá vỡ các test hiện hữu); tạo `accounting_validator.py` (kiểm tra cân đối `TA = TL + E` dung sai 0,5%, `CA <= TA`, `Cash/Inv/AR <= CA`, cảnh báo âm VCSH) và `vn_accounting_mapper.py` ánh xạ mã chỉ tiêu chuẩn **TT99/2025**, **TT200/2014**, **TT133/2016**.
- **Acceptance criteria:**
  - [x] Doanh nghiệp âm VCSH trả `is_negative_equity=True`, `equity_to_assets < 0`, `roe=None`, `debt_to_equity=None` (không `inf`/`NaN`).
  - [x] `accounting_validator` chỉ đích danh tên trường & mức lệch cho mọi lỗi cấu trúc bảng cân đối.
  - [x] `vn_accounting_mapper` ánh xạ đúng các mã chỉ tiêu trọng yếu cho cả 3 chế độ TT99/TT200/TT133 về cùng tập trường chuẩn hóa.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_etl_pipeline.py tests/unit/test_vn_accounting_and_validation.py -k "ratio or validator or mapper"`
- **Dependencies:** T02
- **Files likely touched:**
  - `src/finhealth/etl/financial_ratios.py`
  - `src/finhealth/etl/accounting_validator.py`
  - `src/finhealth/etl/vn_accounting_mapper.py`
  - `tests/unit/test_vn_accounting_and_validation.py`
- **Estimated scope:** Medium (4 files)

### [Lane B — `financial-data`] Task T06: HTKK XML Parser, Biểu mẫu Excel TT99/TT200/TT133 & 3 Hồ sơ Mẫu VN
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane B (agent-financial-data)`
- **Description:** Tạo `htkk_xml_parser.py` dùng `defusedxml` (giới hạn ≤ 5 MB, chặn XXE, tự nhận diện TT99/TT200/TT133, trích MST/kỳ/chỉ tiêu), `excel_templates.py` (`openpyxl` sinh template `.xlsx` có mã chỉ tiêu & parse upload `.xlsx` ở chế độ `read_only=True, data_only=True`), và `vn_samples.py` chứa 3 hồ sơ DN mẫu VN đa kỳ (4–5 năm, cân đối kế toán 100%: Minh An Vững mạnh, Hoàng Long Suy giảm ngầm, Đại Phát Nguy cơ cao).
- **Acceptance criteria:**
  - [x] Parser XML HTKK chặn thành công payload XXE và file > 5 MB; parse đúng các file XML mẫu TT200/TT133/TT99.
  - [x] Round-trip xuất file Excel mẫu → điền số liệu → nạp lại khớp 100% ở cả 3 chế độ kế toán.
  - [x] Cả 3 hồ sơ mẫu VN vượt qua `accounting_validator` với 0 lỗi cứng.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_vn_accounting_and_validation.py`
- **Dependencies:** T05
- **Files likely touched:**
  - `src/finhealth/etl/htkk_xml_parser.py`
  - `src/finhealth/etl/excel_templates.py`
  - `src/finhealth/etl/vn_samples.py`
  - `tests/unit/test_vn_accounting_and_validation.py`
- **Estimated scope:** Medium (4 files)

### [Lane B — `financial-data`] Task T07: API Danh bạ DN Tổ chức, BCTC Draft/Finalized & Import XML/Excel
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane B (agent-financial-data)`
- **Description:** Xây dựng `schemas/org_financials.py` và `routers/org_companies.py` cung cấp CRUD `OrgCompany` (MST, VSIC, `business_type`, `listing_status`, `relationship_tag`, cờ chặn `financial_institution`), quản lý `OrgFinancialStatement` (lưu `draft` / chốt `finalized`, chọn đơn vị Đồng/Triệu/Tỷ, chạy `accounting_validator` trả kèm lỗi từng dòng), tải template `.xlsx`, nạp file XML HTKK / Excel, và `POST /api/v1/org/samples/seed` (idempotent).
- **Acceptance criteria:**
  - [x] Toàn bộ endpoint cô lập tuyệt đối theo `OrgContext.organization.id` và kiểm tra RBAC (`viewer` chỉ đọc, `analyst` tạo/sửa/import, `org_admin` xóa cứng).
  - [x] Không cho phép chốt `finalized` khi còn lỗi cứng cân đối kế toán (trừ khi lưu `draft`).
  - [x] `POST /api/v1/org/samples/seed` chạy 2 lần không tạo bản sao trùng lặp.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/integration/test_org_companies_and_statements.py`
- **Dependencies:** T06
- **Files likely touched:**
  - `src/finhealth/api/schemas/org_financials.py`
  - `src/finhealth/api/routers/org_companies.py`
  - `tests/integration/test_org_companies_and_statements.py`
- **Estimated scope:** Medium (3 files)

---

### [Lane C — `ml-bankruptcy-engine`] Task T08: Sửa Rò rỉ Nhãn `kaggle_loader.py` & 19 Đặc trưng Không thứ nguyên
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane C (agent-ml-engine)`
- **Description:** Sửa `src/finhealth/ml/kaggle_loader.py` gắn `next_is_bankrupt = 1` **chỉ tại dòng `year == max_year`** của mỗi công ty `failed` (mọi năm trước đó mang nhãn `0`), khai thác đủ `X1–X18` (bỏ `X8` vốn hóa và `eps`) để tính toàn bộ 19 đặc trưng không thứ nguyên (`CORE_BANKRUPTCY_FEATURES`) và 5 biến thiên YoY (`MULTI_PERIOD_FEATURES`), kèm cờ `is_negative_equity` & `equity_to_assets`.
- **Acceptance criteria:**
  - [x] Trên `american_bankruptcy.csv`: có đúng 609 dòng `next_is_bankrupt == 1`; Train ≤ 2014 (490), Val 2015–2016 (62), Test 2017–2018 (57); **0% trùng lặp công ty nhãn `1`** giữa Train/Val và Test.
  - [x] Không có biến phụ thuộc đơn vị tiền tệ (`eps`, `X8`, tài sản thô) trong tập đặc trưng huấn luyện.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_ml_bankruptcy_v2.py -k "leakage or loader"`
- **Dependencies:** T02
- **Files likely touched:**
  - `src/finhealth/ml/kaggle_loader.py`
  - `tests/unit/test_ml_bankruptcy_v2.py`
- **Estimated scope:** Small (2 files)

### [Lane C — `ml-bankruptcy-engine`] Task T09: Hiệu chuẩn 4 Mô hình, Độ tin cậy 4 Lớp, PD↔0–100 & Đa Worker Registry
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane C (agent-ml-engine)`
- **Description:** Nâng cấp `distress_classifier.py`, tạo `confidence.py` và cập nhật `registry.py` + `explainer.py`: Platt-calibrate đồng đều cả 4 mô hình (LR, RF, XGB, LGBM) trên Validation; hỗ trợ lưu & suy luận cả 2 pipeline (`single_period` & `multi_period`); triển khai `classify_bankruptcy_tier` (`1%/3%/8%`), `map_pd_to_health_score` (đơn điệu 0–100), Độ tin cậy 4 lớp (Đầy đủ + OOD + Phương sai ensemble + Kiểm toán), `CashFlowOverlay`, và reload `ModelRegistryState` an toàn theo `latest.json` mtime/sha256.
- **Acceptance criteria:**
  - [x] Cả 4 mô hình đều có Platt calibrator và mean predicted probability trên Validation gần base rate thực.
  - [x] Hàm `map_pd_to_health_score` giảm đơn điệu tuyệt đối trên `[0, 1]` và khớp 1-1 với 4 vùng `STRONG/STABLE/WATCH/CRITICAL`.
  - [x] Bất biến đơn vị tiền tệ: nhân toàn bộ khoản mục BCTC với `25_000` cho ra `pd_12m` và `health_score` khớp sai số `< 1e-9`.
  - [x] Sai số tái dựng TreeSHAP `< 1e-5` và `output_space` phản ánh đúng mô hình đang giải thích.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_ml_bankruptcy_v2.py tests/unit/test_ml_pipeline.py`
- **Dependencies:** T08
- **Files likely touched:**
  - `src/finhealth/ml/distress_classifier.py`
  - `src/finhealth/ml/confidence.py`
  - `src/finhealth/ml/registry.py`
  - `src/finhealth/ml/explainer.py`
  - `tests/unit/test_ml_bankruptcy_v2.py`
- **Estimated scope:** Medium (5 files)

### [Lane C — `ml-bankruptcy-engine`] Task T10: Huấn luyện & Xuất bản Artifact `v2.0.0-kaggle` Sạch Leakage
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane C (agent-ml-engine)`
- **Description:** Cập nhật `train_cli.py` hỗ trợ huấn luyện & kiểm định hoàn chỉnh gói `v2.0.0-kaggle` (cả chế độ `single_period` và `multi_period`), sinh đầy đủ `evaluation_report.json`, `BENCHMARK_REPORT.md` và biểu đồ kiểm định out-of-time (ROC/PR/Calibration/SHAP), kiểm chứng thực tế trên tập dữ liệu `data/raw/kaggle/american_bankruptcy.csv`.
- **Acceptance criteria:**
  - [x] Chạy CLI `python -m finhealth.ml.train_cli --dataset kaggle --model-version v2.0.0-kaggle` thành công với `RANDOM_SEED = 42`.
  - [x] `data/artifacts/models/v2.0.0-kaggle/evaluation_report.json` ghi rõ provenance thực (không còn chuỗi stale `"synthetic stochastic outcomes"`), `non_forward_supervised_rows = 0`, 0% entity leakage và Brier score hiệu chuẩn của cả 4 mô hình.
- **Verification:**
  - [x] `.\.venv\Scripts\python.exe -m finhealth.ml.train_cli --dataset kaggle --model-version v2.0.0-kaggle`
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_ml_bankruptcy_v2.py tests/unit/test_visualization_and_cli.py`
- **Dependencies:** T09
- **Files likely touched:**
  - `src/finhealth/ml/train_cli.py`
  - `data/artifacts/models/v2.0.0-kaggle/*`
  - `tests/unit/test_ml_bankruptcy_v2.py`
- **Estimated scope:** Small-Medium (2 code files + generated artifact bundle)

---

### [Lane D — `risk-analytics`] Task T11: Altman $Z/Z'/Z''$ + Chặn TCTC, 5 Trụ cột & Từ điển 20 Chỉ số
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane D (agent-risk-analytics)`
- **Description:** Tạo `src/finhealth/etl/altman.py` triển khai đầy đủ 3 biến thể $Z$ (`1.81/2.99`, yêu cầu vốn hóa), $Z'$ (`1.23/2.90`, vốn sổ sách SX), $Z''$ (`1.10/2.60`, phi SX) và chặn TCTC (`applicable=False`); tạo `metric_catalog.py` (từ điển 20 chỉ số tiếng Việt kèm tooltip, ngưỡng tham chiếu và hàm gán trạng thái); nâng cấp `corporate_finance.py` lên 5 trụ cột (20 chỉ số, phạt `0.0` khi `is_negative_equity=True`, loại `AAA..CCC` ở hàm v2).
- **Acceptance criteria:**
  - [x] Cả 3 công thức Altman trả đúng điểm, vùng và cặp `(cutoff_low, cutoff_high)`; DN tài chính trả `applicable=False`.
  - [x] 5 trụ cột bao phủ đủ 20 chỉ số; khi `is_negative_equity=True`, điểm `debt_to_equity` và `roe` bị gán `0.0` (không bị bỏ qua).
  - [x] Mọi chỉ số trong `metric_catalog.py` có `label_vi`, `tooltip_vi`, `reference_range_vi`.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_risk_analytics_v2.py tests/unit/test_v12_business_logic.py`
- **Dependencies:** T02
- **Files likely touched:**
  - `src/finhealth/etl/altman.py`
  - `src/finhealth/etl/metric_catalog.py`
  - `src/finhealth/etl/corporate_finance.py`
  - `tests/unit/test_risk_analytics_v2.py`
- **Estimated scope:** Medium (4 files)

### [Lane D — `risk-analytics`] Task T12: Điểm Tựa/Điểm Nghẽn, Lịch sử Đa kỳ M11, Chuẩn ngành S01 & So sánh C03
- **Status:** `[x]`
- **Lane:** `Wave 1 / Lane D (agent-risk-analytics)`
- **Description:** Tạo `driver_narrative.py` chuyển TreeSHAP thành tối đa 5 Điểm Tựa (xanh) + 5 Điểm Nghẽn (đỏ) với `impact_share_pct` (tổng 100%, tuyệt đối không trừ điểm sức khỏe sai toán SHAP); xây dựng `schemas/analytics.py`, `services_org.py` và `routers/org_analytics.py` cung cấp `CompanyAssessmentView` đầy đủ (3 nhận định trọng tâm, 5 trụ cột, lịch sử 3–5 năm có `health_score` & `pd_12m`, vị thế ngành S01 đối chiếu SEC cohort, so sánh 2–4 DN tổ chức C03, miễn trừ NĐ 88/2014/NĐ-CP).
- **Acceptance criteria:**
  - [x] Output `drivers` không chứa thuật ngữ lập trình/ML; tổng `impact_share_pct` xấp xỉ 100%.
  - [x] `GET /api/v1/org/companies/{id}/analysis` trả chuỗi lịch sử 3–5 năm liền mạch qua mốc TT200 → TT99 có cả `health_score` và `pd_12m`.
  - [x] `GET /api/v1/org/companies/compare` hỗ trợ 2–4 DN cùng tổ chức, trả 422 nếu >4 và 404 nếu lẫn ID tổ chức khác.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_risk_analytics_v2.py tests/integration/test_org_analysis_and_compare.py`
- **Dependencies:** T11 *(cần đọc contract từ T05/T09; mock nhẹ nếu chạy trước khi merge Wave 1, chạy lại đầy đủ tại Checkpoint W1)*
- **Files likely touched:**
  - `src/finhealth/etl/driver_narrative.py`
  - `src/finhealth/api/schemas/analytics.py`
  - `src/finhealth/api/services_org.py`
  - `src/finhealth/api/routers/org_analytics.py`
  - `tests/integration/test_org_analysis_and_compare.py`
- **Estimated scope:** Medium (5 files)

### Checkpoint W1: Sau Merge 4 Nhánh Wave 1 (T03–T12)
- [x] Merge lần lượt Lane A → Lane B → Lane C → Lane D vào nhánh tích hợp (đối chiếu 0 xung đột file).
- [x] `.\.venv\Scripts\ruff.exe check .` → 0 lỗi
- [x] `.\.venv\Scripts\mypy.exe src/finhealth` → 0 lỗi
- [x] `.\.venv\Scripts\pytest.exe -v` → 100% pass (bao gồm toàn bộ test mới của 4 module)

---

## WAVE 2 — Reporting & 2 Frontend Lanes Song Song (Parallel Coding Agents)

### [Lane E — `batch-and-reporting`] Task T13: Bộ Xuất Báo cáo Thẩm định PDF Chuẩn A4 Tiếng Việt (M12)
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane E (agent-reporting)`
- **Description:** Nhúng font `BeVietnamPro-Regular.ttf` & `BeVietnamPro-Bold.ttf` (SIL OFL) vào `src/finhealth/reporting/fonts/`; xây dựng `src/finhealth/reporting/pdf_generator.py` bằng `reportlab` + `matplotlib` (`Agg`) xuất PDF 3–4 trang A4 từ `CompanyAssessmentView` (Executive Summary, Radar 5 trụ cột, 2 cột Điểm Tựa/Điểm Nghẽn, Bảng 20 chỉ số & biểu đồ đa kỳ, chân trang đóng băng `model_version` + miễn trừ NĐ 88/2014).
- **Acceptance criteria:**
  - [x] Sinh bytes bắt đầu bằng `%PDF-`, hiển thị đúng dấu tiếng Việt UTF-8 trên cả Windows và Linux không cần GTK.
  - [x] Xử lý an toàn khi thiếu dữ liệu lịch sử, âm VCSH hoặc DN thuộc nhóm loại trừ TCTC; đóng mọi `matplotlib` figure tránh rò RAM.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_pdf_and_batch_excel.py -k pdf`
- **Dependencies:** Checkpoint W1
- **Files likely touched:**
  - `src/finhealth/reporting/__init__.py`
  - `src/finhealth/reporting/fonts/BeVietnamPro-{Regular,Bold}.ttf`
  - `src/finhealth/reporting/pdf_generator.py`
  - `tests/unit/test_pdf_and_batch_excel.py`
- **Estimated scope:** Medium (4 files)

### [Lane E — `batch-and-reporting`] Task T14: Thẩm định Hàng loạt qua Excel Bất đồng bộ & API Xuất PDF/Batch (S03, M12)
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane E (agent-reporting)`
- **Description:** Tạo `batch_excel.py` (xuất template `.xlsx`, parse tối đa 500 dòng ≤ 10 MB ở chế độ `read_only`, xuất bảng kết quả `.xlsx` xếp hạng rủi ro giảm dần), `batch_worker.py` (chạy nền trên DB queue `org_batch_jobs`, cô lập lỗi từng dòng), `schemas/batch_reporting.py` và `routers/reporting_v2.py` (endpoints tải template, tạo batch job `202`, xem tiến độ/kết quả, xuất Excel tổng hợp, và tải `report.pdf` cho cả DN tổ chức & DN SEC).
- **Acceptance criteria:**
  - [x] Upload Excel 10 DN có 2 dòng lỗi vẫn hoàn tất 8 dòng hợp lệ, sắp xếp `pd_12m` giảm dần và ghi rõ nguyên nhân 2 dòng lỗi.
  - [x] `viewer` xem & tải PDF/Excel được nhưng bị `403` khi upload batch mới; tổ chức khác gọi `job_id` hoặc `company_id` nhận `404`.
  - [x] Endpoint `report.pdf` trả `Content-Type: application/pdf` có áp dụng rate limit.
- **Verification:**
  - [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_pdf_and_batch_excel.py tests/integration/test_batch_jobs_and_pdf_api.py`
- **Dependencies:** T13
- **Files likely touched:**
  - `src/finhealth/reporting/batch_excel.py`
  - `src/finhealth/reporting/batch_worker.py`
  - `src/finhealth/api/schemas/batch_reporting.py`
  - `src/finhealth/api/routers/reporting_v2.py`
  - `tests/integration/test_batch_jobs_and_pdf_api.py`
- **Estimated scope:** Medium (5 files)

---

### [Lane F — `frontend-core`] Task T15: Frontend API Client, Types, Formatters & Org AuthContext *(Ưu tiên Merge sớm)*
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane F (agent-fe-core)`
- **Description:** Cập nhật `frontend/src/types/api.ts`, `frontend/src/lib/api.ts` (sửa bug `verifyEmail` gửi đủ `new_password`, sửa bug `compareCompanies` gửi `common_fiscal_year`, thêm đầy đủ API cho Organizations/RBAC, Account change-password/change-email/export/delete, Org Companies, Statements, XML/Excel import, Batch Jobs, PDF download), cập nhật `format.ts` (VND/Triệu/Tỷ + 4 cấp độ `RISK_TIER_META`), và mở rộng `AuthContext.tsx` quản lý `activeOrg` + tự động invalidate React Query cache khi đổi Workspace.
- **Acceptance criteria:**
  - [x] `verifyEmail` gửi đủ `{ email, challenge, code, new_password }` khớp backend `VerifyOtpInput`.
  - [x] `compareCompanies` gửi đúng `common_fiscal_year` (khi chọn cùng năm) thay vì `period_policy`.
  - [x] Đổi Workspace trong `AuthContext` lập tức xóa/làm mới cache truy vấn của tổ chức cũ.
- **Verification:**
  - [x] `npm --prefix frontend run typecheck`
  - [x] `npm --prefix frontend test`
- **Dependencies:** Checkpoint W1
- **Files likely touched:**
  - `frontend/src/types/api.ts`
  - `frontend/src/lib/api.ts`
  - `frontend/src/lib/format.ts`
  - `frontend/src/context/AuthContext.tsx`
- **Estimated scope:** Medium (4 files)

### [Lane F — `frontend-core`] Task T16: AccountPage, OrganizationPage & Điều hướng Song Song (`AppShell`)
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane F (agent-fe-core)`
- **Description:** Hoàn thiện `AccountPage.tsx` (sửa bước Verify OTP kèm mật khẩu xác nhận, sửa controlled input `displayName`, bổ sung Đổi mật khẩu OTP, Đổi email OTP, Xuất dữ liệu cá nhân & Xóa tài khoản OTP); xây dựng `OrganizationPage.tsx` (tạo tổ chức, mời thành viên, quản lý vai trò RBAC, nhật ký kiểm toán); tái cấu trúc `AppShell.tsx` với Org Switcher, 2 không gian song song (**Danh bạ Doanh nghiệp** & **Thị trường Mỹ SEC**), **Thẩm định Hàng loạt**, **So sánh**, **Phương pháp luận**, và ẩn menu kỹ thuật ML khỏi người dùng thường.
- **Acceptance criteria:**
  - [x] Người dùng thường không thấy mục `ModelLab` hay `ClusterMap` trên thanh điều hướng.
  - [x] `viewer` không thấy nút mời/xóa thành viên trên `OrganizationPage`.
  - [x] Đủ test component cho `AppShell` và `AccountPage`.
- **Verification:**
  - [x] `npm --prefix frontend run typecheck`
  - [x] `npm --prefix frontend test`
- **Dependencies:** T15
- **Files likely touched:**
  - `frontend/src/pages/AccountPage.tsx`
  - `frontend/src/pages/OrganizationPage.tsx`
  - `frontend/src/components/layout/AppShell.tsx`
  - `frontend/src/components/layout/AppShell.test.tsx`
- **Estimated scope:** Medium (4 files)

### [Lane F — `frontend-core`] Task T17: Danh bạ Doanh nghiệp & Luồng Nhập BCTC (Web 3 Phần, Lưu Nháp, XML HTKK, Excel)
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane F (agent-fe-core)`
- **Description:** Xây dựng `PortfolioPage.tsx` (M03: CRUD danh bạ DN tổ chức, tìm theo Tên/MST/Mã CK, lọc thẻ quan hệ/loại hình/mức sức khỏe, cảnh báo chặn TCTC) và 3 component nhập liệu trong `frontend/src/components/statements/`: `StatementEditorForm.tsx` (M04: 3 tab BS/IS/CF theo mã TT99/TT200/TT133, chọn đơn vị Đồng/Triệu/Tỷ, tự cộng tổng dòng cha, Lưu nháp), `BalanceCheckAssistant.tsx` (M05: tô rõ dòng lệch cân đối kế toán), và `ImportStatementModal.tsx` (tải template Excel + upload XML HTKK / Excel).
- **Acceptance criteria:**
  - [x] Tự động cộng tổng các chỉ tiêu cha và hiển thị cảnh báo đúng dòng lệch khi Tổng TS ≠ Tổng NV.
  - [x] Chuyển đổi mượt giữa Đồng / Triệu đồng / Tỷ đồng và lưu nháp không mất dữ liệu.
  - [x] `viewer` chỉ xem được danh bạ, không thấy nút thêm/sửa/import.
- **Verification:**
  - [x] `npm --prefix frontend run typecheck`
  - [x] `npm --prefix frontend test`
- **Dependencies:** T15
- **Files likely touched:**
  - `frontend/src/pages/PortfolioPage.tsx`
  - `frontend/src/components/statements/StatementEditorForm.tsx`
  - `frontend/src/components/statements/BalanceCheckAssistant.tsx`
  - `frontend/src/components/statements/ImportStatementModal.tsx`
  - `frontend/src/components/statements/StatementEditorForm.test.tsx`
- **Estimated scope:** Medium (5 files)

---

### [Lane G — `frontend-analytics`] Task T18: Bộ Component Đánh giá Chuẩn UX Rules Dùng Chung
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane G (agent-fe-analytics)`
- **Description:** Tạo 5 component chuẩn thương mại trong `frontend/src/components/assessment/`: `HealthHeroCard.tsx` (Quy tắc 3 giây: 1 điểm 0–100, 4 cấp màu, PD 12 tháng, Độ tin cậy 4 lớp, 3 nhận định, nút PDF, miễn trừ pháp lý), `DriversSplitPanel.tsx` (2 cột Xanh–Đỏ Điểm Tựa & Điểm Nghẽn — không chứa chuỗi kỹ thuật ML), `FivePillarsSection.tsx` (Radar 5 trụ cột + bảng 20 chỉ số có tooltip, YoY, vị thế ngành), `DynamicAltmanGauge.tsx` (thanh 3 vùng theo `cutoff_low`/`cutoff_high` động + thẻ loại trừ TCTC), và `MultiPeriodHistoryCharts.tsx` (quỹ đạo Điểm sức khỏe & PD 3–5 năm).
- **Acceptance criteria:**
  - [x] Unit tests xác nhận không có chuỗi kỹ thuật (`SHAP`, `log-odds`, `XGBoost`, `Random Forest`, `AAA`) trong DOM đầu ra.
  - [x] `DynamicAltmanGauge` hiển thị chính xác ngưỡng của $Z$, $Z'$ và $Z''$.
- **Verification:**
  - [x] `npm --prefix frontend run typecheck`
  - [x] `npm --prefix frontend test`
- **Dependencies:** Checkpoint W1 *(chạy song song T15 bằng props từ spec; đồng bộ kiểu sau T15)*
- **Files likely touched:**
  - `frontend/src/components/assessment/HealthHeroCard.tsx`
  - `frontend/src/components/assessment/DriversSplitPanel.tsx`
  - `frontend/src/components/assessment/FivePillarsSection.tsx`
  - `frontend/src/components/assessment/DynamicAltmanGauge.tsx`
  - `frontend/src/components/assessment/MultiPeriodHistoryCharts.tsx`
- **Estimated scope:** Medium (5 files + co-located tests)

### [Lane G — `frontend-analytics`] Task T19: Overview Onboarding (M02), Hồ sơ DN Tổ chức & Thị trường Mỹ (SEC)
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane G (agent-fe-analytics)`
- **Description:** Cập nhật `OverviewPage.tsx` (tổng quan Workspace + nút 1-click nạp 3 DN mẫu VN khi trống, dùng đúng 1 Điểm Sức khỏe duy nhất), xây dựng `OrgCompanyDetailPage.tsx` (4 tab chuẩn UX Rules + nút Xuất PDF + tab quản lý BCTC), tạo `UsMarketPage.tsx` (tab "Thị trường Mỹ SEC" gắn nhãn rõ nguồn SEC/USD) và cập nhật `CompanyDetailPage.tsx` (dùng chung `HealthHeroCard`, `DriversSplitPanel`, `DynamicAltmanGauge` — chấm dứt bug lệch 2 điểm sức khỏe và bug gán nhầm RF thành XGBoost log-odds).
- **Acceptance criteria:**
  - [x] Cùng 1 doanh nghiệp hiển thị đúng 1 con số Điểm Sức khỏe duy nhất trên Overview, Portfolio, Compare và Detail.
  - [x] Người dùng mới nạp 3 DN mẫu và xem trọn hồ sơ trong < 30 giây.
  - [x] Trang chi tiết SEC không còn chuỗi `"SHAP (log-odds)"` hay hardcode `1.81 / 2.99` cho DN phi sản xuất.
- **Verification:**
  - [x] `npm --prefix frontend run typecheck`
  - [x] `npm --prefix frontend test`
- **Dependencies:** T15, T18
- **Files likely touched:**
  - `frontend/src/pages/OverviewPage.tsx`
  - `frontend/src/pages/OrgCompanyDetailPage.tsx`
  - `frontend/src/pages/UsMarketPage.tsx`
  - `frontend/src/pages/CompanyDetailPage.tsx`
- **Estimated scope:** Medium (4 files)

### [Lane G — `frontend-analytics`] Task T20: Trang Batch Excel (S03), Compare (C03), Methodology (B2B) & Admin MLOps
- **Status:** `[x]`
- **Lane:** `Wave 2 / Lane G (agent-fe-analytics)`
- **Description:** Xây dựng `BatchAssessmentPage.tsx` (tải file mẫu, upload `.xlsx`, polling tiến độ job nền, bảng xếp hạng rủi ro + nút xuất Excel), nâng cấp `ComparePage.tsx` (chuyển nguồn DN Tổ chức / DN SEC, giới hạn đúng 2–4 DN, dùng đúng `common_fiscal_year`), tạo `MethodologyPage.tsx` (trang minh bạch kiểm định B2B + điều khoản NĐ 88/2014), và gộp `ModelLabPage` + `ClusterMapPage` thành các tab nội bộ bên trong `AdminPage.tsx` (chỉ admin truy cập).
- **Acceptance criteria:**
  - [x] `ComparePage` chặn thêm quá 4 doanh nghiệp và chọn "Cùng năm tài chính" gửi đúng số năm tới backend.
  - [x] `BatchAssessmentPage` hiển thị tiến độ và tải về file Excel kết quả hợp lệ.
  - [x] `MethodologyPage` trình bày rõ giới hạn mô hình và kiểm định out-of-time mà không lộ nút Train Model.
- **Verification:**
  - [x] `npm --prefix frontend run typecheck`
  - [x] `npm --prefix frontend test`
- **Dependencies:** T15, T18
- **Files likely touched:**
  - `frontend/src/pages/BatchAssessmentPage.tsx`
  - `frontend/src/pages/ComparePage.tsx`
  - `frontend/src/pages/MethodologyPage.tsx`
  - `frontend/src/pages/AdminPage.tsx`
- **Estimated scope:** Medium (4 files)

### Checkpoint W2: Sau Merge 3 Nhánh Wave 2 (T13–T20)
- [x] Merge Lane E + Lane F + Lane G vào nhánh tích hợp.
- [x] `npm --prefix frontend run typecheck && npm --prefix frontend test` → 100% pass
- [x] `.\.venv\Scripts\pytest.exe -v tests/unit/test_pdf_and_batch_excel.py tests/integration/test_batch_jobs_and_pdf_api.py` → 100% pass

---

## WAVE 3 — Final Integration, Wiring & Release Gate (Sequential — Lead Agent)

### Task T21: Đấu nối Routers (`main.py`), SPA Routes (`App.tsx`) & Bộ Kiểm thử E2E V1.0
- **Status:** `[ ]`
- **Lane:** `Wave 3 / lead-integrator`
- **Description:** Đăng ký toàn bộ router mới (`organizations`, `org_companies`, `org_analytics`, `reporting_v2`) và sửa CORS (`PATCH`, `DELETE`) trong `src/finhealth/api/main.py`; đấu nối toàn bộ tuyến đường mới (`/`, `/portfolio`, `/portfolio/:id`, `/batch`, `/compare`, `/us-market`, `/us-market/:identifier`, `/methodology`, `/organization`, `/account`, `/admin/*`) trong `frontend/src/App.tsx`; viết bộ kiểm thử tích hợp đầu-cuối `tests/integration/test_e2e_v10_golive.py` chạy trọn hành trình khách hàng.
- **Acceptance criteria:**
  - [ ] Hành trình E2E chạy xanh hoàn toàn: Đăng ký → Verify OTP → Auto Org → Mời Analyst/Viewer → Seed 3 DN mẫu + Import XML HTKK → Chấm điểm `v2.0.0-kaggle` → Xem 5 Trụ cột/Drivers/Lịch sử → So sánh → Batch Excel → Tải PDF → Xuất & Xóa tài khoản purge sạch dữ liệu.
  - [ ] CORS preflight chấp nhận `GET, POST, PATCH, DELETE, OPTIONS`.
- **Verification:**
  - [ ] `.\.venv\Scripts\pytest.exe -v tests/integration/test_e2e_v10_golive.py`
- **Dependencies:** Checkpoint W2
- **Files likely touched:**
  - `src/finhealth/api/main.py`
  - `frontend/src/App.tsx`
  - `tests/integration/test_e2e_v10_golive.py`
- **Estimated scope:** Medium (3 files)

### Task T22: Cổng Kiểm chứng Phát hành Cuối cùng (Final Go-Live Verification Gate)
- **Status:** `[ ]`
- **Lane:** `Wave 3 / lead-integrator`
- **Description:** Build bản production `frontend/dist`, chạy đầy đủ mọi cổng kiểm chứng bắt buộc của kho mã nguồn (`ruff check .`, `mypy src/finhealth`, `pytest -v`, `frontend` typecheck/test/build, `alembic upgrade head` & `downgrade`), đối chiếu toàn bộ Success Criteria của 6 file `spec/SPEC-*.md` và cập nhật `PRODUCT.md` / `README.md` phản ánh đúng trạng thái V1.0.
- **Acceptance criteria:**
  - [ ] `ruff check .` → 0 lỗi.
  - [ ] `mypy src/finhealth` → 0 lỗi.
  - [ ] `pytest -v` → 0 failed (toàn bộ unit + integration + E2E xanh).
  - [ ] `npm --prefix frontend run typecheck && npm --prefix frontend test && npm --prefix frontend run build` → 0 lỗi.
  - [ ] Mọi mục trong `spec/SPEC-*.md` đạt 100% Success Criteria.
- **Verification:**
  - [ ] `.\.venv\Scripts\ruff.exe check .`
  - [ ] `.\.venv\Scripts\mypy.exe src/finhealth`
  - [ ] `.\.venv\Scripts\pytest.exe -v`
  - [ ] `npm --prefix frontend run typecheck && npm --prefix frontend test && npm --prefix frontend run build`
- **Dependencies:** T21
- **Files likely touched:**
  - `PRODUCT.md`
  - `README.md`
- **Estimated scope:** Small (2 docs files + verification runs)

### Checkpoint Final: Sẵn sàng Go-Live V1.0
- [ ] Toàn bộ 22 task (T01–T22) đều `[x]`
- [ ] 0 lỗi lint, 0 lỗi typecheck, 0 test fail, 0 thuật ngữ kỹ thuật ML lọt ra UI người dùng cuối
- [ ] Sản phẩm sẵn sàng review cuối cùng & triển khai production
