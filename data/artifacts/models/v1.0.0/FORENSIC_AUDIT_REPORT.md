# FinHealth forensic audit | v1.0.0

Audit date 2026-11-14 (UTC+07). Offline audit on Windows with Intel Core i5-6200U,
Python 3.12.14 and SQLite. The audit opened the SEC cache and
the published SQLite database and used the same checksum-verified joblib bundle
as the FastAPI application. No live SEC calls were made. The audit released 2.5 GB of pip download cache when the Windows system volume reached 2.2 MB free. Bundle SHA-256
`35eef0f4d2b5b0b08c7f3be25d18bb9d0c282be22cf906dcd6ddbfe3cdbc59d9`.

## 1. Academic and mathematical fidelity

The implementation switches at SIC 2000–3999. The manufacturing index uses
`1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + X5` with cutoffs 1.81 and 2.99.
The nonmanufacturing index uses `6.56X1 + 3.26X2 + 6.72X3 + 1.05X4`
with cutoffs 1.10 and 2.60. Cutoff equality maps to GREY. Manufacturing X4
uses book equity, while Altman's original public-company X4 uses market equity.
Both implementation branches use operating income as an EBIT proxy. The project
labels use a bespoke fundamentals rule. The Pindado study defines its own
distress criteria and estimation framework. The evaluated classification target
is the project's forward-shifted distress proxy.

