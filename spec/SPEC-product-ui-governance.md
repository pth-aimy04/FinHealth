# Spec: End-User Production UI, Dual-Market Navigation & B2B Governance (`product-ui-governance`) — V1.0

> **Module ID:** `product-ui-governance` (xem [capability-map.md](capability-map.md))  
> **Trạng thái:** Đã chốt (Approved — sẵn sàng triển khai)  
> **Phụ thuộc:** `identity-privacy`, `financial-data`, `risk-analytics`, `batch-and-reporting`  
> **Phạm vi nghiệp vụ:** Tái cấu trúc giao diện React (`frontend/`) đạt 3 UX Rules Go-Live (Quy tắc 3 giây, Không con số trơ trọi, Tách biệt 100% kỹ thuật ML khỏi màn hình tác nghiệp), cung cấp song song **Danh bạ DN Tổ chức** và tab **"Thị trường Mỹ (SEC)"**, thống nhất 1 Điểm Sức khỏe xuyên suốt toàn app, bổ sung trang **"Phương pháp luận & Kiểm định"** cho khách hàng B2B, tách cổng Admin/MLOps nội bộ, và xóa bỏ thư mục `web/` lỗi thời.

---

## 1. Objective

Chuyển đổi giao diện FinHealth từ công cụ trình diễn nghiên cứu kỹ thuật sang **sản phẩm SaaS tài chính Go-Live tinh gọn, nhất quán và thân thiện với CFO/Kế toán trưởng/Chuyên viên tín dụng**, đồng thời vẫn bảo đảm tính minh bạch kiểm định cho khách hàng tổ chức (B2B).

### Yêu cầu giao diện & trải nghiệm cụ thể
1. **Kiến trúc Điều hướng (Navigation Architecture — Tách bạch Tác nghiệp & Kỹ thuật):**
   - **Thanh điều hướng chính của Người dùng cuối (`AppShell.tsx`):**
     1. **Tổng quan (`/`)**: Bảng điều khiển nhanh của Workspace đang chọn (Số DN đang quản lý, phân bổ 4 mức sức khỏe, cảnh báo rủi ro cao cần xem ngay, nút "Khởi tạo 3 DN mẫu" nếu Workspace đang trống — M02, phím tắt Nhập BCTC / Chấm hàng loạt).
     2. **Danh bạ Doanh nghiệp (`/portfolio`)**: Quản lý danh bạ DN riêng của Tổ chức (M03) — tìm kiếm theo Tên / MST / Mã CK, lọc theo Thẻ quan hệ / Mức sức khỏe / Loại hình, tạo DN mới, mở hồ sơ chi tiết hoặc nhập BCTC kỳ mới (M04).
     3. **Thẩm định Hàng loạt (`/batch`)**: Tải file mẫu Excel, kéo-thả file `.xlsx` danh mục DN, theo dõi thanh tiến độ job nền, xem bảng xếp hạng ưu tiên rủi ro và tải Excel tổng hợp (S03).
     4. **So sánh Doanh nghiệp (`/compare`)**: Cho phép chọn chế độ **So sánh DN Tổ chức** hoặc **So sánh DN Thị trường Mỹ (SEC)**, tối đa **2–4 doanh nghiệp** (sửa bug 5 mã và bug `common_fiscal_year` — C03).
     5. **Thị trường Mỹ (SEC) (`/us-market`)**: Giữ song song kho 98+ doanh nghiệp niêm yết Hoa Kỳ (sàng lọc `ScreenerPage`, chi tiết `/us-market/:identifier`, Stress Test What-If sẵn có) với nhãn rõ nguồn dữ liệu *"Dữ liệu công bố SEC EDGAR (Hoa Kỳ — USD)"* để không bao giờ lẫn với danh bạ nội bộ VND của tổ chức.
     6. **Phương pháp luận & Kiểm định (`/methodology`)**: Trang minh bạch dành cho khách hàng B2B (Phòng rủi ro/Ngân hàng) giải thích ngắn gọn bằng tiếng Việt: tập dữ liệu huấn luyện (Kaggle US 1999–2018 + SEC đối chiếu), chỉ số kiểm định out-of-time (ROC-AUC, PR-AUC, Brier, Calibration), nguyên tắc 5 trụ cột, phạm vi loại trừ TCTC và điều khoản pháp lý NĐ 88/2014/NĐ-CP.
     7. **Khu vực tài khoản & Tổ chức (Header/Footer):** Bộ chuyển **Workspace (Org Switcher)**, trang **Quản trị Tổ chức (`/organization`)** (thành viên/RBAC/mời/audit log), và **Tài khoản & Bảo mật (`/account`)** (đủ Đổi mật khẩu OTP, Đổi email OTP, Xuất dữ liệu & Xóa tài khoản).
   - **Ẩn khỏi menu người dùng cuối (Chuyển sang cổng Admin/MLOps `/admin/*` chỉ hiện với `user.role === 'admin'`):**
     - `ModelLabPage` (Kho phiên bản mô hình, biểu đồ ROC/PR/Confusion Matrix, kiểm định nội bộ) → di chuyển vào `/admin/models`.
     - `ClusterMapPage` (Bản đồ phân cụm PCA PC1×PC2) → di chuyển vào `/admin/clusters` (hoặc mục chuyên sâu ẩn dưới `/methodology` nếu không cần cho người dùng phổ thông).
