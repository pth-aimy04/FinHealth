# Competitive & Financial Domain Gap Audit — finhealth v1.0.0

Ngày kiểm tra 2026-11-14. Phạm vi gồm source Python/JS, frontend, cache SEC, Parquet,
SQLite, saved bundle và tests. Đánh giá commercial dựa trên public vendor/author
documentation, không có thử nghiệm trực tiếp các backend commercial.

**Mức sẵn sàng hiện tại** — prototype nghiên cứu có tích hợp và kiểm thử. Provenance,
time isolation và explanation arithmetic có nhiều phần đã xác minh được. Credit
underwriting, legal Probability of Default và enterprise deployment còn cần event
data, debt-service metrics, calibration theo outcome và governance.

Bundle SHA-256 `35eef0f4d2b5b0b08c7f3be25d18bb9d0c282be22cf906dcd6ddbfe3cdbc59d9`. SQLite integrity_check=ok, foreign_key_check=[].

## Executive findings

| Phạm vi | Đã xác minh | Giới hạn có ảnh hưởng domain |
| --- | --- | --- |
| SEC provenance | 1.239 accession và 13.419 direct values khớp raw cache | 302 derived values còn dựa trên giả định không có NCI, custom/segment data chưa đọc |
| Financial institutions | 0 công ty SIC 6000–6799, không có JPM/BAC/C | Chưa có industry gating cho bank được thêm qua API |
| Temporal evaluation | 864 train features, 778 supervised, 80 validation, 150 embargoed test | 30/778 supervised rows có target publication cùng ngày feature publication |
| PCA / K-Means | 12 unit-variance inputs, 3 PC, 4 ordered clusters | Pooled cross-sector, financial ranking do dự án quy định |
| Classification | OOT ROC-AUC 0,953704, PR-AUC 0,833685, 69 rows / 9 events | Outcome là fundamentals proxy, raw weighted score chưa calibrated |
| Forecast | 5 fitted Pseudo-Huber regressors, train-only preprocessing | OCF thua persistence trên cùng 66 rows, thiếu uncertainty và statement coherence |
| TreeSHAP | Max logit additivity error 2,952546e-06 trên 69 rows | Giải thích raw score, chưa giải thích legal PD hoặc causal intervention |
| Product | 81 companies / PCA points, 81 forecasts, 4 views, 6 figures | Thiếu covenant, peer percentile, scenario, credit memo và enterprise controls |

| Tiền đề cần hiệu chỉnh | Kết quả thực tế |
| --- | --- |
| JPM/BAC/C lẫn trong 81 issuers | 0 companies và 0 rows thuộc SIC 6000–6799, JPM/BAC/C đều vắng |
| scale_pos_weight khoảng 8,18 | Fitted weight là 702/76 = 9,236842105263158 |
| Proxy prevalence 10,90% | 136/1.239 = 10,976594% |
| Nhãn là một implementation Pindado 2008 | Nhãn hiện tại fundamental_distress_v1 do dự án thiết kế, thiếu EBITDA/financial expenses và market-value condition |
| elliott-b/american-bankruptcy là authors repo | URL trả 404, authors repo xác minh được là sowide/bankruptcy_dataset |
| 62 ratios là toàn bộ RapidRatings FHR | Vendor page gắn 62 với CHS, category help page hiện nhắc 68 ratios |
| Legal default có prevalence chuẩn 0,5–3,2% | Cần mẫu, horizon, event và jurisdiction. UCI Taiwan có 220/6.819 = 3,226280% |
| EDF/DRSK cùng dùng mapping AAA–D | Tài liệu công khai thể hiện risk grades và implied rating contexts khác nhau, chưa xác minh một mapping chung |

