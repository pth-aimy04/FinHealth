Current Stage 6.6 workflow (supersedes the original Stage 6.5 defaults below):

```powershell
python -m finhealth.ml.train_cli --mode sec-live
```

The project-owner-authorized research contact is configured. The expanded universe
contains 84 ticker identifiers. At least 300 real annual rows disable synthetic
augmentation even in benchmark mode. SEC runs save sec_real_panel.parquet and
persist to a migrated local finhealth.sqlite3 by default; --database-url selects
another database. sec-live replacements archive the old requested artifact version.
Real feature splits default to train through 2021, validation 2022, test after 2022.
Test origins are embargoed until admitted validation t+1 labels have been published.
Figures and tables score exactly the same post-embargo test rows. If the system
temporary drive is full, set TEMP and TMP to a writable directory with available
space before SQLite/training execution. See REMEDIATION_66.md for complete policies.

The offline fallback now samples nonlinear stochastic outcomes independent of
Altman; the default seed yields approximately 17% simulated distress. The notes
below describe the original Stage 6.5 execution; their 2020/2021 defaults and
initial absence of a configured SEC contact are historical, not current behavior.

Original Stage 6.5 offline benchmark invocation:

```powershell
$env:PYTHONPATH = 'src'
python -m finhealth.ml.train_cli
```

The default run constructs an explicitly synthetic 80-company, 2016–2023 corpus,
passes every simulated XBRL observation through the real Stage 4 parser/ratios/
temporal feature pipeline, merges any valid cached SEC observations, and executes
the real Stage 5 estimators. Regimes change stochastically with a fixed seed (42),
so target labels and predictions are not hardcoded. Classification labels are the
financial-distress proxy, not observed bankruptcies. These metrics verify model
execution on the corpus, not real-world predictive performance or deployment fitness.

Training feature years end in 2020; validation is 2021; test is 2022–2023. Filing
and target publication cutoffs further reduce usable training rows. Final-year
targets are unobserved and excluded from scoring. F2 threshold optimization uses
only the separate validation period and only labels observable by the first test
prediction origin. All preprocessing and target clipping are fitted on training
only. Registry workflows without a validation year retain their existing 0.5 cutoff.

Outputs are the actual fitted bundle, evaluation JSON, BENCHMARK_REPORT.md, and
latest.json under data/artifacts/models; six 300-DPI PNGs under data/artifacts/figures;
and the provenance-marked benchmark_panel.parquet under data/processed/parquet.
Each saved artifact version is immutable; use --model-version for subsequent runs.
Figures use held-out predictions and explicitly identify synthetic runs. Core ratio
correlations are computed on training observations only. PR-AUC uses average
precision. Cluster centroid labels indicate relative health, not validated ratings;
near-zero equity tails can dominate PCA despite winsorization and robust scaling.

`--offline` guarantees no network requests. Without that option, a real monitored
SEC_USER_AGENT contact enables a live ingestion attempt when fewer than 30 companies
are cached. The offline example contact is never used for network access. No real
contact was configured during the initial run; only the simulated corpus was used.

For real SEC collection configure .env (including a monitored contact and database
credentials), apply Alembic migrations, then run:

```powershell
python -m finhealth.ml.train_cli --mode sec-live --model-version sec-v1
```

`--database-url` can select a separately migrated database. sec-live persists real
company statements and metrics, writes sec_panel.parquet, and does not inject
simulated issuers. SEC errors are logged per issuer; insufficient training data
fails explicitly. The curated universe is sector-diverse, not a claim that any
named company is distressed. Models trained on latest-filed SEC caches still need
historical restatement/availability controls before retrospective market evaluation.
