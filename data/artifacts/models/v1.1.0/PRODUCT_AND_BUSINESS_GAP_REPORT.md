# FinHealth v1.1.0 — Đánh giá chức năng sản phẩm và nghiệp vụ tài chính

Ngày kiểm tra 14/11/2026. Báo cáo đối chiếu mã nguồn, OpenAPI của ứng dụng, SQLite ở
chế độ chỉ đọc, Parquet, cache SEC và model đang active. Các luồng giao diện được đọc
đến event handler và hàm vẽ, đối chiếu với kiểm thử trình duyệt Stage 8. Lượt này gọi
các endpoint đọc và chạy lại simulator AAPL trên DB chỉ đọc. Luồng Analyze và Train
được kiểm tra qua integration tests, dùng fixture SEC và DB tạm. Các đối chiếu
thương mại dựa trên tài liệu công khai của từng nhà cung cấp.

**Công việc người dùng làm được ngay** là lọc tập công ty đang có, mở một hồ sơ,
so với median ngành, đọc dự báo kỳ kế tiếp, thử giả định và in memo. Hai khoảng
trống gây tốn thao tác nhất là so sánh đúng nhóm doanh nghiệp ngang hàng và lấy dữ
liệu ra để phân tích tiếp. Khoảng trống nghiệp vụ rõ nhất là phân biệt nợ vay với
tổng nợ phải trả, giải thích ROE bằng các cấu phần và đo mức chuyển lợi nhuận thành
dòng tiền. Dữ liệu hiện tại chỉ hỗ trợ đánh giá proxy rủi ro tài chính ở kỳ kế tiếp.

## 1. Bản đồ chức năng hiện có

### 1.1. Thu thập, chuẩn hóa, lưu trữ

