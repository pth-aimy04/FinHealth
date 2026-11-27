> Inactive: the user reverted to the original interface on 2026-11-27. This file records the rejected React migration.

# React frontend migration and feature audit

The React application is the primary UI. FastAPI serves **frontend/dist**; source,
node_modules and the previous UI are outside the public static root. The previous
HTML/CSS/JS and preview have been preserved in frontend/legacy during migration.

## Feature → screen → actual API → permission → verification

All API paths below have prefix `/api/v1`. Authorization is based on router dependencies,
not older README claims. In particular, simulate is public and rate-limited; manual and
batch prediction require a verified session. Write requests use existing Origin/CSRF checks.

| Feature | React screen | Actual API | Permission | Verification |
| --- | --- | --- | --- | --- |
| Inventory and model availability | / | GET dashboard/overview, health | Guest | Browser + API integration |
| Risk distribution and industry coverage | / | GET companies (all bounded pages) | Guest | Browser + formatter tests |
| Ticker/name/CIK search | /screener | GET companies?q= | Guest | Browser query/filter flow |
| Sector/year/risk/cluster/ratio filters | /screener | GET companies with CompanyScreeningFilters | Guest | API filters + URL restore |
| Sort, multi-sort, pagination, column visibility | /screener | Client transforms on full filtered response | Guest | TanStack Table + browser |
| Filtered CSV | /screener | Same filtered company response | Authenticated UI policy | Serializer tests |
| Save screener | /screener | POST me/screeners | Verified owner + CSRF | Browser real cookie write |
| Identity and latest annual/quarterly history | /company/:id | GET companies/:id?form_type=&include_provenance=true | Guest | Browser deep link + API tests |
| Credit ratios and historical provenance | Company financials | Same company response | Guest | API schema + history export tests |
| Composite health and four pillars | Company overview | company, health_pillars | Guest | Server-derived values only |
| Peer medians and percentiles | Company overview | sector_peer_context | Guest | Existing peer invariants |
| DuPont/ROE bridge | Company financials | dupont | Guest | Existing mathematical tests |
| Quality of earnings, accruals, checklist | Company quality | quality_of_earnings, accounting_checklist | Guest | Existing domain tests |
| Next-period forecasts | Company forecast | latest_prediction | Guest | Browser + API parity |
| Threshold and signed TreeSHAP, all inputs | Company forecast | models/evaluation + latest_prediction | Guest | Browser + output-space tests |
| Stress scenarios and presets | Company stress | POST companies/:id/simulate | Public, rate-limited, CSRF when session present | Existing neutral/shock invariants |
| Credit memo / history CSV | Company memo/financials | Current analysis response | Authenticated UI policy | Browser print/export controls |
| Follow company | Company | POST me/watchlist/:cik | Verified owner + CSRF | Browser |
| Compare 2–4 issuers, aligned periods | /compare | GET companies/compare?identifiers=&common_fiscal_year= | Guest | Browser + alignment invariants |
| Comparison medians/history/forecasts | /compare | cohort_medians, historical_series, matched prediction fields | Guest | API comparison tests |
| Publication versions and as-of | /reports | GET reports/:id?as_of=&period_kind=10-K/10-Q | Guest | Browser cutoff |
| SEC/amendment metadata and source tags | /reports | FilingVersionSchema values/provenance/missing_reasons | Guest | Filing-lineage tests |
| Vietnam FPT/HPG pilot | /reports | GET reports/vn:FPT, reports/vn:HPG | Guest, reporting only | Browser FPT |
| Archived forecast evidence | /reports | GET filings/:id/forecasts | Guest | API lineage; hidden for as-of without inference timestamp |
| Report change alerts | /reports | GET report-alerts/:id?as_of= | Guest | Existing version-change tests |
| Data quality | /reports | GET data-quality | Guest | Existing coverage tests |
| PCA and cluster drilldown | /models | GET clusters/map | Guest | Interactive plot + accessible table |
| Model versions/evaluation/calibration | /models | GET models/versions, models/evaluation?model_version= | Guest | Existing evaluation tests |
| Cluster centroids and benchmarks | /models | evaluation_report.clustering and classification fields | Guest | Original API evidence |
| Seven research figures | /models | GET figures/*.png | Guest | Image serving tests |
| Manual prediction | /prediction | POST models/predict-manual | Verified session + CSRF | Frontend validation + API tests |
| Batch prediction (≤200) | /prediction | POST models/predict-batch | Verified session + CSRF | API batch contract |
| Save manual analysis | /prediction | POST me/analyses (server recomputes) | Verified owner + CSRF | Existing ownership tests |
| Private lists, read/delete | /workspace | GET me/{watchlist,screeners,analyses}, GET me/analyses/:id, DELETE me/:collection/:id | Verified owner | Browser write/read/delete + isolation tests |
| Registration/login/email verification | /account | POST auth/register, login, verify-email, resend-verification | Public Origin checked | Existing OTP integration + browser login |
| Recovery, password/email change | /account | POST auth/forgot-password, reset-password, change-password, confirm-password-change, change-email, confirm-email | Recovery public; changes verified session | Existing OTP binding/revocation tests |
| Profile and logout | /account | PATCH auth/profile, POST auth/logout | Verified session + CSRF | Browser + account tests |
| Admin operational state/users | /admin | GET admin/overview, users; PATCH admin/users/:id | Admin | Browser + backend 403 |
| SEC queue/history/events/retry | /admin | POST ingestion/:id, ingestion/:job/retry; GET admin/ingestion, admin/ingestion/:id/events | Admin | Disabled-worker browser view + queue tests |
| Training and audit | /admin | POST models/train; GET admin/audit | Admin | Confirmation UI + existing isolated training tests |

## Serving

Production build uses `/static/assets/*`; only dist is mounted. Supported React routes
refresh to the shell. Unknown API paths, unknown pages, missing assets and traversal
remain 404. Missing dist/index.html returns actionable 503. `/docs`, `/redoc` and
`/openapi.json` retain FastAPI behavior. `FRONTEND_DIR` can explicitly override the build root.

Vite listens on http://127.0.0.1:5173/ and proxies `/api` to port 8000. The proxy
replaces Origin with the backend origin for local development; it retains cookies and
CSRF headers. Production uses the public URL and unchanged server origin validation.

## Regeneration and checks

`frontend/openapi.json` is a snapshot of create_app(...).openapi(), with no database
connection or model loading. `npm run api:types` regenerates schema.d.ts. Rerun the
snapshot exporter after backend contract changes. Auth/workspace/admin ad-hoc responses
are typed separately; the current identity is runtime-validated with Zod.

Mandatory complete terminal outputs are in audit-reports/frontend/ruff.txt and pytest.txt.
Frontend lint, typecheck, unit tests, build and Playwright outputs are alongside them.
Browser screenshots are evidence of the inspected viewport/theme, not financial fixtures.
