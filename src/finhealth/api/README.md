Run with an activated environment and configured `.env`:

```powershell
alembic upgrade head
uvicorn finhealth.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

The factory opens no database connections and sends no SEC requests. Migrations
remain explicit; startup never creates or changes tables. Settings can be supplied
directly to `create_app(settings)` or loaded lazily through `get_settings` when the
factory runs. Interactive OpenAPI documentation is at `/docs`.

Without an explicit `DATABASE_URL` or `POSTGRES_*` setting, the API uses
SQL Server (`mssql+pyodbc://ADMIN-PC/finhealth_db`). The explicit URL takes precedence
over the PostgreSQL and default SQL Server connection fields in `.env`.

Available routes, all under `/api/v1`:

- `GET /health`: executes SELECT 1; SQL failure returns 503 with degraded status.
- `GET /companies?limit=100&offset=0`: overall latest company metric snapshots.
- `GET /companies/{ticker-or-cik}?form_type=10-K`: persisted chronological history
  and the latest prediction scoped to that source form. `10-Q` is also supported.
- `POST /companies/{ticker-or-cik}/analyze?force_refresh=false`: actual SEC ingestion,
  ETL, optional model inference, and atomic database commit. It persists both annual
  and quarterly statements; `form_type` controls the returned history. Models in
  this workflow infer annual t+1 forecasts only, with target year +1 and period FY.
- `GET /clusters/map`: latest available assigned cluster position for each company.
- `GET /models/evaluation`: the actual active bundle report, or 404 when none exists.
- `POST /models/train`: body `{"train_end_year": 2021, "model_version": "v1.0.0"}`.
  Training reads the persisted annual panel, runs the Stage 5 temporal pipeline,
  saves an immutable artifact version, and only then activates it. Insufficient data
  or classes raises an explicit error; no synthetic/bootstrap data is generated.

Analysis commits statements, metrics, PCA assignments, and prediction together.
Response models are validated before commit. Database failures roll back the whole
request and return credential-safe 503 errors. Inference uses accepted persisted
annual statements, so stale raw caches cannot replace newer financial facts.
GET routes do not ingest, infer, or modify records. Blocking ETL/inference runs on
a worker thread after asynchronous SEC fetches; training routes run in FastAPI's
worker pool. Training requests serialize per registry while readers keep using the
previous complete bundle until activation succeeds.

List snapshots may represent a newer quarterly metric, whereas annual history,
predictions, and the latest assigned cluster point may represent the last 10-K.
Their fiscal years are returned explicitly; clients must preserve that distinction.
TreeSHAP values remain in log-odds, as indicated by `output_space` in predictions.

All response schemas read ORM attributes and convert nonfinite numbers to null,
including nested evaluation JSON and SHAP contributions. Numeric response fields
that can undergo this sanitation are nullable in OpenAPI. Missing metrics are not
imputed merely to populate an API response.

ModelRegistryState exposes locked process-local activation. On first initialization
it reads trusted artifact directories and loads the newest valid saved bundle by
created_at/version; invalid candidates are logged and skipped. Tests or embedded
applications may supply an isolated registry through `app.state.model_registry`.
Database, SEC client, settings, and active bundle providers can all be overridden
through FastAPI dependency overrides. No models are loaded at module import time.

SEC request clients share one rate limiter within each running application's event
loop. The single-dispatcher/cross-process restrictions in ingestion/README.md still
apply. CORS origins come from settings; the default is http://localhost:3000 without
credentials. The account frontend uses same-origin cookies. Administrator writes
require a verified administrator session and CSRF in every environment; the legacy
shared bearer token is no longer accepted. See docs/security-and-accounts.md.
Artifact and proxy-label limitations in
ml/README.md continue to apply to all inference and training responses.
