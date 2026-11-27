# Implementation Plan: FinHealth Production — V1.0 (Parallel Coding Agents)

**Source specs:**
- [spec/capability-map.md](../spec/capability-map.md)
- [spec/SPEC-identity-privacy.md](../spec/SPEC-identity-privacy.md)
- [spec/SPEC-financial-data.md](../spec/SPEC-financial-data.md)
- [spec/SPEC-ml-bankruptcy-engine.md](../spec/SPEC-ml-bankruptcy-engine.md)
- [spec/SPEC-risk-analytics.md](../spec/SPEC-risk-analytics.md)
- [spec/SPEC-batch-and-reporting.md](../spec/SPEC-batch-and-reporting.md)
- [spec/SPEC-product-ui-governance.md](../spec/SPEC-product-ui-governance.md)

**Task list target:** [tasks/todo.md](todo.md)

---

## 1. Overview

Kế hoạch này tổ chức triển khai trọn bộ **FinHealth Production V1.0** (6 module: `identity-privacy`, `financial-data`, `ml-bankruptcy-engine`, `risk-analytics`, `batch-and-reporting`, `product-ui-governance`) thành **4 Đợt (Wave 0 → Wave 3)** với các làn chạy song song (Parallel Lanes) có **quyền sở hữu tệp tách biệt hoàn toàn (disjoint file ownership)**. Cách tổ chức này cho phép giao nhiều coding agent (trên các nhánh/worktree độc lập) làm việc đồng thời mà không đụng độ Alembic migration, không xung đột `main.py` hay `pyproject.toml`, và kiểm chứng được từng lát cắt dọc (vertical slice) ngay tại các Checkpoint.

---

## 2. Architecture Decisions

1. **Khóa Schema, Migration & Hợp đồng Giao diện ngay ở Wave 0:** Toàn bộ thay đổi `pyproject.toml`, chuỗi migration Alembic (`0008 → 0011`), ORM models và 2 hợp đồng biên (`OrgContext / require_org_role` và `CORE_BANKRUPTCY_FEATURES`) được chốt tuần tự bởi 1 Lead Agent trước khi mở song song. Nhờ đó, 4 agent ở Wave 1 không bao giờ bị xung đột nhánh Alembic hay lệch kiểu dữ liệu.
2. **Định tuyến Dữ liệu & ML Hai tầng:**
   - Lõi dự báo phá sản 12 tháng (`v2.0.0-kaggle`) huấn luyện trên `data/raw/kaggle/american_bankruptcy.csv` sau khi sửa sạch rò rỉ nhãn (`year == max_year`), dùng 19 đặc trưng 100% không thứ nguyên (bỏ `X8`/`eps`), Platt-calibrate đồng đều cả 4 mô hình (LR, RF, XGB, LGBM), tách 2 chế độ `single_period` / `multi_period`.
   - SEC EDGAR giữ vai trò kép: (a) lớp đối chiếu Dòng tiền / Chuẩn ngành (S01) và (b) tab tra cứu **"Thị trường Mỹ (SEC)"** song song với Danh bạ Doanh nghiệp riêng của Tổ chức.
3. **Thống nhất 1 Điểm Sức khỏe 0–100 & Tuân thủ Pháp lý VN 2026:**
   - Điểm `0–100` ánh xạ đơn điệu trực tiếp từ `pd_12m` đã hiệu chuẩn (+ Cash-Flow Overlay), gắn 4 cấp màu (`STRONG / STABLE / WATCH / CRITICAL`), loại bỏ `AAA..CCC` khỏi UI khách hàng và gắn miễn trừ NĐ 88/2014/NĐ-CP trên mọi phản hồi & PDF.
   - Hỗ trợ đầy đủ **Thông tư 99/2025/TT-BTC** (từ FY2026+), **Thông tư 200/2014** (≤2025), **Thông tư 133/2016** (SME) qua Web Form + Excel + **Import XML HTKK (`defusedxml`)**.
   - Tuân thủ **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15** bằng `GET /auth/me/export` và `POST /auth/delete-account` (OTP, `ON DELETE SET NULL` cho `admin_audit_logs.actor_id`).