- [Altman, 1968](https://doi.org/10.1111/j.1540-6261.1968.tb00843.x)
- [Altman, model variants and thresholds](https://www.stern.nyu.edu/sites/default/files/assets/documents/con_043413.pdf)
- [Pindado, Rodrigues and de la Torre, 2008](https://doi.org/10.1016/j.jbusres.2007.10.006)
- [Lundberg and Lee, 2017](https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html)
- [Lundberg et al., TreeSHAP, 2020](https://doi.org/10.1038/s42256-019-0138-9)

### Filing traces

- AAPL FY2023 CIK=0000320193 SIC=3571 accession=0000320193-23-000106 period_end=2023-09-30 filed=2023-11-03
- AAL FY2020 CIK=0000006201 SIC=4512 accession=0000006201-21-000014 period_end=2020-12-31 filed=2021-02-17
- LUMN FY2023 CIK=0000018926 SIC=4813 accession=0000018926-24-000016 period_end=2023-12-31 filed=2024-02-22

All monetary values are USD except EPS (USD/share). The liabilities in
AAL and LUMN are accounting derivations, explicitly identified in their
provenance. The raw observations, filing context and exact accessions are also
printed in the protocol log. Null ROE and debt/equity follow the 5% equity
cushion and positive-denominator policy.

| XBRL field | AAPL FY2023 | AAL FY2020 | LUMN FY2023 |
| --- | --- | --- | --- |
| current_assets | 143566000000.0 · `AssetsCurrent` | 11095000000.0 · `AssetsCurrent` | 4775000000.0 · `AssetsCurrent` |
| current_liabilities | 145308000000.0 · `LiabilitiesCurrent` | 16569000000.0 · `LiabilitiesCurrent` | 3534000000.0 · `LiabilitiesCurrent` |
| eps_basic | 6.16 · `EarningsPerShareBasic` | -18.36 · `EarningsPerShareBasic` | -10.48 · `EarningsPerShareBasic` |
| eps_diluted | 6.13 · `EarningsPerShareDiluted` | -18.36 · `EarningsPerShareDiluted` | -10.48 · `EarningsPerShareDiluted` |
| net_income | 96995000000.0 · `NetIncomeLoss` | -8885000000.0 · `NetIncomeLoss` | -10298000000.0 · `NetIncomeLoss` |
| operating_cash_flow | 110543000000.0 · `NetCashProvidedByUsedInOperatingActivities` | -6543000000.0 · `NetCashProvidedByUsedInOperatingActivities` | 2160000000.0 · `NetCashProvidedByUsedInOperatingActivities` |
| operating_income | 114301000000.0 · `OperatingIncomeLoss` | -10421000000.0 · `OperatingIncomeLoss` | -9584000000.0 · `OperatingIncomeLoss` |
| retained_earnings | -214000000.0 · `RetainedEarningsAccumulatedDeficit` | -6664000000.0 · `RetainedEarningsAccumulatedDeficit` | -17907000000.0 · `RetainedEarningsAccumulatedDeficit` |
| revenues | 383285000000.0 · `RevenueFromContractWithCustomerExcludingAssessedTax` | 17337000000.0 · `RevenueFromContractWithCustomerExcludingAssessedTax` | 13521000000.0 · `RevenueFromContractWithCustomerExcludingAssessedTax` |
| stockholders_equity | 62146000000.0 · `StockholdersEquity` | -6867000000.0 · `StockholdersEquity` | 417000000.0 · `StockholdersEquity` |
| total_assets | 352583000000.0 · `Assets` | 62008000000.0 · `Assets` | 34018000000.0 · `Assets` |
| total_liabilities | 290437000000.0 · `Liabilities` | 68875000000.0 · `total_assets - stockholders_equity` | 33601000000.0 · `total_assets - stockholders_equity` |

| Metric | AAPL FY2023 | AAL FY2020 | LUMN FY2023 |
| --- | --- | --- | --- |
| altman_z_score | 2.2784833108957683 | -2.163505694318232 | -3.356959731038635 |
| altman_zone | GREY | DISTRESS | DISTRESS |
| asset_turnover | 1.087077369016657 | 0.2795929557476455 | 0.3974660473866776 |
| current_ratio | 0.9880116717592975 | 0.6696239966201943 | 1.3511601584606678 |
| debt_ratio | 0.8237407929480435 | 1.1107437749967746 | 0.987741783761538 |
| debt_ratio_yoy_delta | -0.03261276688810344 | 0.10877694442756036 | 0.2167187697864168 |
| debt_to_equity | 4.673462491552152 | null | null |
| ebit_to_assets | 0.32418182385424144 | -0.16805896013417623 | -0.28173320007055086 |
| eps | 6.13 | -18.36 | -10.48 |
| negative_ocf_streak | 0 | 1 | 0 |
| ocf_ratio | 0.38060921989966845 | -0.09499818511796733 | 0.06428380107734889 |
| ocf_ratio_yoy_delta | -0.02375315732778227 | -0.15846199494279722 | -0.0704475897717292 |
| operating_margin | 0.2982141226502472 | -0.6010843859952703 | -0.7088233118852156 |
| retained_earnings_ratio | -0.0006069492857001047 | -0.10747000387046833 | -0.5263977894056088 |
| roa | 0.27509834563776475 | -0.14328796284350406 | -0.30272208830619085 |
| roa_yoy_delta | -0.007826063654803761 | -0.17139030470532587 | -0.26876056925219904 |
| roe | 1.5607601454639075 | null | null |
| roe_yoy_delta | -0.40882858203846073 | null | null |
| working_capital_ratio | -0.004940680634063469 | -0.08827893175074183 | 0.03648068669527897 |
| is_distressed | 0 | 1 | 1 |
| max_abs_error | 0.0 | 0.0 | 4.440892098500626e-16 |

TreeSHAP compares the actual XGBoost probabilities in float64 logit space
against base plus all 17 signed contributions for each of the 69 classified
test cases. The Altman override re-derives each label twice from the panel.

## 2. Data integrity, time isolation and serving

```text
SEC=1239/1239 replay=1239/1239 SQLite=1239/1239 synthetic=0 direct=13419 derived=531 missing=918
Splits train=864 FY2010–2021 supervised=778 latest_target=2021-12-16 00:00:00 validation=80 FY2022 calibration=2024-04-01 00:00:00 test=150 FY2023–2025 first_test_filing=2024-04-01; fitted arrays within 1e-12
TreeSHAP max abs logit error=2.9525462137414138e-06 n=69
Altman override +999.0/SAFE: 0/1239 labels changed
Altman override -999.0/DISTRESS: 0/1239 labels changed
ROC AUC n=69 real=0.95370370370370372 shuffled=0.45555555555555555
debt_ratio R2 n=67 real=0.87835900179463933 shuffled=-0.11193888881333458
ocf_ratio R2 n=67 real=0.72090339478432819 shuffled=-0.23507328330541388
AAL: P(distress)=0.92041641473770142 max API error=4.4408920985006262e-16
LUMN: P(distress)=0.95233547687530518 max API error=0
AAPL: P(distress)=0.0027008564211428165 max API error=4.4408920985006262e-16
MSFT: P(distress)=0.0017939985264092684 max API error=2.2204460492503131e-16
CCL: P(distress)=0.19593220949172974 max API error=2.2204460492503131e-16
SQLite PCA=1239/1239 max error=0; forecasts=81/81 max scalar error=0
```

- The source replay opens 81 companyfacts files and checks every row and
  recorded fact against SEC accession, unit, filing date, economic period and
  value. SQLite integrity and foreign-key checks pass. The local raw cache
  is the trust boundary for issuer authenticity.
- 209 pre-audit rows used a no-minority-interest derivation despite contrary
  facts in the filing. The repaired parser uses filing-aligned consolidated
  equity for liabilities and adjusts for explicitly reported minority interest
  when deriving attributable equity. For unresolved scope or temporary equity
  it keeps the value missing. Of the 531 remaining derived values, 229 include
  a matched source adjustment and 302 retain the explicit no-minority-interest
  assumption because supported scope tags are absent. Relative to the archived
  panel, liabilities changed on 184 rows (22 became missing) and attributable
  equity on 82 rows (50 became missing). Tags were checked against the
  [official FASB taxonomy](https://xbrl.fasb.org/us-gaap/2025/elts/us-gaap-2025.xsd).
- Parquet, SQLite and `v1.0.0` were rebuilt. The earlier version is retained
  under `data/artifacts/model_archive/v1.0.0-20261113T215314568333` and the
  earlier Parquet and database under `data/artifacts/model_archive/pre-forensic-data`.
  The pre-audit AUC was 0.9462962962962963; debt R² was 0.8557033602910735 and
  OCF R² was 0.7218974513985947.
- Unsupervised fitting uses 864 observable feature rows. Supervised fitting
  uses the 778 rows remaining after the year and publication purge.
  Validation calibrates on 80 observations. The embargo reduces 242 candidate
  test rows to 150, including 69 with classification targets. Independent
  quantiles, imputation medians, robust and standard scaling, and refitted PCA
  reproduce the saved arrays. Winsorizer bounds from the full panel differ.
  No immediately preceding annual feature filing occurs after its origin filing.
- The seed-42 negative control permutes finite training targets only, retains
  missingness and feature values, and scores the original held-out targets.
  A single permutation is a control for this specific workflow. The panel is a
  selected universe of issuers and includes a rule-defined outcome rather than
  observed bankruptcy events. Missing distress signals do not trigger comparisons.
- Every annual record has PCA and cluster fields. All 81 current annual
  predictions, including TreeSHAP, were compared to direct inference, with
  independent five-company HTTP comparisons. SQLite is the settings fallback
  when connection parameters are absent. The workspace `.env` explicitly
  selects the populated SQLite database. A clean temporary-database CLI smoke run also verified [16 Apple metric/PCA rows and one forecast](audit-logs/cli-sync.txt).

## 3. Maintainability and performance

### Timing and memory

| Operation | Samples | Median ms | P95 ms | Peak Python MB | Target ms | Result |
| --- | --- | --- | --- | --- | --- | --- |
| A Apple JSON + annual ETL (uncached decode) | 9 | 18.604600 | 20.567420 | 5.572931 | <25 | PASS |
| A Apple JSON + annual ETL (cached decode) | 15 | 8.756000 | 11.182790 | 4.282260 | <25 | PASS |
| B AAPL inference + TreeSHAP | 15 | 19.693200 | 32.174600 | 0.073030 | <50 | PASS |
| C full training and evaluation | 1 | 3000.167900 | 3000.167900 | 13.340471 | <10000 | PASS |
| D GET /api/v1/health | 25 | 8.214100 | 9.686620 | 0.057300 | <30 | PASS |
| D GET /api/v1/companies | 25 | 14.529200 | 23.353020 | 0.317109 | <30 | PASS |
| D GET /api/v1/companies/AAPL | 25 | 13.319200 | 19.737060 | 0.161358 | <30 | PASS |
| D GET /api/v1/clusters/map | 25 | 17.101300 | 22.139240 | 0.353069 | <30 | PASS |
| D GET /api/v1/models/evaluation | 25 | 6.386700 | 8.021340 | 0.060549 | <30 | PASS |

The repeated ETL gate uses the content-keyed annual projection cache. Every sample opens
and reads the 4.27 MB Apple companyfacts file, then runs statement normalization, ratios,
Altman and temporal features. The cached projection already selected fiscal contexts. The uncached-decode row clears the application
cache before each sample and measures the same end-to-end path with the OS file
cache warm. The uncached row is reported separately from the repeat gate.
Inference uses a loaded bundle and one warm-up. API calls use in-process HTTP
with one warm-up and the populated SQLite database. A clean temporary-database CLI smoke run also verified [16 Apple metric/PCA rows and one forecast](audit-logs/cli-sync.txt). The P95 gate applies to API
calls, median to ETL and inference, and one elapsed sample to the full model fit.
`tracemalloc` peak is a separate invocation and measures traced Python allocations.
It excludes untracked native estimator/decoder memory and retained warm cache.
Coverage instrumentation is suspended during wall-time and allocation measurements.

### Code inspection

- Annual filing selection is shared between offline training and serving.
  Type checking covers all 44 source modules, with missing-stub exemptions scoped
  to third-party packages. The company and cluster list endpoints use one
  projected SQL query each and serialize validated responses once. Preprocessing
  reuses fitted numeric bounds and median arrays. TreeSHAP reuses the fitted tree
  representation and transformed classifier input.
- The AST scan inspected 538 assertions and found 0 unconditional
  truthy literal assertions. Manual test inspection found no mock of the same
  function under test. Substitutions inject the SEC HTTP transport, environment,
  missing Spark import, replacement-file failure, or the session factory used
  by the test. The real audit tests use raw captures, real models and real SQLite.
- The largest remaining functions are CLI orchestration, table formatting and
  benchmark-only synthetic data generation. The CLI and reporting functions
  retain cross-step orchestration and presentation work. Coverage gaps are listed
  exactly below, including optional Spark and live SEC modes. The migration
  suite validates PostgreSQL SQL generation and SQLite execution.
- The audit's empirical tests skip when the local Parquet artifact is absent.
  A present panel with missing SEC, SQLite or model evidence fails.

| Function LOC | File | Function |
| --- | --- | --- |
| 151 | src/finhealth/ml/train_cli.py | run_training |
| 145 | src/finhealth/ml/train_cli.py | benchmark_tables |
| 99 | src/finhealth/api/services.py | _snapshots |
| 97 | src/finhealth/ml/benchmark_data.py | build_benchmark_panel |
| 86 | src/finhealth/etl/xbrl_parser.py | parse |
| 84 | src/finhealth/ml/registry.py | train_and_evaluate_pipeline |
| 73 | src/finhealth/api/main.py | create_app |
| 72 | tests/integration/test_forensic_audit.py | test_all_statement_provenance |
| 69 | tests/unit/test_db_repositories.py | test_metric_and_prediction_upsert_with_shap_json |
| 68 | tests/integration/test_forensic_audit.py | test_out_of_time_and_fitted_statistics |
| 66 | tests/integration/test_forensic_audit.py | test_prediction_and_api_parity |
| 62 | src/finhealth/ml/pca_clustering.py | fit |

### Python inventory and line coverage

Physical LOC counts blank lines and comments. Classes and functions are AST
definitions, including methods and nested/async functions. Maximum function LOC
spans the definition through its last source line. Test files are inventoried
but source coverage is scoped to `finhealth`.

| Python file | LOC | Classes | Functions | Max function LOC | Stmts | Miss | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| src/finhealth/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/api/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/api/dependencies.py | 102 | 1 | 8 | 20 | 65 | 10 | 85% |
| src/finhealth/api/main.py | 96 | 0 | 5 | 73 | 46 | 3 | 93% |
| src/finhealth/api/routers/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/api/routers/companies.py | 65 | 0 | 4 | 12 | 27 | 0 | 100% |
| src/finhealth/api/routers/health.py | 38 | 0 | 1 | 20 | 20 | 4 | 80% |
| src/finhealth/api/routers/models.py | 42 | 0 | 2 | 11 | 18 | 0 | 100% |
| src/finhealth/api/schemas/__init__.py | 27 | 0 | 0 | 0 | 2 | 0 | 100% |
| src/finhealth/api/schemas/models.py | 166 | 10 | 2 | 9 | 118 | 0 | 100% |
| src/finhealth/api/services.py | 353 | 1 | 12 | 99 | 126 | 1 | 99% |
| src/finhealth/core/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/core/config.py | 121 | 1 | 8 | 17 | 68 | 0 | 100% |
| src/finhealth/core/constants.py | 32 | 0 | 0 | 0 | 3 | 0 | 100% |
| src/finhealth/core/exceptions.py | 29 | 7 | 0 | 0 | 7 | 0 | 100% |
| src/finhealth/core/logging.py | 35 | 0 | 1 | 27 | 20 | 0 | 100% |
| src/finhealth/db/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/db/base.py | 34 | 2 | 1 | 3 | 11 | 0 | 100% |
| src/finhealth/db/models.py | 215 | 4 | 0 | 0 | 98 | 0 | 100% |
| src/finhealth/db/repositories.py | 274 | 4 | 17 | 42 | 108 | 0 | 100% |
| src/finhealth/db/session.py | 71 | 0 | 6 | 17 | 38 | 1 | 97% |
| src/finhealth/etl/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/etl/annual.py | 180 | 7 | 3 | 50 | 81 | 2 | 98% |
| src/finhealth/etl/feature_engineering.py | 92 | 1 | 4 | 33 | 56 | 2 | 96% |
| src/finhealth/etl/financial_ratios.py | 110 | 0 | 4 | 41 | 47 | 1 | 98% |
| src/finhealth/etl/pipeline.py | 188 | 1 | 5 | 50 | 81 | 19 | 77% |
| src/finhealth/etl/spark_session.py | 32 | 0 | 1 | 22 | 11 | 4 | 64% |
| src/finhealth/etl/xbrl_parser.py | 270 | 3 | 5 | 86 | 167 | 11 | 93% |
| src/finhealth/ingestion/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/ingestion/rate_limiter.py | 45 | 1 | 4 | 13 | 27 | 0 | 100% |
| src/finhealth/ingestion/schemas.py | 97 | 2 | 8 | 8 | 52 | 0 | 100% |
| src/finhealth/ingestion/sec_client.py | 238 | 1 | 11 | 34 | 151 | 7 | 95% |
| src/finhealth/ml/__init__.py | 0 | 0 | 0 | 0 | 0 | 0 | 100% |
| src/finhealth/ml/benchmark_data.py | 108 | 0 | 1 | 97 | 48 | 0 | 100% |
| src/finhealth/ml/distress_classifier.py | 210 | 2 | 13 | 27 | 90 | 10 | 89% |
| src/finhealth/ml/evaluator.py | 98 | 0 | 3 | 31 | 36 | 3 | 92% |
| src/finhealth/ml/explainer.py | 89 | 1 | 6 | 31 | 44 | 5 | 89% |
| src/finhealth/ml/forecaster.py | 85 | 1 | 3 | 28 | 43 | 2 | 95% |
| src/finhealth/ml/pca_clustering.py | 126 | 1 | 3 | 62 | 67 | 2 | 97% |
| src/finhealth/ml/preprocessing.py | 66 | 1 | 4 | 18 | 44 | 8 | 82% |
| src/finhealth/ml/registry.py | 274 | 1 | 6 | 84 | 133 | 13 | 90% |
| src/finhealth/ml/splitter.py | 168 | 1 | 6 | 43 | 104 | 12 | 88% |
| src/finhealth/ml/train_cli.py | 622 | 0 | 10 | 151 | 214 | 73 | 66% |
| src/finhealth/ml/visualization.py | 274 | 1 | 10 | 34 | 126 | 2 | 98% |
| tests/__init__.py | 0 | 0 | 0 | 0 | — | — | — |
| tests/integration/__init__.py | 0 | 0 | 0 | 0 | — | — | — |
| tests/integration/test_api_endpoints.py | 357 | 0 | 16 | 61 | — | — | — |
| tests/integration/test_db_migrations.py | 68 | 0 | 2 | 27 | — | — | — |
| tests/integration/test_forensic_audit.py | 669 | 0 | 29 | 72 | — | — | — |
| tests/unit/__init__.py | 0 | 0 | 0 | 0 | — | — | — |
| tests/unit/test_core_config.py | 213 | 0 | 14 | 33 | — | — | — |
| tests/unit/test_core_logging.py | 74 | 0 | 4 | 20 | — | — | — |
| tests/unit/test_db_repositories.py | 520 | 0 | 22 | 69 | — | — | — |
| tests/unit/test_db_session.py | 78 | 0 | 6 | 15 | — | — | — |
| tests/unit/test_etl_pipeline.py | 397 | 0 | 15 | 38 | — | — | — |
| tests/unit/test_ml_pipeline.py | 334 | 0 | 11 | 50 | — | — | — |
| tests/unit/test_sec_ingestion.py | 389 | 1 | 26 | 40 | — | — | — |
| tests/unit/test_stage66_remediation.py | 105 | 0 | 5 | 26 | — | — | — |
| tests/unit/test_stage67.py | 56 | 0 | 2 | 28 | — | — | — |
| tests/unit/test_visualization_and_cli.py | 102 | 0 | 2 | 55 | — | — | — |

Coverage total: 2397 statements, 195 missed, 92%.

## 4. Automated checks and exact terminal output

The integration suite is `tests/integration/test_forensic_audit.py`.
Run all commands from the repository root in the project's virtual environment.

| Command | Exact final output | Full transcript |
| --- | --- | --- |
| `ruff check .` | All checks passed! | [ruff](audit-logs/ruff.txt) |
| `mypy src/finhealth` | Success: no issues found in 44 source files | [mypy](audit-logs/mypy.txt) |
| `pytest -s -v tests/integration/test_forensic_audit.py` | ======================= 16 passed, 1 warning in 34.32s ======================== | [Protocols and raw traces](audit-logs/protocols.txt) |
| `pytest --cov=finhealth --cov-report=term-missing -v` | ================= 128 passed, 1 warning in 111.79s (0:01:51) ================== | [Coverage and missing lines](audit-logs/coverage.txt) |
| `pytest -v` | ================== 128 passed, 1 warning in 61.17s (0:01:01) ================== | [Pytest](audit-logs/pytest.txt) |

<details>
<summary>Exact terminal transcripts</summary>

### ruff check .

```text
All checks passed!
```

### mypy src/finhealth

```text
Success: no issues found in 44 source files
```

### forensic protocols

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- D:\DATN\.venv\Scripts\python.exe
cachedir: .venv\pytest-cache
rootdir: D:\DATN
configfile: pyproject.toml
plugins: anyio-4.16.0, asyncio-1.5.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 16 items

tests/integration/test_forensic_audit.py::test_all_statement_provenance SEC=1239/1239 replay=1239/1239 SQLite=1239/1239 synthetic=0 direct=13419 derived=531 missing=918
PASSED
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAPL-2023] Trace AAPL FY2023 CIK=0000320193 SIC=3571 accession=0000320193-23-000106 period_end=2023-09-30 filed=2023-11-03
{"facts": {"current_assets": [143566000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": null, "tag": "AssetsCurrent", "unit": "USD"}], "current_liabilities": [145308000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": null, "tag": "LiabilitiesCurrent", "unit": "USD"}], "eps_basic": [6.16, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": "2022-09-25", "tag": "EarningsPerShareBasic", "unit": "USD/shares"}], "eps_diluted": [6.13, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": "2022-09-25", "tag": "EarningsPerShareDiluted", "unit": "USD/shares"}], "net_income": [96995000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": "2022-09-25", "tag": "NetIncomeLoss", "unit": "USD"}], "operating_cash_flow": [110543000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": "2022-09-25", "tag": "NetCashProvidedByUsedInOperatingActivities", "unit": "USD"}], "operating_income": [114301000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": "2022-09-25", "tag": "OperatingIncomeLoss", "unit": "USD"}], "retained_earnings": [-214000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": null, "tag": "RetainedEarningsAccumulatedDeficit", "unit": "USD"}], "revenues": [383285000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": "2022-09-25", "tag": "RevenueFromContractWithCustomerExcludingAssessedTax", "unit": "USD"}], "stockholders_equity": [62146000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": null, "tag": "StockholdersEquity", "unit": "USD"}], "total_assets": [352583000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": null, "tag": "Assets", "unit": "USD"}], "total_liabilities": [290437000000.0, {"accn": "0000320193-23-000106", "currency": "USD", "duration_basis": "period", "end": "2023-09-30", "filed": "2023-11-03", "start": null, "tag": "Liabilities", "unit": "USD"}]}, "is_distressed": 0, "max_abs_error": 0.0, "metrics": {"altman_z_score": 2.2784833108957683, "altman_zone": "GREY", "asset_turnover": 1.087077369016657, "current_ratio": 0.9880116717592975, "debt_ratio": 0.8237407929480435, "debt_ratio_yoy_delta": -0.03261276688810344, "debt_to_equity": 4.673462491552152, "ebit_to_assets": 0.32418182385424144, "eps": 6.13, "negative_ocf_streak": 0, "ocf_ratio": 0.38060921989966845, "ocf_ratio_yoy_delta": -0.02375315732778227, "operating_margin": 0.2982141226502472, "retained_earnings_ratio": -0.0006069492857001047, "roa": 0.27509834563776475, "roa_yoy_delta": -0.007826063654803761, "roe": 1.5607601454639075, "roe_yoy_delta": -0.40882858203846073, "working_capital_ratio": -0.004940680634063469}}
PASSED
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAL-2020] Trace AAL FY2020 CIK=0000006201 SIC=4512 accession=0000006201-21-000014 period_end=2020-12-31 filed=2021-02-17
{"facts": {"current_assets": [11095000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": null, "tag": "AssetsCurrent", "unit": "USD"}], "current_liabilities": [16569000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": null, "tag": "LiabilitiesCurrent", "unit": "USD"}], "eps_basic": [-18.36, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": "2020-01-01", "tag": "EarningsPerShareBasic", "unit": "USD/shares"}], "eps_diluted": [-18.36, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": "2020-01-01", "tag": "EarningsPerShareDiluted", "unit": "USD/shares"}], "net_income": [-8885000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": "2020-01-01", "tag": "NetIncomeLoss", "unit": "USD"}], "operating_cash_flow": [-6543000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": "2020-01-01", "tag": "NetCashProvidedByUsedInOperatingActivities", "unit": "USD"}], "operating_income": [-10421000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": "2020-01-01", "tag": "OperatingIncomeLoss", "unit": "USD"}], "retained_earnings": [-6664000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": null, "tag": "RetainedEarningsAccumulatedDeficit", "unit": "USD"}], "revenues": [17337000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": "2020-01-01", "tag": "RevenueFromContractWithCustomerExcludingAssessedTax", "unit": "USD"}], "stockholders_equity": [-6867000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": null, "tag": "StockholdersEquity", "unit": "USD"}], "total_assets": [62008000000.0, {"accn": "0000006201-21-000014", "currency": "USD", "duration_basis": "period", "end": "2020-12-31", "filed": "2021-02-17", "start": null, "tag": "Assets", "unit": "USD"}], "total_liabilities": [68875000000.0, {"assumption": "no noncontrolling interests", "derived": "total_assets - stockholders_equity"}]}, "is_distressed": 1, "max_abs_error": 0.0, "metrics": {"altman_z_score": -2.163505694318232, "altman_zone": "DISTRESS", "asset_turnover": 0.2795929557476455, "current_ratio": 0.6696239966201943, "debt_ratio": 1.1107437749967746, "debt_ratio_yoy_delta": 0.10877694442756036, "debt_to_equity": null, "ebit_to_assets": -0.16805896013417623, "eps": -18.36, "negative_ocf_streak": 1, "ocf_ratio": -0.09499818511796733, "ocf_ratio_yoy_delta": -0.15846199494279722, "operating_margin": -0.6010843859952703, "retained_earnings_ratio": -0.10747000387046833, "roa": -0.14328796284350406, "roa_yoy_delta": -0.17139030470532587, "roe": null, "roe_yoy_delta": null, "working_capital_ratio": -0.08827893175074183}}
PASSED
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[LUMN-2023] Trace LUMN FY2023 CIK=0000018926 SIC=4813 accession=0000018926-24-000016 period_end=2023-12-31 filed=2024-02-22
{"facts": {"current_assets": [4775000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": null, "tag": "AssetsCurrent", "unit": "USD"}], "current_liabilities": [3534000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": null, "tag": "LiabilitiesCurrent", "unit": "USD"}], "eps_basic": [-10.48, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": "2023-01-01", "tag": "EarningsPerShareBasic", "unit": "USD/shares"}], "eps_diluted": [-10.48, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": "2023-01-01", "tag": "EarningsPerShareDiluted", "unit": "USD/shares"}], "net_income": [-10298000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": "2023-01-01", "tag": "NetIncomeLoss", "unit": "USD"}], "operating_cash_flow": [2160000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": "2023-01-01", "tag": "NetCashProvidedByUsedInOperatingActivities", "unit": "USD"}], "operating_income": [-9584000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": "2023-01-01", "tag": "OperatingIncomeLoss", "unit": "USD"}], "retained_earnings": [-17907000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": null, "tag": "RetainedEarningsAccumulatedDeficit", "unit": "USD"}], "revenues": [13521000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": "2023-01-01", "tag": "RevenueFromContractWithCustomerExcludingAssessedTax", "unit": "USD"}], "stockholders_equity": [417000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": null, "tag": "StockholdersEquity", "unit": "USD"}], "total_assets": [34018000000.0, {"accn": "0000018926-24-000016", "currency": "USD", "duration_basis": "period", "end": "2023-12-31", "filed": "2024-02-22", "start": null, "tag": "Assets", "unit": "USD"}], "total_liabilities": [33601000000.0, {"assumption": "no noncontrolling interests", "derived": "total_assets - stockholders_equity"}]}, "is_distressed": 1, "max_abs_error": 4.440892098500626e-16, "metrics": {"altman_z_score": -3.356959731038635, "altman_zone": "DISTRESS", "asset_turnover": 0.3974660473866776, "current_ratio": 1.3511601584606678, "debt_ratio": 0.987741783761538, "debt_ratio_yoy_delta": 0.2167187697864168, "debt_to_equity": null, "ebit_to_assets": -0.28173320007055086, "eps": -10.48, "negative_ocf_streak": 0, "ocf_ratio": 0.06428380107734889, "ocf_ratio_yoy_delta": -0.0704475897717292, "operating_margin": -0.7088233118852156, "retained_earnings_ratio": -0.5263977894056088, "roa": -0.30272208830619085, "roa_yoy_delta": -0.26876056925219904, "roe": null, "roe_yoy_delta": null, "working_capital_ratio": 0.03648068669527897}}
PASSED
tests/integration/test_forensic_audit.py::test_altman_distress_independence Altman override +999.0/SAFE: 0/1239 labels changed
Altman override -999.0/DISTRESS: 0/1239 labels changed
PASSED
tests/integration/test_forensic_audit.py::test_out_of_time_and_fitted_statistics Splits train=864 FY2010–2021 supervised=778 latest_target=2021-12-16 00:00:00 validation=80 FY2022 calibration=2024-04-01 00:00:00 test=150 FY2023–2025 first_test_filing=2024-04-01; fitted arrays within 1e-12
PASSED
tests/integration/test_forensic_audit.py::test_tree_shap_all_held_out TreeSHAP max abs logit error=2.9525462137414138e-06 n=69
PASSED
tests/integration/test_forensic_audit.py::test_training_target_permutation ROC AUC n=69 real=0.95370370370370372 shuffled=0.45555555555555555
debt_ratio R2 n=67 real=0.87835900179463933 shuffled=-0.11193888881333458
ocf_ratio R2 n=67 real=0.72090339478432819 shuffled=-0.23507328330541388
PASSED
tests/integration/test_forensic_audit.py::test_prediction_and_api_parity AAL: P(distress)=0.92041641473770142 max API error=4.4408920985006262e-16
LUMN: P(distress)=0.95233547687530518 max API error=0
AAPL: P(distress)=0.0027008564211428165 max API error=4.4408920985006262e-16
MSFT: P(distress)=0.0017939985264092684 max API error=2.2204460492503131e-16
CCL: P(distress)=0.19593220949172974 max API error=2.2204460492503131e-16
SQLite PCA=1239/1239 max error=0; forecasts=81/81 max scalar error=0
PASSED
tests/integration/test_forensic_audit.py::test_etl_and_inference_latency BENCHMARK|A Apple JSON + annual ETL (uncached decode)|9|18.604600|20.567420|5.572931
BENCHMARK|A Apple JSON + annual ETL (cached decode)|15|8.756000|11.182790|4.282260
BENCHMARK|B AAPL inference + TreeSHAP|15|19.693200|32.174600|0.073030
PASSED
tests/integration/test_forensic_audit.py::test_training_latency_and_saved_scores BENCHMARK|C full training and evaluation|1|3000.167900|3000.167900|13.340471
PASSED
tests/integration/test_forensic_audit.py::test_api_latency[/health] BENCHMARK|D GET /api/v1/health|25|8.214100|9.686620|0.057300
PASSED
tests/integration/test_forensic_audit.py::test_api_latency[/companies] BENCHMARK|D GET /api/v1/companies|25|14.529200|23.353020|0.317109
PASSED
tests/integration/test_forensic_audit.py::test_api_latency[/companies/AAPL] BENCHMARK|D GET /api/v1/companies/AAPL|25|13.319200|19.737060|0.161358
PASSED
tests/integration/test_forensic_audit.py::test_api_latency[/clusters/map] BENCHMARK|D GET /api/v1/clusters/map|25|17.101300|22.139240|0.353069
PASSED
tests/integration/test_forensic_audit.py::test_api_latency[/models/evaluation] BENCHMARK|D GET /api/v1/models/evaluation|25|6.386700|8.021340|0.060549
PASSED

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\DATN\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 16 passed, 1 warning in 34.32s ========================
```

### coverage

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- D:\DATN\.venv\Scripts\python.exe
cachedir: .venv\pytest-cache
rootdir: D:\DATN
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0, asyncio-1.5.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 128 items

tests/integration/test_api_endpoints.py::test_health_endpoint_reports_db_and_model_status PASSED [  0%]
tests/integration/test_api_endpoints.py::test_analyze_company_end_to_end_by_ticker_and_cik PASSED [  1%]
tests/integration/test_api_endpoints.py::test_get_company_and_list_companies_after_ingestion PASSED [  2%]
tests/integration/test_api_endpoints.py::test_get_unknown_company_returns_404 PASSED [  3%]
tests/integration/test_api_endpoints.py::test_model_evaluation_endpoint_returns_benchmark_metrics PASSED [  3%]
tests/integration/test_api_endpoints.py::test_api_training_uses_persisted_panel_and_activates_saved_bundle PASSED [  4%]
tests/integration/test_api_endpoints.py::test_schema_nonfinite_sanitization_and_registry_autoload PASSED [  5%]
tests/integration/test_api_endpoints.py::test_sec_failures_are_structured_and_do_not_commit PASSED [  6%]
tests/integration/test_api_endpoints.py::test_analysis_transaction_rolls_back_database_failure PASSED [  7%]
tests/integration/test_db_migrations.py::test_migration_upgrade_matches_metadata_and_downgrade PASSED [  7%]
tests/integration/test_db_migrations.py::test_postgresql_offline_migration_sql PASSED [  8%]
tests/integration/test_forensic_audit.py::test_all_statement_provenance PASSED [  9%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAPL-2023] PASSED [ 10%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAL-2020] PASSED [ 10%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[LUMN-2023] PASSED [ 11%]
tests/integration/test_forensic_audit.py::test_altman_distress_independence PASSED [ 12%]
tests/integration/test_forensic_audit.py::test_out_of_time_and_fitted_statistics PASSED [ 13%]
tests/integration/test_forensic_audit.py::test_tree_shap_all_held_out PASSED [ 14%]
tests/integration/test_forensic_audit.py::test_training_target_permutation PASSED [ 14%]
tests/integration/test_forensic_audit.py::test_prediction_and_api_parity PASSED [ 15%]
tests/integration/test_forensic_audit.py::test_etl_and_inference_latency PASSED [ 16%]
tests/integration/test_forensic_audit.py::test_training_latency_and_saved_scores PASSED [ 17%]
tests/integration/test_forensic_audit.py::test_api_latency[/health] PASSED [ 17%]
tests/integration/test_forensic_audit.py::test_api_latency[/companies] PASSED [ 18%]
tests/integration/test_forensic_audit.py::test_api_latency[/companies/AAPL] PASSED [ 19%]
tests/integration/test_forensic_audit.py::test_api_latency[/clusters/map] PASSED [ 20%]
tests/integration/test_forensic_audit.py::test_api_latency[/models/evaluation] PASSED [ 21%]
tests/unit/test_core_config.py::test_valid_configuration_and_database_url PASSED [ 21%]
tests/unit/test_core_config.py::test_database_url_escapes_credentials PASSED [ 22%]
tests/unit/test_core_config.py::test_database_url_defaults_to_local_sqlite PASSED [ 23%]
tests/unit/test_core_config.py::test_dotenv_loading_and_environment_precedence PASSED [ 24%]
tests/unit/test_core_config.py::test_data_paths_derive_from_root_with_explicit_override PASSED [ 25%]
tests/unit/test_core_config.py::test_example_environment_loads PASSED    [ 25%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[] PASSED [ 26%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[   ] PASSED [ 27%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0] PASSED [ 28%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[research@example.com] PASSED [ 28%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-requests] PASSED [ 29%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-requests/2.31.0 (research@example.com)] PASSED [ 30%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-httpx/0.27.0 (research@example.com)] PASSED [ 31%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[curl/8.0 (research@example.com)] PASSED [ 32%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (missing-email)] PASSED [ 32%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (@example.com)] PASSED [ 33%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (research@)] PASSED [ 34%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (research@example.com)\r\nInjected: header] PASSED [ 35%]
tests/unit/test_core_config.py::test_sec_user_agent_uses_authorized_research_default PASSED [ 35%]
tests/unit/test_core_config.py::test_sec_user_agent_trims_surrounding_whitespace PASSED [ 36%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[10.01] PASSED [ 37%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[11.0] PASSED [ 38%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[0.0] PASSED [ 39%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[-1.0] PASSED [ 39%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[inf] PASSED [ 40%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[nan] PASSED [ 41%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[0.001] PASSED [ 42%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[8.0] PASSED [ 42%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[10.0] PASSED [ 43%]
tests/unit/test_core_config.py::test_assignment_cannot_bypass_sec_rate_validation PASSED [ 44%]
tests/unit/test_core_config.py::test_accounting_concepts_have_nonempty_ordered_tag_candidates PASSED [ 45%]
tests/unit/test_core_logging.py::test_logging_is_idempotent_and_updates_level PASSED [ 46%]
tests/unit/test_core_logging.py::test_invalid_logging_level_has_no_side_effects PASSED [ 46%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[ConfigurationError] PASSED [ 47%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[SecIngestionError] PASSED [ 48%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[EtlProcessingError] PASSED [ 49%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[ModelPipelineError] PASSED [ 50%]
tests/unit/test_db_repositories.py::test_normalize_cik_valid_and_invalid PASSED [ 50%]
tests/unit/test_db_repositories.py::test_company_upsert_idempotency PASSED [ 51%]
tests/unit/test_db_repositories.py::test_company_pagination PASSED       [ 52%]
tests/unit/test_db_repositories.py::test_statement_upsert_and_restatement_handling PASSED [ 53%]
tests/unit/test_db_repositories.py::test_chronological_ordering PASSED   [ 53%]
tests/unit/test_db_repositories.py::test_metric_and_prediction_upsert_with_shap_json PASSED [ 54%]
tests/unit/test_db_repositories.py::test_metric_chronological_order_and_source_alignment PASSED [ 55%]
tests/unit/test_db_repositories.py::test_latest_prediction_version_and_timestamp_tie PASSED [ 56%]
tests/unit/test_db_repositories.py::test_prediction_probability_bounds[-0.01] PASSED [ 57%]
tests/unit/test_db_repositories.py::test_prediction_probability_bounds[1.01] PASSED [ 57%]
tests/unit/test_db_repositories.py::test_database_constraints_and_foreign_keys PASSED [ 58%]
tests/unit/test_db_repositories.py::test_cross_company_analytics_are_rejected PASSED [ 59%]
tests/unit/test_db_repositories.py::test_payloads_cannot_override_identity_or_add_unknown_fields PASSED [ 60%]
tests/unit/test_db_repositories.py::test_cascade_delete_company[orm] PASSED [ 60%]
tests/unit/test_db_repositories.py::test_cascade_delete_company[sql] PASSED [ 61%]
tests/unit/test_db_repositories.py::test_statement_delete_cascades_to_analytics PASSED [ 62%]
tests/unit/test_db_repositories.py::test_relationship_delete_orphans PASSED [ 63%]
tests/unit/test_db_repositories.py::test_repositories_do_not_commit PASSED [ 64%]
tests/unit/test_db_session.py::test_request_session_commits_success PASSED [ 64%]
tests/unit/test_db_session.py::test_request_session_rolls_back_failure PASSED [ 65%]
tests/unit/test_db_session.py::test_request_session_close_rolls_back PASSED [ 66%]
tests/unit/test_db_session.py::test_sqlite_foreign_keys_on_every_connection PASSED [ 67%]
tests/unit/test_etl_pipeline.py::test_xbrl_parser_resolves_comparative_years_from_apple_fixture PASSED [ 67%]
tests/unit/test_etl_pipeline.py::test_duration_priority_restatement_and_unit_resolution PASSED [ 68%]
tests/unit/test_etl_pipeline.py::test_quarter_preference_and_ocf_ytd_fallback PASSED [ 69%]
tests/unit/test_etl_pipeline.py::test_identity_fallbacks_missing_values_and_invalid_input PASSED [ 70%]
tests/unit/test_etl_pipeline.py::test_balance_fallback_accounts_for_equity_scope PASSED [ 71%]
tests/unit/test_etl_pipeline.py::test_financial_ratios_and_negative_equity_guard PASSED [ 71%]
tests/unit/test_etl_pipeline.py::test_altman_z_score_manufacturing_vs_non_manufacturing PASSED [ 72%]
tests/unit/test_etl_pipeline.py::test_temporal_deltas_and_negative_ocf_streak PASSED [ 73%]
tests/unit/test_etl_pipeline.py::test_ratio_winsorizer_prevents_test_leakage PASSED [ 74%]
tests/unit/test_etl_pipeline.py::test_end_to_end_etl_to_db_and_parquet PASSED [ 75%]
tests/unit/test_etl_pipeline.py::test_etl_batch_rollback_and_stale_metrics PASSED [ 75%]
tests/unit/test_etl_pipeline.py::test_optional_spark_missing_dependency_falls_back_to_real_parquet PASSED [ 76%]
tests/unit/test_etl_pipeline.py::test_parser_nonfinite_and_ambiguous_calendar PASSED [ 77%]
tests/unit/test_ml_pipeline.py::test_temporal_splitter_and_next_period_alignment PASSED [ 78%]
tests/unit/test_ml_pipeline.py::test_pca_clustering_deterministic_health_ranking PASSED [ 78%]
tests/unit/test_ml_pipeline.py::test_next_period_forecaster_and_metrics PASSED [ 79%]
tests/unit/test_ml_pipeline.py::test_distress_classifier_vs_baselines_and_f2_threshold PASSED [ 80%]
tests/unit/test_ml_pipeline.py::test_tree_shap_explainer_instance_and_global PASSED [ 81%]
tests/unit/test_ml_pipeline.py::test_full_pipeline_registry_save_load_and_company_inference PASSED [ 82%]
tests/unit/test_ml_pipeline.py::test_labels_metric_edges_and_degenerate_clusters PASSED [ 82%]
tests/unit/test_ml_pipeline.py::test_publication_cutoff_and_train_only_preprocessing PASSED [ 83%]
tests/unit/test_sec_ingestion.py::test_rate_limiter_enforces_minimum_interval PASSED [ 84%]
tests/unit/test_sec_ingestion.py::test_rate_limiter_cancellation_and_context PASSED [ 85%]
tests/unit/test_sec_ingestion.py::test_sic_to_sector_mapping PASSED      [ 85%]
tests/unit/test_sec_ingestion.py::test_fetch_tickers_and_resolve_cik_with_cache PASSED [ 86%]
tests/unit/test_sec_ingestion.py::test_fetch_company_metadata_cache_and_no_tickers PASSED [ 87%]
tests/unit/test_sec_ingestion.py::test_fetch_company_facts_retry_on_503_and_atomic_save PASSED [ 88%]
tests/unit/test_sec_ingestion.py::test_fetch_company_facts_no_retry_on_404_or_403 PASSED [ 89%]
tests/unit/test_sec_ingestion.py::test_retry_exhaustion_transport_and_exponential_backoff PASSED [ 89%]
tests/unit/test_sec_ingestion.py::test_invalid_responses_and_cache_preserve_existing_data PASSED [ 90%]
tests/unit/test_sec_ingestion.py::test_atomic_write_failure_preserves_target PASSED [ 91%]
tests/unit/test_sec_ingestion.py::test_shared_limiter_and_transport_recovery PASSED [ 92%]
tests/unit/test_sec_ingestion.py::test_invalid_metadata_and_ticker_contracts PASSED [ 92%]
tests/unit/test_stage66_remediation.py::test_five_percent_equity_cushion_and_ratio_bounds PASSED [ 93%]
tests/unit/test_stage66_remediation.py::test_unsupervised_training_geometry_is_zero_mean_and_unit_variance PASSED [ 94%]
tests/unit/test_stage66_remediation.py::test_fallback_outcomes_are_sparse_nonlinear_and_not_altman_labels PASSED [ 95%]
tests/unit/test_stage66_remediation.py::test_first_filed_annual_context_excludes_quarterly_and_future_revisions PASSED [ 96%]
tests/unit/test_stage66_remediation.py::test_calibration_labels_precede_every_scored_test_origin PASSED [ 96%]
tests/unit/test_stage67.py::test_fundamental_distress_rules_ignore_altman_columns PASSED [ 97%]
tests/unit/test_stage67.py::test_forecast_scoring_clips_only_finite_truth_at_fitted_bounds PASSED [ 98%]
tests/unit/test_visualization_and_cli.py::test_visualization_and_cli_artifacts PASSED [ 99%]
tests/unit/test_visualization_and_cli.py::test_benchmark_reproducibility_and_cached_sec_etl PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\DATN\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=============================== tests coverage ================================
______________ coverage: platform win32, python 3.12.14-final-0 _______________

Name                                       Stmts   Miss  Cover   Missing
------------------------------------------------------------------------
src\finhealth\__init__.py                      0      0   100%
src\finhealth\api\__init__.py                  0      0   100%
src\finhealth\api\dependencies.py             65     10    85%   53-54, 77-79, 88-91, 102
src\finhealth\api\main.py                     46      3    93%   36-38
src\finhealth\api\routers\__init__.py          0      0   100%
src\finhealth\api\routers\companies.py        27      0   100%
src\finhealth\api\routers\health.py           20      4    80%   28-30, 32
src\finhealth\api\routers\models.py           18      0   100%
src\finhealth\api\schemas\__init__.py          2      0   100%
src\finhealth\api\schemas\models.py          118      0   100%
src\finhealth\api\services.py                126      1    99%   193
src\finhealth\core\__init__.py                 0      0   100%
src\finhealth\core\config.py                  68      0   100%
src\finhealth\core\constants.py                3      0   100%
src\finhealth\core\exceptions.py               7      0   100%
src\finhealth\core\logging.py                 20      0   100%
src\finhealth\db\__init__.py                   0      0   100%
src\finhealth\db\base.py                      11      0   100%
src\finhealth\db\models.py                    98      0   100%
src\finhealth\db\repositories.py             108      0   100%
src\finhealth\db\session.py                   38      1    97%   58
src\finhealth\etl\__init__.py                  0      0   100%
src\finhealth\etl\annual.py                   81      2    98%   127-128
src\finhealth\etl\feature_engineering.py      56      2    96%   62, 90
src\finhealth\etl\financial_ratios.py         47      1    98%   66
src\finhealth\etl\pipeline.py                 81     19    77%   71, 93, 118, 135-136, 142-188
src\finhealth\etl\spark_session.py            11      4    64%   21-30
src\finhealth\etl\xbrl_parser.py             167     11    93%   115, 147, 162, 165, 193, 208, 211, 214, 219, 240-241
src\finhealth\ingestion\__init__.py            0      0   100%
src\finhealth\ingestion\rate_limiter.py       27      0   100%
src\finhealth\ingestion\schemas.py            52      0   100%
src\finhealth\ingestion\sec_client.py        151      7    95%   61, 79, 81, 85, 115, 149, 231
src\finhealth\ml\__init__.py                   0      0   100%
src\finhealth\ml\benchmark_data.py            48      0   100%
src\finhealth\ml\distress_classifier.py       90     10    89%   42, 96, 101-103, 113, 135-136, 181, 183
src\finhealth\ml\evaluator.py                 36      3    92%   32, 77, 84
src\finhealth\ml\explainer.py                 44      5    89%   28, 35, 43, 45, 54
src\finhealth\ml\forecaster.py                43      2    95%   56, 80
src\finhealth\ml\pca_clustering.py            67      2    97%   38, 115
src\finhealth\ml\preprocessing.py             44      8    82%   21, 31, 34-35, 41, 52, 55-56
src\finhealth\ml\registry.py                 133     13    90%   63, 88, 96, 150, 177-178, 195, 198, 201, 210, 213, 239, 241
src\finhealth\ml\splitter.py                 104     12    88%   68, 72, 74, 76, 80, 94, 97, 118, 129, 142, 159, 163
src\finhealth\ml\train_cli.py                214     73    66%   135-136, 163-164, 170-196, 380-413, 431, 433, 444-448, 450-452, 462, 519-525, 528-531, 589-595, 609-610, 622
src\finhealth\ml\visualization.py            126      2    98%   65, 166
------------------------------------------------------------------------
TOTAL                                       2397    195    92%
================= 128 passed, 1 warning in 111.79s (0:01:51) ==================
```