2. **Tuân thủ Tuyệt đối 3 UX Rules trên Màn hình Hồ sơ Chi tiết Doanh nghiệp (`/portfolio/:id` & `/us-market/:identifier`):**
   - **UX Rule 1 — Quy tắc 3 giây (Hero Summary Card):** Ngay phần đầu màn hình (above the fold) chỉ hiển thị đúng 4 thông tin cốt lõi:
     1. **1 Điểm Sức khỏe Tài chính duy nhất (`0–100`)** — đồng nhất tuyệt đối giữa Tổng quan, Danh bạ, So sánh và Chi tiết (chấm dứt bug hiển thị 2 điểm khác nhau giữa `OverviewPage` và `CompanyDetailPage`).
     2. **Nhãn Xếp hạng 4 cấp độ màu sắc** (*Vững mạnh* Xanh lá · *Ổn định* Xanh dương · *Cần theo dõi sát* Vàng cam · *Nguy cơ khủng hoảng cao* Đỏ) — **không hiển thị `AAA..CCC`**.
     3. **Tỷ lệ Nguy cơ Khủng hoảng 12 tháng (%)** + huy hiệu **Độ tin cậy đánh giá** (*Cao / Khá / Cần lưu ý* — bấm vào xem giải thích 4 tiêu chí) + cờ cảnh báo Dòng tiền (nếu kích hoạt).
     4. **3 nhận định quan trọng nhất** + nút hành động trực tiếp (**Xuất Báo cáo PDF** M12, **Nhập BCTC kỳ mới** M04, **So sánh** C03).
   - **UX Rule 2 — Không con số trơ trọi:**
     - **Tab 1 — Điểm Tựa, Điểm Nghẽn & 5 Trụ cột:**
       - Bảng 2 cột Xanh–Đỏ **"Điểm Tựa & Điểm Nghẽn Tài Chính"** (M10) hoàn toàn bằng tiếng Việt nghiệp vụ (tuyệt đối không có chuỗi `"TreeSHAP"`, `"SHAP (log-odds)"`, `"XGBoost"`, `"roa_lag1"`).
       - Biểu đồ Radar **5 Trụ cột** + Thẻ **Altman Z-Score** với thanh thước đo 3 vùng theo đúng ngưỡng động (`cutoff_low / cutoff_high`) của biến thể $Z / Z' / Z''$ (hoặc thẻ thông báo loại trừ nếu là Ngân hàng/TCTC).
       - Thẻ **Chất lượng Lợi nhuận (QoE)** & **Miễn trừ trách nhiệm pháp lý**.
     - **Tab 2 — Chi tiết 20 Chỉ số Tài chính (M09):** Bảng nhóm theo 5 trụ cột; mỗi dòng hiển thị: Tên chỉ số + **Tooltip giải thích & ngưỡng tham chiếu**, Giá trị kỳ này, Biến động so với kỳ trước (YoY), **Vị thế so với ngành** (Top 25% / Trung bình / Thấp hơn — S01), và Đèn trạng thái.
     - **Tab 3 — Lịch sử Đa kỳ 3–5 Năm (M11):** Biểu đồ quỹ đạo **Điểm Sức khỏe (0–100)** & **Nguy cơ Phá sản (%)** qua các năm, cùng biểu đồ Doanh thu – Lợi nhuận – Dòng tiền và Cơ cấu Nợ/Vốn chủ (gắn nhãn rõ chuẩn kế toán từng kỳ TT200 → TT99).
     - **Tab 4 — Quản lý BCTC & Nhập liệu (M04, M05):** Danh sách các kỳ BCTC (`Nháp` / `Đã chốt`), nút tải file **XML HTKK**, tải **Excel chuẩn TT99/TT200/TT133**, hoặc mở **Biểu mẫu Web 3 phần** (*Báo cáo tình hình tài chính / KQHĐKD / LCTT*) có chọn đơn vị tiền tệ (Đồng / Triệu / Tỷ), tự động cộng tổng dòng cha, **Lưu nháp** và **Trợ lý kiểm tra cân đối kế toán** tô đỏ đúng dòng lệch số liệu.
   - **UX Rule 3 — Tách biệt 100% Vận hành Kỹ thuật AI:** Không có bất kỳ menu chọn thuật toán, nút huấn luyện, ma trận nhầm lẫn hay từ khóa lập trình ML nào trên toàn bộ tuyến đường người dùng cuối (`/`, `/portfolio`, `/batch`, `/compare`, `/us-market`).
