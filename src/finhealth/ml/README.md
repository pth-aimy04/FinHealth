The ML engine uses fiscal-year out-of-time partitions, never random panel splits.
`build_next_period_panel` shifts only within company/form groups. Annual targets
must be the following fiscal year; quarterly targets require Q1..Q4 sequential
fiscal ordinals. Missing quarterly filings (including a missing Q4 10-Q) remain
gaps; the engine does not fabricate fourth-quarter observations from 10-K data.

Feature-year splitting alone is insufficient: a 2021 feature row may contain a
2022 shifted label. `training_horizon_rows` purges targets past the training year
and retains that boundary in DataFrame attrs so repeated calls are idempotent.
When filing dates are provided, target filings must also be available by year end.
The orchestrator additionally excludes training feature filings published after
the cutoff. Per-fact historical revision control remains the caller's data-layer
responsibility: Stage 4's latest-filing snapshots are not point-in-time archives.

Winsorization, imputation, scaling, PCA, and K-Means fit on training data only.
Regression target clipping is learned from observed finite training targets, with
separate regressors and no target imputation. All-missing feature columns retain
their dimensions and use SimpleImputer's fixed-zero empty-feature behavior; this
is model preprocessing, not a fabricated accounting fact. Degenerate PCA variance
fractions are reported as zero; silhouette is zero when mathematically undefined.

Cluster IDs are ordered by the specified composite scaled financial health score,
with original-space training centroids retained for inspection. These semantic
labels express relative sample clusters, not validated credit ratings. If fewer
than four clusters can be fitted, only the corresponding first K labels are used.

Observed binary labels take precedence row by row. Missing labels use the specified
financial distress proxy. A classifier trained on this proxy predicts that proxy;
it is not empirically validated bankruptcy probability. The requested Altman
baseline uses a fixed 1.81 cutoff for all firms and a continuous logistic risk score;
it is a benchmark and does not fit probability calibration. It deliberately does
not reuse the selected XGBoost decision threshold.

The registry's default train/test workflow keeps threshold 0.5. Call
`optimize_threshold` only on a distinct validation period, never on test rows.
Threshold selection maximizes validation F2; fixed risk bands remain independent
of the classification threshold. One-class test ROC AUC and unobservable regression
metrics are JSON null; their sample counts remain explicit.

TreeSHAP uses the actual fitted XGBoost ensemble with path-dependent training tree
statistics, not a background fitted on held-out data. Contributions and base value
are in **log-odds**: `expit(base_value + sum(contributions))` reconstructs probability.
Top-driver feature values are the clipped/imputed inputs actually seen by the model.
Held-out global SHAP importance is evaluation output, never used for feature selection.

Artifact versions are immutable directories published by an atomic staging rename.
Existing versions cannot be overwritten. Metadata records dependency versions and
the model payload checksum; report JSON must match the serialized bundle. Load
only trusted local joblib artifacts: a checksum provides corruption detection, not
authentication or safe deserialization. Use matching dependency versions for reload.
No trained models are committed to the repository. Tests use explicitly synthetic,
accounting-consistent panel data and exercise real models, baselines, TreeSHAP,
and disk round trips; their scores are software verification, not market validation.