4. **PDF & Batch Không lệ thuộc Hạ tầng Nặng:** Dùng `reportlab` + `matplotlib` (Agg) + font BeVietnamPro TTF nhúng cho PDF A4 đa nền tảng (Windows/Linux Docker chạy 100% không cần GTK); dùng DB-backed background worker (giống `ingestion/jobs.py`) cho Batch Excel S03.
5. **Tách biệt Quyền sở hữu Tệp cho Agent Song song:** Mỗi Lane trong cùng một Wave chỉ chỉnh sửa tập file được cấp riêng; các file hợp nhất trung tâm (`src/finhealth/api/main.py`, `frontend/src/App.tsx`, `frontend/src/lib/api.ts`) chỉ giao đúng 1 Lane/Wave duy nhất sở hữu tại một thời điểm.

---

## 3. Parallel Execution Topology (Sơ đồ Làn Chạy Song Song)

```text
WAVE 0 (Sequential — Lead Agent)
  [T01 Baseline + Deps + Xóa web/] ──► [T02 Migrations 0008..0011 + ORM + Boundary Contracts]
                                                  │
        ┌─────────────────────────┬───────────────┴───────────────┬──────────────────────────┐
        ▼                         ▼                               ▼                          ▼
WAVE 1 (4 Agents Song Song — Disjoint File Ownership)
  Lane A: identity-privacy   Lane B: financial-data          Lane C: ml-bankruptcy-engine   Lane D: risk-analytics
  [T03 Org + RBAC API]       [T05 Ratios + Validator + VAS]  [T08 Clean Kaggle Loader]      [T11 Altman Z/Z'/Z'' + 5 Pillars + Catalog]
  [T04 Privacy 91/2025 API]  [T06 HTKK XML + Excel + Sample] [T09 4-Model Calib + Conf]     [T12 Drivers + Org Analysis/Compare API]
                             [T07 Org Companies/Stmts API]   [T10 Train v2.0.0-kaggle]
        │                         │                               │                          │
        └─────────────────────────┴───────────────┬───────────────┴──────────────────────────┘
                                                  ▼
                                      [CHECKPOINT WAVE 1: Merge + Backend Gate]
                                                  │
        ┌─────────────────────────────────────────┼──────────────────────────────────────────┐
        ▼                                         ▼                                          ▼
WAVE 2 (3 Agents Song Song — Disjoint File Ownership)
  Lane E: batch-and-reporting       Lane F: frontend-core (Auth/Org/Input)     Lane G: frontend-analytics (Views/Compare/Batch)
  [T13 PDF Engine (M12)]            [T15 API Client + Types + AuthContext]     [T18 Shared Assessment Components]
  [T14 Async Batch Excel (S03)]     [T16 Account + Organization + AppShell]    [T19 Overview + OrgDetail + USMarket/SEC]
                                    [T17 Portfolio + Statement Editor/Import]  [T20 Batch + Compare + Methodology + Admin]
        │                                         │                                          │
        └─────────────────────────────────────────┴───────────────┬──────────────────────────┘
                                                                  ▼
                                      [CHECKPOINT WAVE 2: Merge + Full Stack Build]
                                                                  │
                                                                  ▼
WAVE 3 (Sequential — Lead Agent)
  [T21 Wire Routers/Routes + E2E Integration Suite] ──► [T22 Final Release Gate: ruff, mypy, pytest, vitest, vite build, alembic]
```

### Ma trận Sở hữu Tệp Chống Xung đột (File Ownership Rules)

