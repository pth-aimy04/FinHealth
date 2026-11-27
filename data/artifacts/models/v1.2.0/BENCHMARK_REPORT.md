# FinHealth empirical benchmark: v1.2.0

This run uses only real SEC EDGAR annual financial statements. All metrics below come from real fitted models and held-out predictions. Labels are a financial distress proxy, not observed bankruptcy outcomes.

Live ingestion: not attempted (offline or no monitored SEC contact). Training through 2021; validation through 2022; later years are test data.

```text
DATASET AND TEMPORAL SPLITS

+-------------------------------------+-----------------------------------+
| Measure                             | Value                             |
+-------------------------------------+-----------------------------------+
| Panel rows                          | 1506                              |
| Companies                           | 98                                |
| Synthetic rows                      | 0                                 |
| Cached SEC rows                     | 1506                              |
| Training feature rows               | 1047                              |
| Training supervised rows            | 900                               |
| Non-forward supervised rows         | 0                                 |
| Validation labeled rows             | 97                                |
| Test feature rows                   | 196                               |
| Test labeled rows                   | 98                                |
| Panel proxy distress prevalence (%) | 12.682603                         |
| Threshold source                    | validation_fiscal_years_2022_2022 |
| Calibration publication date        | 2024-03-01T00:00:00               |
+-------------------------------------+-----------------------------------+

PCA VARIANCE

+-----------+----------+------------+
| Component | Variance | Cumulative |
+-----------+----------+------------+
| 1         | 0.367170 | 0.367170   |
| 2         | 0.223216 | 0.590387   |
| 3         | 0.108327 | 0.698714   |
+-----------+----------+------------+

Silhouette Score: 0.301974

TRAINING CLUSTER PROFILES (original-space centroids)

+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+
| ID | Label                          | Health    | ROA       | ROE       | OCF      | Current  | Debt     |
+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+
| 0  | Strong Financial Health        | 5.503723  | 0.120329  | 0.230492  | 0.375597 | 2.758542 | 0.471991 |
| 1  | Stable / Moderate Leverage     | -0.396934 | 0.053403  | 0.143928  | 0.182817 | 1.241274 | 0.620233 |
| 2  | Elevated Leverage / Watchlist  | -1.132191 | 0.096263  | 0.355532  | 0.178613 | 1.228637 | 0.824947 |
| 3  | Financial Distress / High Risk | -5.246297 | -0.072427 | -0.072788 | 0.033837 | 1.626735 | 0.735848 |
+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+

NEXT-PERIOD REGRESSION (unclipped test targets)

+------------+----------+----------+----------+--------+
| Target     | MAE      | RMSE     | R2       | N_Test |
+------------+----------+----------+----------+--------+
| roa        | 0.039566 | 0.076459 | 0.540163 | 94     |
| roe        | 0.138302 | 0.281598 | 0.617776 | 71     |
| eps        | 2.321120 | 3.499109 | 0.715720 | 96     |
| debt_ratio | 0.044627 | 0.107632 | 0.841167 | 94     |
| ocf_ratio  | 0.043357 | 0.070076 | 0.860749 | 93     |
+------------+----------+----------+----------+--------+

NEXT-PERIOD REGRESSION (test targets clipped to training bounds)

+------------+----------+----------+----------+--------+
| Target     | MAE      | RMSE     | R2       | N_Test |
+------------+----------+----------+----------+--------+
| roa        | 0.037005 | 0.065893 | 0.385344 | 94     |
| roe        | 0.093680 | 0.139816 | 0.789890 | 71     |
| eps        | 1.971103 | 2.872631 | 0.742830 | 96     |
| debt_ratio | 0.052390 | 0.119928 | 0.714856 | 94     |
| ocf_ratio  | 0.046546 | 0.077035 | 0.776442 | 93     |
+------------+----------+----------+----------+--------+

+------------+----------------------+----------------------+
| Target     | Training lower bound | Training upper bound |
+------------+----------------------+----------------------+
| roa        | -0.207423            | 0.216449             |
| roe        | -0.589601            | 1.095243             |
| eps        | -6.145000            | 16.209000            |
| debt_ratio | 0.270753             | 1.129091             |
| ocf_ratio  | -0.164896            | 0.850362             |
+------------+----------------------+----------------------+

DISTRESS RELIABILITY BY SCORE DECILE

+------------+----------+----------+----+----------+------------+---------------+
| Score      | Lower    | Upper    | N  | Positive | Mean score | Observed rate |
+------------+----------+----------+----+----------+------------+---------------+
| raw        | 0.000000 | 0.100000 | 40 | 0        | 0.045217   | 0.000000      |
| raw        | 0.100000 | 0.200000 | 14 | 0        | 0.156897   | 0.000000      |
| raw        | 0.200000 | 0.300000 | 8  | 0        | 0.248624   | 0.000000      |
| raw        | 0.300000 | 0.400000 | 7  | 0        | 0.367249   | 0.000000      |
| raw        | 0.400000 | 0.500000 | 8  | 1        | 0.466970   | 0.125000      |
| raw        | 0.500000 | 0.600000 | 5  | 1        | 0.538769   | 0.200000      |
| raw        | 0.600000 | 0.700000 | 2  | 2        | 0.637967   | 1.000000      |
| raw        | 0.700000 | 0.800000 | 3  | 1        | 0.731203   | 0.333333      |
| raw        | 0.800000 | 0.900000 | 3  | 2        | 0.859647   | 0.666667      |
| raw        | 0.900000 | 1.000000 | 8  | 8        | 0.945296   | 1.000000      |
| calibrated | 0.000000 | 0.100000 | 57 | 0        | 0.033012   | 0.000000      |
| calibrated | 0.100000 | 0.200000 | 12 | 0        | 0.151979   | 0.000000      |
| calibrated | 0.200000 | 0.300000 | 10 | 2        | 0.251418   | 0.200000      |
| calibrated | 0.300000 | 0.400000 | 4  | 1        | 0.332653   | 0.250000      |
| calibrated | 0.400000 | 0.500000 | 3  | 2        | 0.454997   | 0.666667      |
| calibrated | 0.500000 | 0.600000 | 1  | 0        | 0.546188   | 0.000000      |
| calibrated | 0.600000 | 0.700000 | 1  | 1        | 0.641216   | 1.000000      |
| calibrated | 0.700000 | 0.800000 | 2  | 1        | 0.720837   | 0.500000      |
| calibrated | 0.800000 | 0.900000 | 6  | 6        | 0.847578   | 1.000000      |
| calibrated | 0.900000 | 1.000000 | 2  | 2        | 0.918793   | 1.000000      |
+------------+----------+----------+----+----------+------------+---------------+

PAIRED FORECASTS VS. NAIVE PERSISTENCE (same observed test targets)

+------------+----+-----------+----------+-----------+-----------+----------+----------+
| Target     | N  | Candidate | Weight   | Model MAE | Naive MAE | Model R2 | Naive R2 |
+------------+----+-----------+----------+-----------+-----------+----------+----------+
| roa        | 93 | level     | 0.400000 | 0.039760  | 0.043024  | 0.540542 | 0.411338 |
| roe        | 69 | level     | 0.950000 | 0.121597  | 0.140914  | 0.662730 | 0.513346 |
| eps        | 95 | residual  | 0.850000 | 2.318877  | 2.670000  | 0.717240 | 0.441189 |
| debt_ratio | 94 | level     | 0.000000 | 0.044627  | 0.044627  | 0.841167 | 0.841167 |
| ocf_ratio  | 92 | level     | 0.350000 | 0.043548  | 0.046240  | 0.860852 | 0.839132 |
+------------+----+-----------+----------+-----------+-----------+----------+----------+

DISTRESS CLASSIFICATION BENCHMARK

+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+----+----+----+
| Model               | Threshold | Accuracy | Precision | Recall   | F1       | F2       | ROC-AUC  | PR-AUC   | Brier    | Log loss | Mean score | TP | FP | TN | FN |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+----+----+----+
| xgboost             | 0.185952  | 0.846939 | 0.500000  | 0.866667 | 0.634146 | 0.755814 | 0.957430 | 0.868300 | 0.059193 | 0.205226 | 0.180050   | 13 | 13 | 70 | 2  |
| lightgbm            | 0.233225  | 0.857143 | 0.520000  | 0.866667 | 0.650000 | 0.764706 | 0.959839 | 0.873069 | 0.053491 | 0.195631 | 0.183509   | 13 | 12 | 71 | 2  |
| random_forest       | 0.246959  | 0.887755 | 0.583333  | 0.933333 | 0.717949 | 0.833333 | 0.975904 | 0.898999 | 0.048583 | 0.178226 | 0.188442   | 14 | 10 | 73 | 1  |
| logistic_regression | 0.500000  | 0.755102 | 0.384615  | 1.000000 | 0.555556 | 0.757576 | 0.960643 | 0.868948 | 0.149351 | 0.452581 | 0.404180   | 15 | 24 | 59 | 0  |
| altman_z_baseline   | 0.500000  | 0.765306 | 0.382353  | 0.866667 | 0.530612 | 0.691489 | 0.903614 | 0.840343 | 0.201654 | 0.566110 | 0.484797   | 13 | 21 | 62 | 2  |
| xgboost_raw         | 0.500000  | 0.887755 | 0.611111  | 0.733333 | 0.666667 | 0.705128 | 0.957430 | 0.868300 | 0.073316 | 0.222041 | 0.220608   | 11 | 7  | 76 | 4  |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+----+----+----+

Selected best model: random_forest. Test prevalence: 0.153061. Raw TreeSHAP maximum margin error: 1.03216047e-15.

TOP 10 GLOBAL TREESHAP FEATURES (mean absolute log-odds contribution)

+-------------------------+-------------+
| Feature                 | Mean |SHAP| |
+-------------------------+-------------+
| roa                     | 0.072392    |
| ebit_to_assets          | 0.071815    |
| ocf_ratio               | 0.067805    |
| retained_earnings_ratio | 0.058908    |
| operating_margin        | 0.040737    |
| roe                     | 0.028249    |
| current_ratio           | 0.025948    |
| working_capital_ratio   | 0.019200    |
| negative_ocf_streak     | 0.018994    |
| debt_ratio              | 0.017046    |
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
- [07_reliability_calibration.png](../../figures/07_reliability_calibration.png)