# BÁO CÁO KIỂM ĐỊNH KHOA HỌC, TOÁN HỌC VÀ THUẬT TOÁN (ACADEMIC AND ALGORITHMIC REVIEW)

## 1. Tổng quan các Thành phần Học thuật và Thuật toán Được Đánh giá

Dự án **FinHealth** chứa hệ thống mô hình định lượng tài chính doanh nghiệp và học máy có giám sát / không giám sát trên dữ liệu bảng theo thời gian (longitudinal panel financial data). Cuộc kiểm định đã rà soát độc lập từng công thức toán học, thuật toán, quy trình phân chia dữ liệu và kiểm soát rò rỉ thông tin trong các module `src/finhealth/etl/` và `src/finhealth/ml/`.

---

## 2. Đánh giá Chi tiết Từng Thành phần Toán học & Thuật toán

### 2.1. Trích xuất Khái niệm Kế toán US-GAAP & Đẳng thức Bảng Cân đối (`src/finhealth/etl/xbrl_parser.py`, `annual.py`)
- **Trạng thái**: `VERIFIED` (Độ chính xác cao, tuân thủ chuẩn mực kế toán)
- **Kiểm chứng**:
  1. **Chọn ngữ cảnh kỳ báo cáo (Context & Duration Resolution)**:
     - Báo cáo năm (`10-K`): Các chỉ tiêu dòng chảy (flow facts: `revenues`, `net_income`, `operating_income`, `operating_cash_flow`, `eps_basic`, `eps_diluted`, `interest_expense`, `capex`) bắt buộc có khoảng thời gian $330 \le (\text{end} - \text{start}) \le 380$ ngày (`xbrl_parser.py:163-165`), loại bỏ triệt để các chú thích quý (quarterly footnotes) thường nằm lẫn trong tệp XBRL 10-K.
     - Báo cáo quý (`10-Q`): Yêu cầu khoảng thời gian $70 \le \text{days} \le 110$ ngày, ngoại trừ `operating_cash_flow` được phép fallback sang số liệu lũy kế đầu năm (`YTD`, $110 < \text{days} \le 380$) với nhãn `duration_basis = "YTD"` và sau đó được bóc tách thành dòng tiền quý đơn lẻ trong `src/finhealth/etl/report_periods.py:112-136` chỉ khi hai kỳ liên tiếp có cùng ngày bắt đầu năm tài chính (`start`), cùng thẻ (`tag`), cùng đơn vị (`unit`) và ngày nộp hợp lệ.
  2. **Suy diễn thận trọng theo Đẳng thức Kế toán (`_balance_fallback` tại `xbrl_parser.py:106-143`)**:
     - Khi thiếu đúng 1 trong 2 chỉ tiêu `total_liabilities` hoặc `stockholders_equity` (và đã có `total_assets` từ cùng một accession và ngày nộp), thuật toán **không** ngây thơ lấy $\text{Assets} - \text{Equity}$ nếu có lợi ích cổ đông không kiểm soát (Noncontrolling Interest / Minority Interest) hoặc vốn chủ sở hữu tạm thời (Temporary / Redeemable Equity):
       - Nếu có bất kỳ thẻ `TemporaryEquity*` nào khác 0: **Từ chối suy diễn**, giữ nguyên giá trị thiếu (`None`).
       - Nếu thiếu `total_liabilities` và có thẻ vốn chủ sở hữu hợp nhất (`StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`): Tính $\text{Liabilities} = \text{Assets} - \text{ConsolidatedEquity}$.
       - Nếu có `MinorityInterest`: Tính phần còn thiếu $= \text{Assets} - \text{KnownComponent} - \text{MinorityInterest}$.
     - Đây là cách xử lý rất chặt chẽ về mặt kế toán hợp nhất.