Các hiệu chỉnh ngoài workspace được đối chiếu với
[RapidRatings](https://www.rapidratings.com/member-value/about-the-fhr),
[category guide](https://help.fhrexchange.com/en/articles/16775800-how-to-read-section-2-of-your-fhr-report),
[Pindado](https://doi.org/10.1016/j.jbusres.2007.10.006),
[authors repo](https://github.com/sowide/bankruptcy_dataset) và
[UCI](https://archive.ics.uci.edu/dataset/572/taiwanese%2Bbankruptcy%2Bprediction).

## 1. Technical & econometric direction

### 1.1 Nền tảng đã xác minh

**SEC provenance.** Tất cả 1.239 rows có data_source=cached_sec, zero synthetic,
1.239 accessions hợp regex. Có 13.419 direct values khớp tuple raw
tag/unit/start/end/filed/accn/value. 82 companyfacts files được cache, 81 CIK tạo
panel này. Đây là consistency check với raw capture. Companyfacts có scope
non-custom taxonomy và entity-wide facts nên chưa bao phủ company extension tags,
segments và notes. [SEC API scope](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

**Deduplication và contexts.** `etl/xbrl_parser.py` chọn theo tag priority, duration,
filing/accession. `etl/annual.py` chọn first-observed annual context, loại endpoints
mơ hồ trong một calendar year. Generic parser giữ latest-filing view còn training
dùng annual projection riêng. Cách này giữ availability tốt hơn random/latest
snapshot nhưng “first observed trong companyfacts” chưa chứng minh đã có original
filing lịch sử cho mọi period.

**Accounting identity.** Có 531 derived fields gồm 498 liabilities và 33 equity.
195 liabilities dùng consolidated equity, 1 liabilities và 33 equity có minority
adjustment. 302 values còn dùng giả định no noncontrolling interests. Parser giữ
missing với temporary equity hoặc nguồn balance khác accession/filed. Các scope
guards là điểm đúng, còn 302 assumptions cần kiểm evidence thêm ở cấp filing.

**OOT và purge.** Cutoff training FY 2021 và publication <=2021-12-31. 864 feature
rows fit clustering, 778 supervised rows còn sau purge. Các target fitting nằm
trong year/publication cutoff. Validation FY 2022 có 80 labels, ngày chọn threshold
2024-04-01. Embargo giữ 150 test origins từ 242 candidates, 69 có classification
labels. Calendar target shift được kiểm, còn 30 training pairs có target biết
cùng ngày origin cần xử lý trước khi nâng claim forecast. [Source splitter](../../../../src/finhealth/ml/splitter.py).

**PCA/K-Means.** 12 ratio inputs dùng training-only winsorization, median imputation,
RobustScaler rồi StandardScaler. Max absolute training mean 1,1513424e-16,
max abs(variance−1) 4,4408921e-16. Three PC và four K-Means clusters được fit
seed 42/n_init 10, cluster IDs được xếp bằng centroid health score. Các nhãn
Strong/Stable/Watchlist/Distress là ranking do dự án thiết kế. Chưa có independent
credit-risk validation cho ordinal labels. Global scaling chưa là sector normalization.

**Forecast/TreeSHAP.** Cả năm fitted objectives là reg:pseudohubererror,
feature/target bounds fit trên train. Exact raw-margin additivity được kiểm trên
cả 69 held-out rows, max error 2,952546213741414e-06. SHAP đang giải thích 17
classifier inputs đã winsorize/impute, chưa giải thích một calibrated legal PD.
[Forecaster](../../../../src/finhealth/ml/forecaster.py),
[Explainer](../../../../src/finhealth/ml/explainer.py).

### 1.2 Flaw A — Financial institutions

Query `CAST(sic_code AS INTEGER) BETWEEN 6000 AND 6799` trả 0 công ty và 0
statements. JPM/BAC/C đều không có. NULL counts của current_assets,
current_liabilities, current_ratio, working_capital_ratio và altman_z_score trong
cohort này đều là 0 trên mẫu số 0. Completeness rate của cohort rỗng là unavailable.
Sự pha trộn bank là rủi ro mở rộng, chưa là contamination đang có trong panel.

API nhận issuer mới qua SEC mà không có bank-specific dispatch hoặc industrial
model exclusion. `is_manufacturing_sic` chỉ phân nhánh 2000–3999, còn bank sẽ theo
nonmanufacturing branch và median imputation nếu đi vào flow này. Khoảng
6000–6799 còn gồm insurance/real estate, nên bank routing cần taxonomy cụ thể.
[SIC helpers](../../../../src/finhealth/ingestion/schemas.py),
[API service](../../../../src/finhealth/api/services.py).

### 1.3 Flaw B — Weighted scores, calibration và legal PD

Train có 76 positive/778 và 702 negative. Fitted scale_pos_weight=9,236842105263158,
log(weight)=2,22320006373948. Saved classifier là XGBClassifier, không có fitted
calibrator attribute. Source không có Platt/isotonic/CalibratedClassifierCV step.
`threshold_calibration_asof` chỉ ghi ngày chọn threshold, không xác nhận probability
calibration. Saved evaluation chưa lưu Brier hoặc reliability curve.
[Classifier](../../../../src/finhealth/ml/distress_classifier.py).

Trong population optimum của weighted binary log-loss, q=w*p/(1−p+w*p) và
logit(q)=logit(p)+log(w). Với w hiện tại, q=50% ứng với p≈9,7686% trong minh họa
lý tưởng này. Regularization, finite trees, sampling và drift khiến phép trừ
log(weight) chưa đủ để xác nhận probability calibration của fitted model.
Không thể suy ra mọi row đều tăng score theo cùng lượng so với một unweighted
model refit. [XGBoost tuning guide](https://xgboost.readthedocs.io/en/stable/tutorials/param_tuning.html).

| Tập | N | Min | P25 | Median | P75 | P90 | Max | Mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OOT labeled | 69 | 0.1373% | 0.8831% | 4.4190% | 20.9749% | 80.8189% | 98.3183% | 20.7550% |
| Latest SQL | 81 | 0.1033% | 0.9906% | 3.2250% | 19.5932% | 64.2772% | 98.5152% | 17.5736% |

Latest risk bands là LOW 61, MEDIUM 8, HIGH 5, CRITICAL 7, theo thresholds cứng
20%/50%/75%. Decision threshold là 36%. Chưa có map các band này vào legal PD
hoặc agency rating. Test mean score 20,7550% so với proxy event frequency 9/69
=13,0435%, chênh 7,7115 percentage points. 81 latest forecasts chưa có legal
target tương lai để đo calibration.

| Raw score bin | N | Positive | Mean score | Observed proxy rate |
| --- | --- | --- | --- | --- |
| 0.0–0.1 | 39 | 0 | 1.7109% | 0.0000% |
| 0.1–0.2 | 11 | 1 | 13.0547% | 9.0909% |
| 0.2–0.3 | 5 | 0 | 22.7814% | 0.0000% |
| 0.4–0.5 | 1 | 0 | 45.4927% | 0.0000% |
| 0.5–0.6 | 2 | 1 | 52.9754% | 50.0000% |
| 0.6–0.7 | 1 | 0 | 61.0411% | 0.0000% |
| 0.7–0.8 | 2 | 1 | 78.0719% | 50.0000% |
| 0.8–0.9 | 2 | 1 | 82.0351% | 50.0000% |
| 0.9–1.0 | 6 | 5 | 95.8601% | 83.3333% |

| Metric mới tính trong audit | Giá trị | Diễn giải |
| --- | --- | --- |
| Raw Brier | 0.065693029322 | Proper score trên proxy target, bao gồm cả discrimination |
| Constant train-prior Brier | 0.114494008274 | Baseline dùng prevalence 76/778 |
| Constant test-prior Brier | 0.113421550095 | Oracle descriptive comparator |
| Raw log loss | 0.213439450802 | Đo trên 69 labeled rows |
| Validation events | 13/80 | Quy mô nhỏ cho nonparametric isotonic |

Brier thấp hơn constant forecast không tự chứng minh calibrated probabilities.
Bins có 1–2 samples mang bất định lớn. Sigmoid là ứng viên ban đầu hợp lý ở mẫu
nhỏ, còn isotonic dễ overfit. Tập calibration cần nằm sau fitting và trước final
test theo time. Calibration bằng proxy labels chỉ tạo xác suất proxy, legal PD
cần legal-event labels đúng horizon. [Calibration documentation](https://scikit-learn.org/stable/modules/calibration.html).

### 1.4 Flaw C — Selection/survivorship và outcome definition

`SEC_UNIVERSE` là danh sách ticker chọn trước, resolve theo mapping hiện tại,
lọc cache hợp lệ. Năm broad divisions và 81 CIK chưa tạo historical market
population bao gồm đầy đủ exits, delistings và censoring. Có selection/survivorship
exposure, chưa đủ evidence để lượng hóa độ thiên lệch performance.
[Training CLI](../../../../src/finhealth/ml/train_cli.py).

Parquet không có observed `is_bankrupt` hoặc `is_distressed` column. SQL không có
event table, petition_date, court/docket hoặc insolvency-delisting source. 136
positive/1239=10,976594% đều derive từ rule sau.

```text
(ROA<0 AND (OCF/liabilities<.06 OR negative_OCF_streak>=1))
OR ((ROA<-.03 OR OCF/liabilities<0 OR operating_margin<-.05) AND liabilities/assets>.65)
OR (current_ratio<.90 AND liabilities/assets>.75 AND (ROA<.02 OR OCF/liabilities<.08))
OR negative_OCF_streak>=2
```

Missing comparisons không trigger điều kiện. Có 58 rows cùng thiếu ROA và OCF
ratio. Lookup observed labels trong code chỉ có tác dụng khi đầu vào thật sự
mang các cột nhãn. [Label source](../../../../src/finhealth/ml/splitter.py).

Pindado et al. xem bankruptcy hoặc đồng thời EBITDA thấp hơn financial expenses
hai năm liên tiếp và market value giảm giữa hai kỳ. Hai nhóm input đó hiện chưa
được lưu/khai thác. Gọi current rule là implementation Pindado 2008 sẽ vượt evidence.
[Pindado et al.,2008](https://doi.org/10.1016/j.jbusres.2007.10.006).

LEH/ENRN/HTZ/SIVB/BBBY/SAVE/WE/RAD/YELL vắng trong 81 companies. Tuy vậy, điều này
không chứng minh universe chỉ có doanh nghiệp chưa từng bankruptcy. AAL có CIK
0000006201 và rows FY 2010/2011/2012, đều proxy 1. AMR/American đã Chapter 11 ngày
2011-11-29 theo issuer announcement. FY 2010 được filed 2011-02-16 có thể dùng cho
event audit trước petition, nhưng model fit qua 2021 không hỗ trợ claim prospective
dự báo vụ 2011. [AMR announcement](https://americanairlines.gcs-web.com/news-releases/news-release-details/amr-and-american-airlines-file-chapter-11-reorganization-achieve).

Chapter 7/11 là legal events gắn debtor cụ thể. Delisting do minimum-bid-price,
M&A hay bankruptcy của subsidiary cần event class/entity mapping riêng. Lender
default definition còn có thể bao gồm failure-to-pay/distressed exchange. Tỷ lệ
0,5–3,2% thiếu horizon, population và jurisdiction không dùng làm prior cố định.
[US Courts](https://www.uscourts.gov/court-programs/bankruptcy/bankruptcy-basics).

### 1.5 Flaw D — Sector context

Financial ratios là canonical arithmetic rồi global training winsorization/
imputation/scaling. SIC/sector chưa là input trong 17 features, chưa có sector
median, percentile, Zsector hoặc sector-specific calibration.

| Ticker | FY | SIC | Operating margin | Current ratio | Liabilities/assets | Cluster |
| --- | --- | --- | --- | --- | --- | --- |
| NVDA | 2025 | 3674 | 0.624175 | 4.4399 | 0.2892 | 0 |
| WMT | 2025 | 5331 | 0.043508 | 0.8227 | NULL | 1 |
| KR | 2025 | 5411 | 0.026162 | 0.9582 | 0.8426 | 2 |
| MSFT | 2025 | 7372 | 0.456220 | 1.3534 | 0.4451 | 0 |
| AAPL | 2025 | 3571 | 0.319708 | 0.8933 | 0.7948 | 2 |
| CCL | 2025 | 4400 | 0.168395 | 0.3223 | 0.7623 | 3 |
| AAL | 2025 | 4512 | 0.026852 | 0.4983 | 1.0603 | 3 |
| LUMN | 2025 | 4813 | -0.071662 | 1.8016 | 1.0325 | 3 |
| GM | 2025 | 3711 | 0.017318 | 1.1653 | 0.7754 | 3 |

KR latest margin 2,6162%, WMT 4,3508%, MSFT 45,6220%, NVDA 62,4175%. Đây là observed
FY 2025 values, không phải threshold chung của ngành. KR và AAPL có cluster 2,
trong khi AAPL latest classifier score khoảng 0,27%. Cluster geometry và forward
proxy score cần giải thích như hai kết quả khác mục đích.

Có 44 SIC4 groups,26 singleton groups;24 SIC2 groups,6 singleton groups. Percentile
trên một công ty không có khả năng phân biệt. Peer-z khi variance 0 hoặc cohort quá
nhỏ cần unavailable. Peer cohort phải cùng as-of, accounting basis, ngành và
scale, có fallback công bố. Broad Manufacturing/Services chưa đủ.

### 1.6 Những phát hiện domain/econometric bổ sung

| Mức | Phát hiện | Evidence và hệ quả |
| --- | --- | --- |
| P0 | Nonforward training pairs | 30/778=3,8560% có next_filed_date<=filed_date, outcome đã biết cùng ngày origin |
| P0 | Ticker identity | PARA là Parabolic Technologies, CIK 0001826011, SIC 7372, tên cũ Banzai/7GC |
| P1 | Baseline Altman khác variant policy | expit(1.81−z), missingz→1.81 được áp cho cả Z và Z″, còn Z″ reference dùng 1.10/2.60 |
| P1 | XGB chưa đứng đầu AUC | Altman 0,987037, logit 0,961111, XGB 0,953704 trên cùng 69 rows |
| P1 | OCF thua persistence | Cùng 66 rows, persistence R²0,842834 và MAE 0,047505; XGB R²0,720866 và MAE 0,056292 |
| P1 | Debt benchmark nhạy outlier | PARA FY 2023 liabilities/assets 7,027458→1,107650. Loại haiPARA origins thì persistence R²0,769619, XGB 0,889964 |
| P1 | Total liabilities khác interest-bearing debt | Debt ratio hiện tại chưa là covenant debt ratio hoặc net leverage |
| P1 | Manufacturing Altman proxy | Book-equity X4 và operating-income X3 giới hạn comparability với model gốc |
| P2 | Fiscal-year naming | 152 revenue observations có SEC filing-context fy khác stored end-calendar-year |
| P2 | Generalization | 67/68 test companies đã xuất hiện supervised train |
| P2 | Forecast meaning | Năm ratio regressors độc lập, thiếu accounting reconciliation và prediction intervals |
| P2 | Sample and transformation dependence | ROE 5% guard/caps và train target clipping ảnh hưởng target availability và R² |

Ví dụ nonforward pairs gồm LUMN FY 2010/2011 cùng filing 2012-02-28 và DAL
FY 2010/2011 cùng 2012-02-10. Điều này làm yếu forecasting training objective,
chưa tự động chứng minh test chronology sai. Trong 69 scored rows, feature
filing→target period end 260–345 ngày, median 320; tới target publication 350–400
ngày, median 364.

SEC filing xác nhận Parabolic dùng PARA/PARAW từ 2026-08-07 và đổi tên sau Banzai
trong tháng 10/2026. Source values thật vẫn cần đối chiếu issuer mà người dùng
ngầm nghĩ khi chọn historical ticker. [SEC prospectus](https://www.sec.gov/Archives/edgar/data/1826011/000149315226050319/form424b4.htm).

Fiscal-context disagreement có cả early IPO comparatives như ABBV/BYND và
issuer fiscal-year naming. Đây là yêu cầu giữ hai trường riêng, chưa chứng minh
cả 152 values là sai kỳ. Generic YTD quarterly OCF cũng chưa được de-accumulate
thành single-quarter cash flow.

### 1.7 Production readiness

Limiter là asyncio.Lock trong một event loop, raw writer lock là process-local.
README yêu cầu single ingestion dispatcher cho mỗi SEC identity; chưa có
distributed limiter hoặc raw-cache multi-writer coordination. Không thấy
authentication/authorization cho mutate endpoints, tenant isolation, drift/
calibration monitoring hoặc independent model-promotion policy. Checksum joblib
giúp kiểm local artifact integrity, còn authenticity dựa trên trusted local storage.
Filesystem publish và SQL commit chưa là một cross-system transaction.
[Ingestion contract](../../../../src/finhealth/ingestion/README.md),
[API orchestration](../../../../src/finhealth/api/services.py).

## 2. Exact inventory

### 2.1 SQL data coverage

| Chỉ tiêu | Giá trị thực |
| --- | --- |
| Companies |81 |
| Statements / metrics |1239 /1239 |
| Predictions |81, toàn bộv 1.0.0 |
| Fiscal-year keys |2010–2025 |
| 10-K |1239 |
| 10-Q |0 |
| Legal-event / market-price tables |0 /0 |
| PCA assignments |1239 /1239 theo forensic verification |

| Sector / SIC division | Công ty | % universe | Statements |
| --- | --- | --- | --- |
| Manufacturing | 37 | 45.6790% | 564 |
| Retail Trade | 16 | 19.7531% | 255 |
| Transportation, Communications and Utilities | 13 | 16.0494% | 207 |
| Services | 12 | 14.8148% | 165 |
| Mining | 3 | 3.7037% | 48 |

| Fiscal-year key | Statement rows |
| --- | --- |
| 2010 | 70 |
| 2011 | 73 |
| 2012 | 72 |
| 2013 | 76 |
| 2014 | 76 |
| 2015 | 75 |
| 2016 | 76 |
| 2017 | 78 |
| 2018 | 80 |
| 2019 | 80 |
| 2020 | 79 |
| 2021 | 81 |
| 2022 | 81 |
| 2023 | 80 |
| 2024 | 81 |
| 2025 | 81 |

| Ratio | Non-NULL / 1.239 | NULL | Panel coverage | Latest coverage / 81 |
| --- | --- | --- | --- | --- |
| roa | 1142 | 97 | 92.1711% | 96.2963% |
| roe | 912 | 327 | 73.6077% | 70.3704% |
| eps | 1202 | 37 | 97.0137% | 98.7654% |
| debt_ratio | 1155 | 84 | 93.2203% | 96.2963% |
| debt_to_equity | 960 | 279 | 77.4818% | 72.8395% |
| current_ratio | 1197 | 42 | 96.6102% | 98.7654% |
| operating_margin | 954 | 285 | 76.9976% | 82.7160% |
| ocf_ratio | 1020 | 219 | 82.3245% | 95.0617% |
| working_capital_ratio | 1196 | 43 | 96.5295% | 98.7654% |
| retained_earnings_ratio | 1225 | 14 | 98.8701% | 100.0000% |
| ebit_to_assets | 1013 | 226 | 81.7595% | 82.7160% |
| asset_turnover | 1146 | 93 | 92.4939% | 100.0000% |
| altman_z_score | 887 | 352 | 71.5900% | 76.5432% |

Các NULL giữ đúng missing/domain policy. ROE/debt-equity có intentionalNULL do
equity/assets<5%, negative equity hoặc missing raw facts. Latest 81 có 19 NULL
Altman,27 DISTRESS,16 GREY,19 SAFE. Bank cohort rỗng không giải thích cácNULL này.

### 2.2 Saved ML benchmarks

| Model | Threshold | ROC-AUC | PR-AUC | Precision | Recall | F1 | F2 | TN / FP / FN / TP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| XGBoost | 0.3600 | 0.953704 | 0.833685 | 0.571429 | 0.888889 | 0.695652 | 0.800000 | 54 / 6 / 1 / 8 |
| logistic_regression | 0.5000 | 0.961111 | 0.855864 | 0.300000 | 1.000000 | 0.461538 | 0.681818 | 39 / 21 / 0 / 9 |
| altman_z_baseline | 0.5000 | 0.987037 | 0.951389 | 0.333333 | 1.000000 | 0.500000 | 0.714286 | 42 / 18 / 0 / 9 |

| Target | N | R² raw | MAE raw | RMSE raw | R² target clipped |
| --- | --- | --- | --- | --- | --- |
| roa | 66 | 0.209645 | 0.063589 | 0.178064 | 0.462866 |
| roe | 47 | 0.339740 | 0.156686 | 0.426401 | 0.735315 |
| eps | 68 | 0.678961 | 2.444006 | 3.588484 | 0.731622 |
| debt_ratio | 67 | 0.878359 | 0.060064 | 0.084434 | 0.917799 |
| ocf_ratio | 67 | 0.720903 | 0.055718 | 0.112210 | 0.892684 |

Target raw đã qua fixed ETL caps/denominator guards, còn clipped scores áp
train-fitted target bounds. Các R² này cần được đọc theo đúng target policy.
Persistence comparison dưới đây dùng cùng rows có current/next observations,
không tự impute current cho baseline.

| Target | N cùng mẫu | Persistence R² | XGB R² | Persistence MAE | XGB MAE |
| --- | --- | --- | --- | --- | --- |
| roa | 66 | -0.138224 | 0.209645 | 0.069367 | 0.063589 |
| roe | 46 | 0.444515 | 0.673829 | 0.113766 | 0.101033 |
| eps | 68 | 0.509168 | 0.678961 | 2.578824 | 2.444006 |
| debt_ratio | 67 | -8.180533 | 0.878359 | 0.136435 | 0.060064 |
| ocf_ratio | 66 | 0.842834 | 0.720866 | 0.047505 | 0.056292 |

ROE raw metric dùng 47 rows, còn same-row comparison dùng 46 rows có current ROE.
Thay đổi sample làm R² thay đổi, nên không so chéo các dòng này như cùng một test.
Forensic negative controls gồm permutedAUC 0,455556, debtR²−0,111939 và
OCFR²−0,235073, chỉ hỗ trợ workflow trên current proxy panel.
[Forensic suite](../../../../tests/integration/test_forensic_audit.py).

### 2.3 API và views

| Endpoint | Capability / evidence |
| --- | --- |
| GET / | 200, dashboard HTML |
| GET /static/* | 5 frontend files, JavaScript MIME portable trên Windows |
| GET /api/v 1/health | 200, database_connected và active v1.0.0 |
| GET /api/v 1/dashboard/overview | 200, company_count=81 và annual_statement_count=1239 |
| GET /api/v 1/companies | 200, 81 summaries, limit/offset |
| GET /api/v 1/companies/{identifier} | AAPL 200, 16 annual rows, 17 SHAP features và forecast |
| POST /api/v 1/companies/{identifier}/analyze | Route + external-HTTP-boundary tests, SEC refresh và persistence |
| GET /api/v 1/clusters/map | 200, 81 latest PCA coordinates |
| GET /api/v 1/models/evaluation | 200, actual saved evaluation report |
| POST /api/v 1/models/train | Route + persisted-panel integration test |
| GET /api/v 1/figures/* | 6 original 300-DPI PNGs qua static mount |
| simulate / peer comparison / credit memo | Chưa có domain endpoint |

Các GET được thực thi qua TestClient với SQLite và bundle thật. POST được kiểm
bằng route inspection và existing integration tests ở external HTTP boundary.
Audit không gọi live SEC refresh, train/promote model hoặc update financial facts.

| View | Đã có | Domain gap |
| --- | --- | --- |
| Market screener |Search/filter/multi-sort, risk distribution, PCA preview |Peer percentile và portfolio exposure |
| Company analysis |Annual history,5 forecast charts, delta table, diagnostic |Quarterly/TTM, covenants, coherent stress |
| Risk attribution |Gauge/threshold,17 inputs/contributions, Altman components |Calibration, PD horizon, uncertainty |
| Models & regimes |PC 1/PC 2/PC 3 drilldown, centroids, benchmarks,6 figures |Sector/bank validation và external legal benchmark |

Executive diagnostic là deterministic template từ số liệu. Chưa có generative
LLM hoặc MD&A text-understanding pipeline. Frontend phân biệt reported và model
input, có nhắc distress proxy/book-equity scope. Cụm distress probability vẫn
cần hạn chế rõ interpretation legal PD. Source/HTTP đã kiểm; visual browser QA
từ Stage 7 vẫn còn giới hạn do công cụ/browser launch bị chặn.
[App controller](../../../../frontend/js/app.js),
[Charts](../../../../frontend/js/charts.js).

### 2.4 Module inventory

| Module | Trách nhiệm theo mã thực tế |
| --- | --- |
| [src/finhealth/__init__.py](../../../../src/finhealth/__init__.py) | Package namespace |
| [src/finhealth/api/__init__.py](../../../../src/finhealth/api/__init__.py) | Package namespace |
| [src/finhealth/api/dependencies.py](../../../../src/finhealth/api/dependencies.py) | Injectable database, SEC client, settings, and thread-safe model activation state. |
| [src/finhealth/api/main.py](../../../../src/finhealth/api/main.py) | FastAPI application factory with explicit dependencies and structured domain failures. |
| [src/finhealth/api/routers/__init__.py](../../../../src/finhealth/api/routers/__init__.py) | Package namespace |
| [src/finhealth/api/routers/companies.py](../../../../src/finhealth/api/routers/companies.py) | Thin company analysis, retrieval, and cluster-map endpoints. |
| [src/finhealth/api/routers/dashboard.py](../../../../src/finhealth/api/routers/dashboard.py) | Read-only dashboard inventory derived from the connected database. |
| [src/finhealth/api/routers/health.py](../../../../src/finhealth/api/routers/health.py) | Live database and model readiness route. |
| [src/finhealth/api/routers/models.py](../../../../src/finhealth/api/routers/models.py) | Thin model evaluation and persisted-panel training routes. |
| [src/finhealth/api/schemas/__init__.py](../../../../src/finhealth/api/schemas/__init__.py) | Public API request and response contracts. |
| [src/finhealth/api/schemas/models.py](../../../../src/finhealth/api/schemas/models.py) | Explicit API contracts with recursive nonfinite-to-null normalization. |
| [src/finhealth/api/services.py](../../../../src/finhealth/api/services.py) | Repository-backed analysis orchestration; routers contain no financial or ML logic. |
| [src/finhealth/api/static.py](../../../../src/finhealth/api/static.py) | Portable static-file responses for browser ES modules and optional figure directories. |
| [src/finhealth/core/__init__.py](../../../../src/finhealth/core/__init__.py) | Package namespace |
| [src/finhealth/core/config.py](../../../../src/finhealth/core/config.py) | Validated environment settings without import-time side effects. |
| [src/finhealth/core/constants.py](../../../../src/finhealth/core/constants.py) | Canonical US-GAAP concept candidates, ordered by preference. |
| [src/finhealth/core/exceptions.py](../../../../src/finhealth/core/exceptions.py) | Domain exception hierarchy for FinHealth components. |
| [src/finhealth/core/logging.py](../../../../src/finhealth/core/logging.py) | Application-scoped logging with idempotent handler configuration. |
| [src/finhealth/db/__init__.py](../../../../src/finhealth/db/__init__.py) | Package namespace |
| [src/finhealth/db/base.py](../../../../src/finhealth/db/base.py) | Declarative metadata and shared UTC timestamp columns. |
| [src/finhealth/db/models.py](../../../../src/finhealth/db/models.py) | Typed relational contracts for financial fundamentals, features, and predictions. |
| [src/finhealth/db/repositories.py](../../../../src/finhealth/db/repositories.py) | Session-bound repositories; callers commit or roll back the complete unit of work. |
| [src/finhealth/db/session.py](../../../../src/finhealth/db/session.py) | Lazy engine creation and explicit request-scoped transaction ownership. |
| [src/finhealth/etl/__init__.py](../../../../src/finhealth/etl/__init__.py) | Package namespace |
| [src/finhealth/etl/annual.py](../../../../src/finhealth/etl/annual.py) | Select annual filing contexts shared by training and serving. |
| [src/finhealth/etl/feature_engineering.py](../../../../src/finhealth/etl/feature_engineering.py) | Group-isolated backward-looking trajectories and training-only quantile clipping. |
| [src/finhealth/etl/financial_ratios.py](../../../../src/finhealth/etl/financial_ratios.py) | Finite financial ratios and the explicitly specified book-equity Altman variants. |
| [src/finhealth/etl/pipeline.py](../../../../src/finhealth/etl/pipeline.py) | Latest-filing ETL composition, transactional repository writes, and Parquet export. |
| [src/finhealth/etl/spark_session.py](../../../../src/finhealth/etl/spark_session.py) | Optional Spark startup with an explicit UTC session timezone. |
| [src/finhealth/etl/xbrl_parser.py](../../../../src/finhealth/etl/xbrl_parser.py) | Deterministic latest-filing XBRL normalization with per-fact provenance. |
| [src/finhealth/ingestion/__init__.py](../../../../src/finhealth/ingestion/__init__.py) | Package namespace |
| [src/finhealth/ingestion/rate_limiter.py](../../../../src/finhealth/ingestion/rate_limiter.py) | Monotonic, cancellation-safe request spacing within one asyncio event loop. |
| [src/finhealth/ingestion/schemas.py](../../../../src/finhealth/ingestion/schemas.py) | Validated SEC metadata and SIC division helpers. |
| [src/finhealth/ingestion/sec_client.py](../../../../src/finhealth/ingestion/sec_client.py) | Async SEC JSON retrieval with bounded retries and validated atomic disk caches. |
| [src/finhealth/ml/__init__.py](../../../../src/finhealth/ml/__init__.py) | Package namespace |
| [src/finhealth/ml/benchmark_data.py](../../../../src/finhealth/ml/benchmark_data.py) | Explicitly synthetic accounting-consistent benchmark corpus passed through the real XBRL ETL. |
| [src/finhealth/ml/distress_classifier.py](../../../../src/finhealth/ml/distress_classifier.py) | Next-period distress XGBoost, validation-only threshold selection, and real baselines. |
| [src/finhealth/ml/evaluator.py](../../../../src/finhealth/ml/evaluator.py) | Binary and multi-target metrics with explicit undefined-data edge cases. |
| [src/finhealth/ml/explainer.py](../../../../src/finhealth/ml/explainer.py) | Real TreeSHAP contributions in XGBoost binary log-odds output space. |
| [src/finhealth/ml/forecaster.py](../../../../src/finhealth/ml/forecaster.py) | Dedicated next-period XGBoost regressors with train-only feature and target clipping. |
| [src/finhealth/ml/pca_clustering.py](../../../../src/finhealth/ml/pca_clustering.py) | Training-only PCA and financially ordered K-Means semantics. |
| [src/finhealth/ml/preprocessing.py](../../../../src/finhealth/ml/preprocessing.py) | Shared fitted financial feature contract without held-out statistic leakage. |
| [src/finhealth/ml/registry.py](../../../../src/finhealth/ml/registry.py) | Out-of-time model orchestration and immutable, atomically published artifact bundles. |
| [src/finhealth/ml/splitter.py](../../../../src/finhealth/ml/splitter.py) | Chronological panel labels, sequential targets, and out-of-time partitions. |
| [src/finhealth/ml/train_cli.py](../../../../src/finhealth/ml/train_cli.py) | Executable ETL/model benchmark runner with empirical tables, artifacts, and figures. |
| [src/finhealth/ml/visualization.py](../../../../src/finhealth/ml/visualization.py) | Headless 300-DPI evaluation figures computed from real fitted models and held-out predictions. |

Frontend gồm index.html/styles.css/js/api.js/js/charts.js/js/app.js, tổng~89,8KB.
Tests có 106 test-function definitions và 144 cases sau parametrization.

## 3. Head-to-head competitive matrix

### 3.1 Commercial systems

| Platform | Coverage / methods | Outputs / workflow | Gap của finhealth / nguồn |
| --- | --- | --- | --- |
| finhealth v1.0.0 | 81 US issuers, 12 ratios + 5 temporal inputs, pooled PCA/K-Means và XGB | Annual t+1 proxy score, 5 point forecasts, SHAP, 4 workspace, 6 figures | Chưa có legal-event PD, private-company ingestion, market data hoặc peer-relative fit |
| RapidRatings FHR | Public/private, CHS dùng 62 ratios theo product page, Resilience layer | FHR/CHS/EPD, historical reports, operating strength và short-term capacity | K-Means hiện tại chưa tách CHS/resilience. [Vendor](https://www.rapidratings.com/member-value/about-the-fhr) |
| Moody’s CreditEdge | Structural asset value, default point và asset volatility | EDF term structure 1–10 năm theo official glossary, model-implied risk context | Thiếu market equity/volatility, empirical event mapping và term structure. [Glossary](https://ma.moodys.com/rs/961-KCJ-308/images/CreditEdge%20-%20Glossary%20and%20Tips.pdf) |
| Bloomberg DRSK | Fundamental inputs và quantitative issuer-credit models theo overview | PD nhiều tenor, implied CDS, history và term-structure screens | Thiếu multi-tenor PD và credit-spread calibration. [Vendor](https://data.bloomberglp.com/professional/sites/10/2093894.pdf) |
| Koyfin | Quarterly/annual financial statements, templates và global market data | Peer tables, watchlists, financial research và consensus | Thiếu quarterly/TTM workflow và peer context. [Financials](https://www.koyfin.com/features/financial-analysis/), [Peers](https://www.koyfin.com/blog/compare-valuation-multiples-peers/) |
| Simply Wall St | TTM performance và snowflake/checklist methodology | Company-level research, financial-health assessments và visual narrative | Template summary của finhealth còn ít checks và thiếu TTM. [Snowflake](https://support.simplywall.st/hc/en-us/articles/360001740916-How-does-the-Snowflake-work), [TTM](https://support.simplywall.st/hc/en-us/articles/9092894930831-Understanding-The-Past-Performance-Section) |

RapidRatings tách medium-term Core Health và short-term Resilience. Four
K-Means colors/gauge hiện tại chưa tạo hai trục domain đó. [Methodology](https://fasttrackhelp.rapidratings.com/en/articles/12640440-fhr-methodology-overview).
Moody’s glossary mô tả EDF horizons 1–10 năm. Bloomberg official overview xác nhận
multi-tenor PD/implied CDS, còn exact production version của hybrid structural
specification chưa được xác minh trong tài liệu public đọc được. Chưa có căn cứ
gán cùng architecture/rating mapping cho EDF và DRSK.
[Bloomberg DRSK example](https://assets.bbhub.io/professional/sites/10/RMB-Bond-Solutions.pdf).
Vendor accuracy claims và AUC của finhealth khác outcome/mẫu, nên ma trận mô tả
capabilities thay vì một numerical commercial-model leaderboard.

### 3.2 Open-source và academic systems

| Repository / benchmark | Capability xác minh | Khoảng cách / lưu ý tích hợp | Nguồn |
| --- | --- | --- | --- |
| dgunning/edgartools | Multi-period statement stitching và dimension-aware financials | finhealth mới chọn subset entity-wide companyfacts, chưa có segments/notes/full-text | [XBRL](https://edgartools.readthedocs.io/en/stable/api/xbrl/), [Dimensions](https://edgartools.readthedocs.io/en/stable/xbrl/concepts/dimension-handling/) |
| jadchaar/sec-edgar-downloader | Full-filing acquisition theo ticker/CIK/form | Downloader là lớp lấy tài liệu, statement stitching và NLP cần xử lý tiếp | [Repository](https://github.com/jadchaar/sec-edgar-downloader) |
| sowide/bankruptcy_dataset | CSV thực có 8.971 companies, 78.682 rows, 18 financial inputs | 609 failed companies, status_label cố định theo company, cần kiểm task/horizon | [CSV](https://raw.githubusercontent.com/sowide/bankruptcy_dataset/main/american_bankruptcy_dataset.csv) |
| UCI / TEJ Taiwan | 6.819 rows, 95 predictors, 220 positives, years 1999–2009 theo metadata | Khác jurisdiction/schema, flat matrix thiếu company/time key cho purged SEC-style split | [UCI](https://archive.ics.uci.edu/dataset/572/taiwanese%2Bbankruptcy%2Bprediction) |
| ProsusAI/finBERT | Financial text sentiment classifier | Chưa có Item 7/1A extraction hay sentiment fusion trong finhealth | [Repository](https://github.com/ProsusAI/finBERT) |
| sowide/Multi-modal-bankrutpcy | Annual-report Items 1/5/7 và financial time series | Tham khảo text/tabular alignment và multimodal ablation | [Authors](https://github.com/sowide/Multi-modal-bankrutpcy) |

**US benchmark version/task audit.** elliott-b/american-bankruptcy trả 404.
Authors repo được xác minh là sowide/bankruptcy_dataset. Đã đọc CSV live trong
memory, có 78.682 rows,8.971 company IDs,609 failed firms,5.220 failed rows và
73.462 alive rows. Mỗi company có đúng một status_label xuyên mọi fyear.
Tỷ lệ 6,6343% failed rows vì thế chưa là annual default incidence. README và
paper authors hiện ghi 8.262 companies, còn CSV hiện tại có 8.971, cần khóa version/
hash khi so sánh. [Authors README](https://raw.githubusercontent.com/sowide/bankruptcy_dataset/main/README.md),
[CSV](https://raw.githubusercontent.com/sowide/bankruptcy_dataset/main/american_bankruptcy_dataset.csv).

Paper mô tả label tại fiscal year trước chapter filing và temporal splits.
Không được lấy status failed cố định cho mọi historical row rồi gọi là
one-year default. Repo có dataset_paper.zip với financial train/validation/test
và text items, đã kiểm danh sách file, chưa tái chứng nhận event của từng debtor.
[Lombardo et al.,2022](https://www.mdpi.com/1999-5903/14/8/244).

**Taiwan benchmark.** Đã đọc UCI archive trong memory, xác nhận 6.819 rows,
95 predictors,220 positive và 6.599 negative. Prevalence 3,226280%.
UCI định nghĩa bankruptcy theo Taiwan Stock Exchange, chưa xác nhận tương đương
US Chapter 7/11. Released flat matrix thiếu CIK/company-year identifiers để tự
dựng purged SEC-style time split. Công bố đúng benchmark protocol và outcome.
[UCI](https://archive.ics.uci.edu/dataset/572/taiwanese%2Bbankruptcy%2Bprediction).

Feature spaces khác 12+5 SEC schema. Có thể kiểm cùng estimator/preprocessing/
explanation architecture qua adapter được thẩm định. Chưa có cơ sở rename 95
normalized Taiwan inputs thành raw SEC ratios hoặc claim pipeline nguyên trạng
chạy tương đương. FinBERT là sentiment model; uncertainty tone cần definition/
validation riêng. Text fusion cần dated filings, chunk aggregation và ablation.
[FinBERT authors](https://github.com/ProsusAI/finBERT).

## 4. Gaps theo bốn personas

| Persona | Nhu cầu | Hiện trạng / hệ quả | Deliverable cần có |
| --- | --- | --- | --- |
| Bank credit officer | Interest coverage, FCF, debt-service capacity | Thiếu interest, CapEx, debt schedule, EBITDA, DSCR và covenant-specific definition | ICR, FCF/debt, cash coverage, debt maturity/interest schedule và source-linked memo |
| Bank credit officer | Peer percentile và credit memo | Sector chỉ là broad division, 26 SIC4 groups singleton, chưa có memo export | Cohort as-of, minimum sample, percentile bands, memo print/download |
| CFO / FP&A / treasury | What-if stress testing | Không có simulate endpoint hoặc scenario state | Accounting-consistent revenue/margin/debt/tax/cash bridge, baseline/stress comparison và OOD flag |
| CFO / FP&A / treasury | Quarterly / TTM early warning | DB 10-Q=0, training và UI chủ yếu annual, parser OCF có thể dùng YTD | Quarter isolation, Q4 bridge, FY−YTDprior+YTDcurrent, seasonality-aware deltas |
| Equity / distressed-debt analyst | Market risk, capital structure và event cases | Thiếu prices/market cap/volatility/DD/spreads/maturity. Không có legal-event registry | Market data timestamped, CIK/debtor event map, pre-event backtests và debt instruments |
| Academic committee | SEC proxy + legal-bankruptcy experiment | Hiện chỉ một proxy panel, 69 labeled OOT rows, 9 events | Schema adapter có kiểm chứng, frozen legal holdout, calibration, Brier/reliability và uncertainty |
| Academic committee | Robust baselines và generalization | Altman/logit AUC cao hơn XGB, OCF thua persistence, 67/68 test firms đã nằm train | Same-row comparisons, fix forward-origin protocol, unseen-company and rolling-window validation |

### 4.1 Credit officer / lender

Interest coverage là metric quan trọng, còn covenant trọng yếu tùy deal/borrower.
DSCR cần debt principal+interest và cash-flow definition riêng của hợp đồng.
Total liabilities chưa là debt service, còn next-period ratios chưa thể hiện
balloon/refinancing needs. [OCC Commercial Loans](https://www.occ.treas.gov/publications-and-resources/publications/comptrollers-handbook/files/commercial-loans/pub-ch-commercial-loans.pdf),
[OCC refinancing risk](https://occ.gov/news-issuances/bulletins/2024/bulletin-2024-29.html).

Cash/current liabilities, cash/short-term interest-bearing debt và runway là ba
metrics riêng. Runway cần burn rate và đơn vị thời gian. NetDebt/EBITDA cần
debt/cash eligibility, lease policy và denominator guards. Peer percentile phải
có cohort đủ, as-of và confidence về accounting comparability. Memo cần source
filing, assumptions, unavailable inputs và scope của probability.

### 4.2 CFO / treasury

Revenue−15%, margin−5 percentage points hoặc debt+$5B cần truyền qua operating
income/tax/working-capital/cash/financing assumptions, có reconciliation.
Slider-driven XGB score là conditional model response, chưa là causal effect.
Scenario cần tách khỏi actual financial tables và flag OOD. TTM phải lấy summed
flows và latest balance stocks, tránh double-count quarterly OCF đang mang YTD.

### 4.3 Equity / distressed-debt analyst

Thiếu market cap, equity volatility, price drawdown, debt instruments, spreads,
market-DD. Book-only disclosure hiện có là điểm đúng. Structural risk-neutral
probability cần mapping empirical physical/legal default trước khi gọi là PD.
CIK/entity phải ổn định xuyên đổi ticker, spinoff, reorganization.

Event registry pilot có thể bắt đầu bằng AMR/AAL CIK 0000006201, petition
2011-11-29, và Hertz Global CIK 0001657853, petition 2020-05-22. CIK/ngày Hertz
được xác minh trong SEC correspondence. Mỗi record cần debtor, parent/subsidiary,
court/docket, event date và source accession. Bank receivership và parent-company
Chapter 11 cần phân loại/entity mapping riêng.
[AMR](https://americanairlines.gcs-web.com/news-releases/news-release-details/amr-and-american-airlines-file-chapter-11-reorganization-achieve),
[Hertz SEC](https://www.sec.gov/Archives/edgar/data/1657853/000110465920085532/filename1.htm).

### 4.4 Academic reviewer

1. Freeze proxy target/protocol; xử lý 30 nonforward origins trong version mới và
   công bố provenance/performance deltas.
2. Tạo legal-event benchmark adapter theo đúng task, giữ firm/time split và
   event horizon, loại post-event observations và kiểm censoring.
3. Fit preprocessing trên train, calibration trên subsequent window, tune
   threshold riêng hoặc nested temporal validation; final test giữ nguyên.
4. Báo cáo discrimination, Brier/log loss/reliability và uncertainty intervals.
   Chỉ 9 positives làm một false negative đổi recall 11,11 percentage points.
5. So persistence/logit/variant-consistent Altman/XGB trên cùng rows. Phân biệt
   proxy/legal, raw/clipped targets, same-firm/unseen-firm và rolling regimes.
6. Sau nonlinear calibration, current SHAP sum vẫn giải thích raw logit.
   Cần output contract riêng hoặc explanation mới cho calibrated output.

## 5. Roadmap theo ROI và feasibility

Đây là backlog đề xuất. Effort là ước lượng một kỹ sư nắm repo, chưa gồm xin
quyền dữ liệu và independent review. Thứ tự đặt đúng target/identity trước việc
mở rộng feature/UI.

| Ưu tiên | Deliverable | ROI / effort ước lượng | Dependency | Acceptance gate |
| --- | --- | --- | --- | --- |
| P0 / Tier 1 | Meaning của target/horizon/identity | Rất cao / 2–4 ngày | Outcome contract | 30 nonforward pairs được xử lý, version mới, CIK as-of và disclosure raw proxy score |
| P1 / Tier 1 | Critical credit ratios | Rất cao / 4–7 ngày | Period/unit/scope và debt definitions | ICR, FCF/debt, cash ratio có provenance, missing giữ NULL và denominator policy rõ |
| P1 / Tier 1 | Bank gating + sector peers | Cao / 3–6 ngày | Peer cohort đủ và industry taxonomy | Routing SIC 6000–6799, as-of cohorts, sample floor, zero-variance policy |
| P1 / Tier 1 | Legal-event registry + benchmark | Rất cao / 5–10 ngày pilot | Debtor/CIK/court mapping và original task metadata | AAL/AMR, Hertz có nguồn, pre-event features, matched at-risk cohort và censoring |
| P1 / Tier 1 | Post-hoc probability calibration | Rất cao / 2–4 ngày sau dữ liệu | Tập calibration thời gian độc lập, đúng outcome | Sigmoid/isotonic candidates, Brier/log loss/reliability, final test frozen |
| P2 / Tier 1 | Peer comparison + export credit memo | Cao / 2–4 ngày | Credit/peer/event contracts | Memo printable/downloadable có as-of, source filing, assumptions và missingness |
| P2 / Tier 1 | POST simulate và UI | Cao / 4–7 ngày | Credit ratios và coherent accounting adjustments | Baseline/stress ratios, PCA/score/SHAP, scenario riêng với actual data, OOD flags |
| P2 / Tier 1 | Quarterly / TTM workflow | Cao / 5–10 ngày | Annual/YTD matching và Q4 | Đúng TTM sums, latest balance stocks, không cộng lặp YTD hoặc cộng ratio |
| P3 / Tier 2 | FinBERT MD&A fusion | Nghiên cứu / 3–6 tuần | Text extraction và publication timestamps | Tabular/text/fusion ablation, chunking và temporal leakage controls |
| P3 / Tier 2 | Merton/DD và multi-horizon PD | Nghiên cứu / 3–6 tuần | Licensed market inputs và event histories | Asset inference, default point, empirical physical-PD calibration và term structures |
| P3 / Tier 2 | Near-real-time 10-Q monitoring | Hạ tầng / 2–4 tuần | TTM correctness và distributed admission | Dispatcher/jobs, freshness SLA, observability và model governance |

### Tính khả thi của credit ratios từ cache

Đếm tag presence không chứng minh semantic equivalence. Cột cuối đòi
tag/USD/form 10-K/annual duration và accession/end/filed khớp một stored statement;
chưa là xác minh consolidated scope, noncash interest hoặc covenant debt.

| Tag trong raw cache | CIKs / 81 | Annual context matches / 1.239 |
| --- | --- | --- |
| InterestExpense | 68 | 822 |
| PaymentsToAcquirePropertyPlantAndEquipment | 63 | 814 |
| CashAndCashEquivalentsAtCarryingValue | 81 | 1133 |
| ShortTermBorrowings | 39 | 239 |
| LongTermDebtCurrent | 64 | 555 |
| LongTermDebtNoncurrent | 66 | 690 |
| DepreciationDepletionAndAmortization | 67 | 798 |
| InterestAndDebtExpense | 8 | 87 |

- InterestExpense/InterestAndDebtExpense không mặc định tương đương hay cộng được.
  ICR cần positive denominator. OperatingIncome dùng dưới disclosure EBIT proxy.
- FCF cần cùng-period OCF/CapEx. PPE acquisition payments chưa bao phủ mọi
  software/intangible investment. Missing CapEx giữ unavailable.
- FCF/debt cần interest-bearing debt definition, tránh dùng total liabilities
  rồi vẫn đặt tên net debt. Cash-only tag chưa đủ short-term-investment coverage.
- Bank/insurance/real-estate cần industry policy trước industrial imputation.
  Peer percentile màn hình có thể tính trên latest observable cohort, còn
  ML peer-z cần persisted as-of fit/transform contract và không dùng future peers.
- Calibration dùng proxy labels vẫn chỉ ước lượng proxy. Thêm vài case bankruptcy
  tạo case study, representative PD cần cả matched at-risk population/censoring.
- Scenario API/UI là bước sau debt-service và accounting contracts, không dùng
  trực tiếp việc tùy chỉnh 17 model inputs làm mô phỏng báo cáo tài chính đầy đủ.

## Kết luận cho product brief / luận văn

finhealth chứng minh tích hợp annual SEC provenance, temporal evaluation,
five-ratio forecasts, classifier và exact TreeSHAP vào API/dashboard có tests.
Các benchmark hiện đo fundamentals proxy trong selected issuer panel.
Credit underwriting/legal PD cần debt-service domain, dated event records,
sector controls và outcome-specific calibration. Những yếu tố quyết định chất
lượng kinh tế lượng nằm ở target/identity/availability và benchmark design.

## Appendix A — SQL và evidence protocol

```sql
SELECT sector,COUNT(*) FROM companies GROUP BY sector;
SELECT form_type,COUNT(*),MIN(fiscal_year),MAX(fiscal_year)
FROM financial_statements GROUP BY form_type;
SELECT cik,ticker,name,sic_code FROM companies
WHERE CAST(sic_code AS INTEGER) BETWEEN 6000 AND 6799;
SELECT COUNT(*)-COUNT(roa),COUNT(*)-COUNT(roe),
       COUNT(*)-COUNT(current_ratio),COUNT(*)-COUNT(altman_z_score)
FROM financial_metrics;
SELECT ticker,cik,name,sic_code FROM companies
WHERE ticker IN ('JPM','BAC','C','PARA','AAL');
SELECT model_version,COUNT(*) FROM model_predictions GROUP BY model_version;
PRAGMA integrity_check;
PRAGMA foreign_key_check;
```

Read-only SQLite URI mode=ro, checksum-verified load_bundle, actual preprocessing/
prediction/TreeSHAP, derive_distress_label và reconstructed splits/purge/embargo
được dùng trong inspection. Benchmark CSVs chỉ đọc trongmemory, chưa đưa vào
application database/panel/models. Supporting audit scripts/evidence nằm
trong .venv, ngoài application source.


## Appendix B — Integrity và quality gates

Manifest SHA-256 gồm 69 source/frontend/test files. Số file thay đổi trong inspection là **0**. Bundle hash khớp metadata. Các deliverables thêm mới là audit report và terminal transcripts.

### ruff check .

[Exact full terminal output](audit-logs/domain-ruff.txt)

```text
All checks passed!
```

### pytest -v

[Exact full terminal output](audit-logs/domain-pytest.txt)

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- D:\DATN\.venv\Scripts\python.exe
cachedir: .venv\pytest-cache
rootdir: D:\DATN
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0, asyncio-1.5.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 144 items

tests/integration/test_api_endpoints.py::test_health_endpoint_reports_db_and_model_status PASSED [  0%]
tests/integration/test_api_endpoints.py::test_analyze_company_end_to_end_by_ticker_and_cik PASSED [  1%]
tests/integration/test_api_endpoints.py::test_get_company_and_list_companies_after_ingestion PASSED [  2%]
tests/integration/test_api_endpoints.py::test_get_unknown_company_returns_404 PASSED [  2%]
tests/integration/test_api_endpoints.py::test_model_evaluation_endpoint_returns_benchmark_metrics PASSED [  3%]
tests/integration/test_api_endpoints.py::test_api_training_uses_persisted_panel_and_activates_saved_bundle PASSED [  4%]
tests/integration/test_api_endpoints.py::test_schema_nonfinite_sanitization_and_registry_autoload PASSED [  4%]
tests/integration/test_api_endpoints.py::test_sec_failures_are_structured_and_do_not_commit PASSED [  5%]
tests/integration/test_api_endpoints.py::test_analysis_transaction_rolls_back_database_failure PASSED [  6%]
tests/integration/test_dashboard_ui.py::test_dashboard_index_and_lazy_asgi_entry PASSED [  6%]
tests/integration/test_dashboard_ui.py::test_dashboard_static_assets[styles.css] PASSED [  7%]
tests/integration/test_dashboard_ui.py::test_dashboard_static_assets[js/api.js] PASSED [  8%]
tests/integration/test_dashboard_ui.py::test_dashboard_static_assets[js/charts.js] PASSED [  9%]
tests/integration/test_dashboard_ui.py::test_dashboard_static_assets[js/app.js] PASSED [  9%]
tests/integration/test_dashboard_ui.py::test_publication_figures[01_correlation_heatmap.png] PASSED [ 10%]
tests/integration/test_dashboard_ui.py::test_publication_figures[02_pca_scree_and_clusters.png] PASSED [ 11%]
tests/integration/test_dashboard_ui.py::test_publication_figures[03_roc_pr_curves_comparison.png] PASSED [ 11%]
tests/integration/test_dashboard_ui.py::test_publication_figures[04_confusion_matrices.png] PASSED [ 12%]
tests/integration/test_dashboard_ui.py::test_publication_figures[05_forecasting_actual_vs_predicted.png] PASSED [ 13%]
tests/integration/test_dashboard_ui.py::test_publication_figures[06_shap_global_importance.png] PASSED [ 13%]
tests/integration/test_dashboard_ui.py::test_default_real_universe_and_evaluation PASSED [ 14%]
tests/integration/test_dashboard_ui.py::test_company_features_explanations_and_altman[AAPL] PASSED [ 15%]
tests/integration/test_dashboard_ui.py::test_company_features_explanations_and_altman[AAL] PASSED [ 15%]
tests/integration/test_dashboard_ui.py::test_static_roots_are_configurable_and_confined PASSED [ 16%]
tests/integration/test_dashboard_ui.py::test_dashboard_leaves_audited_model_unchanged PASSED [ 17%]
tests/integration/test_db_migrations.py::test_migration_upgrade_matches_metadata_and_downgrade PASSED [ 18%]
tests/integration/test_db_migrations.py::test_postgresql_offline_migration_sql PASSED [ 18%]
tests/integration/test_forensic_audit.py::test_all_statement_provenance PASSED [ 19%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAPL-2023] PASSED [ 20%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAL-2020] PASSED [ 20%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[LUMN-2023] PASSED [ 21%]
tests/integration/test_forensic_audit.py::test_altman_distress_independence PASSED [ 22%]
tests/integration/test_forensic_audit.py::test_out_of_time_and_fitted_statistics PASSED [ 22%]
tests/integration/test_forensic_audit.py::test_tree_shap_all_held_out PASSED [ 23%]
tests/integration/test_forensic_audit.py::test_training_target_permutation PASSED [ 24%]
tests/integration/test_forensic_audit.py::test_prediction_and_api_parity PASSED [ 25%]
tests/integration/test_forensic_audit.py::test_etl_and_inference_latency PASSED [ 25%]
tests/integration/test_forensic_audit.py::test_training_latency_and_saved_scores PASSED [ 26%]
tests/integration/test_forensic_audit.py::test_api_latency[/health] PASSED [ 27%]
tests/integration/test_forensic_audit.py::test_api_latency[/companies] PASSED [ 27%]
tests/integration/test_forensic_audit.py::test_api_latency[/companies/AAPL] PASSED [ 28%]
tests/integration/test_forensic_audit.py::test_api_latency[/clusters/map] PASSED [ 29%]
tests/integration/test_forensic_audit.py::test_api_latency[/models/evaluation] PASSED [ 29%]
tests/unit/test_core_config.py::test_valid_configuration_and_database_url PASSED [ 30%]
tests/unit/test_core_config.py::test_database_url_escapes_credentials PASSED [ 31%]
tests/unit/test_core_config.py::test_database_url_defaults_to_local_sqlite PASSED [ 31%]
tests/unit/test_core_config.py::test_dotenv_loading_and_environment_precedence PASSED [ 32%]
tests/unit/test_core_config.py::test_data_paths_derive_from_root_with_explicit_override PASSED [ 33%]
tests/unit/test_core_config.py::test_example_environment_loads PASSED    [ 34%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[] PASSED [ 34%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[   ] PASSED [ 35%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0] PASSED [ 36%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[research@example.com] PASSED [ 36%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-requests] PASSED [ 37%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-requests/2.31.0 (research@example.com)] PASSED [ 38%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-httpx/0.27.0 (research@example.com)] PASSED [ 38%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[curl/8.0 (research@example.com)] PASSED [ 39%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (missing-email)] PASSED [ 40%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (@example.com)] PASSED [ 40%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (research@)] PASSED [ 41%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (research@example.com)\r\nInjected: header] PASSED [ 42%]
tests/unit/test_core_config.py::test_sec_user_agent_uses_authorized_research_default PASSED [ 43%]
tests/unit/test_core_config.py::test_sec_user_agent_trims_surrounding_whitespace PASSED [ 43%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[10.01] PASSED [ 44%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[11.0] PASSED [ 45%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[0.0] PASSED [ 45%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[-1.0] PASSED [ 46%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[inf] PASSED [ 47%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[nan] PASSED [ 47%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[0.001] PASSED [ 48%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[8.0] PASSED [ 49%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[10.0] PASSED [ 50%]
tests/unit/test_core_config.py::test_assignment_cannot_bypass_sec_rate_validation PASSED [ 50%]
tests/unit/test_core_config.py::test_accounting_concepts_have_nonempty_ordered_tag_candidates PASSED [ 51%]
tests/unit/test_core_logging.py::test_logging_is_idempotent_and_updates_level PASSED [ 52%]
tests/unit/test_core_logging.py::test_invalid_logging_level_has_no_side_effects PASSED [ 52%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[ConfigurationError] PASSED [ 53%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[SecIngestionError] PASSED [ 54%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[EtlProcessingError] PASSED [ 54%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[ModelPipelineError] PASSED [ 55%]
tests/unit/test_db_repositories.py::test_normalize_cik_valid_and_invalid PASSED [ 56%]
tests/unit/test_db_repositories.py::test_company_upsert_idempotency PASSED [ 56%]
tests/unit/test_db_repositories.py::test_company_pagination PASSED       [ 57%]
tests/unit/test_db_repositories.py::test_statement_upsert_and_restatement_handling PASSED [ 58%]
tests/unit/test_db_repositories.py::test_chronological_ordering PASSED   [ 59%]
tests/unit/test_db_repositories.py::test_metric_and_prediction_upsert_with_shap_json PASSED [ 59%]
tests/unit/test_db_repositories.py::test_metric_chronological_order_and_source_alignment PASSED [ 60%]
tests/unit/test_db_repositories.py::test_latest_prediction_version_and_timestamp_tie PASSED [ 61%]
tests/unit/test_db_repositories.py::test_prediction_probability_bounds[-0.01] PASSED [ 61%]
tests/unit/test_db_repositories.py::test_prediction_probability_bounds[1.01] PASSED [ 62%]
tests/unit/test_db_repositories.py::test_database_constraints_and_foreign_keys PASSED [ 63%]
tests/unit/test_db_repositories.py::test_cross_company_analytics_are_rejected PASSED [ 63%]
tests/unit/test_db_repositories.py::test_payloads_cannot_override_identity_or_add_unknown_fields PASSED [ 64%]
tests/unit/test_db_repositories.py::test_cascade_delete_company[orm] PASSED [ 65%]
tests/unit/test_db_repositories.py::test_cascade_delete_company[sql] PASSED [ 65%]
tests/unit/test_db_repositories.py::test_statement_delete_cascades_to_analytics PASSED [ 66%]
tests/unit/test_db_repositories.py::test_relationship_delete_orphans PASSED [ 67%]
tests/unit/test_db_repositories.py::test_repositories_do_not_commit PASSED [ 68%]
tests/unit/test_db_session.py::test_request_session_commits_success PASSED [ 68%]
tests/unit/test_db_session.py::test_request_session_rolls_back_failure PASSED [ 69%]
tests/unit/test_db_session.py::test_request_session_close_rolls_back PASSED [ 70%]
tests/unit/test_db_session.py::test_sqlite_foreign_keys_on_every_connection PASSED [ 70%]
tests/unit/test_etl_pipeline.py::test_xbrl_parser_resolves_comparative_years_from_apple_fixture PASSED [ 71%]
tests/unit/test_etl_pipeline.py::test_duration_priority_restatement_and_unit_resolution PASSED [ 72%]
tests/unit/test_etl_pipeline.py::test_quarter_preference_and_ocf_ytd_fallback PASSED [ 72%]
tests/unit/test_etl_pipeline.py::test_identity_fallbacks_missing_values_and_invalid_input PASSED [ 73%]
tests/unit/test_etl_pipeline.py::test_balance_fallback_accounts_for_equity_scope PASSED [ 74%]
tests/unit/test_etl_pipeline.py::test_financial_ratios_and_negative_equity_guard PASSED [ 75%]
tests/unit/test_etl_pipeline.py::test_altman_z_score_manufacturing_vs_non_manufacturing PASSED [ 75%]
tests/unit/test_etl_pipeline.py::test_temporal_deltas_and_negative_ocf_streak PASSED [ 76%]
tests/unit/test_etl_pipeline.py::test_ratio_winsorizer_prevents_test_leakage PASSED [ 77%]
tests/unit/test_etl_pipeline.py::test_end_to_end_etl_to_db_and_parquet PASSED [ 77%]
tests/unit/test_etl_pipeline.py::test_etl_batch_rollback_and_stale_metrics PASSED [ 78%]
tests/unit/test_etl_pipeline.py::test_optional_spark_missing_dependency_falls_back_to_real_parquet PASSED [ 79%]
tests/unit/test_etl_pipeline.py::test_parser_nonfinite_and_ambiguous_calendar PASSED [ 79%]
tests/unit/test_ml_pipeline.py::test_temporal_splitter_and_next_period_alignment PASSED [ 80%]
tests/unit/test_ml_pipeline.py::test_pca_clustering_deterministic_health_ranking PASSED [ 81%]
tests/unit/test_ml_pipeline.py::test_next_period_forecaster_and_metrics PASSED [ 81%]
tests/unit/test_ml_pipeline.py::test_distress_classifier_vs_baselines_and_f2_threshold PASSED [ 82%]
tests/unit/test_ml_pipeline.py::test_tree_shap_explainer_instance_and_global PASSED [ 83%]
tests/unit/test_ml_pipeline.py::test_full_pipeline_registry_save_load_and_company_inference PASSED [ 84%]
tests/unit/test_ml_pipeline.py::test_labels_metric_edges_and_degenerate_clusters PASSED [ 84%]
tests/unit/test_ml_pipeline.py::test_publication_cutoff_and_train_only_preprocessing PASSED [ 85%]
tests/unit/test_sec_ingestion.py::test_rate_limiter_enforces_minimum_interval PASSED [ 86%]
tests/unit/test_sec_ingestion.py::test_rate_limiter_cancellation_and_context PASSED [ 86%]
tests/unit/test_sec_ingestion.py::test_sic_to_sector_mapping PASSED      [ 87%]
tests/unit/test_sec_ingestion.py::test_fetch_tickers_and_resolve_cik_with_cache PASSED [ 88%]
tests/unit/test_sec_ingestion.py::test_fetch_company_metadata_cache_and_no_tickers PASSED [ 88%]
tests/unit/test_sec_ingestion.py::test_fetch_company_facts_retry_on_503_and_atomic_save PASSED [ 89%]
tests/unit/test_sec_ingestion.py::test_fetch_company_facts_no_retry_on_404_or_403 PASSED [ 90%]
tests/unit/test_sec_ingestion.py::test_retry_exhaustion_transport_and_exponential_backoff PASSED [ 90%]
tests/unit/test_sec_ingestion.py::test_invalid_responses_and_cache_preserve_existing_data PASSED [ 91%]
tests/unit/test_sec_ingestion.py::test_atomic_write_failure_preserves_target PASSED [ 92%]
tests/unit/test_sec_ingestion.py::test_shared_limiter_and_transport_recovery PASSED [ 93%]
tests/unit/test_sec_ingestion.py::test_invalid_metadata_and_ticker_contracts PASSED [ 93%]
tests/unit/test_stage66_remediation.py::test_five_percent_equity_cushion_and_ratio_bounds PASSED [ 94%]
tests/unit/test_stage66_remediation.py::test_unsupervised_training_geometry_is_zero_mean_and_unit_variance PASSED [ 95%]
tests/unit/test_stage66_remediation.py::test_fallback_outcomes_are_sparse_nonlinear_and_not_altman_labels PASSED [ 95%]
tests/unit/test_stage66_remediation.py::test_first_filed_annual_context_excludes_quarterly_and_future_revisions PASSED [ 96%]
tests/unit/test_stage66_remediation.py::test_calibration_labels_precede_every_scored_test_origin PASSED [ 97%]
tests/unit/test_stage67.py::test_fundamental_distress_rules_ignore_altman_columns PASSED [ 97%]
tests/unit/test_stage67.py::test_forecast_scoring_clips_only_finite_truth_at_fitted_bounds PASSED [ 98%]
tests/unit/test_visualization_and_cli.py::test_visualization_and_cli_artifacts PASSED [ 99%]
tests/unit/test_visualization_and_cli.py::test_benchmark_reproducibility_and_cached_sec_etl PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\DATN\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 144 passed, 1 warning in 57.00s =======================
```