3. **Dọn dẹp Nợ kỹ thuật Frontend:**
   - Xóa hoàn toàn thư mục `web/` cũ (đã lỗi thời và tham chiếu sai trường schema ở `web/src/pages/ModelsPage.tsx:67-70`).
   - Bảo đảm tính truy cập (accessibility WCAG 2.2 AA: tương phản màu sắc cho cả Light/Dark mode, điều hướng bàn phím cho tab/modal/tooltip, `aria-label` đầy đủ, phản hồi lỗi `role="alert"`).

---

## 2. Tech Stack

- React 19, TypeScript 5.7, Vite 6.2, Tailwind CSS 4, `@tanstack/react-query` v5, `react-router-dom` v7, `recharts`, `react-hook-form`, `zod`, `lucide-react`.
- Font: `@fontsource/be-vietnam-pro` + `@fontsource/jetbrains-mono` (đã có trong `frontend/package.json`).

---

## 3. Commands

```powershell
# Typecheck, unit tests & production build cho frontend
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build

# Xác minh backend phục vụ đúng SPA dist mới
.\.venv\Scripts\pytest.exe -v tests/integration/test_dashboard_ui.py
```

---

## 4. Project Structure

```text
frontend/src/
  ├── App.tsx                                   # Route mới: /, /portfolio, /portfolio/:id, /portfolio/:id/statements/new,
  │                                             # /batch, /compare, /us-market, /us-market/:identifier, /methodology,
  │                                             # /organization, /account, /admin/* (tách ModelLab & ClusterMap vào /admin)
  ├── lib/
  │   ├── api.ts                                # Bổ sung đầy đủ client cho org companies, statements, XML/Excel upload,
  │   │                                         # batch jobs, PDF download, org RBAC; sửa verifyEmail & compareCompanies
  │   └── format.ts                             # Định dạng VND/Triệu/Tỷ + USD, nhãn 4 cấp độ sức khỏe, bỏ mã kỹ thuật
  ├── components/
  │   ├── layout/AppShell.tsx                   # Navigation mới (Portfolio + Thị trường Mỹ SEC + Org Switcher), ẩn kỹ thuật ML
  │   ├── assessment/
  │   │   ├── HealthHeroCard.tsx                # Khối 3 giây: Điểm 0-100, 4 cấp màu, PD %, Độ tin cậy, 3 nhận định, nút PDF
  │   │   ├── DriversSplitPanel.tsx             # Bảng 2 cột Xanh-Đỏ "Điểm Tựa & Điểm Nghẽn Tài Chính" (M10)
  │   │   ├── FivePillarsSection.tsx            # Radar 5 trụ cột + bảng 20 chỉ số có tooltip & vị thế ngành (M09, S01)
  │   │   ├── DynamicAltmanGauge.tsx            # Thước đo Altman Z/Z'/Z'' theo ngưỡng động + trạng thái chặn TCTC (M08)
  │   │   └── MultiPeriodHistoryCharts.tsx      # Quỹ đạo Điểm sức khỏe & PD 3–5 năm + Tài chính (M11)
  │   └── statements/
  │       ├── StatementEditorForm.tsx           # Biểu mẫu Web 3 phần (TT99/TT200/TT133), chọn đơn vị, tự cộng tổng, lưu nháp (M04)
  │       ├── BalanceCheckAssistant.tsx         # Trợ lý kiểm tra cân đối kế toán tô rõ dòng lệch (M05)
  │       └── ImportStatementModal.tsx          # Modal nạp file XML HTKK hoặc Excel chuẩn + tải file mẫu (M04)
  └── pages/
      ├── OverviewPage.tsx                      # Tổng quan Workspace + 3 DN mẫu onboarding (M02)
      ├── PortfolioPage.tsx                     # Danh bạ DN Tổ chức CRUD (M03)
      ├── OrgCompanyDetailPage.tsx              # Hồ sơ chi tiết DN Tổ chức (4 tab chuẩn UX Rules)
      ├── BatchAssessmentPage.tsx               # Thẩm định hàng loạt qua Excel (S03)
      ├── ComparePage.tsx                       # So sánh 2–4 DN Tổ chức hoặc SEC (sửa 2 bug — C03)
      ├── UsMarketPage.tsx                      # Tab "Thị trường Mỹ (SEC)" (tái sử dụng ScreenerPage)
      ├── CompanyDetailPage.tsx                 # Cập nhật trang chi tiết SEC dùng chung HealthHeroCard, DriversSplitPanel, DynamicAltmanGauge
      ├── MethodologyPage.tsx                   # Trang "Phương pháp luận & Kiểm định" cho B2B
      ├── OrganizationPage.tsx                  # Quản trị Workspace Tổ chức & RBAC
      ├── AccountPage.tsx                       # Đủ Đăng ký/OTP, Đổi MK/Email OTP, Xuất & Xóa tài khoản
      └── AdminPage.tsx                         # Cổng Admin chứa tab Hệ thống, Ingestion, Users, Audit, ModelLab (nội bộ)
[XÓA] web/                                      # Gỡ bỏ hoàn toàn frontend trùng lặp lỗi thời
```

