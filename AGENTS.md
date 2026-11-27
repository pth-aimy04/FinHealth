# FinHealth engineering standards

These rules apply to every task and every contributor in this repository.

## Architecture

Use Python 3.10+ and the `src/finhealth` package layout:

- `core`: settings, constants, domain exceptions, and logging.
- `db`: SQLAlchemy models, connections, repositories, and migrations.
- `ingestion`: SEC EDGAR clients, throttling, retries, and raw capture.
- `etl`: normalization, accounting concepts, panel assembly, and quality checks.
- `ml`: leakage-safe features, training, evaluation, explainability, and artifacts.
- `api/schemas`: validated request and response contracts.
- `api/routers`: thin FastAPI endpoints delegating to domain services.
- `tests/unit`: isolated mathematical, validation, and structural invariants.
- `tests/integration`: boundaries between components and external systems.
- `frontend`: presentation code, separate from financial and model logic.

Keep raw SEC responses in `data/raw/sec_edgar`, derived Parquet in
`data/processed/parquet`, and model artifacts in `data/artifacts/models`.
Do not commit downloaded data, credentials, database contents, or trained models.
Owner-authorized exception for the GitHub handoff: public financial SEC/Kaggle data,
derived Parquet, model bundles, publication figures, and the allowlisted financial-only
snapshot `data/seed/financial.sqlite3` may be committed. Never include original database
backups, user accounts, password hashes, sessions, OTPs, private workspaces or real `.env`.
Do not perform network requests, create directories, or instantiate settings at import time.

## Data integrity and SEC access

- Every SEC EDGAR REST request MUST send a declared `User-Agent` in the format
  `AppName/Version (ContactEmail)`. Replace the example contact with a monitored
  email address before making real requests.
- Limit aggregate SEC traffic to at most 10 requests/second per user across all
  workers and machines. Configuration validation alone is not a rate limiter;
  ingestion must implement shared throttling and bounded retries with backoff.
- Never invent APIs, library methods, financial values, or XBRL tags. Verify tags
  against SEC filings or the official FASB taxonomy. Retain source tag, accession,
  filing date, fiscal period, currency, units, and amendment provenance.
- Ordered concept candidates are not necessarily equivalent accounting measures.
  Match period, units, consolidation scope, and availability before using a fallback.
  Never substitute liabilities plus equity for liabilities, or consolidated equity
  including noncontrolling interests for equity attributable to stockholders.
- Preserve missing facts as missing; never turn them into zero implicitly.
- Panel financial data MUST NEVER use random train/test splits. Use temporal
  (out-of-time) or company-grouped splits according to the evaluation objective.
  Temporal backtests must only use information available on the prediction date;
  account for publication lag and subsequent restatements.
- Ratios with zero or negative denominators must return `None` or `np.nan` under
  an explicit documented domain policy. Never emit infinity or silently add epsilon.
- Fit Winsorization, imputation, scaling, feature selection, and other learned
  preprocessing ONLY on the training split; apply fitted transforms to later splits.

SEC policy: https://www.sec.gov/about/developer-resources and
https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data.
Official taxonomy: https://xbrl.fasb.org/.

## Implementation quality

- Give every function and method full parameter and return type annotations and
  a concise docstring. Follow PEP 8 and single-responsibility design.
- Use explicit domain exceptions with actionable messages and preserve causes
  when wrapping errors. Never silently swallow exceptions or use bare `except`.
- Never log database passwords, credentials, or sensitive configuration dumps.
- Use `RANDOM_SEED = 42` by default and propagate the configured seed to every
  stochastic component. Document any remaining nondeterminism.
- Keep environment configuration in `core/config.py`, with `.env.example` as
  the onboarding contract. Do not commit `.env` or real contact credentials.

## Tests and completion gates

- Test concrete mathematical and structural invariants with realistic edge and
  failure cases. No placeholder tests, tautological assertions, hardcoded bypasses,
  or mocking the exact function under test. Mock only external boundaries.
- Keep unit tests offline and deterministic. Isolate environment variables and
  temporary paths; integration tests must explicitly declare service requirements.
- Before completing ANY task that creates or modifies files, run `ruff check .`
  and `pytest -v` from the repository root. Fix failures and rerun relevant gates.
- Report the exact full terminal output of both mandatory commands. If a check
  cannot run, state the concrete blocker; never claim an unexecuted check passed.

## Local workflow

Create a Python virtual environment, install with `pip install -e ".[dev]"`,
copy `.env.example` to `.env`, and configure a real SEC contact before ingestion.
Use `docker compose up -d postgres` when a local PostgreSQL service is needed.
Stage 1 provides scaffolding and core infrastructure; do not imply an ingestion
pipeline, trained predictor, or API server exists until implemented and tested.
