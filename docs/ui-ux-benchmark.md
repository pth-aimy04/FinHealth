# FinHealth UI/UX Benchmark & Domain Research

## 1. Mục tiêu nghiên cứu
Tổng hợp các mẫu thiết kế (design patterns) tốt nhất từ các nền tảng phân tích tài chính doanh nghiệp, rủi ro tín dụng, dữ liệu SEC EDGAR và giải thích mô hình ML (XAI), để xây dựng giao diện **FinHealth** đạt chuẩn chuyên nghiệp (`Mode: Operate` của Impeccable + quy tắc chống "AI-slop" của tasteskill).

---

## 2. Phân tích 4 nhóm sản phẩm tham chiếu

| Nhóm sản phẩm | Đại diện tiêu biểu | Điểm mạnh UI/UX học hỏi | Áp dụng vào FinHealth |
|---|---|---|---|
| **Financial Terminals & Screening** | Koyfin, Bloomberg Terminal, Finviz | - Mật độ thông tin cao nhưng phân tầng rõ (`Glance Test`).<br>- Bảng số liệu dùng `tabular-nums`, căn phải cho số, căn trái cho text, đóng băng cột định danh (Ticker/Company).<br>- Viền mảnh 1px thay cho zebra striping gây nhiễu. | - **Company Explorer & Screener (`/companies`)**<br>- **Peer Comparison (`/compare`)** với bảng chỉ số tài chính 10-K / 10-Q. |
| **SEC Filings & Provenance** | BamSEC, Quartr | - Gắn nhãn rõ nguồn báo cáo (`10-K` FY vs `10-Q`), ngày nộp (`filing_date`), mã `accession_number`.<br>- Cho phép chuyển đổi nhanh kỳ báo cáo mà không mất ngữ cảnh. | - **Company Deep-Dive (`/companies/:id`)**: Toggle `10-K` / `10-Q`, tab **Filing Lineage & Forecast Evidence** (`/filings/{id}/forecasts`, `/report-alerts/{id}`). |
| **Credit Risk & ML Explainability** | Moody's CreditEdge, SHAP / What-If Tool, Dataiku | - Hiển thị Xác suất vỡ nợ/kiệt quệ (`distress_probability`) kèm phân loại rủi ro rõ ràng.<br>- Biểu đồ **SHAP Waterfall / Bar** đi từ Base Value, phân biệt nhân tố tăng rủi ro vs giảm rủi ro, chú thích rõ đơn vị (`output_space: log-odds`).<br>- **Stress-Test Sim Deck**: thanh trượt tác động vĩ mô/chỉ số và cập nhật delta xác suất tức thì. | - **TreeSHAP Contribution Chart** + **Stress Test Simulator** (`POST /companies/{id}/simulate`) + **ML Studio (`/models`)** hiển thị ROC/PR, Calibration & 7 publication figures (`/api/v1/figures/*`). |
| **SaaS Workspace & Governance** | Linear, Stripe Dashboard | - Sidebar điều hướng gọn, thanh tìm kiếm nhanh (`Cmd/Ctrl + K` hoặc Global Ticker Search).<br>- Trạng thái hệ thống minh bạch (Health, Ingestion Job progress, Data Quality).<br>- Quy trình xác thực & quản trị rõ ràng. | - **Workspace (`/watchlist`, `/analyses`)**, **Ingestion & Data Quality (`/ingestion`)**, **Auth & Admin (`/login`, `/admin`)**. |

---

## 3. Quy tắc Thiết kế Cốt lõi (Do's & Don'ts)

1. **Numeric Discipline:** Mọi con số tài chính, tỷ số, xác suất, log-odds phải dùng `font-variant-numeric: tabular-nums`. Giá trị thiếu (`null` / `NaN` từ backend) hiển thị tường minh là `—` (N/A), **tuyệt đối không tự quy đổi thành `0`**.
2. **Semantic Color Restraint:** Màu đỏ/xanh/hổ phách chỉ dùng cho tín hiệu rủi ro (`High Distress`, `Watch`, `Healthy`), delta tăng/giảm, và trạng thái hệ thống (`Degraded`, `Completed`, `Failed`). Không dùng màu đỏ/xanh làm màu trang trí nút bấm chung.
3. **Period & Space Honesty:** Luôn hiển thị rõ kỳ tài chính (`FY 2024 · 10-K` vs `Q3 2024 · 10-Q`) và không gian đầu ra (`log-odds` cho TreeSHAP vs `probability` cho dự báo).
4. **No AI-Slop:** Không dùng gradient tím/xanh loè loẹt, không nhồi KPI card rỗng, không dùng câu từ sáo rỗng; ưu tiên mật độ thông tin hữu ích và khả năng kiểm toán dữ liệu.
