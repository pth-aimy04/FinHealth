# FinHealth empirical benchmark: kaggle-v1.2.0

This run uses the Kaggle US Company Bankruptcy dataset (1999-2018 historical annual financial statements with observed bankruptcy status labels). All metrics below come from real fitted models and held-out predictions. Labels reflect observed corporate bankruptcy outcomes from the Kaggle dataset, rather than synthetic simulations or SEC distress proxy rules.

Live ingestion: not applicable (Kaggle US Company Bankruptcy dataset). Training through 2014; validation through 2016; later years are test data.

```text
DATASET AND TEMPORAL SPLITS

+-------------------------------------+-----------------------------------+
| Measure                             | Value                             |
+-------------------------------------+-----------------------------------+
| Panel rows                          | 78682                             |
| Companies                           | 8971                              |
| Synthetic rows                      | 0                                 |
| Cached SEC rows                     | 0                                 |
| Training feature rows               | 66400                             |
| Training supervised rows            | 57218                             |
| Non-forward supervised rows         | N/A                               |
| Validation labeled rows             | 5901                              |
| Test feature rows                   | 5737                              |
| Test labeled rows                   | 2643                              |
| Panel proxy distress prevalence (%) | 6.634300                          |
| Threshold source                    | validation_fiscal_years_2015_2016 |
| Calibration publication date        | N/A                               |
+-------------------------------------+-----------------------------------+

PCA VARIANCE

+-----------+----------+------------+
| Component | Variance | Cumulative |
+-----------+----------+------------+
| 1         | 0.391027 | 0.391027   |
| 2         | 0.259907 | 0.650933   |
| 3         | 0.102126 | 0.753059   |
+-----------+----------+------------+

Silhouette Score: 0.361314

TRAINING CLUSTER PROFILES (original-space centroids)

+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+
| ID | Label                          | Health    | ROA       | ROE       | OCF      | Current  | Debt     |
+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+
| 0  | Strong Financial Health        | 2.806965  | 0.023045  | 0.040355  | 0.000000 | 4.015629 | 0.290641 |
| 1  | Stable / Moderate Leverage     | -1.065861 | -0.014845 | -0.023040 | 0.000000 | 1.393463 | 0.686656 |
| 2  | Elevated Leverage / Watchlist  | -2.438502 | -0.681486 | -0.972706 | 0.000000 | 3.821310 | 0.409148 |
| 3  | Financial Distress / High Risk | -5.775220 | -1.059053 | -0.042026 | 0.000000 | 0.539992 | 1.419298 |
+----+--------------------------------+-----------+-----------+-----------+----------+----------+----------+

NEXT-PERIOD REGRESSION (unclipped test targets)

+------------+----------+-----------+----------+--------+
| Target     | MAE      | RMSE      | R2       | N_Test |
+------------+----------+-----------+----------+--------+
| roa        | 0.496261 | 4.471040  | 0.441899 | 2643   |
| roe        | 0.247623 | 0.498464  | 0.512610 | 2339   |
| eps        | N/A      | N/A       | N/A      | 0      |
| debt_ratio | 0.790460 | 12.581746 | 0.496286 | 2643   |
| ocf_ratio  | N/A      | N/A       | N/A      | 0      |
+------------+----------+-----------+----------+--------+

NEXT-PERIOD REGRESSION (test targets clipped to training bounds)

+------------+----------+-----------+-------------+--------+
| Target     | MAE      | RMSE      | R2          | N_Test |
+------------+----------+-----------+-------------+--------+
| roa        | 0.412071 | 4.400620  | -76.419955  | 2643   |
| roe        | 0.220182 | 0.426492  | 0.554526    | 2339   |
| eps        | N/A      | N/A       | N/A         | 0      |
| debt_ratio | 0.783024 | 11.735029 | -568.590728 | 2643   |
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
| raw        | 0.000000 | 0.100000 | 1    | 0        | 0.099600   | 0.000000      |
| raw        | 0.100000 | 0.200000 | 168  | 0        | 0.171207   | 0.000000      |
| raw        | 0.200000 | 0.300000 | 433  | 2        | 0.252703   | 0.004619      |
| raw        | 0.300000 | 0.400000 | 431  | 1        | 0.351098   | 0.002320      |
| raw        | 0.400000 | 0.500000 | 456  | 3        | 0.448667   | 0.006579      |
| raw        | 0.500000 | 0.600000 | 593  | 5        | 0.549710   | 0.008432      |
| raw        | 0.600000 | 0.700000 | 408  | 9        | 0.642132   | 0.022059      |
| raw        | 0.700000 | 0.800000 | 146  | 15       | 0.733578   | 0.102740      |
| raw        | 0.800000 | 0.900000 | 7    | 1        | 0.830749   | 0.142857      |
| calibrated | 0.000000 | 0.100000 | 2581 | 31       | 0.019964   | 0.012011      |
| calibrated | 0.100000 | 0.200000 | 56   | 4        | 0.122035   | 0.071429      |
| calibrated | 0.200000 | 0.300000 | 5    | 1        | 0.228565   | 0.200000      |
| calibrated | 0.300000 | 0.400000 | 1    | 0        | 0.305077   | 0.000000      |
+------------+----------+----------+------+----------+------------+---------------+

PAIRED FORECASTS VS. NAIVE PERSISTENCE (same observed test targets)

+------------+------+-----------+----------+-----------+-----------+----------+----------+
| Target     | N    | Candidate | Weight   | Model MAE | Naive MAE | Model R2 | Naive R2 |
+------------+------+-----------+----------+-----------+-----------+----------+----------+
| roa        | 2643 | level     | 0.400000 | 0.496261  | 0.590154  | 0.441899 | 0.108452 |
| roe        | 2277 | level     | 0.800000 | 0.225377  | 0.247818  | 0.542172 | 0.335839 |
| eps        | 0    | level     | 1.000000 | N/A       | N/A       | N/A      | N/A      |
| debt_ratio | 2643 | level     | 0.050000 | 0.790460  | 0.793887  | 0.496286 | 0.497654 |
| ocf_ratio  | 0    | level     | 1.000000 | N/A       | N/A       | N/A      | N/A      |
+------------+------+-----------+----------+-----------+-----------+----------+----------+

DISTRESS CLASSIFICATION BENCHMARK

+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+------+------+----+
| Model               | Threshold | Accuracy | Precision | Recall   | F1       | F2       | ROC-AUC  | PR-AUC   | Brier    | Log loss | Mean score | TP | FP   | TN   | FN |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+------+------+----+
| xgboost             | 0.074804  | 0.942111 | 0.102041  | 0.416667 | 0.163934 | 0.257732 | 0.807527 | 0.082107 | 0.013111 | 0.064799 | 0.022629   | 15 | 132  | 2475 | 21 |
| lightgbm            | 0.081086  | 0.953840 | 0.094340  | 0.277778 | 0.140845 | 0.200000 | 0.801656 | 0.075508 | 0.013149 | 0.065396 | 0.022388   | 10 | 96   | 2511 | 26 |
| random_forest       | 0.070250  | 0.937571 | 0.094340  | 0.416667 | 0.153846 | 0.247525 | 0.798481 | 0.068786 | 0.013140 | 0.065270 | 0.022279   | 15 | 144  | 2463 | 21 |
| logistic_regression | 0.500000  | 0.714340 | 0.025099  | 0.527778 | 0.047919 | 0.105438 | 0.680369 | 0.044564 | 0.248655 | 0.693502 | 0.495034   | 19 | 738  | 1869 | 17 |
| altman_z_baseline   | 0.500000  | 0.635641 | 0.027523  | 0.750000 | 0.053097 | 0.120000 | 0.726197 | 0.026185 | 0.280045 | 2.741266 | 0.393293   | 27 | 954  | 1653 | 9  |
| xgboost_raw         | 0.500000  | 0.572456 | 0.025997  | 0.833333 | 0.050420 | 0.115562 | 0.807527 | 0.082107 | 0.227376 | 0.642367 | 0.452169   | 30 | 1124 | 1483 | 6  |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----------+----------+------------+----+------+------+----+

Selected best model: xgboost. Test prevalence: 0.013621. Raw TreeSHAP maximum margin error: 8.91741365e-07.

TOP 10 GLOBAL TREESHAP FEATURES (mean absolute log-odds contribution)

+-------------------------+-------------+
| Feature                 | Mean |SHAP| |
+-------------------------+-------------+
| working_capital_ratio   | 0.219983    |
| asset_turnover          | 0.210035    |
| roa                     | 0.176617    |
| debt_ratio              | 0.151617    |
| retained_earnings_ratio | 0.102845    |
| operating_margin        | 0.100619    |
| current_ratio           | 0.079689    |
| roe                     | 0.060880    |
| roe_yoy_delta           | 0.056757    |
| debt_to_equity          | 0.051274    |
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