| Wave / Lane | Agent Role | Thư mục / Tệp ĐỘC QUYỀN sở hữu | Cấm chạm trong Wave hiện tại |
| :--- | :--- | :--- | :--- |
| **Wave 0** | `lead-architect` | `pyproject.toml`, `migrations/versions/0008..0011*`, `src/finhealth/db/*`, `src/finhealth/api/security.py`, `src/finhealth/ml/feature_contracts.py`, `web/` (xóa), sửa 2 lỗi test baseline | — |
| **Wave 1 — Lane A** | `agent-identity` | `src/finhealth/api/routers/{accounts,organizations,workspace}.py`, `src/finhealth/api/schemas/accounts.py`, `tests/{unit/test_org_rbac_invariants,integration/test_organizations_and_privacy}.py` | `main.py`, `etl/`, `ml/`, `frontend/` |
| **Wave 1 — Lane B** | `agent-financial-data` | `src/finhealth/etl/{financial_ratios,accounting_validator,vn_accounting_mapper,htkk_xml_parser,excel_templates,vn_samples}.py`, `src/finhealth/api/schemas/org_financials.py`, `src/finhealth/api/routers/org_companies.py`, `tests/{unit/test_vn_accounting_and_validation,integration/test_org_companies_and_statements}.py` | `main.py`, `ml/`, `corporate_finance.py`, `frontend/` |
| **Wave 1 — Lane C** | `agent-ml-engine` | `src/finhealth/ml/{kaggle_loader,distress_classifier,confidence,registry,explainer,train_cli}.py`, `data/artifacts/models/v2.0.0-kaggle/*`, `tests/unit/test_ml_bankruptcy_v2.py` | `main.py`, `etl/`, `api/routers/`, `frontend/` |
| **Wave 1 — Lane D** | `agent-risk-analytics` | `src/finhealth/etl/{altman,corporate_finance,metric_catalog,driver_narrative}.py`, `src/finhealth/api/schemas/analytics.py`, `src/finhealth/api/services_org.py`, `src/finhealth/api/routers/org_analytics.py`, `tests/{unit/test_risk_analytics_v2,integration/test_org_analysis_and_compare}.py` | `main.py`, `financial_ratios.py`, `ml/`, `frontend/` |
| **Wave 2 — Lane E** | `agent-reporting` | `src/finhealth/reporting/*`, `src/finhealth/api/schemas/batch_reporting.py`, `src/finhealth/api/routers/reporting_v2.py`, `tests/{unit/test_pdf_and_batch_excel,integration/test_batch_jobs_and_pdf_api}.py` | `main.py`, `frontend/` |
| **Wave 2 — Lane F** | `agent-fe-core` | `frontend/src/{types/api.ts,lib/api.ts,lib/format.ts,context/AuthContext.tsx}`, `frontend/src/components/{layout/AppShell.tsx,statements/*}`, `frontend/src/pages/{AccountPage,OrganizationPage,PortfolioPage}.tsx` | `frontend/src/App.tsx`, `frontend/src/components/assessment/*`, pages của Lane G |
| **Wave 2 — Lane G** | `agent-fe-analytics` | `frontend/src/components/assessment/*`, `frontend/src/pages/{OverviewPage,OrgCompanyDetailPage,CompanyDetailPage,UsMarketPage,BatchAssessmentPage,ComparePage,MethodologyPage,AdminPage}.tsx` | `api.ts` (đọc hợp đồng kiểu từ T15 hoặc merge T15 trước khi chạy T19–T20), `App.tsx` |
| **Wave 3** | `lead-integrator` | `src/finhealth/api/main.py` (mount tất cả router mới + sửa CORS), `frontend/src/App.tsx` (mount tất cả route mới), `tests/integration/test_e2e_v10_golive.py` | — |

> **Lưu ý điều phối Wave 2:** Trong Wave 2, **Lane F hoàn thành T15 (`types/api.ts`, `lib/api.ts`, `format.ts`) đầu tiên** (khoảng 15 phút) rồi đẩy lên nhánh chung trước khi Lane G nối API ở T19–T20 (trong khi chờ T15, Lane G vẫn làm song song T18 — các component hiển thị thuần nhận props từ Spec!).

---

## 4. Task Index (Chi tiết nằm trong [tasks/todo.md](todo.md))

### Wave 0: Foundation, Migrations & Shared Contracts (Sequential)
- [ ] **T01:** Dọn dẹp baseline, cập nhật dependencies (`pyproject.toml`) và xóa thư mục `web/` lỗi thời
- [ ] **T02:** Tạo chuỗi migration `0008–0011`, ORM models (`account_models`, `org_models`, `batch_models`, `models`) và boundary contracts (`OrgContext`, `feature_contracts`)
- **Checkpoint W0:** `alembic upgrade head` + `downgrade` sạch; `ruff`, `mypy`, `pytest` baseline xanh 100%

