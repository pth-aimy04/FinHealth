Stage 6.6 changes

- ROE and debt/equity require positive equity and, when assets are positive finite,
  equity/assets >= 5%. Accepted ROE is bounded to [-3,3], debt/equity to [0,20].
  Missing equity ratios remain missing through ETL and target scoring.
- Unsupervised geometry fits 5th/95th percentile bounds, median imputation,
  RobustScaler, then StandardScaler, then PCA/K-Means, on training only. Varying
  training features have population variance 1; constant features necessarily have
  variance 0. Unit scaling does not impose an upper bound on PC1: correlated
  features can legitimately produce PC1 >90%. Diagnostics report the actual result.
- SEC_UNIVERSE contains 84 requested ticker identifiers. Current SEC ticker
  mappings are authoritative; missing/retired tickers are logged rather than
  replaced with invented identifiers. The project-owner-authorized academic
  contact is configured in .env.example, .env, and the Settings default.
- Real training selects the first observed annual filing/accession for each
  annual-duration period, before actual ETL. Later revisions and quarterly footnotes
  are excluded; unsupported fiscal-calendar collisions are explicitly logged and
  excluded by calendar year, retaining unambiguous years from the same company.
  Earliest companyfacts observations are not guaranteed to reconstruct every
  original historic filing; availability dates and per-fact provenance are retained.
- At least 300 usable real annual rows disable synthetic augmentation, including
  in benchmark mode. sec-live never adds synthetic rows. The real panel covers
  calendar period-end years 2010–2025 and is saved as sec_real_panel.parquet.
- Default real feature splits are train through 2021, validation 2022, test after
  2022. Training targets and feature filings after the fit cutoff are purged.
  Annual validation t+1 labels must be published by December of validation year+2.
  Their latest publication is the threshold calibration time. Test origins earlier
  than that time are embargoed; tables and all figures use exactly the remaining
  held-out rows. Thus many 2023 origins are not scored, while later origins remain
  strictly after threshold calibration. This avoids tuning on a single early filer
  or exposing a global threshold to information not yet published.
- Without --database-url, CLI SEC runs migrate and persist to the durable local
  SQLite database data/processed/parquet/finhealth.sqlite3. An explicit URL selects
  another database. The API retains its configured database URL independently.
- sec-live rebuilds a requested existing artifact version only after successful
  fitting/chart creation. Its old bundle is archived under data/artifacts/model_archive;
  it is restored if publishing the replacement fails. Ordinary benchmark runs
  retain immutable-version behavior. latest.json points to the replacement.
- Offline synthetic data remains explicitly simulated. Its financial risk outcomes
  are stochastic nonlinear interactions, independent of the Altman decision rule;
  leverage is bounded and regime sampling is weighted toward healthy/stable firms.
  The default seed produces approximately 17% simulated distress, not a claim
  about any real universe's prevalence.

Real SEC financial data still supplies financial-distress proxy labels, not verified
bankruptcy outcomes. Do not force real prevalence to match the fallback's 15–25%
range, discard adverse baseline comparisons, or treat classifier outputs as
calibrated bankruptcy probabilities. Report every measured score and coverage gap.
