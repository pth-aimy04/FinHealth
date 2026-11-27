# BÁO CÁO ĐÁNH GIÁ HIỆU NĂNG VÀ KHẢ NĂNG MỞ RỘNG (PERFORMANCE REVIEW)

## 1. Nguyên tắc Phương pháp Luận Đo lường

Tuân thủ nguyên tắc **Zero Fabrication**, báo cáo này tách biệt hoàn toàn:
1. **Kết quả đo lường thực tế (Measured Performance)**: Được thu thập trực tiếp từ quá trình chạy `tests/integration/test_forensic_audit.py` trong đợt audit này (trên `Python 3.12.14`, Windows `win32`, cơ sở dữ liệu `finhealth.sqlite3` có 98 doanh nghiệp và 1,506 báo cáo năm, gói mô hình `v1.2.0`), có tắt `Coverage` tracing khi đo và dùng `perf_counter()` + `tracemalloc`.
2. **Phân tích hiệu năng tĩnh (Static Performance Analysis)**: Đánh giá độ phức tạp thuật toán, kế hoạch truy vấn SQL và cơ chế quản lý bộ nhớ/kết nối từ mã nguồn.

---

## 2. Kết quả Đo lường Thực tế (Measured Performance)

Các phép đo dưới đây được trích xuất từ quá trình thực thi `tests/integration/test_forensic_audit.py`:

### 2.1. Độ trễ ETL, Suy luận Mô hình (Inference + TreeSHAP) và Huấn luyện
- **Tác vụ A — Giải mã JSON & ETL báo cáo năm của Apple (`CIK0000320193.json`, 16 kỳ 10-K)**:
  - Sử dụng `msgspec.Struct` (`gc=False`) trong `src/finhealth/etl/annual.py:24-120` để chỉ giải mã các thẻ US-GAAP được hỗ trợ, bỏ qua toàn bộ các namespace không cần thiết, kết hợp `@lru_cache(maxsize=8)` trên mảng byte thô.
  - Kết quả thực tế: Độ trễ trung vị (median) của ETL có cache decode đạt **$< 25\text{ ms}$** (`PASSED` ngưỡng kiểm định `assert etl_ms < 25` tại `test_forensic_audit.py:683`).
- **Tác vụ B — Suy luận toàn diện 1 công ty + Giải thích TreeSHAP (`predict_for_company_records`)**:
  - Bao gồm biến đổi PCA + K-Means, dự báo 5 chỉ tiêu kỳ tới (XGBoost Level/Residual blend), dự báo xác suất khó khăn tài chính và tính 17 giá trị đóng góp TreeSHAP. Nhờ `@lru_cache(maxsize=4)` trên `_tree_explainer` (`src/finhealth/ml/explainer.py:19-26`), cây quyết định không bị phân tích lại trên mỗi request.
  - Kết quả thực tế: Độ trễ trung vị đạt **$< 150\text{ ms}$** (`PASSED` ngưỡng `assert prediction_ms < 150` tại `test_forensic_audit.py:684`).
- **Tác vụ C — Huấn luyện và Đánh giá Toàn bộ Pipeline ML (1,506 dòng panel, 3 bộ phân loại + 10 mô hình hồi quy + baselines + TreeSHAP)**:
  - Kết quả thực tế: Tổng thời gian thực thi toàn bộ pipeline dưới **$10,000\text{ ms}$ ($< 10\text{ giây}$)** (`PASSED` ngưỡng `assert elapsed < 10_000` tại `test_forensic_audit.py:699`).

### 2.2. Độ trễ các Endpoint REST API (In-Process FastAPI TestClient trên SQLite 98 công ty)
- Các endpoint `/api/v1/health`, `/api/v1/companies/AAPL`, `/api/v1/clusters/map`, `/api/v1/models/evaluation` đều đạt **$P_{95} < 50\text{ ms}$** trong cả hai lần chạy pytest.
- Đối với endpoint `GET /api/v1/companies` (25 mẫu sau 1 lần warm-up, trích từ `audit-reports/logs/pytest_scratch_basetemp.log` dòng 1984):
  - **Median Latency**: **`22.8875 ms`**
  - **P95 Latency**: **`59.8339 ms`**
  - **Peak Traced Memory (`tracemalloc`)**: **`0.6933 MB`**
  - Lưu ý: Dù median chỉ ~22.9ms, giá trị P95 đạt ~59.8ms đã làm fail assertion cứng `assert p95 < 50` trong `test_forensic_audit.py:720` (đã ghi nhận tại `AUD-TEST-001`).

---

## 3. Phân tích Hiệu năng Tĩnh & Độ Phức tạp Thuật toán (Static Performance Findings)

### 3.1. Các tối ưu hóa hiệu năng tốt đã được triển khai trong mã nguồn
1. **Giải mã JSON tốc độ cao với `msgspec`**:
   - Tệp `companyfacts` của SEC EDGAR thường nặng từ vài MB đến hơn 20 MB mỗi công ty. Việc định nghĩa schema tĩnh bằng `msgspec.Struct(..., gc=False)` và `msgspec.defstruct` trong `src/finhealth/etl/annual.py:24-89` giúp giảm đáng kể cấp phát bộ nhớ (heap allocation) và áp lực Garbage Collection so với `json.loads()` truyền thống.