### Wave 1: 4 Backend Lanes Song Song
- **Lane A (`identity-privacy`):**
  - [ ] **T03:** Triển khai Organization Workspace + RBAC API (`organizations.py`, phạm vi `org_id` trên `workspace.py`)
  - [ ] **T04:** Triển khai quyền xuất/xóa dữ liệu Luật 91/2025/QH15 + tự tạo personal org khi verify email
- **Lane B (`financial-data`):**
  - [ ] **T05:** Mở rộng tỷ số tài chính, sửa bug âm VCSH, bộ kiểm tra cân đối kế toán & mapper TT99/TT200/TT133
  - [ ] **T06:** Xây dựng parser XML HTKK (`defusedxml`), biểu mẫu/parser Excel (`openpyxl`) và 3 hồ sơ DN mẫu VN
  - [ ] **T07:** Triển khai CRUD API Danh bạ DN & BCTC Tổ chức (`org_companies.py`) kèm kiểm thử cô lập
- **Lane C (`ml-bankruptcy-engine`):**
  - [ ] **T08:** Sửa rò rỉ nhãn `kaggle_loader.py` (`year == max_year`) và trích xuất đủ 19 tỷ số không thứ nguyên từ `X1–X18`
  - [ ] **T09:** Platt calibration đồng đều cả 4 mô hình, chế độ `single_period`/`multi_period`, Độ tin cậy 4 lớp, PD↔0–100 & Cash-Flow Overlay, reload registry đa worker
  - [ ] **T10:** Huấn luyện & kiểm chứng gói `v2.0.0-kaggle` (0% leakage, bất biến tiền tệ VND=USD)
- **Lane D (`risk-analytics`):**
  - [ ] **T11:** Triển khai đủ Altman $Z/Z'/Z''$ + chặn TCTC (`altman.py`), 5 Trụ cột & Từ điển 20 chỉ số có tooltip (`metric_catalog.py`, `corporate_finance.py`)
  - [ ] **T12:** Xây dựng bộ diễn giải 2 cột Điểm Tựa & Điểm Nghẽn (`driver_narrative.py`), dịch vụ lịch sử đa kỳ M11, chuẩn ngành S01 & So sánh 2–4 DN C03 (`services_org.py`, `org_analytics.py`)
- **Checkpoint W1:** Merge 4 nhánh Wave 1; toàn bộ unit + integration test backend xanh 100%

### Wave 2: Reporting & 2 Frontend Lanes Song Song
- **Lane E (`batch-and-reporting`):**
  - [ ] **T13:** Xây dựng bộ xuất Báo cáo Thẩm định PDF A4 tiếng Việt (`pdf_generator.py` + font BeVietnamPro TTF)
  - [ ] **T14:** Xây dựng Thẩm định Hàng loạt qua Excel chạy nền bất đồng bộ & xuất Excel tổng hợp (`batch_excel.py`, `batch_worker.py`, `reporting_v2.py`)
- **Lane F (`frontend-core`):**
  - [ ] **T15:** Cập nhật `types/api.ts`, `lib/api.ts` (sửa `verifyEmail` & `compareCompanies`), `format.ts`, `AuthContext.tsx` *(merge sớm cho Lane G)*
  - [ ] **T16:** Hoàn thiện `AccountPage.tsx`, `OrganizationPage.tsx` và tái cấu trúc `AppShell.tsx` (Org Switcher + 2 không gian song song, ẩn ML tech)
  - [ ] **T17:** Xây dựng `PortfolioPage.tsx`, `StatementEditorForm.tsx`, `BalanceCheckAssistant.tsx`, `ImportStatementModal.tsx` (M03, M04, M05)