### pytest -v

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- D:\DATN\.venv\Scripts\python.exe
cachedir: .venv\pytest-cache
rootdir: D:\DATN
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0, asyncio-1.5.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collecting ... collected 128 items

tests/integration/test_api_endpoints.py::test_health_endpoint_reports_db_and_model_status PASSED [  0%]
tests/integration/test_api_endpoints.py::test_analyze_company_end_to_end_by_ticker_and_cik PASSED [  1%]
tests/integration/test_api_endpoints.py::test_get_company_and_list_companies_after_ingestion PASSED [  2%]
tests/integration/test_api_endpoints.py::test_get_unknown_company_returns_404 PASSED [  3%]
tests/integration/test_api_endpoints.py::test_model_evaluation_endpoint_returns_benchmark_metrics PASSED [  3%]
tests/integration/test_api_endpoints.py::test_api_training_uses_persisted_panel_and_activates_saved_bundle PASSED [  4%]
tests/integration/test_api_endpoints.py::test_schema_nonfinite_sanitization_and_registry_autoload PASSED [  5%]
tests/integration/test_api_endpoints.py::test_sec_failures_are_structured_and_do_not_commit PASSED [  6%]
tests/integration/test_api_endpoints.py::test_analysis_transaction_rolls_back_database_failure PASSED [  7%]
tests/integration/test_db_migrations.py::test_migration_upgrade_matches_metadata_and_downgrade PASSED [  7%]
tests/integration/test_db_migrations.py::test_postgresql_offline_migration_sql PASSED [  8%]
tests/integration/test_forensic_audit.py::test_all_statement_provenance PASSED [  9%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAPL-2023] PASSED [ 10%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[AAL-2020] PASSED [ 10%]
tests/integration/test_forensic_audit.py::test_raw_ratio_trace[LUMN-2023] PASSED [ 11%]
tests/integration/test_forensic_audit.py::test_altman_distress_independence PASSED [ 12%]
tests/integration/test_forensic_audit.py::test_out_of_time_and_fitted_statistics PASSED [ 13%]
tests/integration/test_forensic_audit.py::test_tree_shap_all_held_out PASSED [ 14%]
tests/integration/test_forensic_audit.py::test_training_target_permutation PASSED [ 14%]
tests/integration/test_forensic_audit.py::test_prediction_and_api_parity PASSED [ 15%]
tests/integration/test_forensic_audit.py::test_etl_and_inference_latency PASSED [ 16%]
tests/integration/test_forensic_audit.py::test_training_latency_and_saved_scores PASSED [ 17%]
tests/integration/test_forensic_audit.py::test_api_latency[/health] PASSED [ 17%]
tests/integration/test_forensic_audit.py::test_api_latency[/companies] PASSED [ 18%]
tests/integration/test_forensic_audit.py::test_api_latency[/companies/AAPL] PASSED [ 19%]
tests/integration/test_forensic_audit.py::test_api_latency[/clusters/map] PASSED [ 20%]
tests/integration/test_forensic_audit.py::test_api_latency[/models/evaluation] PASSED [ 21%]
tests/unit/test_core_config.py::test_valid_configuration_and_database_url PASSED [ 21%]
tests/unit/test_core_config.py::test_database_url_escapes_credentials PASSED [ 22%]
tests/unit/test_core_config.py::test_database_url_defaults_to_local_sqlite PASSED [ 23%]
tests/unit/test_core_config.py::test_dotenv_loading_and_environment_precedence PASSED [ 24%]
tests/unit/test_core_config.py::test_data_paths_derive_from_root_with_explicit_override PASSED [ 25%]
tests/unit/test_core_config.py::test_example_environment_loads PASSED    [ 25%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[] PASSED [ 26%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[   ] PASSED [ 27%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0] PASSED [ 28%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[research@example.com] PASSED [ 28%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-requests] PASSED [ 29%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-requests/2.31.0 (research@example.com)] PASSED [ 30%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[python-httpx/0.27.0 (research@example.com)] PASSED [ 31%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[curl/8.0 (research@example.com)] PASSED [ 32%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (missing-email)] PASSED [ 32%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (@example.com)] PASSED [ 33%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (research@)] PASSED [ 34%]
tests/unit/test_core_config.py::test_invalid_sec_user_agent_is_rejected[FinHealth/1.0 (research@example.com)\r\nInjected: header] PASSED [ 35%]
tests/unit/test_core_config.py::test_sec_user_agent_uses_authorized_research_default PASSED [ 35%]
tests/unit/test_core_config.py::test_sec_user_agent_trims_surrounding_whitespace PASSED [ 36%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[10.01] PASSED [ 37%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[11.0] PASSED [ 38%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[0.0] PASSED [ 39%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[-1.0] PASSED [ 39%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[inf] PASSED [ 40%]
tests/unit/test_core_config.py::test_invalid_sec_rate_is_rejected[nan] PASSED [ 41%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[0.001] PASSED [ 42%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[8.0] PASSED [ 42%]
tests/unit/test_core_config.py::test_valid_sec_rate_boundaries[10.0] PASSED [ 43%]
tests/unit/test_core_config.py::test_assignment_cannot_bypass_sec_rate_validation PASSED [ 44%]
tests/unit/test_core_config.py::test_accounting_concepts_have_nonempty_ordered_tag_candidates PASSED [ 45%]
tests/unit/test_core_logging.py::test_logging_is_idempotent_and_updates_level PASSED [ 46%]
tests/unit/test_core_logging.py::test_invalid_logging_level_has_no_side_effects PASSED [ 46%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[ConfigurationError] PASSED [ 47%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[SecIngestionError] PASSED [ 48%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[EtlProcessingError] PASSED [ 49%]
tests/unit/test_core_logging.py::test_domain_exceptions_preserve_message[ModelPipelineError] PASSED [ 50%]
tests/unit/test_db_repositories.py::test_normalize_cik_valid_and_invalid PASSED [ 50%]
tests/unit/test_db_repositories.py::test_company_upsert_idempotency PASSED [ 51%]
tests/unit/test_db_repositories.py::test_company_pagination PASSED       [ 52%]
tests/unit/test_db_repositories.py::test_statement_upsert_and_restatement_handling PASSED [ 53%]
tests/unit/test_db_repositories.py::test_chronological_ordering PASSED   [ 53%]
tests/unit/test_db_repositories.py::test_metric_and_prediction_upsert_with_shap_json PASSED [ 54%]
tests/unit/test_db_repositories.py::test_metric_chronological_order_and_source_alignment PASSED [ 55%]
tests/unit/test_db_repositories.py::test_latest_prediction_version_and_timestamp_tie PASSED [ 56%]
tests/unit/test_db_repositories.py::test_prediction_probability_bounds[-0.01] PASSED [ 57%]
tests/unit/test_db_repositories.py::test_prediction_probability_bounds[1.01] PASSED [ 57%]
tests/unit/test_db_repositories.py::test_database_constraints_and_foreign_keys PASSED [ 58%]
tests/unit/test_db_repositories.py::test_cross_company_analytics_are_rejected PASSED [ 59%]
tests/unit/test_db_repositories.py::test_payloads_cannot_override_identity_or_add_unknown_fields PASSED [ 60%]
tests/unit/test_db_repositories.py::test_cascade_delete_company[orm] PASSED [ 60%]
tests/unit/test_db_repositories.py::test_cascade_delete_company[sql] PASSED [ 61%]
tests/unit/test_db_repositories.py::test_statement_delete_cascades_to_analytics PASSED [ 62%]
tests/unit/test_db_repositories.py::test_relationship_delete_orphans PASSED [ 63%]
tests/unit/test_db_repositories.py::test_repositories_do_not_commit PASSED [ 64%]
tests/unit/test_db_session.py::test_request_session_commits_success PASSED [ 64%]
tests/unit/test_db_session.py::test_request_session_rolls_back_failure PASSED [ 65%]
tests/unit/test_db_session.py::test_request_session_close_rolls_back PASSED [ 66%]
tests/unit/test_db_session.py::test_sqlite_foreign_keys_on_every_connection PASSED [ 67%]
tests/unit/test_etl_pipeline.py::test_xbrl_parser_resolves_comparative_years_from_apple_fixture PASSED [ 67%]
tests/unit/test_etl_pipeline.py::test_duration_priority_restatement_and_unit_resolution PASSED [ 68%]
tests/unit/test_etl_pipeline.py::test_quarter_preference_and_ocf_ytd_fallback PASSED [ 69%]
tests/unit/test_etl_pipeline.py::test_identity_fallbacks_missing_values_and_invalid_input PASSED [ 70%]
tests/unit/test_etl_pipeline.py::test_balance_fallback_accounts_for_equity_scope PASSED [ 71%]
tests/unit/test_etl_pipeline.py::test_financial_ratios_and_negative_equity_guard PASSED [ 71%]
tests/unit/test_etl_pipeline.py::test_altman_z_score_manufacturing_vs_non_manufacturing PASSED [ 72%]
tests/unit/test_etl_pipeline.py::test_temporal_deltas_and_negative_ocf_streak PASSED [ 73%]
tests/unit/test_etl_pipeline.py::test_ratio_winsorizer_prevents_test_leakage PASSED [ 74%]
tests/unit/test_etl_pipeline.py::test_end_to_end_etl_to_db_and_parquet PASSED [ 75%]
tests/unit/test_etl_pipeline.py::test_etl_batch_rollback_and_stale_metrics PASSED [ 75%]
tests/unit/test_etl_pipeline.py::test_optional_spark_missing_dependency_falls_back_to_real_parquet PASSED [ 76%]
tests/unit/test_etl_pipeline.py::test_parser_nonfinite_and_ambiguous_calendar PASSED [ 77%]
tests/unit/test_ml_pipeline.py::test_temporal_splitter_and_next_period_alignment PASSED [ 78%]
tests/unit/test_ml_pipeline.py::test_pca_clustering_deterministic_health_ranking PASSED [ 78%]
tests/unit/test_ml_pipeline.py::test_next_period_forecaster_and_metrics PASSED [ 79%]
tests/unit/test_ml_pipeline.py::test_distress_classifier_vs_baselines_and_f2_threshold PASSED [ 80%]
tests/unit/test_ml_pipeline.py::test_tree_shap_explainer_instance_and_global PASSED [ 81%]
tests/unit/test_ml_pipeline.py::test_full_pipeline_registry_save_load_and_company_inference PASSED [ 82%]
tests/unit/test_ml_pipeline.py::test_labels_metric_edges_and_degenerate_clusters PASSED [ 82%]
tests/unit/test_ml_pipeline.py::test_publication_cutoff_and_train_only_preprocessing PASSED [ 83%]
tests/unit/test_sec_ingestion.py::test_rate_limiter_enforces_minimum_interval PASSED [ 84%]
tests/unit/test_sec_ingestion.py::test_rate_limiter_cancellation_and_context PASSED [ 85%]
tests/unit/test_sec_ingestion.py::test_sic_to_sector_mapping PASSED      [ 85%]
tests/unit/test_sec_ingestion.py::test_fetch_tickers_and_resolve_cik_with_cache PASSED [ 86%]
tests/unit/test_sec_ingestion.py::test_fetch_company_metadata_cache_and_no_tickers PASSED [ 87%]
tests/unit/test_sec_ingestion.py::test_fetch_company_facts_retry_on_503_and_atomic_save PASSED [ 88%]
tests/unit/test_sec_ingestion.py::test_fetch_company_facts_no_retry_on_404_or_403 PASSED [ 89%]
tests/unit/test_sec_ingestion.py::test_retry_exhaustion_transport_and_exponential_backoff PASSED [ 89%]
tests/unit/test_sec_ingestion.py::test_invalid_responses_and_cache_preserve_existing_data PASSED [ 90%]
tests/unit/test_sec_ingestion.py::test_atomic_write_failure_preserves_target PASSED [ 91%]
tests/unit/test_sec_ingestion.py::test_shared_limiter_and_transport_recovery PASSED [ 92%]
tests/unit/test_sec_ingestion.py::test_invalid_metadata_and_ticker_contracts PASSED [ 92%]
tests/unit/test_stage66_remediation.py::test_five_percent_equity_cushion_and_ratio_bounds PASSED [ 93%]
tests/unit/test_stage66_remediation.py::test_unsupervised_training_geometry_is_zero_mean_and_unit_variance PASSED [ 94%]
tests/unit/test_stage66_remediation.py::test_fallback_outcomes_are_sparse_nonlinear_and_not_altman_labels PASSED [ 95%]
tests/unit/test_stage66_remediation.py::test_first_filed_annual_context_excludes_quarterly_and_future_revisions PASSED [ 96%]
tests/unit/test_stage66_remediation.py::test_calibration_labels_precede_every_scored_test_origin PASSED [ 96%]
tests/unit/test_stage67.py::test_fundamental_distress_rules_ignore_altman_columns PASSED [ 97%]
tests/unit/test_stage67.py::test_forecast_scoring_clips_only_finite_truth_at_fitted_bounds PASSED [ 98%]
tests/unit/test_visualization_and_cli.py::test_visualization_and_cli_artifacts PASSED [ 99%]
tests/unit/test_visualization_and_cli.py::test_benchmark_reproducibility_and_cached_sec_etl PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\DATN\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================== 128 passed, 1 warning in 61.17s (0:01:01) ==================
```

</details>
