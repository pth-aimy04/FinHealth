# FinHealth empirical benchmark: v1.0.0

This run uses only real SEC EDGAR annual financial statements. All metrics below come from real fitted models and held-out predictions. Labels are a financial distress proxy, not observed bankruptcy outcomes.

Live ingestion: not attempted (offline or no monitored SEC contact). Training through 2021; validation through 2022; later years are test data.

```text
DATASET AND TEMPORAL SPLITS

+-------------------------------------+-----------------------------------+
| Measure                             | Value                             |
+-------------------------------------+-----------------------------------+
| Panel rows                          | 1239                              |
| Companies                           | 81                                |
| Synthetic rows                      | 0                                 |
| Cached SEC rows                     | 1239                              |
| Training feature rows               | 864                               |
| Training supervised rows            | 778                               |
| Validation labeled rows             | 80                                |
| Test feature rows                   | 150                               |
| Test labeled rows                   | 69                                |
| Panel proxy distress prevalence (%) | 10.976594                         |
| Threshold source                    | validation_fiscal_years_2022_2022 |
| Calibration publication date        | 2024-04-01T00:00:00               |
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
| roa        | 0.063589 | 0.178064 | 0.209645 | 66     |
| roe        | 0.156686 | 0.426401 | 0.339740 | 47     |
| eps        | 2.444006 | 3.588484 | 0.678961 | 68     |
| debt_ratio | 0.060064 | 0.084434 | 0.878359 | 67     |
| ocf_ratio  | 0.055718 | 0.112210 | 0.720903 | 67     |
+------------+----------+----------+----------+--------+

NEXT-PERIOD REGRESSION (test targets clipped to training bounds)

+------------+----------+----------+----------+--------+
| Target     | MAE      | RMSE     | R2       | N_Test |
+------------+----------+----------+----------+--------+
| roa        | 0.035012 | 0.055491 | 0.462866 | 66     |
| roe        | 0.095524 | 0.131947 | 0.735315 | 47     |
| eps        | 2.029153 | 2.824301 | 0.731622 | 68     |
| debt_ratio | 0.050376 | 0.064015 | 0.917799 | 67     |
| ocf_ratio  | 0.041582 | 0.057794 | 0.892684 | 67     |
+------------+----------+----------+----------+--------+

+------------+----------------------+----------------------+
| Target     | Training lower bound | Training upper bound |
+------------+----------------------+----------------------+
| roa        | -0.154261            | 0.218927             |
| roe        | -0.407812            | 1.028983             |
| eps        | -5.960000            | 15.485000            |
| debt_ratio | 0.237504             | 1.109337             |
| ocf_ratio  | -0.097041            | 0.930972             |
+------------+----------------------+----------------------+

DISTRESS CLASSIFICATION BENCHMARK

+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----+----+----+----+
| Model               | Threshold | Accuracy | Precision | Recall   | F1       | F2       | ROC-AUC  | PR-AUC   | TP | FP | TN | FN |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----+----+----+----+
| XGBoost             | 0.360000  | 0.898551 | 0.571429  | 0.888889 | 0.695652 | 0.800000 | 0.953704 | 0.833685 | 8  | 6  | 54 | 1  |
| logistic_regression | 0.500000  | 0.695652 | 0.300000  | 1.000000 | 0.461538 | 0.681818 | 0.961111 | 0.855864 | 9  | 21 | 39 | 0  |
| altman_z_baseline   | 0.500000  | 0.739130 | 0.333333  | 1.000000 | 0.500000 | 0.714286 | 0.987037 | 0.951389 | 9  | 18 | 42 | 0  |
+---------------------+-----------+----------+-----------+----------+----------+----------+----------+----------+----+----+----+----+

TOP 10 GLOBAL TREESHAP FEATURES (mean absolute log-odds contribution)

+-------------------------+-------------+
| Feature                 | Mean |SHAP| |
+-------------------------+-------------+
| operating_margin        | 0.927983    |
| ebit_to_assets          | 0.757349    |
| ocf_ratio               | 0.688741    |
| roa                     | 0.448129    |
| debt_ratio_yoy_delta    | 0.417646    |
| asset_turnover          | 0.379148    |
| retained_earnings_ratio | 0.291853    |
| working_capital_ratio   | 0.263106    |
| ocf_ratio_yoy_delta     | 0.253453    |
| current_ratio           | 0.203522    |
+-------------------------+-------------+
```

Threshold tuning uses validation only and ranks F1 and precision within 0.02 of maximum F2. Labels beyond the fit/publication cutoff are purged. SEC caches still require point-in-time revision controls for market backtests.

Regression tables report both original test targets and targets clipped to the training 2.5th and 97.5th percentiles. The parity chart uses original test targets. Cluster labels rank relative centroid health.

- [01_correlation_heatmap.png](../../figures/01_correlation_heatmap.png)
- [02_pca_scree_and_clusters.png](../../figures/02_pca_scree_and_clusters.png)
- [03_roc_pr_curves_comparison.png](../../figures/03_roc_pr_curves_comparison.png)
- [04_confusion_matrices.png](../../figures/04_confusion_matrices.png)
- [05_forecasting_actual_vs_predicted.png](../../figures/05_forecasting_actual_vs_predicted.png)
- [06_shap_global_importance.png](../../figures/06_shap_global_importance.png)