- **Lane G (`frontend-analytics`):**
  - [ ] **T18:** Xây dựng 5 component đánh giá dùng chung (`HealthHeroCard`, `DriversSplitPanel`, `FivePillarsSection`, `DynamicAltmanGauge`, `MultiPeriodHistoryCharts`)
  - [ ] **T19:** Xây dựng `OverviewPage.tsx` (3 DN mẫu), `OrgCompanyDetailPage.tsx`, `UsMarketPage.tsx` và đồng bộ `CompanyDetailPage.tsx` (sửa lệch điểm & Altman cutoff)
  - [ ] **T20:** Xây dựng `BatchAssessmentPage.tsx`, nâng cấp `ComparePage.tsx` (2–4 DN Org/SEC), `MethodologyPage.tsx` và gộp `ModelLab`/`ClusterMap` vào `AdminPage.tsx`
- **Checkpoint W2:** Merge 3 nhánh Wave 2; `npm --prefix frontend run typecheck && test && build` xanh 100%

### Wave 3: Integration, Wiring & Release Gate (Sequential)
- [ ] **T21:** Đấu nối hoàn chỉnh `src/finhealth/api/main.py` (tất cả router + CORS `PATCH`/`DELETE`) và `frontend/src/App.tsx`; viết bộ test E2E liên module (`test_e2e_v10_golive.py`)
- [ ] **T22:** Chạy toàn bộ cổng kiểm chứng Go-Live cuối cùng (`ruff check .`, `mypy`, `pytest -v`, `frontend` checks, `alembic` upgrade/downgrade, cập nhật tài liệu)

---

## 5. Risks and Mitigations

| Rủi ro | Mức độ | Biện pháp giảm thiểu |
| :--- | :--- | :--- |
| **Xung đột nhánh Alembic migration khi nhiều agent chạy song song** | Cao | Khóa toàn bộ migrations `0008–0011` trong **Wave 0 (T02)** tuần tự trước khi mở Wave 1. |
| **SQL Server (MSSQL) báo lỗi multiple cascade paths** | Cao | Mọi bảng mới trong `0008–0011` phải kiểm tra qua `test_sqlserver_offline_migration_uses_one_cascade_path` ngay ở Checkpoint W0. |
| **Font tiếng Việt lỗi dấu khi sinh PDF trên Windows/Linux** | Trung bình | Nhúng trực tiếp file `BeVietnamPro-Regular.ttf` & `BeVietnamPro-Bold.ttf` (giấy phép SIL OFL) trong `src/finhealth/reporting/fonts/` và viết test kiểm tra Unicode PDF ở T13. |
| **Gãy liên kết kiểu dữ liệu giữa Lane F & Lane G** | Trung bình | Đóng băng schema response trong `SPEC-risk-analytics.md` & `SPEC-batch-and-reporting.md`, đồng thời ưu tiên merge T15 trước khi Lane G nối API ở T19–T20. |
| **Bất đồng thang điểm hoặc lọt thuật ngữ ML lên UI** | Cao | Viết unit test tự động ở T18 khẳng định `HealthHeroCard` & `DriversSplitPanel` không chứa bất kỳ chuỗi cấm (`SHAP`, `log-odds`, `XGBoost`, `AAA`). |

---

## 6. Hướng dẫn Khởi chạy Agent Coding Song Song

1. Chạy tuần tự **T01 → T02** trên nhánh tích hợp chính (`feat/v1-golive`), xác nhận **Checkpoint W0** xanh 100%.
2. Tạo 4 git worktree/nhánh riêng từ commit sau Checkpoint W0 cho **Lane A, Lane B, Lane C, Lane D**; giao mỗi agent đúng 1 Spec tương ứng trong `spec/` và đúng các Task trong `tasks/todo.md`.
3. Sau khi 4 agent hoàn thành & merge vào `feat/v1-golive`, xác nhận **Checkpoint W1**.
4. Tạo 3 git worktree/nhánh cho **Lane E, Lane F, Lane G** (merge sớm T15 của Lane F để Lane G rebase và chạy T19–T20 song song).
5. Merge Wave 2, xác nhận **Checkpoint W2**, chạy **Wave 3 (T21 → T22)** để khóa bản phát hành V1.0.
