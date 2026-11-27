# Capability Map: FinHealth Production — V1.0

> **Trạng thái:** Đã phê duyệt (Approved)  
> **Định hướng dữ liệu & ML:** Lõi dự báo phá sản 12 tháng (PD) huấn luyện trên **Kaggle US Bankruptcy (`american_bankruptcy.csv`)** (đã loại bỏ hoàn toàn look-ahead/entity leakage, dùng tỷ số không thứ nguyên từ `X1–X18` bỏ `X8`/`eps`) + **SEC EDGAR (`10-K`/`10-Q`)** làm lớp đối chiếu Dòng tiền (OCF/Lãi vay/QoE), Chuẩn ngành và tab tra cứu **"Thị trường Mỹ (SEC)"** song song với Danh bạ Doanh nghiệp riêng của Tổ chức.

---

## Bản đồ Module (Module Table)

| Module ID | Trách nhiệm cốt lõi (Responsibility) | Phụ thuộc (`Depends on`) |
| :--- | :--- | :--- |
| `identity-privacy` | Xác thực Email + Mật khẩu + OTP, phiên cookie + CSRF thu hồi được, sửa lỗi 422 `verify-email` và nối đủ UI đổi mật khẩu/đổi email; **Workspace Tổ chức (Multi-Tenant Organization) + RBAC** (`org_admin`, `analyst`, `viewer`, mời thành viên qua OTP/email, tách cô lập dữ liệu tuyệt đối theo `org_id`); quyền **tự xuất & tự xóa tài khoản/dữ liệu** theo Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15; sửa CORS bổ sung `PATCH`/`DELETE`. *(M01)* | `—` |
| `financial-data` | Mở rộng schema `FinancialStatement` lưu đủ khoản mục cốt lõi (Giá vốn, Lãi gộp, Phải thu, Tồn kho, Phải trả, Khấu hao, EBITDA, Nợ vay ngắn/dài hạn, Chi phí HĐ); bảng `OrgCompany` & `OrgFinancialStatement` cô lập theo `org_id` (MST, ngành VSIC, niêm yết/chưa niêm yết, chặn TCTC/Ngân hàng, thẻ quản lý); nhập BCTC qua **Web 3 biểu mẫu + Lưu nháp + Excel chuẩn + Import XML HTKK** hỗ trợ **Thông tư 99/2025/TT-BTC** (FY2026+), **Thông tư 200/2014** (≤2025) và **Thông tư 133/2016** (SME); kiểm tra cân đối kế toán & sửa bug âm VCSH; 3 hồ sơ DN mẫu VN onboarding; duy trì kho dữ liệu SEC EDGAR cho tab "Thị trường Mỹ (SEC)" và chuẩn ngành. *(M02, M03, M04, M05)* | `identity-privacy` |
| `ml-bankruptcy-engine` | Sửa rò rỉ nhãn `kaggle_loader.py` (chỉ gắn nhãn `1` ở `year == max_year` cho DN phá sản → 490/62/57 ca out-of-time sạch); xây bộ đặc trưng 100% không thứ nguyên từ `X1–X18` (bỏ `X8`/`eps`), tách rõ luồng 1 kỳ và đa kỳ; Platt-calibrate đồng đều cả 4 mô hình (LR, RF, XGB, LGBM); Chỉ báo Độ tin cậy 4 lớp (Độ đầy đủ + OOD + Phương sai ensemble hiệu chuẩn + Kiểm toán); phân vùng PD thực (~1%/3%/8%) ánh xạ đơn điệu sang **1 Điểm Sức khỏe 0–100 duy nhất**; lớp cờ cảnh báo Dòng tiền (Cash-Flow Overlay); model registry & cache đồng bộ đa worker. *(M06, M07)* | `financial-data` |
| `risk-analytics` | Altman đủ 3 biến thể $Z / Z' / Z''$ + chặn TCTC + sửa ngưỡng động trên biểu đồ; 5 Trụ cột / 18–22 tỷ số + chú giải ngưỡng; DuPont & QoE (C02); bảng 2 cột **"Điểm Tựa & Điểm Nghẽn Tài Chính"** bằng ngôn ngữ nghiệp vụ (không sai toán SHAP, không gán nhầm RF thành XGBoost log-odds); lịch sử sức khỏe & PD 3–5 năm (khớp nối TT200 → TT99); so sánh vị thế ngành (S01); so sánh trực diện 2–4 DN (sửa 2 bug `ComparePage`, hỗ trợ cả DN tổ chức & DN SEC — C03); gắn miễn trừ trách nhiệm NĐ 88/2014/NĐ-CP & bỏ nhãn `AAA..CCC`. *(M08, M09, M10, M11, S01, C02-QoE, C03)* | `financial-data`, `ml-bankruptcy-engine` |
| `batch-and-reporting` | Thẩm định hàng loạt qua Excel bất đồng bộ (background job + xếp hạng ưu tiên rủi ro + xuất Excel tổng hợp — S03); xuất **Báo cáo Thẩm định PDF** phía server (Executive Summary, 5 trụ cột, bảng chỉ số, đóng băng `model_version`, `rule_version` & miễn trừ pháp lý — M12). *(M12, S03)* | `risk-analytics` |
| `product-ui-governance` | Tái cấu trúc SPA React (`frontend/`) theo 3 UX Rules (Quy tắc 3 giây, mọi chỉ số có ngữ cảnh, ẩn kỹ thuật ML/`ModelLab`/`ClusterMap` khỏi luồng tác nghiệp); cung cấp 2 không gian song song: **Danh bạ DN Tổ chức** và **Thị trường Mỹ (SEC)**; thống nhất 1 Điểm Sức khỏe xuyên suốt toàn ứng dụng; trang **"Phương pháp luận & Kiểm định"** minh bạch cho khách hàng B2B; tách cổng Admin/MLOps nội bộ; xóa thư mục `web/` lỗi thời. *(UX Rules, M06–M11 UI, Governance)* | `identity-privacy`, `financial-data`, `risk-analytics`, `batch-and-reporting` |