---

## 5. Code Style

Tuân thủ TypeScript strict mode (`tsc -b --noEmit`), React Query tách riêng query key theo `activeOrg?.id`, mọi số tiền/tỷ số định dạng qua helper `format.ts` (không hiển thị `NaN`/`Infinity`, thiếu dữ liệu hiển thị `—`), dùng semantic CSS variables sẵn có trong `frontend/src/index.css`.

```tsx
export const RISK_TIER_META = {
  STRONG: { label: 'Vững mạnh', tone: 'low' },
  STABLE: { label: 'Ổn định', tone: 'info' },
  WATCH: { label: 'Cần theo dõi sát', tone: 'medium' },
  CRITICAL: { label: 'Nguy cơ khủng hoảng cao', tone: 'critical' },
} as const;
```

---

## 6. Testing Strategy

- **Frontend unit/component tests (`vitest` + `@testing-library/react`):**
  - `HealthHeroCard.test.tsx`: Kiểm tra hiển thị đủ 4 yếu tố Quy tắc 3 giây, **không chứa chuỗi kỹ thuật** (`SHAP`, `log-odds`, `XGBoost`, `AAA`), và hiển thị miễn trừ pháp lý.
  - `DynamicAltmanGauge.test.tsx`: Kiểm tra ngưỡng `1.81/2.99` (Z), `1.23/2.90` (Z'), `1.10/2.60` (Z'') và thông báo loại trừ TCTC.
  - `StatementEditorForm.test.tsx`: Kiểm tra tự động cộng tổng dòng cha, cảnh báo lệch cân đối kế toán tại dòng sai, và chuyển đổi đơn vị Đồng / Triệu / Tỷ.
  - `AppShell.test.tsx`: Kiểm tra user thường không thấy menu `ModelLab`/`ClusterMap`/`Admin`, nhưng thấy cả **Danh bạ Doanh nghiệp** và **Thị trường Mỹ (SEC)**.
- **Build gate:** `npm --prefix frontend run typecheck && npm --prefix frontend test && npm --prefix frontend run build` bắt buộc xanh 100% và `frontend/dist` phục vụ sạch qua FastAPI.

---

## 7. Boundaries

- **Always:**
  - Invalidate React Query cache theo `activeOrg.id` mỗi khi người dùng đổi Workspace để không rò rỉ dữ liệu hiển thị giữa 2 tổ chức.
  - Bảo đảm mọi trang có hỗ trợ Light/Dark mode và hiển thị tốt trên cả màn hình laptop (1280px) và tablet/mobile.
- **Ask first:**
  - Thêm bất kỳ thư viện UI/chart ngoài mới nào vào `frontend/package.json`.
- **Never:**
  - Không bao giờ hiển thị `SHAP value`, `log-odds`, tên cột lập trình (`roa_yoy_delta`), nút Train Model hay bảng Confusion Matrix trên màn hình người dùng cuối.
  - Không bao giờ hiển thị 2 con số "Điểm Sức khỏe Tổng hợp" khác nhau cho cùng 1 doanh nghiệp trên các trang khác nhau.
  - Không bao giờ giữ lại `web/` sau khi bàn giao V1.0.

---

## 8. Success Criteria

1. Người dùng mới đăng nhập lần đầu có thể bấm nạp 3 DN mẫu VN và xem trọn vẹn hồ sơ phân tích trong **< 30 giây**, nắm bắt kết luận cốt lõi trong **3 giây** ở màn hình đầu tiên.
2. Không có bất kỳ thuật ngữ kỹ thuật ML (`SHAP`, `log-odds`, `Random Forest`, `XGBoost`, `SMOTE`, `roa_yoy_delta`) nào xuất hiện trên luồng người dùng cuối (`/`, `/portfolio/*`, `/batch`, `/compare`, `/us-market/*`).
3. Hai không gian **Danh bạ Doanh nghiệp (Tổ chức)** và **Thị trường Mỹ (SEC)** hoạt động song song rõ ràng, không lẫn đơn vị tiền tệ hay điểm sức khỏe.
4. Thư mục `web/` đã được gỡ bỏ sạch; `frontend` typecheck, unit tests và production build xanh 100%.

---

## 9. Out of Scope (Deferred)

- Kéo-thả giả lập kịch bản kinh doanh thời gian thực (C01 mở rộng cho DN tổ chức — V1.1; giữ nguyên StressLab hiện có cho tab SEC).
- Trung tâm thông báo chuông (In-app notification bell) cho cảnh báo tụt hạng Watchlist (S04 — V1.1).
- Giao diện sổ tay ghi chú & tải tệp chứng từ (S06 — V1.1/V2.0).