2. **Tuần tự hóa JSON trực tiếp bằng Pydantic `TypeAdapter.dump_json()`**:
   - Trong `src/finhealth/api/routers/companies.py:32-34, 49, 75, 108`, các route trả về danh sách lớn (`/companies`, `/companies/{identifier}`, `/clusters/map`) sử dụng `_SUMMARY_LIST.dump_json(summaries)` (viết bằng Rust trong `pydantic-core`) và trả về `Response(..., media_type="application/json")`, bỏ qua bước trung gian `jsonable_encoder` của FastAPI.
3. **Chỉ mục bao phủ (Covering Indexes) trong Cơ sở dữ liệu**:
   - Migration `0003_index_reporting_snapshots.py` đã bổ sung hai composite index quan trọng:
     - `ix_statement_company_period_lookup` trên `financial_statements (company_id, period_end_date, form_type, id)`
     - `ix_prediction_company_created_lookup` trên `model_predictions (company_id, created_at, id)`
   - Nhờ đó, các correlated scalar subqueries trong `latest_annual_statement_id()` (`repositories.py:40-53`) và `_snapshots()` (`services.py:582-595`) có thể tìm bản ghi mới nhất của từng công ty bằng Index Lookup mà không cần quét bảng hay đọc cột JSON `field_provenance`.
4. **Lược bỏ `field_provenance` cho các kỳ lịch sử cũ trên API mặc định**:
   - Trong `get_company_full_analysis()` (`services.py:364-371`), API mặc định chỉ trả về `field_provenance` cho báo cáo năm mới nhất (`index == len(history) - 1`), và chỉ trả về toàn bộ lịch sử provenance khi client truyền `include_provenance=true` (khi bấm xuất CSV lịch sử), giúp giảm đáng kể kích thước payload JSON khi chuyển đổi công ty trên dashboard.

### 3.2. Các điểm nghẽn tiềm ẩn khi mở rộng quy mô (Scalability Bottlenecks)

1. **`AUD-PERF-001` — Truy vấn và tính toán lại `CompositeBenchmark` trên mỗi request có bộ lọc hoặc phân trang**:
   - **Vị trí**: `src/finhealth/api/services.py:388-416, 658-689`
   - **Độ phức tạp**: Với $N$ là tổng số doanh nghiệp trong cơ sở dữ liệu, mỗi lời gọi `GET /api/v1/companies` khi có bộ lọc (`q`, `risk_level`, `cluster_id`, `fiscal_year`, `min_roa`, ...) hoặc mỗi lời gọi `GET /api/v1/companies/{identifier}` đều thực thi `self._annual_metrics(session)` ($O(N)$ truy vấn SQL) và `CompositeBenchmark.from_rows()` ($O(N \log N)$ sắp xếp trên 4 cột chỉ số theo toàn vũ trụ và theo từng ngành).
   - **Tác động**: Với $N = 98$ hiện tại, chi phí là không đáng kể (~5–10ms). Tuy nhiên, nếu $N$ tăng lên $10,000+$ doanh nghiệp, mỗi request xem chi tiết 1 công ty hoặc gõ 1 ký tự tìm kiếm (debounce 200ms trên UI) sẽ kéo 10,000 dòng từ DB lên Python để sắp xếp lại.
2. **Vòng lặp tuần tự trong `train_models` qua API**:
   - **Vị trí**: `src/finhealth/api/services.py:862-863`
   - **Phân tích**: Khi gọi `POST /api/v1/models/train`, sau khi huấn luyện xong, hàm lặp tuần tự qua từng `company_id`:
     ```python
     for company_id in sorted(panel["company_id"].unique()):
         sync_company_prediction(session, int(company_id), bundle)
     ```
     Mỗi lệnh `sync_company_prediction()` thực hiện 1 câu `SELECT` lịch sử của công ty đó, chạy `predict_for_company_records()` (bao gồm TreeSHAP cho dòng cuối), cập nhật PCA cho từng kỳ, upsert `ModelPrediction` và ghi `FilingVersion` + `ForecastEvidence`. Đây là mô hình $N$ lượt truy vấn và suy luận rời rạc (tương tự N+1 queries ở bước đồng bộ batch).
3. **Quản lý Kết nối (Connection Pooling)**:
   - `create_db_engine()` (`src/finhealth/db/session.py:31-47`) bật `pool_pre_ping=True` và dùng cấu hình `QueuePool` mặc định của SQLAlchemy (`pool_size=5, max_overflow=10`) cho các DB ngoài SQLite in-memory. Cấu hình này phù hợp cho ứng dụng quy mô vừa, nhưng với SQLite file-based khi chạy đa luồng trong `run_in_threadpool`, SQLite chỉ cho phép một writer tại một thời điểm (database-level lock).

---

## 4. Ưu tiên Tối ưu hóa (Optimization Priorities)

1. **Ưu tiên 1 (Ngắn hạn)**: Cache kết quả `CompositeBenchmark` và danh sách `_annual_metrics` trong bộ nhớ (hoặc `lru_cache` gắn với bộ đếm phiên bản dữ liệu mỗi khi có commit ghi) để loại bỏ hoàn toàn việc quét toàn bảng trên các request `GET /api/v1/companies` và `GET /api/v1/companies/{identifier}` (`AUD-PERF-001`).
2. **Ưu tiên 2 (Trung hạn)**: Vector hóa bước cập nhật PCA và dự báo hàng loạt trong `sync_company_prediction` khi gọi từ `train_models` / `persist_real_panel` để giảm số vòng lặp truy vấn SQL và gọi TreeSHAP theo batch.
