# FinHealth empirical benchmark: v1.1.0

This run uses only real SEC EDGAR annual financial statements. All metrics below come from real fitted models and held-out predictions. Labels are a financial distress proxy, not observed bankruptcy outcomes.

Live ingestion: not attempted (offline or no monitored SEC contact). Training through 2021; validation through 2022; later years are test data.

```text
DATASET AND TEMPORAL SPLITS

+-------------------------------------+-----------------------------------+
| Measure                             | Value                             |
+-------------------------------------+-----------------------------------+
| Panel rows                          | 1234                              |
| Companies                           | 80                                |
| Synthetic rows                      | 0                                 |
| Cached SEC rows                     | 1234                              |
| Training feature rows               | 864                               |
| Training supervised rows            | 748                               |
| Non-forward supervised rows         | 0                                 |
| Validation labeled rows             | 79                                |
| Test feature rows                   | 160                               |
| Test labeled rows                   | 80                                |
| Panel proxy distress prevalence (%) | 10.696921                         |
| Threshold source                    | validation_fiscal_years_2022_2022 |
| Calibration publication date        | 2024-03-01T00:00:00               |
+-------------------------------------+-----------------------------------+

PCA VARIANCE

+-----------+----------+------------+
| Component | Variance | Cumulative |
+-----------+----------+------------+
| 1         | 0.383353 | 0.383353   |
| 2         | 0.203142 | 0.586495   |
| 3         | 0.110781 | 0.697276   |
+-----------+----------+------------+

Silhouette Score: 0.300717

TRAINING CLUSTER PROFILES (original-space centroids)

+----+--------------------------------+-----------+----------+----------+----------+----------+----------+
| ID | Label                          | Health    | ROA      | ROE      | OCF      | Current  | Debt     |
+----+--------------------------------+-----------+----------+----------+----------+----------+----------+
| 0  | Strong Financial Health        | 5.979849  | 0.130782 | 0.248788 | 0.412856 | 2.814957 | 0.464773 |
| 1  | Stable / Moderate Leverage     | 0.301771  | 0.072572 | 0.179619 | 0.220551 | 1.288978 | 0.593362 |
| 2  | Elevated Leverage / Watchlist  | -0.866224 | 0.106395 | 0.395239 | 0.191027 | 1.269118 | 0.836617 |
| 3  | Financial Distress / High Risk | -3.992331 | 0.004696 | 0.075373 | 0.116313 | 1.189578 | 0.756436 |
+----+--------------------------------+-----------+----------+----------+----------+----------+----------+

NEXT-PERIOD REGRESSION (unclipped test targets)

+------------+----------+----------+----------+--------+
| Target     | MAE      | RMSE     | R2       | N_Test |
+------------+----------+----------+----------+--------+
| roa        | 0.036218 | 0.074221 | 0.234163 | 77     |
| roe        | 0.145065 | 0.280432 | 0.496837 | 55     |
| eps        | 2.382000 | 3.607555 | 0.668738 | 79     |
| debt_ratio | 0.048250 | 0.117443 | 0.823081 | 77     |
| ocf_ratio  | 0.040275 | 0.061195 | 0.867869 | 76     |
+------------+----------+----------+----------+--------+

NEXT-PERIOD REGRESSION (test targets clipped to training bounds)

+------------+----------+----------+----------+--------+
| Target     | MAE      | RMSE     | R2       | N_Test |
+------------+----------+----------+----------+--------+
| roa        | 0.033829 | 0.062493 | 0.233609 | 77     |
| roe        | 0.107992 | 0.159583 | 0.631874 | 55     |
| eps        | 1.949121 | 2.815722 | 0.706040 | 79     |
| debt_ratio | 0.058274 | 0.132952 | 0.656169 | 77     |
| ocf_ratio  | 0.038270 | 0.057042 | 0.878783 | 76     |
+------------+----------+----------+----------+--------+

+------------+----------------------+----------------------+
| Target     | Training lower bound | Training upper bound |
+------------+----------------------+----------------------+
| roa        | -0.143178            | 0.218520             |
| roe        | -0.397598            | 1.037090             |
| eps        | -6.235000            | 15.200000            |
| debt_ratio | 0.256135             | 1.115179             |
| ocf_ratio  | -0.090992            | 0.907030             |
+------------+----------------------+----------------------+

DISTRESS RELIABILITY BY SCORE DECILE

+------------+----------+----------+----+----------+------------+---------------+
| Score      | Lower    | Upper    | N  | Positive | Mean score | Observed rate |
+------------+----------+----------+----+----------+------------+---------------+
| raw        | 0.000000 | 0.100000 | 50 | 0        | 0.019626   | 0.000000      |
| raw        | 0.100000 | 0.200000 | 11 | 2        | 0.148797   | 0.181818      |
| raw        | 0.200000 | 0.300000 | 3  | 0        | 0.218180   | 0.000000      |
| raw        | 0.300000 | 0.400000 | 3  | 1        | 0.337148   | 0.333333      |
| raw        | 0.400000 | 0.500000 | 2  | 0        | 0.470271   | 0.000000      |
| raw        | 0.500000 | 0.600000 | 1  | 1        | 0.562289   | 1.000000      |
| raw        | 0.600000 | 0.700000 | 1  | 0        | 0.659659   | 0.000000      |
| raw        | 0.800000 | 0.900000 | 2  | 1        | 0.861641   | 0.500000      |
| raw        | 0.900000 | 1.000000 | 7  | 5        | 0.957812   | 0.714286      |
| calibrated | 0.000000 | 0.100000 | 47 | 0        | 0.037453   | 0.000000      |
| calibrated | 0.100000 | 0.200000 | 17 | 2        | 0.142664   | 0.117647      |
| calibrated | 0.200000 | 0.300000 | 5  | 1        | 0.252721   | 0.200000      |
| calibrated | 0.300000 | 0.400000 | 2  | 1        | 0.355687   | 0.500000      |
| calibrated | 0.500000 | 0.600000 | 4  | 1        | 0.563904   | 0.250000      |
| calibrated | 0.700000 | 0.800000 | 2  | 2        | 0.754538   | 1.000000      |
| calibrated | 0.800000 | 0.900000 | 3  | 3        | 0.805247   | 1.000000      |
+------------+----------+----------+----+----------+------------+---------------+

PAIRED FORECASTS VS. NAIVE PERSISTENCE (same observed test targets)

+------------+----+-----------+----------+-----------+-----------+----------+-----------+
| Target     | N  | Candidate | Weight   | Model MAE | Naive MAE | Model R2 | Naive R2  |
+------------+----+-----------+----------+-----------+-----------+----------+-----------+
| roa        | 77 | level     | 0.400000 | 0.036218  | 0.040333  | 0.234163 | -0.022787 |
| roe        | 54 | residual  | 1.000000 | 0.118813  | 0.116189  | 0.608431 | 0.499915  |
| eps        | 78 | level     | 0.750000 | 2.382617  | 2.479487  | 0.670463 | 0.538523  |
| debt_ratio | 77 | level     | 0.000000 | 0.048250  | 0.048250  | 0.823081 | 0.823081  |
| ocf_ratio  | 75 | level     | 0.700000 | 0.040675  | 0.042296  | 0.867871 | 0.819935  |
+------------+----+-----------+----------+-----------+-----------+----------+-----------+

DISTRESS CLASSIFICATION BENCHMARK

+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+----+----+----+
| Model               | Threshold | Accuracy | Precision | Recall   | F1       | F2       | ROC-AUC  | PR-AUC   | Brier    | Log loss | Mean score | TP | FP | TN | FN |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+----+----+----+
| XGBoost calibrated  | 0.471507  | 0.912500 | 0.666667  | 0.600000 | 0.631579 | 0.612245 | 0.944286 | 0.778636 | 0.058535 | 0.205068 | 0.154263   | 6  | 3  | 67 | 4  |
| XGBoost raw         | 0.500000  | 0.912500 | 0.636364  | 0.700000 | 0.666667 | 0.686275 | 0.944286 | 0.778636 | 0.072606 | 0.228313 | 0.185931   | 7  | 4  | 66 | 3  |
| logistic_regression | 0.500000  | 0.687500 | 0.285714  | 1.000000 | 0.444444 | 0.666667 | 0.942857 | 0.772384 | 0.203669 | 0.623490 | 0.427983   | 10 | 25 | 45 | 0  |
| altman_z_baseline   | 0.500000  | 0.762500 | 0.333333  | 0.900000 | 0.486486 | 0.671642 | 0.910000 | 0.815241 | 0.211377 | 0.589341 | 0.475532   | 9  | 18 | 52 | 1  |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+----+----+----+

Test proxy prevalence: 0.125000. Raw TreeSHAP maximum margin error: 2.10688449e-06.

TOP 10 GLOBAL TREESHAP FEATURES (mean absolute log-odds contribution)

+-------------------------+-------------+
| Feature                 | Mean |SHAP| |
+-------------------------+-------------+
| ebit_to_assets          | 0.971832    |
| ocf_ratio               | 0.693739    |
| roa                     | 0.507162    |
| asset_turnover          | 0.503983    |
| retained_earnings_ratio | 0.479968    |
| debt_ratio_yoy_delta    | 0.463603    |
| operating_margin        | 0.402135    |
| working_capital_ratio   | 0.275324    |
| ocf_ratio_yoy_delta     | 0.252430    |
| current_ratio           | 0.244411    |
+-------------------------+-------------+
```

Calibration, threshold selection and forecast shrinkage use only eligible validation labels. The test origins are embargoed until those labels are observable. SEC caches still require point-in-time revision controls for market backtests.

Regression tables report both original test targets and targets clipped to the training 2.5th and 97.5th percentiles. The parity chart uses original test targets. Cluster labels rank relative centroid health.

- [01_correlation_heatmap.png](../../figures/01_correlation_heatmap.png)
- [02_pca_scree_and_clusters.png](../../figures/02_pca_scree_and_clusters.png)
- [03_roc_pr_curves_comparison.png](../../figures/03_roc_pr_curves_comparison.png)
- [04_confusion_matrices.png](../../figures/04_confusion_matrices.png)
- [05_forecasting_actual_vs_predicted.png](../../figures/05_forecasting_actual_vs_predicted.png)
- [06_shap_global_importance.png](../../figures/06_shap_global_importance.png)