| Khâu | Hành vi hiện tại | Nguồn đối chiếu |
| --- | --- | --- |
| Tra mã | `www.sec.gov/files/company_tickers.json` ánh xạ ticker sang CIK 10 chữ số. CIK hợp lệ nhập trực tiếp đi thẳng đến submissions. So ticker không phân biệt hoa thường. | [SEC client](../../../../src/finhealth/ingestion/sec_client.py) |
| Metadata | `data.sec.gov/submissions/CIK{cik}.json` cung cấp tên, ticker đầu tiên nếu có, SIC và mô tả SIC. Hệ thống suy sector theo dải SIC. Danh tính lưu theo CIK. | [SEC client](../../../../src/finhealth/ingestion/sec_client.py), [SIC helpers](../../../../src/finhealth/ingestion/schemas.py) |
| Financial facts | `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`. ETL chọn danh sách tag `us-gaap` chuẩn, đơn vị USD, riêng EPS dùng USD/share. Cache gồm `company_tickers.json`, `submissions/` và `companyfacts/` dưới `data/raw/sec_edgar/`. Companyfacts cung cấp facts chuẩn cho toàn thực thể báo cáo. | [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [constants](../../../../src/finhealth/core/constants.py) |
| Vận hành fetch | User-Agent cấu hình, cache ghi thay thế nguyên tử từng JSON, limiter chia sẻ trong một ứng dụng, mặc định cấu hình 8 request/s, giới hạn cấu hình 10 request/s. Timeout HTTP cấu hình 30 giây, tối đa 3 retry sau lượt đầu với backoff cho lỗi tạm thời. 403/404 dừng sớm. Bộ điều tiết có phạm vi tiến trình, cần điều phối riêng nếu chạy nhiều máy/worker. | [SEC client](../../../../src/finhealth/ingestion/sec_client.py), [config](../../../../src/finhealth/core/config.py), [rate limiter](../../../../src/finhealth/ingestion/rate_limiter.py) |
| Dạng hồ sơ | Parser xử lý đúng chuỗi form `10-K` và `10-Q`. Không có đường xử lý riêng 10-K/A, 10-Q/A, 8-K, 20-F hay IFRS. Khóa kỳ dùng `end`, `form` và fiscal period. FY năm trong panel lấy năm của period-end, còn `fy` theo ngữ cảnh filing nằm trong provenance. | [XBRL parser](../../../../src/finhealth/etl/xbrl_parser.py) |
| Báo cáo năm dùng cho train/API | Tìm accession và filing date xuất hiện sớm nhất cho một economic year-end dựa vào flow 330–380 ngày. Chỉ lấy facts từ accession đó, giữ thiếu nếu chưa công bố và bỏ endpoint năm mơ hồ. Một báo cáo có thể chứa cả số hiện tại và số so sánh. Cặp target công bố cùng ngày không đủ điều kiện huấn luyện. | [Annual selection](../../../../src/finhealth/etl/annual.py), [splitter](../../../../src/finhealth/ml/splitter.py) |
| Báo cáo quý qua Analyze | Phân loại Q1–Q4 theo `fp`, ưu tiên flow dạng quý 70–110 ngày theo thứ tự tag, OCF có đường fallback YTD. Flow credit cần duration và context khớp. OCF YTD giữ provenance `YTD`, chưa có bước tách về quý đơn hay dựng TTM. | [XBRL parser](../../../../src/finhealth/etl/xbrl_parser.py), [analysis service](../../../../src/finhealth/api/services.py) |
| Phạm vi ngành | SIC 6000–6799 bị chặn vì cần mô hình tài chính chuyên biệt. CIK `0001826011` bị loại theo định danh. SIC 2000–3999 dùng công thức manufacturing, SIC khác dùng Z″, kể cả SIC chưa xác định nếu đã qua scope gate. | [SIC helpers](../../../../src/finhealth/ingestion/schemas.py), [ETL](../../../../src/finhealth/etl/pipeline.py) |
| Lưu quan hệ | Bốn bảng `companies`, `financial_statements`, `financial_metrics`, `model_predictions`. Statement upsert theo công ty/FY/kỳ/form, bản filing cũ hơn hàng đang lưu không ghi đè. Metric gắn statement, forecast gắn công ty/statement nguồn/version. Một transaction SQL chứa dữ liệu và dự báo của lần Analyze. | [ORM](../../../../src/finhealth/db/models.py), [repositories](../../../../src/finhealth/db/repositories.py) |
| Lưu để train/audit | Parquet annual xuất qua PyArrow, ETL cũng có đường Spark tùy chọn. Parquet giữ cột provenance JSON. SQLite lưu provenance theo fact, API chi tiết trả provenance đầy đủ của kỳ mới nhất trong response. Active bundle đọc từ `latest.json`. | [ETL](../../../../src/finhealth/etl/pipeline.py), [registry state](../../../../src/finhealth/api/dependencies.py) |

**Danh mục 15 trường kế toán chuẩn hóa**. Một dòng có thể thiếu nhiều trường.

| Báo cáo | Trường | Tag hoặc quy tắc lựa chọn |
| --- | --- | --- |
| Balance sheet | `total_assets`, `current_assets` | `Assets`, `AssetsCurrent` |
| Balance sheet | `total_liabilities`, `current_liabilities` | `Liabilities`, `LiabilitiesCurrent` |
| Balance sheet | `stockholders_equity`, `retained_earnings` | `StockholdersEquity`, `RetainedEarningsAccumulatedDeficit` |
| Balance sheet | `cash_and_equivalents` | `CashAndCashEquivalentsAtCarryingValue`, rồi `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`. Tag thứ hai được lưu nhưng không dùng làm cash ratio. |
| Income statement | `revenues` | Thứ tự `RevenueFromContractWithCustomerExcludingAssessedTax` → `RevenueFromContractWithCustomerIncludingAssessedTax` → `Revenues` → `SalesRevenueNet`. Basis thuế theo tag gốc cần được giữ khi so sánh. |
| Income statement | `operating_income`, `net_income` | `OperatingIncomeLoss`, `NetIncomeLoss` |
| Income statement | `eps_basic`, `eps_diluted` | `EarningsPerShareBasic`, `EarningsPerShareDiluted` |
| Income statement | `interest_expense` | `InterestExpense` rồi `InterestAndDebtExpense` cùng context. Fallback thứ hai có thể bao gồm cấu phần chi phí nợ rộng hơn. |
| Cash flow | `operating_cash_flow`, `capex` | `NetCashProvidedByUsedInOperatingActivities` và `PaymentsToAcquirePropertyPlantAndEquipment`. CapEx là tiền chi mua PP&E trong phạm vi tag. |

Parser ghép balance identity khi có tài sản, đúng một trường trong liabilities
và stockholders’ equity bị thiếu, các dữ kiện liên quan cùng accession/ngày nộp,
và không thấy temporary equity khác 0. Thiếu liabilities thì ưu tiên
`A − consolidated equity` nếu có. Với minority interest phù hợp, suy
`A − trường còn lại − minority interest`. Nếu thiếu cả dữ kiện consolidated
equity lẫn minority interest, phép `A − trường còn lại` ghi rõ giả định
`no noncontrolling interests`. Không lấy consolidated equity gán thẳng cho
equity cổ đông công ty mẹ. Parquet có **498 liabilities và 33 equity suy ra**.
Provenance giữ tag, unit/currency, start/end, filed, accession, `fy` và
basis period/YTD hoặc công thức/giả định.

| Sector trong dữ liệu đang phục vụ | Số CIK | Số 10-K |
| --- | ---: | ---: |
| Manufacturing | 37 | 564 |
| Retail Trade | 16 | 255 |
| Transportation, Communications and Utilities | 13 | 207 |
| Services | 11 | 160 |
| Mining | 3 | 48 |
| Tổng, FY 2010–2025 | **80** | **1.234** |

SQLite có 1.234 metric rows, 0 báo cáo 10-Q, 80 forecast đang dùng `v1.1.0` và
80 forecast lưu từ `v1.0.0`. Panel hiện tại hoàn toàn từ SEC cache. Số công ty
và kỳ này phản ánh sample hiện hành, không đại diện toàn thị trường Mỹ.
API Analyze có thể ghi thêm cả quý lẫn năm, trong khi Company Analysis, peer và
simulator luôn dùng annual mặc định.

### 1.2. Danh mục chỉ số và ý nghĩa

Ký hiệu `A` tài sản, `L` tổng nợ phải trả, `E` book equity thuộc cổ đông,
`CA/CL` tài sản/nợ ngắn hạn, `NI` net income, `OP` operating income,
`R` doanh thu, `RE` retained earnings, `OCF` dòng tiền hoạt động. Tài sản và
vốn trong các tỷ số hiện tại là số cuối kỳ. Mẫu số yêu cầu dương và đủ xa 0
(nhỏ hơn `1e-9` là thiếu). Số thiếu/không hữu hạn không tạo vô cực.

| Nhóm nghiệp vụ | Trường | Cách tính hiện tại | Có dữ liệu / 1.234 | Kỳ mới nhất / 80 |
| --- | --- | --- | ---: | ---: |
| Sinh lời | `roa` | NI / A | 1.137 | 77 |
| Sinh lời | `roe` | NI / E, bỏ E dưới 5% A khi A dương; giới hạn [−3, 3] | 911 | 56 |
| Sinh lời | `eps` | EPS diluted nếu hữu hạn, nếu không lấy basic; USD/share | 1.199 | 79 |
| Sinh lời | `operating_margin` | OP / R | 951 | 66 |
| Sinh lời | `ebit_to_assets` | OP / A với OP làm proxy EBIT | 1.008 | 66 |
| Đòn bẩy | `debt_ratio` | L / A | 1.150 | 77 |
| Đòn bẩy | `debt_to_equity` | L / E, cùng guard equity với ROE; giới hạn [0, 20] | 959 | 58 |
| Tích lũy vốn | `retained_earnings_ratio` | RE / A | 1.220 | 80 |
| Thanh khoản | `current_ratio` | CA / CL | 1.192 | 79 |
| Thanh khoản | `cash_ratio` | Cash equivalents đủ điều kiện / CL; bỏ tag có restricted cash | 1.097 | 69 |
| Thanh khoản | `working_capital_ratio` | (CA − CL) / A | 1.191 | 79 |
| Dòng tiền, trả nợ | `ocf_ratio` | OCF / L | 1.015 | 76 |
| Dòng tiền, trả nợ | `interest_coverage` | OP / interest expense dương, giới hạn [−20×, 50×] | 745 | 15 |
| Dòng tiền, trả nợ | `fcf_to_liabilities` | (OCF − CapEx) / L khi có OCF và CapEx ≥ 0 | 683 | 50 |
| Hiệu quả | `asset_turnover` | R / A | 1.143 | 80 |

Hai biến thể Altman dùng `X1 = (CA − CL)/A`, `X2 = RE/A`, `X3 = OP/A`,
`X4 = E/L` và, với manufacturing, `X5 = R/A`. Score có 882/1.234
quan sát, 61/80 kỳ mới nhất. Thiếu cấu phần bắt buộc thì score/zone để trống.

| Biến thể | Công thức | DISTRESS / GREY / SAFE |
| --- | --- | --- |
| Manufacturing book-equity proxy | `1.2 X1 + 1.4 X2 + 3.3 X3 + 0.6 X4 + X5` | `Z < 1.81` / `1.81 ≤ Z ≤ 2.99` / `Z > 2.99` |
| Nonmanufacturing Z″ | `6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4` | `Z″ < 1.10` / `1.10 ≤ Z″ ≤ 2.60` / `Z″ > 2.60` |

| Tín hiệu thời gian | Hành vi |
| --- | --- |
| `roa_yoy_delta` | ROA kỳ hiện tại trừ ROA hàng quan sát trước |
| `roe_yoy_delta` | ROE hiện tại trừ ROE trước, có thể thiếu do guard equity |
| `debt_ratio_yoy_delta` | (L/A) hiện tại trừ kỳ trước |
| `ocf_ratio_yoy_delta` | (OCF/L) hiện tại trừ kỳ trước |
| `negative_ocf_streak` | Đếm chuỗi hàng có OCF âm theo CIK/form. OCF thiếu hoặc không âm đưa streak về 0. |

Các delta nhóm theo công ty và form, dùng hàng quan sát trước theo thời gian.
Tên `yoy` cho 10-Q không biểu thị cách nhau bốn quý. Trong dữ liệu có gap,
hiệu vẫn có thể lấy giữa hai năm không liên tiếp. Gate của target supervised
là một khâu riêng. [Công thức ratios](../../../../src/finhealth/etl/financial_ratios.py),
[tín hiệu thời gian](../../../../src/finhealth/etl/feature_engineering.py).

**Tám Sector Peer Percentiles** gồm `roa`, `roe`, `operating_margin`,
`debt_ratio`, `ocf_ratio`, `current_ratio`, `interest_coverage` và
`fcf_to_liabilities`. Mỗi doanh nghiệp đóng góp kỳ năm mới nhất với metric
đã tính. Cohort cùng sector phải có ít nhất 5 công ty, nếu không dùng toàn
universe hợp lệ. Doanh nghiệp đang xem nằm trong cohort. Mỗi chỉ tiêu bỏ
null/không hữu hạn trước khi tính median, `n_observed` và percentile
`100 × (số thấp hơn + 0,5 × số bằng)/N`. P cao của `debt_ratio` phản ánh
đòn bẩy cao. Ngưỡng 5 áp dụng theo cohort, chưa áp theo từng ratio và chưa căn
chung kỳ tài chính. Ví dụ AAPL Manufacturing có 37 công ty, ROA P92,9 trên
35 quan sát, interest coverage thiếu tại AAPL và median 9,29× từ 8 quan sát.
OXY ở Mining có 3 công ty nên dùng 80 công ty. [Tính peer](../../../../src/finhealth/api/services.py).

### 1.3. Bốn hệ con mô hình

| Hệ con | Input và mô hình | Giá trị dùng được và ranh giới |
| --- | --- | --- |
| PCA + K-Means | 12 ratios gốc. Winsor P5–P95 và median imputation fit trên train, tiếp theo RobustScaler, StandardScaler, PCA 3 chiều và K-Means 4 cụm. Rank từ centroid chuẩn hóa: ROA + ROE + OCF/L + current ratio − L/A − L/E. | PC1, PC2, PC3 và regime có nghĩa tương đối trong sample. Bốn nhãn Strong Financial Health, Stable / Moderate Leverage, Elevated Leverage / Watchlist, Financial Distress / High Risk. Bảng centroid có `health_score` nội bộ, không có điểm công ty 0–100. |
| Forecast kỳ tiếp theo | 17 inputs = 12 ratios + 5 temporal features. Mỗi target ROA, ROE, EPS, L/A, OCF/L có XGBoost Pseudo-Huber level và ứng viên residual, clip train P2.5–P97.5. Validation chọn blend với persistence. Level model dùng khi current missing. | Một vector point estimate của kỳ kế tiếp, không có prediction interval. Khi current L/A có dữ liệu, bundle này chọn trọng số cây 0. ROA/EPS/OCF vượt persistence theo cả R² và MAE, ROE cải thiện R² và MAE cao hơn nhẹ. |
| XGBoost distress và baselines | 17 inputs, class weighting khoảng 9,8406, sigmoid logit calibration và chọn threshold bằng FY2022 validation. Logistic baseline có impute/scale, Altman reference dùng `sigmoid(cutoff − Z)` với ngưỡng strict, missing neutral 0,5. | Điểm proxy FY t+1, threshold hiện hành khoảng 47,15%. Risk bands theo điểm 20%/50%/75% độc lập threshold. ROC-AUC 0,944286, Brier 0,058535 và log loss 0,205068 trên 80 nhãn test, 10 dương. |
| TreeSHAP | Tính trên inputs đã transform bằng cây XGBoost. Với một công ty, lưu raw margin, raw probability, base và 17 đóng góp, xếp driver theo trị tuyệt đối, top 10 cho chart. Global importance dùng mean absolute SHAP trên test có nhãn. | Dùng để tra input nào nâng/hạ raw margin của dự báo cụ thể. Sigmoid raw margin cho raw probability. Calibration cho xác suất hiển thị. Dấu, độ lớn và thứ tự driver không biểu thị quan hệ nhân quả hay tác động phần trăm trực tiếp. |

V1.1.0 dùng 864 hàng train feature, 748 supervised cặp forward, 79 validation
outcomes FY2022, 160 test feature rows sau embargo và 80 nhãn test. Altman,
ba credit ratios và percentile không đi vào 17 model inputs. Proxy được xây
từ tổ hợp profitability, cash flow, leverage, liquidity và OCF âm kéo dài.
Nhãn chương 7/11 có xác minh chưa có trong dataset. [Splitter](../../../../src/finhealth/ml/splitter.py),
[bundle pipeline](../../../../src/finhealth/ml/registry.py), [kết quả và toàn bộ hình](BENCHMARK_REPORT.md).

### 1.4. REST, tài liệu và tài nguyên trình duyệt

OpenAPI live có **9 đường nghiệp vụ** dưới `/api/v1`. Các GET bên dưới và
simulation đã trả 200 trong TestClient với SQLite chỉ đọc. Hai POST ghi dữ
liệu được kiểm tra ở test sau khi cô lập SEC và DB.

| Method + route | Dữ liệu/điều khiển | Phạm vi sử dụng |
| --- | --- | --- |
| GET `/api/v1/health` | status, môi trường, database_connected, active model version | Thanh trạng thái và kiểm tra vận hành |
| GET `/api/v1/dashboard/overview` | company_count, annual_statement_count | KPI tổng |
| GET `/api/v1/companies` | `limit` mặc định 100, 1–1000, `offset≥0`. Trả snapshot theo CIK. | Frontend lấy một lần với limit 1000 rồi lọc client-side |
| GET `/api/v1/companies/{identifier}` | Ticker hoặc CIK, `form_type=10-K/10-Q`. History, forecast theo version active, Altman components và peer cho annual. | Company, Risk Attribution, memo. AAPL 10-Q hiện trả history rỗng. |
| POST `/api/v1/companies/{identifier}/analyze` | `force_refresh` và `form_type` qua query. Nạp SEC, ETL, tính forecast annual nếu có model, upsert SQL. | Nút Analyze SEC filing |
| POST `/api/v1/companies/{identifier}/simulate` | Bốn shock trong JSON, trả baseline/stressed và quality flags | Các slider trong Company Analysis |
| GET `/api/v1/clusters/map` | Một điểm PCA mới nhất đã gán cụm mỗi công ty, risk, Altman | Mini PCA và PCA lớn |
| GET `/api/v1/models/evaluation` | Model version, created_at, evaluation report active | Tab benchmark, AUC header và threshold gauge |
| POST `/api/v1/models/train` | JSON `train_end_year`, `model_version` mới. Fit annual từ SQL, lưu bundle và activate. | API kỹ thuật. Contract chưa nhận validation year, nên đường train này dùng nhánh không calibration validation, threshold mặc định 0,5. Không có nút train trên web. |
| GET/HEAD tài nguyên `/static/{path}` | CSS và ES modules được static mount phục vụ | Runtime giao diện |
| GET/HEAD tài nguyên `/api/v1/figures/{filename}` | PNG xuất sẵn | Gallery và Open original |
| GET `/`, `/docs`, `/redoc`, `/openapi.json` | Dashboard, Swagger UI, ReDoc và schema | `/docs` có liên kết từ sidebar. Có route OAuth redirect mặc định của Swagger, không có cơ chế đăng nhập OAuth cho sản phẩm. |

Lỗi domain có `error_type` và `detail`, gồm 404 tài nguyên, 422 phạm vi/dữ
liệu/mô hình, 429 SEC throttling/403 upstream, 502 lỗi SEC, 503 lỗi DB.
422 validation request của FastAPI có cấu trúc riêng. Ở GET list, bản nguồn
chọn kỳ mới nhất theo period-end bất kể form, và forecast theo created_at.
Chi tiết mặc định 10-K, còn peer luôn 10-K. Khi Analyze bắt đầu có quarterly
rows, screen và deep dive có thể đang so hai kỳ khác nhau dù screen ghi
“Latest annual observations”. Cần sửa semantics hiển thị trước khi xuất hoặc
so ở chế độ annual. [Company router](../../../../src/finhealth/api/routers/companies.py),
[Model router](../../../../src/finhealth/api/routers/models.py),
[App factory](../../../../src/finhealth/api/main.py).

### 1.5. Bốn tab và các thành phần hiện có

| Vị trí | Thành phần và tương tác thực tế |
| --- | --- |
| Workspace chung | Sidebar 4 tab, hash điều hướng, phím mũi tên/Home/End cho tabs, link API documentation, trạng thái DB/version, tổng công ty/filings/test AUC, selector một công ty, chips benchmark và form ticker/CIK. Notice có nút đóng, có trạng thái loading. |
| Market Screener | 4 KPI SEC corporations, annual 10-K, elevated forward risk (HIGH + CRITICAL), test ROC-AUC. Search, 3 select filters, Reset, số hàng kết quả, bảng có micro-bar và badge risk. Sidebar có Risk Distribution, Health Regimes và mini scatter PC1×PC2. Explore mở Models & Regimes. Điểm PCA mở hồ sơ. |
| Company Analysis | Overview tên/ticker/CIK/SIC/FY, regime, Altman zone, distress, Altman Z và L/A. Ba credit cards, bảng 8 chỉ tiêu peer có progress bar khi có percentile, memo button, stress sliders, diagnostics theo template, 5 line charts, bảng actual vs forecast/delta, bảng 16 cột lịch sử 10-K. |
| Risk Attribution | Gauge bán nguyệt, marker decision threshold, màu band, diverging bars driver, raw-logit reconciliation, bảng đầy đủ 17 feature, bảng Altman X1–X5 theo biến thể. |
| Models & Regimes | PCA scatter PC1×PC2/PC3, chọn trục Y và click/focus điểm, legend bốn regime. 4 KPI train features/supervised/test/PCA variance. Bảng centroid, classification benchmark và regression benchmark. |
| Figure gallery | Sáu ảnh 300 DPI: correlation heatmap, PCA scree/clusters, ROC/PR, confusion matrices, forecast parity, global SHAP. Click xem lightbox, Open original mở file, Escape/×/click nền đóng. Reliability bins có trong report/JSON, gallery chưa có reliability curve riêng. |

[HTML dashboard](../../../../frontend/index.html),
[event handlers và render](../../../../frontend/js/app.js),
[SVG charts](../../../../frontend/js/charts.js),
[browser QA đã lưu](audit-logs/browser-qa.json).

## 2. Năm hành trình người dùng làm được ngay

### 2.1. Lọc và mở hồ sơ từ universe

1. Mở Market Screener. Search khớp một phần với ticker, tên hoặc CIK, không
   phân biệt hoa thường. Ba filter kết hợp đồng thời là risk band, PCA regime
   và FY của snapshot mới nhất. FY filter không chuyển toàn bảng về snapshot
   lịch sử. Không có bộ lọc sector/SIC, ngưỡng ratio tùy chọn hay lưu bộ lọc.
2. Mặc định sắp xếp distress giảm dần. Bấm các đầu cột Company, Distress,
   Altman Z, ROA, ROE, Debt/assets, OCF/liabilities, FY để sort. Risk badge
   không có nút sort riêng. Shift-click thêm hoặc đổi khóa phụ. Giá trị thiếu
   nằm sau giá trị có số, tie cuối theo ticker/CIK. **Reset filters** xóa
   filter và đưa sort về distress giảm dần. Chỉ báo `x of 80` cập nhật theo lọc.
3. Chọn từ dropdown hoặc chip **AAPL, MSFT, NVDA, F, AAL, CCL, LUMN, KSS**.
   Chip chỉ hiện nếu ticker có trong universe. Bấm hàng/ticker hoặc điểm PCA
   mở Company Analysis. Dropdown và chip chọn một CIK. Không có chip nào
   tự động thêm vào danh mục.
4. Đọc phân bố toàn universe hiện hành: **64 LOW, 13 MEDIUM, 1 HIGH, 2 CRITICAL**.
   Theo thứ tự cluster 0–3 có **9, 21, 27, 23** công ty. Các cột phân bố và KPI
   dùng toàn danh sách đã tải, không thay đổi denominator theo filter bảng.
   Nếu công ty chưa có score, risk distribution có thêm Unscored. Kích thước
   điểm PCA tăng theo proxy probability. Tooltip có ticker, tên, regime, score
   nếu có, Altman và tọa độ.

**Đầu ra thực tế** là danh sách để chọn hồ sơ trong tập đang phục vụ. Một issuer
có thể ở cluster 3 nhưng risk band LOW vì cụm nhận diện geometry của ratios hiện
tại, còn classifier ước lượng nhãn proxy kỳ tới.

### 2.2. Đọc hồ sơ, lịch sử và forecast

1. Mở Company Analysis. Header nhận diện công ty và kỳ. Ba card tín dụng
   hiển thị interest coverage, FCF/liabilities, cash ratio. Peer panel cho số
   công ty trong cohort, reported value, median, P-rank và N từng tỷ số.
2. Đọc **Financial signals at a glance**. Bốn câu theo template dùng regime,
   score/band, Altman/zone, leverage và OCF, delta dự báo ROA/L/A/OCF và tối đa
   ba driver SHAP. Narrative tổng hợp từ số liệu API bằng JavaScript.
3. Di chuột hoặc focus từng điểm của 5 biểu đồ **ROA, ROE, EPS, debt ratio,
   OCF ratio**. Đường thực tế liền, chấm và đoạn nối t+1 nét đứt nếu có
   current value. Khu forecast có nền nhạt. Tooltip/crosshair chỉ đúng FY và
   giá trị. Hàng có null làm đứt đường. Dữ liệu sắp theo FY nhưng khoảng trống FY
   không có hàng riêng vẫn có thể được nối giữa hai observation.
4. Đọc bảng actual, t+1 và delta. Delta ratio dùng điểm phần trăm, EPS dùng
   USD/share. Bảng lịch sử mới nhất trước gồm FY, filed, assets, liabilities,
   equity, revenue, NI, OCF, ROA, ROE, EPS, L/A, OCF/L, Altman Z, zone, accession.
   Không có click mở filing từ ô accession, bộ chọn khoảng kỳ hay forecast
   nhiều năm.

**Ví dụ AAPL** có 16 báo cáo năm, kỳ mới nhất FY2025 (filed 31/10/2025,
accession `0000320193-25-000079`). Cash ratio 0,217×, FCF/L 34,59% và
interest coverage trống. Forecast FY2026 gồm ROA 24,29%, ROE 92,38%,
EPS 6,36 USD/share, L/A 79,48% và OCF/L 32,75%. Scope này là point estimate
từ số liệu kỳ gốc. FY2026 trong forecast là kỳ mục tiêu, không xác nhận dữ
liệu thực tế FY2026 đã được nạp.

### 2.3. Truy xét tín hiệu rủi ro

1. Giữ công ty đã chọn và mở Risk Attribution. Gauge 0–100% đọc calibrated
   score và band. Marker lấy threshold của evaluation report active. Band
   LOW dưới 20%, MEDIUM từ 20% đến dưới 50%, HIGH từ 50% đến dưới 75% và
   CRITICAL từ 75%. Mốc threshold có thể nằm trong một band.
2. Biểu đồ hàm `renderShapWaterfallChart` thực tế là **thanh phân kỳ có gốc
   0**. Tối đa 10 driver, trái giảm và phải tăng raw log-odds, tooltip/focus
   cho model input, số SHAP và dấu. Đây không phải waterfall cộng dồn từng
   bước hay stress causality. Bảng sắp theo độ lớn có đủ 17 feature, giá trị
   gốc và input sau preprocessing, giá trị SHAP và hướng.
3. Dòng đối chiếu trình bày base, tổng raw log-odds, raw sigmoid và reported
   probability. AAPL raw khoảng 0,313%, calibrated khoảng 1,850%. Calibration
   có thể tăng điểm ở vùng thấp dù giảm mean trên tập test. SHAP vẫn tái dựng
   raw margin. Người dùng nên đọc báo cáo kế toán để diễn giải nguyên nhân
   kinh tế phía sau một giá trị SHAP lớn.
4. Đọc Altman score/zone, biến thể theo SIC và bảng component value, weight,
   weighted value. Nonmanufacturing có hàng X5 hiển thị excluded. Altman là
   reference phân tích riêng, điểm SAFE/DISTRESS của Altman không phải kết
   luận classifier hay trạng thái phá sản.

### 2.4. Thử shock và in hồ sơ tín dụng

| Control | Phạm vi UI | Tác động nghiệp vụ |
| --- | --- | --- |
| Revenue shock `revenue_shock_pct` | −50% đến +50% | `R′ = R × (1 + shock)` |
| Operating margin change `operating_margin_delta_pct` | −30 đến +30 pp | Cộng tuyệt đối vào `OP/R`. `OP′ = R′ × (OP/R + delta)` |
| Liabilities change `debt_change_pct` | −50% đến +100% | Cùng scale tổng liabilities và current liabilities. Không biết phần interest-bearing debt. |
| OCF shock `ocf_shock_pct` | −80% đến +80% | `OCF′ = OCF + abs(OCF) × shock`. Shock âm làm OCF âm xấu thêm. |

Mặc định 0, UI gửi fractional values sau debounce 220 ms. Thay slider lần
nữa hủy request cũ và chặn response đến muộn. **Reset scenario** đưa về 0.
Slider tắt nếu không có latest prediction. API cần annual statement và bundle.
Thiếu dữ kiện bắt buộc cho cú sốc hoặc tài sản sau điều chỉnh thấp hơn tài sản
ngắn hạn có thể trả 422. UI hiển thị lỗi của scenario.

Thay đổi OP truyền 75% sang NI, E, RE theo giả định thuế biên 25%. Lãi vay
giữ nguyên. Tài sản thay đổi bằng tổng thay đổi nợ và lợi nhuận sau thuế,
giữ số dư identity ban đầu, phần thay đổi ghi vào noncurrent assets. Cash,
current assets và CapEx đứng yên. EPS mô phỏng dựa trên số cổ phần suy ra
khi NI/EPS có dấu phù hợp. OCF shock độc lập và không tạo cầu nối working
capital hay dòng vốn. Từ bản sao statement, API tính lại 15 ratios, Altman,
timeline features, PCA, forecast, calibrated score và SHAP. P1–P99 theo train
được kiểm trên model inputs gốc trước clipping. Ngoài khoảng là cờ OOD,
result vẫn hiển thị.

UI cho **baseline → stressed** của score, Altman và regime, cùng change score
và Altman. Mở **Forecasts, SHAP changes and assumptions** để xem bảng 5
forecast, 5 SHAP shifts lớn nhất và giả định. API trả thêm hai snapshot ratios
và các tọa độ/thông số mô hình. Bản kiểm tra AAPL cho shock −15% doanh thu,
−5 pp margin, +20% liabilities, −25% OCF ghi nhận **1,850% → 4,886%**,
Altman **2,421 → khoảng 1,492**, không đổi cluster, OOD ở ROE. SQLite giữ
nguyên hash và kết quả giả lập không được lưu trong ứng dụng.

**Print / Export Credit Risk Memo** dựng memo của hồ sơ gốc đang chọn và mở
print dialog. Save as PDF phụ thuộc browser. Nội dung có tên/ticker/CIK/sector,
FY, form, accession/period-end/filed, tag/unit/accession cho tiền, interest và
CapEx, 3 credit ratios, bảng cohort medians/percentile/N, 5 chỉ tiêu tại prior
FY/latest FY/forecast, score/band/Altman/model version và tối đa 5 driver raw
log-odds. Memo ghi rõ proxy scope và basis Altman. Chưa có scenario results,
email, lưu memo server-side, covenant worksheet hay workflow ký duyệt.
[Bản in AAPL đã kiểm tra](audit-logs/aapl-credit-memo-qa.pdf).

### 2.5. Analyze SEC và kiểm tra mô hình

1. Gõ ticker hoặc CIK vào ô chung, bấm **Analyze SEC filing**. Ứng dụng báo
   loading, khóa nút chống submit lặp ở cùng UI và gọi
   `POST /api/v1/companies/{identifier}/analyze?force_refresh=true`.
2. Server normalize CIK trực tiếp hoặc tìm ticker từ cache danh mục SEC
   (fetch nếu chưa có). Tham số refresh làm mới submissions/companyfacts,
   không truyền vào resolve ticker. Ticker mới trong SEC có thể chưa nằm
   trong cache danh mục. CIK vẫn là đường xác định trực tiếp.
3. Validate metadata và chặn SIC/CIK ngoài scope trước khi lấy companyfacts.
   Sau fetch, chuẩn hóa dạng năm và quý, tính ratios/temporal features.
   Chạy model active trên annual, ghi PCA cho các statement annual có metrics
   và forecast kỳ kế tiếp của annual mới nhất. SQL commit một lượt cho company,
   statements, metrics và prediction. Raw cache ghi ở khâu fetch độc lập SQL.
4. Nếu thành công, browser refresh universe/KPI/cluster/benchmark, chọn
   CIK vừa nạp và mở Company Analysis. Lỗi ghi DB rollback SQL. Nếu SEC không
   tìm được ticker, báo 404 và không tự tìm ticker thay thế. Thiếu model vẫn
   có thể xem annual financials sau Analyze, nhưng thiếu forecast.
5. Mở **Models & Regimes** để xem benchmark active, bảng centroid và sáu
   PNG. Dùng Swagger/REST để kiểm tra health và report JSON. Analyze thêm
   dữ liệu phục vụ, không tái fit model. Đường train qua API và CLI có hành vi
   khác nhau về validation.

| Công việc CLI | Cách dùng và kết quả |
| --- | --- |
| Tái fit từ cache annual | `python -m finhealth.ml.train_cli --offline --require-real --model-version <version-moi>`. Mặc định real train đến FY2021 và validation FY2022. Có thể chọn `--train-end-year` và `--validation-end-year`. `--require-real` cần ít nhất 300 annual rows hợp lệ trong cửa sổ. |
| Tái tạo đúng tên local | Dùng `--model-version v1.1.0 --replace-existing` khi chủ động thay bản hiện hành. CLI archive bundle cũ, xuất Parquet, sync SQLite, tạo 6 PNG, in tables, lưu models/evaluation/metadata/report và cập nhật pointer. API đang chạy giữ model trong bộ nhớ, cần khởi động lại để đọc pointer CLI mới. |
| Tải dữ liệu theo universe CLI | `--mode sec-live` dùng danh sách ticker có sẵn và cần SEC contact hợp lệ. Với benchmark không offline, client có thể thử live khi cache dưới 40 công ty và có contact hợp lệ. Benchmark cache nhỏ dưới 300 rows có thể bổ sung synthetic khi không bật `--require-real`. |
| Chọn thư mục / SQL | `--data-dir` và `--database-url`. Real training mặc định SQLite cục bộ nếu không chỉ định SQL URL. Tùy chọn filesystem khác có trong settings. |

## 3. Đối sánh sản phẩm và nghiệp vụ

Trạng thái trong bảng chấm **FinHealth `v1.1.0`** theo đúng capability ở cột
trái. “Đã có đầy đủ” nghĩa luồng cụ thể được nêu đã chạy trong phạm vi annual
và universe hiện hành. Tính năng đối thủ chỉ ghi theo tài liệu công khai. Không
quy đồng khả năng giữa hai sản phẩm cùng nhóm hoặc giữa các gói trả phí.

| Capability | Trạng thái FinHealth | FinHealth hiện hành | Đối chứng công khai |
| --- | --- | --- | --- |
| Bộ kiểm tra sức khỏe, narrative và valuation visualization | Đã có một phần (Cơ bản) | Credit ratios, Altman, proxy, template diagnostics. Không có fair-value analysis, DCF hay radar tổng hợp. | Simply Wall St Snowflake **5 trục**, gồm Valuation, Future Growth, Past Performance, Financial Health, Dividend. Mỗi trục có 6 checks, nguồn của nhầm lẫn “6-axis”. [Snowflake](https://support.simplywall.st/hc/en-us/articles/360001740916-How-does-the-Snowflake-work), [Financial Health](https://support.simplywall.st/hc/en-us/articles/9812782597135-Understanding-The-Financial-Health-Section), [Valuation](https://support.simplywall.st/hc/en-us/articles/4751563581071-Understanding-the-Valuation-section-in-the-company-report) |
| Piotroski 9 tiêu chí | Chưa có (Thiếu sót) | Dữ liệu có sẵn cho một số checks, không có hàm, field hoặc view F-Score. | Tài liệu Snowflake nêu bộ checks riêng. Chưa xác minh Piotroski chính thức từ các tài liệu Simply Wall St đã xem. [Piotroski 2000](https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf) |
| Bảng head-to-head và overlay xu hướng | Chưa có (Thiếu sót) | Screener có nhiều dòng và deep dive một doanh nghiệp, chưa có cohort người dùng chọn + overlay. | Koyfin dùng watchlist/financial comparables và graph nhiều series. Fiscal.ai mô tả custom industry peers, bảng và chart so sánh performance. [Koyfin peers](https://www.koyfin.com/blog/compare-valuation-multiples-peers/), [Fiscal.ai changelog](https://fiscal.ai/changelog/), [Fiscal.ai performance](https://fiscal.ai/blog/best-tikr-alternative/) |
| 3-/5-Step DuPont dựng sẵn | Chưa có (Thiếu sót) | Có ROE, asset turnover, NI, R, A, E. UI không giải thích biến động ROE theo nhân tố. | Koyfin/Fiscal.ai có dữ liệu và công cụ ratio/formula. Chưa xác minh view DuPont chuyên biệt ở cả hai từ tài liệu đã xem. [Koyfin watchlist/screener](https://www.koyfin.com/help/release-notes/v3-67-historic-data-in-watchlist-screener/), [Fiscal.ai Help](https://fiscal.ai/help/) |
| Theo dõi quý và LTM/TTM | Đã có một phần (Cơ bản) | 10-Q có ở parser/route, DB hiện 0 và UI/forecast annual. Chưa dựng TTM. | Koyfin có FQ/LTM series. Fiscal.ai có Annual/Quarterly/LTM, Simply Wall St dùng TTM trong phân tích kết quả. [Koyfin](https://www.koyfin.com/help/release-notes/release-v3-15/), [Fiscal.ai](https://fiscal.ai/changelog/), [Simply Wall St](https://support.simplywall.st/hc/en-us/articles/9092894930831-Understanding-The-Past-Performance-Section) |
| CSV/Excel từ bảng và lịch sử | Chưa có (Thiếu sót) | Có JSON qua API, Parquet từ CLI và bản in memo. Chưa tải bảng financial từ UI. | Koyfin hỗ trợ CSV từ screener, phạm vi download tùy loại data. Fiscal.ai xuất dashboard table và hỗ trợ Excel fundamentals theo plan/coverage. [Koyfin CSV](https://www.koyfin.com/help/my-screens/), [chính sách download](https://www.koyfin.com/help/faq/can-i-download-data/), [Fiscal.ai Help](https://fiscal.ai/help/) |
| Custom watchlist, portfolio risk, alerts | Chưa có (Thiếu sót) | Chips cố định, filter phiên hiện tại, phân bố toàn universe. Không có watchlist persistence/exposure/alerts. | Koyfin có My Watchlists. Fiscal.ai có watchlist/dashboard và portfolio. RapidRatings có phân tích portfolio tùy chỉnh và alerts. CreditEdge có import portfolio, exposure và aggregate stats. [Koyfin](https://www.koyfin.com/help/my-screens/), [Fiscal.ai](https://fiscal.ai/changelog/), [RapidRatings](https://www.rapidratings.com/products-and-services-details), [CreditEdge](https://ma.moodys.com/rs/961-KCJ-308/images/CreditEdge%20-%20Glossary%20and%20Tips.pdf) |
| CHS trung hạn × FHR/risk ngắn hạn | Chưa có (Thiếu sót) | Hai trục PCA và bốn clusters không biểu thị hai horizon. | RapidRatings dùng CHS cho sức khỏe trung hạn và FHR tích hợp resiliency để biểu thị risk ngắn hạn. Quadrant vẽ CHS đối chiếu FHR, không phải hai PC và cũng không phải riêng một ratio Resilience. [Quadrant Analysis](https://fasttrackhelp.rapidratings.com/en/articles/13612877-quadrant-analysis), [FHR methodology](https://fasttrackhelp.rapidratings.com/en/articles/12640440-fhr-methodology-overview) |
| Chạy what-if cho một issuer | Đã có đầy đủ | Bốn shock thủ công, tính lại hai snapshot, forecasts và SHAP, không ghi DB. | RapidRatings mô tả mô phỏng khoản bất thường và công bố case stress tariff trên tập suppliers. Chưa xác minh bộ slider/preset tự phục vụ tương đương. CreditEdge mô tả scenario theo market inputs và EDF drivers cho công ty hoặc danh mục. [FHR report](https://fasttrackhelp.rapidratings.com/en/articles/12259392-about-the-financial-health-rating-fhr), [tariff stress case](https://info.rapidratings.com/hubfs/Documents%20and%20Collateral/PDFs/Whitepapers%20and%20Reports/Supply%20Chain%20Infographic%20Tariffs.pdf?hsLang=en), [CreditEdge guide](https://ma.moodys.com/rs/961-KCJ-308/images/CreditEdge%20-%20Glossary%20and%20Tips.pdf) |
| Peer median/rank cho một issuer | Đã có đầy đủ | Tám tỷ số annual theo sector hoặc universe fallback, median và sample count. Chưa có cohort tự chọn hoặc benchmark lịch sử. | Koyfin có peers/multiples và percentile; FHR có peer comparisons; Altman Plus mô tả industry percentile; CreditEdge có phân tích EDF theo peers trong bộ công cụ. [Koyfin peers](https://www.koyfin.com/blog/compare-valuation-multiples-peers/), [FHR report](https://fasttrackhelp.rapidratings.com/en/articles/12259392-about-the-financial-health-rating-fhr), [Altman Plus primer](https://altmanzscoreplus.weebly.com/primer.html), [CreditEdge guide](https://ma.moodys.com/rs/961-KCJ-308/images/CreditEdge%20-%20Glossary%20and%20Tips.pdf) |
| PD term structure nhiều năm | Chưa có (Thiếu sót) | Có một score proxy kỳ tài chính kế tiếp, không có legal PD horizon. | CreditEdge công bố EDF 1–10 năm theo mô hình structural có tín hiệu thị trường. Altman Plus primer mô tả PD 1–10 năm theo BRE và lịch sử default. [CreditEdge glossary](https://ma.moodys.com/rs/961-KCJ-308/images/CreditEdge%20-%20Glossary%20and%20Tips.pdf), [Altman Plus primer](https://altmanzscoreplus.weebly.com/primer.html) |
| Health score và implied rating | Chưa có (Thiếu sót) | LOW–CRITICAL, Altman zone và cluster health rank phục vụ đọc nhanh. Chưa có score issuer 0–100 hoặc AAA–D. | RapidRatings có FHR/CHS 0–100. CreditEdge có implied credit categories theo EDF. Altman Plus công bố Bond Rating Equivalent theo bản Z tương ứng và phân lớp AAA đến D. [FHR](https://www.rapidratings.com/financial-health-intelligence/the-fhr), [CreditEdge data guide](https://ma.moodys.com/rs/moodys/images/CE_DataServices%20EDF9%20User%20Guide.pdf), [Altman Plus](https://altmanzscoreplus.weebly.com/primer.html) |
| Legal Chapter 11 event registry có CIK và ngày | Chưa có (Thiếu sót) | Thiếu bảng sự kiện và căn cứ nguồn cho nhãn Chapter 7/11. | CreditEdge nói EDF dựa trên dữ liệu default toàn cầu, Altman Plus dùng lịch sử default theo hạng. Chưa xác nhận giao diện cho người dùng truy một registry chỉ gồm Chapter 11 kèm hồ sơ tòa. [CreditEdge glossary](https://ma.moodys.com/rs/961-KCJ-308/images/CreditEdge%20-%20Glossary%20and%20Tips.pdf), [Altman Plus primer](https://altmanzscoreplus.weebly.com/primer.html) |

## 4. Khoảng trống và hệ quả nghiệp vụ

### 4.1. Nghiệp vụ phân tích tài chính và tín dụng

**Piotroski F-Score** chưa được triển khai. Bốn tín hiệu về lợi nhuận và dòng
tiền, ba tín hiệu tài trợ/thanh khoản, hai tín hiệu hiệu quả tạo tổng 0–9.
Nghiên cứu gốc chọn các công ty high book-to-market để phân tích đầu tư. Việc
tính chín tín hiệu kế toán không cần giá cổ phiếu, còn việc lặp lại thí nghiệm
chọn cổ phiếu theo high book-to-market thì cần. [Piotroski 2000, mục 2.3](https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf).

| Tín hiệu được 1 điểm | Đầu vào theo định nghĩa gốc | Kiểm tra tính sẵn có và điểm cần sửa |
| --- | --- | --- |
| ROA dương | Lợi nhuận trước khoản bất thường / tài sản đầu năm > 0 | FinHealth có NI và assets. ROA hiện lấy assets cuối năm. Dùng NI GAAP cần ghi rõ phiên bản điều chỉnh và kiểm tra scope lợi nhuận. |
| OCF dương | OCF / assets đầu năm > 0 | Có OCF và assets kỳ trước. OCF/liabilities hiện không cùng denominator. |
| ΔROA dương | ROA năm t (basis đầu năm) > ROA năm t−1 (basis đầu năm) | Cần cả assets t−1 và t−2 hoặc balance đầu kỳ có bằng chứng. `roa_yoy_delta` hiện có thể đi qua FY gap. |
| Accrual thuận lợi | OCF > lợi nhuận cùng kỳ và cùng scope, với assets đầu năm dương | Có thể dựng khi đủ NI, OCF và assets. Không dùng OCF/L trừ ROA. |
| ΔLeverage giảm | Tổng nợ dài hạn gồm phần đến hạn / average assets giảm | `debt_ratio_yoy_delta` dùng tổng liabilities. Cần extract/ghép debt facts hai kỳ, cùng phạm vi lease và tránh cộng trùng. |
| ΔCurrent ratio tăng | CA/CL hiện tại > CA/CL kỳ liền trước | Có dữ liệu một phần. Bổ sung delta so đúng FY liền trước và positive denominator. |
| Không phát hành common equity | Bằng chứng không có phát hành common equity trong năm | EPS và số cổ phần bình quân không đủ. Buyback có thể che phát hành, stock split có thể đổi số cổ phần. Không có tag phát hành cũng không chứng minh bằng 0. |
| ΔGross margin tăng | Gross profit / revenue tăng | Cần gross profit hoặc revenue trừ COGS khớp scope/accrual basis. Operating margin không thay thế được. |
| ΔAsset turnover tăng | Revenue / assets đầu năm tăng | Có các trường gốc. Recompute basis đầu năm để hai kỳ so được. |

Ấn định ba trạng thái `pass/fail/unavailable`. Chỉ trả `f_score_0_9` khi chín
check có bằng chứng. Các hồ sơ thiếu vẫn xem được `observed_passes`,
`observed_checks` và lý do thiếu theo từng check. Không đổi thiếu thành fail,
pass hoặc scale `6/7` sang thang 9. Nếu cần chỉ báo dễ tính từ Δshares đã xử
lý split, đặt tên riêng `share_count_change_proxy` và giữ bên ngoài F-Score
chuẩn. Với bối cảnh hiện hành, F-Score đầy đủ khả thi **cho tập con xác minh
được**, độ phủ toàn bộ 80 công ty chưa được xác lập.

**DuPont** hiện thiếu cả 3-step và 5-step. Ba lớp đề xuất dùng
`NI/R × R/avg(A) × avg(A)/avg(E) = NI/avg(E)`, cùng scope vốn và lợi nhuận.
Cần ghi rõ đây là ROE chưa clip dùng average equity. ROE đang hiển thị dùng
ending equity và guard/cap nên hai kết quả có thể khác cả chiều biến động.
Ví dụ tính thử từ Parquet, ROE cuối kỳ AAPL giảm **164,59% → 151,91%**
giữa FY2024 và FY2025, còn ROE bình quân tăng **157,41% → 171,42%**. Trên
basis bình quân, net margin 23,97% → 26,92%, asset turnover 1,090× → 1,149×,
equity multiplier 6,025× → 5,542×. Hai nhân tố hoạt động cải thiện đồng thời
mức sử dụng đòn bẩy theo DuPont giảm. Để gán mức đóng góp vào chênh lệch ROE,
dùng phương pháp chia đều tương tác theo mọi thứ tự thay thế ba nhân tố, với
tổng đóng góp tính được khớp `ΔROE`. Không suy tỷ phần tăng trưởng ROE bằng
cách cộng thẳng phần trăm thay đổi của từng nhân tố.

5-step tách margin theo `NI/EBT × EBT/EBIT × EBIT/R`, sau đó nhân turnover
và equity multiplier. Cần EBT, EBIT và NI nhất quán về continuing operations,
NCI, kỳ, scope và quy tắc mẫu số trong năm lỗ. OP là proxy EBIT hiện tại,
interest expense riêng lẻ không tái tạo được EBT. Gác 5-step tới khi hoàn tất
mapping và kiểm số trên hồ sơ mẫu.

**Quality of Earnings và accruals** hiện chưa có. Hai quan sát để đưa vào
màn hình thẩm định là `OCF/NI` khi NI dương và
`(NI − OCF)/avg(A)` với average assets dương cùng scope. Hiển thị cả NI,
OCF và chênh lệch USD. Khi NI không dương vẫn xem chênh lệch và accruals
nếu có dữ liệu, QoE ratio để null với lý do. AAPL FY2025 tính thử cho
QoE **0,995×** và accruals **+0,146%** assets bình quân. Sloan 1996 dùng
điều chỉnh working capital (loại cash, short-term debt và taxes payable)
trừ depreciation, chia average assets. Công thức NI−OCF là **cash-flow
accruals proxy**, không tái tạo chính xác Sloan gốc. Một accrual cao có thể
do biến động vốn lưu động, acquisition, kỳ thu tiền hoặc phi tiền mặt.
Beneish cần bộ biến riêng như receivables, gross margin, asset quality,
sales growth, depreciation, SG&A, leverage và accruals. Dấu hiệu kế toán
là điểm để điều tra, không đủ căn cứ kết luận thao túng.
[Sloan 1996](https://www.cuhk.edu.hk/acy2/workshop/June2009Wasley/1996TAR%29.pdf),
[Beneish 1999](https://doi.org/10.2469/faj.v55.n5.2296).

**Interest-bearing debt và EBITDA** hiện chưa có. Total liabilities bao gồm
phải trả thương mại và nhiều nghĩa vụ phi nợ vay. Analyst chưa biết leverage
tài trợ, debt maturity, nhu cầu tái cấp vốn, EBITDA hay covenant headroom từ
`L/A`, `L/E`, `OCF/L` hoặc `FCF/L`. Hướng khả thi là trích riêng short-term
borrowings, current maturities và noncurrent debt, phân loại lease theo
scope có công bố, tách accounts payable và kiểm các tổng/subtotal trùng.
Cần xác minh nghĩa vụ bị thiếu là **không áp dụng**, **báo gộp**, hoặc **không
biết** trước khi cộng. EBITDA từ OP + D&A chỉ gọi là operating EBITDA proxy
trên cùng basis, cần reconcile D&A và operating earnings để tránh cộng hai
lần. Negative/zero EBITDA cho ratio null và hiện số tiền riêng. Net debt
dùng cash đủ điều kiện, loại restricted cash và nêu policy với short-term
investments và leases. Interest coverage đang có chỉ là screening ratio
từ `OP/interest`, chưa đo amortization schedule, DSCR hay covenant-specific EBITDA.

**Composite và rating** hiện chỉ có rank của centroid, bốn risk bands và
ba Altman zones. Một company health score 0–100 có thể tính từ số liệu nội
tại. Mapping AAA–CCC cần được trình bày là **hạng nội bộ thử nghiệm** với
từ điển công thức, ngưỡng, phiên bản, missingness và nhóm so sánh. Không gọi
là implied credit rating ngoại suy từ proxy, không gắn mặc định ngưỡng xác
suất vỡ nợ và không hiển thị D khi thiếu sự kiện đã xác minh. Equivalence
với rating agency cần sample rated issuers, default data, horizon, validation
ngoài thời gian, stability/discrimination theo ngành và kiểm chứng ordinal.
Ký hiệu chữ giống hạng agency có nguy cơ gây nhầm ngay cả khi mất tooltip.

### 4.2. Thiếu dữ liệu thao tác và luồng quyết định

| Gaps UX | Người dùng phải làm gì hiện nay | Kết quả nghiệp vụ cần có |
| --- | --- | --- |
| Head-to-head 2–4 công ty | Chuyển từng CIK và tự ghi số. Peer median không dựng tập AAPL/MSFT/HPQ hoặc AAL/DAL/UAL. | Bảng có kỳ/source per cell và overlay các điểm cùng basis. Dùng AAL/DAL/UAL để thử cùng ngành, AAPL/MSFT/HPQ để kiểm cảnh báo so khác mô hình kinh doanh. |
| Watchlist/portfolio | Quick chips chung cho mọi người. Sàng lọc không lưu và không có exposure, watch events, severity, threshold hay alert history. | Lưu theo CIK, hiển thị stale filings, counts, weighted proxy score nếu có exposure và mẫu số coverage. Một trung bình PD kể cả khi có PD thật chỉ là trung bình theo công ty/phơi nhiễm, không phải xác suất đồng thời hay xác suất danh mục có ít nhất một default. |
| Export dữ liệu | In memo, mở ảnh hoặc tự gọi JSON. Không có nút CSV của screener/history. | Xuất đúng màn hình/filters và unit, trace theo CIK + accession, có metadata model as-of. Đọc bằng Excel giữ được CIK và accession. |
| Preset stress | Tự kéo bốn slider, chỉ reset, không có baseline scenario library, timing/horizon hay history. | Presets minh bạch bốn input có thể sửa. Cú sốc lãi suất thật cần debt repricing, spread, coupon, tỷ trọng floating và pass-through; hiện chỉ mô phỏng liabilities và OCF. |
| Review và kiểm soát thao tác | Memo là bản in tức thời. Analyze và Train chưa có quyền riêng theo vai trò, audit trail của analyst, duyệt phiên bản hay background queue. | Với quy trình nhiều người, tách quyền nạp/huấn luyện và phân tích, log ai/chạy phiên bản nào, trạng thái dự thảo và reviewer, quản lý độ mới của dữ liệu. Không đặt phần này làm dependency của MVP cục bộ một người dùng. |

### 4.3. Event data, 10-Q/TTM và thị trường

| Gap | Bằng chứng và hệ quả | Điều kiện trước khi dùng |
| --- | --- | --- |
| Quý và TTM | 0 quý trong SQL kiểm tra, mặc dù raw companyfacts có thể chứa report quý và parser nhận 10-Q. Một quarterly row có thể trộn quarter income với OCF YTD. Dashboard chưa theo dõi giữa hai 10-K. | Backfill từ cache là một pilot riêng. Chuẩn hóa flow YTD → quarter increments, tính Q4 = FY trừ 9M có basis phù hợp, cộng bốn quý liên tiếp khi đủ facts. Balance sheet lấy số cuối kỳ. Căn FY/period-end/availability và checks tránh ghi đè annual. |
| Verified bankruptcy event registry | Bốn bảng SQL không lưu court case, event date, chapter hay ground truth. Distress được gán theo proxy profitability/cash/liquidity. | CIK/entity và identifier history có hiệu lực theo ngày, docket/court hoặc hồ sơ nguồn có kiểm chứng, ngày event/first public và endpoints Chapter 7/11 tách khỏi other default/delisting, cohort at risk, censoring, audit thay đổi nhãn. Facts kế toán hiện có chỉ cung cấp biến dự báo. |
| Market cap/volatility | Companyfacts chuẩn có thể chứa share counts, ứng dụng thiếu price series, return history và corporate-action adjustments. | Cần nguồn giá/returns có quyền dùng, date/giao dịch và share count khớp, điều chỉnh splits/corporate actions. Chỉ dùng khi timestamp hợp lệ cho market cap, volatility và phương pháp Merton. |

### 4.4. Kiểm kê dữ liệu trước khi cam kết v1.2.0

Đã dò 80 file companyfacts trùng CIK trong panel, trong 82 file cached trên
đĩa. Bảng ghi số period có quan sát trùng **CIK + 10-K + accession +
period-end + filed date + unit**. Flow còn phải trùng ngày bắt đầu với
basis thống nhất trong các flow chính của dòng Parquet. Balance facts phải
là instant. Đây là số **ứng viên**, chưa phải facts đã được ETL phê duyệt hoặc
coverage của ratio. Các nhóm tag có thể chồng lên nhau.

| Tag hoặc nhóm ứng viên đã thấy trong cache | CIK có tag/unit / 80 | Hàng khớp / 1.234 | Kỳ mới nhất / 80 |
| --- | ---: | ---: | ---: |
| `GrossProfit` | 45 | 455 | 27 |
| `CostOfRevenue` | 32 | 313 | 18 |
| `CostOfGoodsAndServicesSold` | 50 | 426 | 39 |
| `CostOfGoodsSold` | 36 | 245 | 0 |
| Có GrossProfit hoặc ít nhất một ứng viên cost of sales | — | 934 | 56 |
| `ShortTermBorrowings` | 39 | 239 | 16 |
| `LongTermDebtCurrent` | 64 | 555 | 43 |
| `LongTermDebtNoncurrent` | 66 | 690 | 45 |
| Đồng thời có cả 3 tags debt trên | — | 107 | 7 |
| `AccountsPayableCurrent` | 76 | 1.103 | 72 |
| `DepreciationDepletionAndAmortization` | 66 | 796 | 60 |
| `ProceedsFromIssuanceOfCommonStock` | 42 | 320 | 18 |
| `StockIssuedDuringPeriodSharesNewIssues` | 17 | 43 | 2 |
| `WeightedAverageNumberOfSharesOutstandingBasic` | 80 | 1.188 | 80 |
| `CommonStockSharesOutstanding` | 54 | 754 | 51 |

Ngay cả trước kiểm tra hai năm gross margin và phát hành, **56/80** là
trần vòng dò cho gross margin ở kỳ mới nhất trong tập tag trên. Đồng thời chỉ
có **7/80** kỳ mới nhất khớp cả ba tag debt minh họa. Việc thiếu thành phần debt
cần được đọc theo policy báo gộp và trường hợp không áp dụng, không thể tự
cộng bằng 0. Tag weighted-average shares có ở toàn bộ kỳ mới nhất nhưng
mang ý nghĩa per-share denominator, không chứng minh non-issuance.

| Hạng mục khả thi từ Parquet hiện có | Điều kiện dò số | Hàng đủ input / 1.234 | Kỳ mới nhất / 80 |
| --- | --- | ---: | ---: |
| Annual pair liền năm | Cùng CIK, FY liền, current filed > prior filed | 1.117 | 80 |
| 3-step DuPont average basis | Annual pair như trên, assets và equity đầu/cuối dương, revenue dương, NI có số | 808 | 57 |
| Cash-flow accruals trên average assets | Annual pair, assets hai đầu dương, NI và OCF có số | 942 | 76 |
| Cash-flow accruals trên ending assets | NI và OCF có số, assets cuối kỳ dương | 1.028 | 76 |
| Quality of Earnings | NI dương và OCF có số | 902 | 71 |
| Core composite 4 thành phần theo đề xuất bên dưới | ROA, OCF/L, current ratio, L/A cùng có số | 955 | 72 |

Đây là upper-bound theo kiểm tra số học và publication order. Chưa trừ thêm
case thay đổi phạm vi hợp nhất, tiền tệ, thời lượng hoặc basis. Các trường
`NetIncomeLoss`, OCF và equity thuộc cổ đông cần kiểm scope trước khi kết
luận reconciliation kinh tế. Với đối chứng point-in-time trong v1.2, cần
chọn cả current và prior sao cho sẵn có tại `as_of` và có lý do rõ ràng khi
chọn số comparative/restated khác với first-observed.

## 5. Gói nâng cấp v1.2.0 theo ROI

Đề xuất chốt MVP làm việc với cache local và annual data. Effort dưới đây là
ước tính ngày công cho một kỹ sư quen repo, đã gồm test cho thay đổi. Cần
checkpoint coverage và schema review trước các hạng mục kế toán. Compare,
CSV, presets, DuPont, QoE và composite nội bộ có đầu vào sẵn. F-Score đầy đủ
chỉ phát hành theo độ phủ được chứng minh của từng issuer-period.

| Ưu tiên | Deliverable và cách triển khai | Tiêu chí nghiệm thu | Effort ước tính |
| --- | --- | --- | ---: |
| 1 | **Head-to-head workspace**. Thêm route đọc `GET /api/v1/companies/compare?identifiers=AAPL,MSFT,ORCL` ở trước route động. Resolve 2–4 CIK khác nhau, join theo batch, tái dùng ratios và forecast hiện có. Chọn latest annual, có tùy chọn common FY khi cả cohort đủ. | AAL/DAL/UAL hiện đúng nguồn, FY, model version và số thiếu; chọn 2–4 mã, loại CIK trùng; lỗi identifier/scope rõ ràng; overlay 2–4 series với đơn vị đồng nhất, null làm ngắt đường. Không fetch SEC hoặc tạo prediction khi đọc. | 3–5 |
| 2 | **Hai CSV export**. Screener CSV dùng chính snapshot đã lọc/sort. Company 10-K History CSV xuất lịch sử theo dữ liệu API. Xuất browser Blob hoặc streaming nếu cần phân trang, không tạo bản CSV tồn tại trên server. | CSV đúng số hàng và thứ tự đang xem; kiểm quotes/newline/Unicode, locale decimal, null rỗng, CIK định dạng text, escape formula-looking text trong Excel, giữ số âm đúng dạng số. Có CIK, ticker, form, FY, period-end, filed, accession và version ở dòng dùng forecast. | 1–2 |
| 3 | **3-Step DuPont + QoE/accruals**. Thêm domain helper và panel với NI margin, asset turnover, equity multiplier, ROE average và ba đóng góp vào chênh lệch ROE nếu có hai kỳ, cộng cặp dòng NI/OCF. Dùng cùng engine cho compare, memo và CSV. | Tích bằng NI/average equity trong tolerance. Delta bridge cộng đúng tổng. Test case âm equity, NI≤0, kỳ đứt, scope và missing. UI nêu basis và không trộn với ROE hiện trong ML. Đo và công bố coverage lại. | 2–4 |
| 4 | **Macro presets một lần bấm**. Đăng ký cấu hình static có id/version và đầy đủ bốn inputs, tái dùng endpoint simulator. Nút apply điền slider và trigger một request. | Baseline và preset có JSON giống kéo tay cho cùng inputs, cờ OOD/giả định hiện rõ, cho chỉnh tiếp/reset. Cùng test isolate DB và parity với xử lý hiện có. | 1–2 |
| 5 | **Piotroski checklist và F-Score có gate**. Bổ sung danh sách nhỏ tag đã đối chiếu, dùng scoped annual projection, giữ provenance theo CIK/accession. Revenue/COGS được reconcile. Đọc equity issuance riêng. Check từng tiêu chí có pass/fail/unavailable và lý do. | Tái tính 9 check độc lập trên hồ sơ có đủ evidence. Tối thiểu test gross margin, debt subtotal overlap, stock split, buyback+issuance, missing, FY gap, comparative availability. Không hứa đủ 9 điểm với toàn bộ universe. | 4–7 |
| 6 | **Composite 0–100 và grade nội bộ**. Bốn thành phần minh bạch, cohort/policy cố định, tách response khỏi proxy. Cùng thuật toán cho mọi issuer đủ điều kiện. Hiển thị raw inputs, P-rank, N, điểm đóng góp và rating method version. | Score 0–100 và monotone cho từng phần khi cohort cố định, không đổi loại cohort giữa các cấu phần, không cấp điểm khi thiếu bắt buộc. Version và khoảng điểm nhìn thấy ngay. Label “Internal research grade” đi kèm mọi ký hiệu AAA–CCC trong web/memo/CSV. | 2–4 |

**Định dạng so sánh.** Payload đề xuất có `requested_identifiers`,
`resolved_companies`, `period_policy`, `as_of`, `active_model_version`,
`snapshots` và `series`. Annual latest mỗi issuer có thể kết thúc ngày khác
nhau. Gắn period-end và filed date theo cột, dùng chung thang đo cho cùng
metric. Với overlay EPS, ghi USD/share và lưu ý scale per issuer. Không xếp
hạng EPS tuyệt đối giữa doanh nghiệp như lợi nhuận chuẩn hóa. Forecast có
điểm marker tách khỏi lịch sử, chỉ hiển thị nếu forecast version và
source statement phù hợp. Màn hình phân biệt peer median của cohort tự chọn
với sector median có sẵn. Test cạnh tranh route `/compare` với `/{identifier}`.

**Presets đề xuất để thử UI.** Đây là giả định nội bộ, không có tần suất
xác suất hay diễn giải là named historical scenario.

| Preset | Revenue | Margin | Liabilities | OCF |
| --- | ---: | ---: | ---: | ---: |
| Suy thoái nhẹ | −10% | −3 pp | 0% | −15% |
| Doanh thu gián đoạn | −20% | −8 pp | +10% | −25% |
| Căng thẳng dòng tiền | −25% | −6 pp | +20% | −45% |

Các preset đều trong contract hiện tại. Chỉ gọi tên “cú sốc lãi suất”
khi simulator thực sự truyền lãi suất vào chi phí lãi và dòng tiền. Giữ
chi phí lãi cố định và scale liabilities không mô tả coupon repricing. Hiển
thị OOD trong compare nếu dùng dữ liệu scenario ở phiên bản sau. Stress memo
có thể bổ sung bảng assumptions + original/stressed với tag “hypothetical”
sau khi baseline export ổn định.

**Composite MVP có thể tính từ cache.** Cố định bốn thành phần là ROA,
OCF/liabilities, current ratio, và nghịch percentile của liabilities/assets.
Trọng số thử nghiệm chia đều. Định nghĩa
`S = (P_ROA + P_OCF/L + P_Current + (100 − P_L/A)) / 4` với cùng cohort
benchmark trong mọi thành phần, toàn bộ dùng hàng đủ bốn tỷ số, midpoint
ties, metadata `benchmark_as_of`. Chọn cohort sector tối thiểu 10 quan sát
đủ dữ liệu. Nếu dưới 10 thì lấy universe phù hợp, báo cỡ mẫu và scope ngay
trên UI. Cố định snapshot benchmark theo phiên bản và lưu metadata để chạy
lại. Phương án này có **72/80** issuer mới nhất đủ bốn input gốc, trước bước
xác thực context. Review sensitivity theo weighting, cohort, missingness và
thời gian. FCF, interest coverage và DuPont hiển thị cạnh điểm. Giữ các
thành phần có coverage thấp ngoài công thức MVP để score đo được cùng
khái niệm ở mọi issuer hợp lệ.

| Khoảng score thử nghiệm | Band nội bộ, tùy chọn UI |
| --- | --- |
| `[85,100]` | AAA |
| `[75,85)` | AA |
| `[65,75)` | A |
| `[55,65)` | BBB |
| `[45,55)` | BB |
| `[35,45)` | B |
| `[0,35)` | CCC |
| Thiếu input hoặc benchmark | Unscored |

Các ngưỡng minh họa là policy giao diện và cần analyst chốt. Grade chỉ nên
mở như lựa chọn nghiên cứu khi label nội bộ hiển thị cùng ký hiệu ở mọi
đầu ra. Mặc định ưu tiên tên “Financial Health Score” và nhóm mô tả bằng
chữ. Chưa đưa grade vào quyết định tín dụng, không ánh xạ SEC distress
proxy sang xác suất sự kiện pháp lý. Không dùng `1 − proxy probability` làm
điểm sức khỏe hoặc cộng cùng Altman và PCA vì dễ đếm lặp leverage/profitability.

**Ranh giới lưu trữ và phát hành.** Dùng cùng 80 raw file, đọc chọn tag
khi backfill, lưu các trường nullable nhỏ hoặc tính on demand từ các cột
đã chuẩn hóa. Không tạo bản clone cache theo cohort hay lưu CSV/PDF mỗi
lần tải. Các analytical metrics mới đứng ngoài 17 inputs hiện hành. Chỉ
tái fit và tăng model version riêng khi có mục tiêu nghiên cứu/validation
mới. Rà lại alignment annual ở screener/compare/export và giữ model pointer
nhất quán; API train cần validation giống CLI trước khi dùng để publish
model cho người dùng. Những phần cần nguồn khác hoặc lịch xử lý riêng gồm
court event registry, market data, TTM validation toàn bộ, lãi suất thực,
5-step DuPont và ratings tương đương agency. Watchlist có thể bắt đầu bằng
lưu CIK trên một browser sau v1.2, portfolio alerts đa người dùng cần
identity, exposure, lịch scan và nơi lưu alert history.

## Tệp đối chứng

Lượt kiểm tra mới từ repo root trả `All checks passed!` với `ruff check .`
và `159 passed, 1 warning in 68.17s (0:01:08)` với `pytest -v`. Warning từ
Starlette TestClient về deprecated httpx transport. Manifest SHA-256 của 88
tệp trong source, frontend, migrations và tests trùng trước/sau. Lượt
simulate dùng SQLite read-only và xác nhận hash DB trước/sau giống nhau.

- [Benchmark v1.1.0](BENCHMARK_REPORT.md), [forensic audit](FORENSIC_AUDIT_REPORT.md) và [competitive audit](COMPETITIVE_AND_DOMAIN_AUDIT.md).
- [Số liệu truy vấn và cache coverage](audit-logs/product-evidence.json).
- [Ruff nguyên văn](audit-logs/product-ruff.txt) và [pytest -v nguyên văn](audit-logs/product-pytest.txt).