---

## Thứ tự Xây dựng (Build Order)

```text
identity-privacy
  └──► financial-data
         └──► ml-bankruptcy-engine
                └──► risk-analytics
                       └──► batch-and-reporting
                              └──► product-ui-governance
```

`Build order: identity-privacy → financial-data → ml-bankruptcy-engine → risk-analytics → batch-and-reporting → product-ui-governance`

---

## Phạm vi Ngoài V1.0 (Out of Scope / Deferred)

| Phiên bản | Tính năng trì hoãn & Lý do |
| :--- | :--- |
| **V1.1** | **S02** (Cảnh báo chuỗi suy giảm ngầm 3 kỳ), **S04** (Watchlist + Email cảnh báo tụt hạng), **S05** (Chế độ khẩu vị rủi ro chỉnh ngưỡng cắt), **S06** (Ghi chú thẩm định văn bản), **C01 mở rộng** (Stress test thuế TNDN VN + đòn bẩy Lãi suất/Tồn kho/Phải thu), **C04** (Khuyến nghị công nợ thương mại), **W02** (Nhận định tự động bằng Deterministic NLG không ảo giác). |
| **V2.0+** | **Google OAuth** (M01 — không phải blocker B2B), **S06 đính kèm chứng từ** (cần Object Storage & kiểm soát quét file), **C02 Beneish M-Score đầy đủ**, **C05** (Link chia sẻ mật khẩu — rủi ro rò rỉ BCTC nhạy cảm), **W01** (Counterfactual bảo toàn kế toán kép), **W03** (Trích xuất PDF kiểm toán Human-in-the-Loop cho đối tác bên ngoài), **W04** (Dự báo 2–3 năm — chỉ triển khai khi có panel sự kiện đa kỳ hạn phù hợp). |

---

## Danh mục Đặc tả Module (`spec/`)

- [x] `identity-privacy` → [SPEC-identity-privacy.md](SPEC-identity-privacy.md)
- [x] `financial-data` → [SPEC-financial-data.md](SPEC-financial-data.md)
- [x] `ml-bankruptcy-engine` → [SPEC-ml-bankruptcy-engine.md](SPEC-ml-bankruptcy-engine.md)
- [x] `risk-analytics` → [SPEC-risk-analytics.md](SPEC-risk-analytics.md)
- [x] `batch-and-reporting` → [SPEC-batch-and-reporting.md](SPEC-batch-and-reporting.md)
- [x] `product-ui-governance` → [SPEC-product-ui-governance.md](SPEC-product-ui-governance.md)