### 2.2. Các Tỷ số Tài chính & Mô hình Altman Z / Z″ (`src/finhealth/etl/financial_ratios.py`)
- **Trạng thái**: `VERIFIED`
- **Kiểm chứng toán học**:
  1. **Chính sách mẫu số dương và vùng đệm vốn chủ sở hữu (`_safe_div` & 5% Equity Cushion)**:
     - Mọi phép chia tài chính trong `compute_statement_ratios()` đều đặt `require_positive_den=True` và ngưỡng gần không $|\text{den}| < 10^{-9}$ trả về `None` (không bao giờ phát sinh `inf`, `-inf` hay cộng $\epsilon$ làm méo tỷ số).
     - Đối với `roe` và `debt_to_equity`, khi $\text{Assets} > 0$ nhưng $\text{StockholdersEquity} / \text{Assets} < 5\%$, hệ thống gán `meaningful_equity = None` (`financial_ratios.py:92-98`). Khi hợp lệ, `roe` được giới hạn trong $[-3.0, 3.0]$ ($\pm 300\%$) và `debt_to_equity` trong $[0.0, 20.0]$. Chính sách cố định theo miền nghiệp vụ (domain policy) này ngăn chặn hiện tượng vốn chủ sở hữu tiệm cận 0 làm nổ phương sai (exploding ratios) ở các doanh nghiệp đang tái cơ cấu nợ (như AAL, SBUX, MCD).
  2. **Biến thể Altman Z và Z″ (`compute_altman_z_score` tại `financial_ratios.py:33-74`)**:
     - Định nghĩa các biến thành phần:
       $$X_1 = \frac{\text{Current Assets} - \text{Current Liabilities}}{\text{Total Assets}}, \quad X_2 = \frac{\text{Retained Earnings}}{\text{Total Assets}}, \quad X_3 = \frac{\text{Operating Income}}{\text{Total Assets}}, \quad X_4 = \frac{\text{Book Stockholders' Equity}}{\text{Total Liabilities}}, \quad X_5 = \frac{\text{Revenues}}{\text{Total Assets}}$$
     - Với doanh nghiệp sản xuất (`SIC 2000–3999`):
       $$Z_{\text{book}} = 1.2 X_1 + 1.4 X_2 + 3.3 X_3 + 0.6 X_4 + 1.0 X_5$$
       Các ngưỡng phân vùng: `SAFE` ($> 2.99$), `GREY` ($[1.81, 2.99]$), `DISTRESS` ($< 1.81$).
     - Với doanh nghiệp phi sản xuất (các mã SIC còn lại):
       $$Z'' = 6.56 X_1 + 3.26 X_2 + 6.72 X_3 + 1.05 X_4$$
       Các ngưỡng phân vùng: `SAFE` ($> 2.60$), `GREY` ($[1.10, 2.60]$), `DISTRESS` ($< 1.10$).
     - **Lưu ý học thuật (`AUD-INFO-001`)**: Trong công trình gốc của Altman (1968) cho doanh nghiệp sản xuất niêm yết đại chúng, $X_4$ sử dụng **Giá trị thị trường của vốn chủ sở hữu (Market Value of Equity)**, trong khi hệ số $0.6$ đi với Book Equity trên đây là một biến thể xấp xỉ theo giá trị sổ sách (do dữ liệu SEC EDGAR XBRL không cung cấp giá cổ phiếu thị trường). Ngược lại, trong `src/finhealth/ml/kaggle_loader.py:104-120` (nơi bộ dữ liệu Kaggle có cột `X8` là Market Value), dự án đã sử dụng đúng Market Value cho $X_4$. Sự khác biệt này đã được ghi chú rõ ràng trong docstring và giao diện của dự án.

### 2.3. Phân tích DuPont 3 Nhân tố và Phân rã Shapley (`src/finhealth/etl/corporate_finance.py`)
- **Trạng thái**: `VERIFIED` (Chính xác tuyệt đối về mặt đại số)
- **Kiểm chứng toán học**:
  - Định nghĩa 3 nhân tố DuPont trên số dư bình quân đầu kỳ và cuối kỳ ($\bar{A}_t = \frac{A_t + A_{t-1}}{2}$, $\bar{E}_t = \frac{E_t + E_{t-1}}{2}$ với điều kiện cả hai kỳ liền kề có ngày nộp thuận chiều $t > t-1$ và $E \ge 0.05 A$):
    $$\text{ROE}_{\text{DuPont}, t} = \underbrace{\left(\frac{\text{Net Income}_t}{\text{Revenues}_t}\right)}_{m_t \text{ (Margin)}} \times \underbrace{\left(\frac{\text{Revenues}_t}{\bar{A}_t}\right)}_{u_t \text{ (Turnover)}} \times \underbrace{\left(\frac{\bar{A}_t}{\bar{E}_t}\right)}_{\ell_t \text{ (Leverage)}} = \frac{\text{Net Income}_t}{\bar{E}_t}$$
  - **Cầu nối thay đổi ROE (`dupont_bridge` tại `corporate_finance.py:94-108`)**:
    Để phân rã hiệu số $\Delta \text{ROE} = m_1 u_1 \ell_1 - m_0 u_0 \ell_0$ thành đóng góp cộng tính của 3 nhân tố mà không bị phụ thuộc thứ tự thay thế (path dependence), hàm `dupont_bridge()` lấy trung bình đóng góp biên qua tất cả $3! = 6$ hoán vị (`permutations(range(3))`) bằng `math.fsum`. Đây chính là **giá trị Shapley chính xác (Exact Shapley Value)** cho hàm tích 3 biến, đảm bảo tính chất cộng tính nghiêm ngặt:
    $$\phi_{\text{margin}} + \phi_{\text{turnover}} + \phi_{\text{leverage}} \equiv \Delta \text{ROE}_{\text{DuPont}}$$
    (Đã được kiểm chứng đối chiếu với nghiệm giải tích đóng đến sai số $< 10^{-12}$ tại `tests/unit/test_v12_business_logic.py:43-65`).

### 2.4. Thiết kế Chống Rò rỉ Dữ liệu Thời gian (Temporal Splitting, Purging & Publication Embargo)
- **Trạng thái**: `VERIFIED` trên dữ liệu SEC (`AUD-ACAD-001` ghi nhận giới hạn thiếu `filed_date` trên dữ liệu Kaggle)
- **Kiểm chứng phương pháp luận**:
  Một sai lầm phổ biến trong các nghiên cứu ML tài chính là chỉ chia tập train/test theo năm tài chính của đặc trưng ($X_t$) mà quên rằng nhãn mục tiêu của dòng đó ($Y_{t+1}$) thuộc về năm $t+1$. FinHealth đã giải quyết triệt để vấn đề này qua 4 lớp bảo vệ trong `src/finhealth/ml/splitter.py` và `registry.py`:
  1. **Dịch chuyển nội bộ theo nhóm (`build_next_period_panel`)**: Chỉ ghép cặp $(t, t+1)$ trong cùng `(company_id, form_type)` khi `next_fiscal_year == fiscal_year + 1`, khoảng cách giữa hai ngày kết thúc kỳ nằm trong $[1, 400]$ ngày, và **ngày nộp báo cáo kỳ sau phải lớn hơn nghiêm ngặt ngày nộp báo cáo kỳ trước** (`next_filed_date > filed_date`).
  2. **Cắt ngày công bố đặc trưng tập huấn luyện (`registry.py:101-103`)**: Loại bỏ mọi báo cáo năm có `fiscal_year <= train_end_year` nhưng bị nộp muộn sau ngày `31/12/train_end_year`.
  3. **Thanh lọc chân trời nhãn tập huấn luyện (`training_horizon_rows` tại `splitter.py:111-123`)**: Loại bỏ mọi dòng có `next_fiscal_year > train_end_year` hoặc `next_filed_date > YYYY-12-31`. Ví dụ khi `train_end_year = 2021`, các dòng đặc trưng năm 2021 (có nhãn ở năm 2022) vẫn được dùng cho phân cụm không giám sát (PCA/K-Means, $N = 1,047$), nhưng **bị loại bỏ hoàn toàn** khỏi tập huấn luyện có giám sát ($N = 900$, `max_train_target_year = 2021`).
  4. **Lệnh cấm vận ngày công bố tập kiểm định (`prepare_validation_test` tại `splitter.py:151-173`)**:
     - Tập validation sử dụng các dòng đặc trưng năm `2022` (có nhãn mục tiêu là kết quả năm `2023`, được công bố vào đầu năm `2024`).
     - Thời điểm hiệu chuẩn ngưỡng và xác suất (`threshold_calibration_asof`) được xác định là $\max(\text{next\_filed\_date})$ của toàn bộ các nhãn validation hợp lệ (cụ thể là `2024-03-01T00:00:00` trong `v1.2.0`).
     - Mọi quan sát trong tập test có ngày nộp báo cáo đặc trưng (`filed_date`) **trước** ngày `2024-03-01` đều bị loại bỏ (embargoed: giảm từ 293 dòng xuống 196 dòng, trong đó có 98 dòng có nhãn năm tiếp theo). Điều này đảm bảo không có bất kỳ dự báo test nào sử dụng ngưỡng phân loại hoặc hệ số Platt scaling được học từ các báo cáo validation chưa được công bố tại thời điểm dự báo.
  5. **Tiền xử lý chỉ học trên tập Train (`FinancialPreprocessor`)**: Winsorization (`RatioWinsorizer`), điền khuyết trung vị (`SimpleImputer`), chuẩn hóa (`RobustScaler`, `StandardScaler`), `PCA` và `KMeans` đều chỉ gọi `.fit()` trên tập `train` / `supervised`. Tập `validation` và `test` chỉ gọi `.transform()`. (Đã được chứng minh độc lập với sai số $< 10^{-12}$ trong `test_forensic_audit.py:393-462`).

### 2.5. Hiệu chuẩn Xác suất (Probability Calibration) và Giải thích Mô hình TreeSHAP
- **Trạng thái**: Thuật toán backend chính xác (`VERIFIED`), nhưng có lỗi bất đồng bộ dữ liệu lưu trữ trong SQLite (`AUD-DATA-001`), lỗi hiển thị UI cho Random Forest (`AUD-FUNC-001`) và lỗi vẽ biểu đồ hiệu chuẩn 07 (`AUD-FUNC-002`).
- **Kiểm chứng toán học**:
  1. **Hiệu chuẩn Logit có bù trọng số lớp (`fit_calibration` tại `distress_classifier.py:171-189`)**:
     - Khi huấn luyện trên tập dữ liệu mất cân bằng với trọng số `scale_pos_weight` ($w = N_- / N_+$), nghiệm tối ưu lý thuyết của hàm mất mát logistic dịch chuyển log-odds một lượng $\Delta = \ln(w)$.
     - Hàm `fit_calibration()` trừ đi độ lệch $\offset = \ln(\text{scale\_pos\_weight\_})$ rồi khớp hồi quy logistic một biến (Platt scaling có điều chuẩn $L_2$) trên tập validation. Nếu hệ số góc $\text{slope} > 0$, mô hình lưu phép biến đổi affine $(\text{slope}, \text{intercept} - \text{slope} \cdot \text{offset})$; nếu tập validation suy biến, mô hình fallback về nghiệm lý thuyết $(1.0, -\ln w)$.
     - Trên bộ dữ liệu thực tế `v1.2.0`, hiệu chuẩn này giúp giảm Brier score của XGBoost từ `0.073316` xuống `0.059193` và của Random Forest đạt `0.048583`.
  2. **Tính cộng tính của TreeSHAP (`ShapExplainer` tại `explainer.py:29-104`)**:
     - Với `XGBClassifier` và `LGBMClassifier`, `shap.TreeExplainer(model, model_output="raw", feature_perturbation="tree_path_dependent")` tính đóng góp trên không gian `log_odds` ($\text{base\_value} + \sum_{j=1}^{17} \phi_j = \text{raw\_margin}$, sai số cực đại $< 10^{-5}$).
     - Với `RandomForestClassifier`, `shap.TreeExplainer(model)` tính đóng góp trên không gian xác suất lớp dương ($\text{base\_value} + \sum_{j=1}^{17} \phi_j = \text{raw\_probability}$, sai số cực đại trong `v1.2.0` là $1.032 \times 10^{-15}$).
     - **Điểm lỗi phát hiện (`AUD-DATA-001`, `AUD-FUNC-001`)**: Mặc dù `explainer.py:76` và `registry.py:160-169` đã xử lý đúng cả hai không gian `"log_odds"` và `"probability"`, các bản ghi lưu trong `finhealth.sqlite3` lại được ghi từ phiên bản code cũ trước khi `explainer.py` phân nhánh `output_space` cho Random Forest, và tầng giao diện (`frontend/js/app.js`, `charts.js`, `index.html`) vẫn gắn cứng nhãn `log-odds` / `sigmoid` cho mọi mô hình.

### 2.6. Mô hình Hồi quy Kỳ tới Kết hợp Co rút về Persistence (`NextPeriodForecaster` tại `forecaster.py`)
- **Trạng thái**: `VERIFIED`
- **Kiểm chứng toán học**:
  - Với mỗi chỉ tiêu mục tiêu $y \in \{\text{roa}, \text{roe}, \text{eps}, \text{debt\_ratio}, \text{ocf\_ratio}\}$, mô hình huấn luyện hai bộ ước lượng `XGBRegressor` với hàm mục tiêu bền vững `reg:pseudohubererror`:
    1. Mô hình mức độ (`level`): Dự báo trực tiếp $\hat{y}_{t+1}^{\text{level}}$ từ $X_t$.
    2. Mô hình phần dư (`residual`): Dự báo biến thiên $\widehat{\Delta y}_{t+1}$ so với giá trị hiện tại đã cắt ngưỡng $\tilde{y}_t$, cho ra $\hat{y}_{t+1}^{\text{res}} = \tilde{y}_t + \widehat{\Delta y}_{t+1}$.
  - Trên tập validation, hàm `tune_shrinkage()` (`forecaster.py:123-148`) tìm phương pháp $m \in \{\text{level}, \text{residual}\}$ và trọng số pha trộn $w \in \{0.05, 0.10, \dots, 1.0\}$ (hoặc $w = 0$ tức giữ nguyên giá trị kỳ hiện tại — naive persistence $y_t$) sao cho tối thiểu hóa tổng tỷ số $\frac{\text{MAE}}{\text{MAE}_{\text{naive}}} + \frac{\text{RMSE}}{\text{RMSE}_{\text{naive}}}$.
  - Công thức dự báo cuối cùng khi $y_t$ quan sát được:
    $$\hat{y}_{t+1} = y_t + w \left(\hat{y}_{t+1}^{(m)} - y_t\right)$$
  - Đây là kỹ thuật shrinkage / ensemble với baseline ngây thơ (random walk / persistence) rất hợp lý trong kinh tế lượng tài chính, giúp mô hình không bao giờ tệ hơn đáng kể so với dự báo persistence đối với các chuỗi có tính tự tương quan bậc 1 cao như `debt_ratio` (trên tập validation, `debt_ratio` chọn $w = 0.0$, tức trùng khít với persistence trên tập test).

---

## 3. Đánh giá Tính Tái lập Khoa học (Scientific Reproducibility)

- **Quản lý hạt giống ngẫu nhiên (`RANDOM_SEED = 42`)**: Được truyền nhất quán tới tất cả các thành phần ngẫu nhiên (`np.random.default_rng(42)`, `PCA(random_state=42)`, `KMeans(random_state=42, n_init=10)`, `XGBClassifier(..., random_state=42, n_jobs=1)`, `LGBMClassifier(..., random_state=42, n_jobs=1)`, `RandomForestClassifier(..., random_state=42, n_jobs=1)`, `XGBRegressor(..., random_state=42, n_jobs=1)`, `LogisticRegression(..., random_state=42)`).
- **Xác minh thực nghiệm tính tái lập**:
  - Trong `tests/integration/test_forensic_audit.py::test_training_latency_and_saved_scores`, việc huấn luyện lại toàn bộ pipeline trên `sec_real_panel.parquet` với `train_end_year=2021, validation_end_year=2022` đã tái tạo **chính xác 100%** các từ điển kết quả `classification_xgboost`, `forecasting` và `split_summary` lưu trong `data/artifacts/models/v1.2.0/evaluation_report.json` (`PASSED`).
  - Trong `test_forensic_audit.py::test_training_target_permutation`, kiểm thử đối chứng âm (negative control) hoán vị ngẫu nhiên nhãn huấn luyện với seed 42 làm ROC-AUC trên tập test sụt giảm từ `0.9759` xuống `< 0.65` và $R^2$ hồi quy sụt giảm $> 0.50$, chứng minh mô hình học từ tín hiệu thực chứ không phải từ rò rỉ dữ liệu hay hằng số hardcode (`PASSED`).
