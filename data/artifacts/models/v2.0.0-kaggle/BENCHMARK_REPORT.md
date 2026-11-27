# FinHealth empirical benchmark: v2.0.0-kaggle

This run uses the Kaggle US Company Bankruptcy dataset (1999-2018 historical annual financial statements with observed bankruptcy status labels). All metrics below come from real fitted models and held-out predictions. Labels reflect observed corporate bankruptcy outcomes from the Kaggle dataset, rather than synthetic simulations or SEC distress proxy rules.

Live ingestion: not applicable (Kaggle US Company Bankruptcy dataset). Training through 2014; validation through 2016; later years are test data.

```text
DATASET AND TEMPORAL SPLITS

+-----------------------------------------------------+-----------------------------------+
| Measure                                             | Value                             |
+-----------------------------------------------------+-----------------------------------+
| Panel rows                                          | 78682                             |
| Companies                                           | 8971                              |
| Kaggle US bankruptcy rows                           | 78682                             |
| Total 1Y bankruptcy events (year == max_year)       | 609                               |
| Train positive events                               | 490                               |
| Validation positive events                          | 62                                |
| Test positive events                                | 57                                |
| Entity leakage (Train/Val vs Test bankrupt overlap) | 0                                 |
| Training feature rows                               | 66400                             |
| Training supervised rows                            | 66400                             |
| Non-forward supervised rows                         | 0                                 |
| Validation labeled rows                             | 6545                              |
| Test feature rows                                   | 5737                              |
| Test labeled rows                                   | 5737                              |
| Panel 1Y bankruptcy prevalence (%)                  | 0.774002                          |
| Threshold source                                    | validation_fiscal_years_2015_2016 |
| Calibration publication date                        | 2016-12-31                        |
+-----------------------------------------------------+-----------------------------------+

PCA VARIANCE

+-----------+----------+------------+
| Component | Variance | Cumulative |
+-----------+----------+------------+
| 1         | 0.392127 | 0.392127   |
| 2         | 0.259384 | 0.651511   |
| 3         | 0.103653 | 0.755164   |
+-----------+----------+------------+

Silhouette Score: 0.371265

TRAINING CLUSTER PROFILES (original-space centroids)

+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+
| ID | Label                          | Health    | ROA       | ROE       | OCF      | Current  | Debt     |
+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+
| 0  | Strong Financial Health        | 2.792309  | 0.023795  | 0.040802  | 0.000000 | 4.087271 | 0.287394 |
| 1  | Stable / Moderate Leverage     | -1.054879 | -0.010918 | -0.018641 | 0.000000 | 1.406504 | 0.680026 |
| 2  | Elevated Leverage / Watchlist  | -2.563552 | -0.692135 | -0.951831 | 0.000000 | 3.902060 | 0.410986 |
| 3  | Financial Distress / High Risk | -5.704009 | -1.065031 | 0.020520  | 0.000000 | 0.539782 | 1.488770 |
+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+

NEXT-PERIOD REGRESSION (unclipped test targets)

+------------+----------+-----------+----------+--------+
| Target     | MAE      | RMSE      | R2       | N_Test |
+------------+----------+-----------+----------+--------+
| roa        | 0.496255 | 4.471757  | 0.441720 | 2643   |
| roe        | 0.247587 | 0.498099  | 0.513323 | 2339   |
| eps        | N/A      | N/A       | N/A      | 0      |
| debt_ratio | 0.790464 | 12.581749 | 0.496286 | 2643   |
| ocf_ratio  | N/A      | N/A       | N/A      | 0      |
+------------+----------+-----------+----------+--------+

NEXT-PERIOD REGRESSION (test targets clipped to training bounds)

+------------+----------+-----------+-------------+--------+
| Target     | MAE      | RMSE      | R2          | N_Test |
+------------+----------+-----------+-------------+--------+
| roa        | 0.412004 | 4.400603  | -76.419336  | 2643   |
| roe        | 0.220136 | 0.426224  | 0.555085    | 2339   |
| eps        | N/A      | N/A       | N/A         | 0      |
| debt_ratio | 0.783031 | 11.735028 | -568.590630 | 2643   |
| ocf_ratio  | N/A      | N/A       | N/A         | 0      |
+------------+----------+-----------+-------------+--------+

+------------+----------------------+----------------------+
| Target     | Training lower bound | Training upper bound |
+------------+----------------------+----------------------+
| roa        | -2.398094            | 0.233005             |
| roe        | -2.625209            | 0.482902             |
| debt_ratio | 0.080941             | 2.787268             |
+------------+----------------------+----------------------+

DISTRESS RELIABILITY BY SCORE DECILE

+------------+----------+----------+------+----------+------------+---------------+
| Score      | Lower    | Upper    | N    | Positive | Mean score | Observed rate |
+------------+----------+----------+------+----------+------------+---------------+
| raw        | 0.000000 | 0.100000 | 2648 | 1        | 0.045273   | 0.000378      |
| raw        | 0.100000 | 0.200000 | 1024 | 3        | 0.143172   | 0.002930      |
| raw        | 0.200000 | 0.300000 | 555  | 3        | 0.245900   | 0.005405      |
| raw        | 0.300000 | 0.400000 | 388  | 5        | 0.348478   | 0.012887      |
| raw        | 0.400000 | 0.500000 | 257  | 3        | 0.446278   | 0.011673      |
| raw        | 0.500000 | 0.600000 | 236  | 6        | 0.547824   | 0.025424      |
| raw        | 0.600000 | 0.700000 | 219  | 7        | 0.644976   | 0.031963      |
| raw        | 0.700000 | 0.800000 | 221  | 9        | 0.749533   | 0.040724      |
| raw        | 0.800000 | 0.900000 | 175  | 13       | 0.842989   | 0.074286      |
| raw        | 0.900000 | 1.000000 | 14   | 7        | 0.917437   | 0.500000      |
| calibrated | 0.000000 | 0.100000 | 5702 | 48       | 0.007913   | 0.008418      |
| calibrated | 0.100000 | 0.200000 | 35   | 9        | 0.122951   | 0.257143      |
+------------+----------+----------+------+----------+------------+---------------+

PAIRED FORECASTS VS. NAIVE PERSISTENCE (same observed test targets)

+------------+------+-----------+----------+-----------+-----------+----------+----------+
| Target     | N    | Candidate | Weight   | Model MAE | Naive MAE | Model R2 | Naive R2 |
+------------+------+-----------+----------+-----------+-----------+----------+----------+
| roa        | 2643 | level     | 0.400000 | 0.496255  | 0.590154  | 0.441720 | 0.108452 |
| roe        | 2277 | level     | 0.800000 | 0.225407  | 0.247818  | 0.542237 | 0.335839 |
| eps        | 0    | level     | 1.000000 | N/A       | N/A       | N/A      | N/A      |
| debt_ratio | 2643 | level     | 0.050000 | 0.790464  | 0.793887  | 0.496286 | 0.497654 |
| ocf_ratio  | 0    | level     | 1.000000 | N/A       | N/A       | N/A      | N/A      |
+------------+------+-----------+----------+-----------+-----------+----------+----------+

DISTRESS CLASSIFICATION BENCHMARK

+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+------+------+----+
| Model               | Threshold | Accuracy | Precision | Recall   | F1       | F2       | ROC-AUC  | PR-AUC   | Brier    | Log loss | Mean score | TP | FP   | TN   | FN |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+------+------+----+
| logistic_regression | 0.027177  | 0.969148 | 0.077465  | 0.192982 | 0.110553 | 0.148649 | 0.844604 | 0.048603 | 0.009717 | 0.050310 | 0.008843   | 11 | 131  | 5549 | 46 |
| random_forest       | 0.065691  | 0.970193 | 0.104167  | 0.263158 | 0.149254 | 0.201613 | 0.887376 | 0.124262 | 0.009322 | 0.043668 | 0.008440   | 15 | 129  | 5551 | 42 |
| xgboost             | 0.075327  | 0.978735 | 0.171717  | 0.298246 | 0.217949 | 0.259939 | 0.891074 | 0.178409 | 0.009266 | 0.042995 | 0.008615   | 17 | 82   | 5598 | 40 |
| lightgbm            | 0.055161  | 0.972111 | 0.094488  | 0.210526 | 0.130435 | 0.169014 | 0.860038 | 0.142106 | 0.009425 | 0.045382 | 0.008924   | 12 | 115  | 5565 | 45 |
| calibrated_ensemble | 0.080000  | 0.988321 | 0.333333  | 0.175439 | 0.229885 | 0.193798 | 0.890308 | 0.158958 | 0.009370 | 0.044095 | 0.008704   | 10 | 20   | 5660 | 47 |
| altman_z_baseline   | 0.500000  | 0.607983 | 0.022232  | 0.894737 | 0.043386 | 0.101110 | 0.810634 | 0.026606 | 0.305002 | 3.118416 | 0.419186   | 51 | 2243 | 3437 | 6  |
| xgboost_raw         | 0.500000  | 0.853931 | 0.048555  | 0.736842 | 0.091106 | 0.192132 | 0.891074 | 0.178409 | 0.099053 | 0.313843 | 0.217783   | 42 | 823  | 4857 | 15 |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+------+------+----+

Selected best model: xgboost. Test prevalence: 0.009936. Raw TreeSHAP maximum margin error: 3.19769606e-06.

TOP 10 GLOBAL TREESHAP FEATURES (mean absolute log-odds contribution)

+-------------------------+-------------+
| Feature                 | Mean |SHAP| |
+-------------------------+-------------+
| roa                     | 0.376398    |
| equity_to_assets        | 0.352156    |
| quick_ratio             | 0.327941    |
| debt_ratio              | 0.256010    |
| debt_ratio_yoy_delta    | 0.242777    |
| operating_margin        | 0.242435    |
| gross_margin            | 0.183238    |
| receivables_to_revenue  | 0.160580    |
| retained_earnings_ratio | 0.149521    |
| ebitda_to_assets        | 0.146545    |
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