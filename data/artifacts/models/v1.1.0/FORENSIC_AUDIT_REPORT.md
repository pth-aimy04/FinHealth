# FinHealth forensic audit | v1.1.0

The 2026-11-14 offline run used existing SEC EDGAR companyfacts and submissions caches.
The active pointer names `v1.1.0`. The complete fitted benchmarks, calibration
deciles and six publication figures are linked from [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md).
The checksum in [metadata.json](metadata.json) covers the serialized fitted model.
The previous run is documented in the [v1.0.0 audit](../v1.0.0/FORENSIC_AUDIT_REPORT.md).

| Check | Evidence |
| --- | --- |
| Panel | 1,234 annual 10-K statements from 80 issuers, 0 quarterly or synthetic rows |
| Industrial scope | No SIC 6000–6799 issuers in the panel. CIK 0001826011 and its five annual rows were removed from the active panel and SQLite. Its raw SEC files remain available. |
| Point-in-time split | 864 training feature rows, 748 supervised rows, 0 non-forward publications, 79 validation labels with 12 positives, 160 embargoed test origins, 80 test labels with 10 positives |
| Publication cutoff | Validation labels were observable by 2024-03-01. A test origin enters the evaluation only when its reported filing is on or after this date. |
| SQLite | Alembic 0003. Integrity check returned `ok` and foreign-key check returned no rows. All 1,234 statements and metrics were reconciled to Parquet and raw facts. |
| Model/API parity | All 1,234 PCA assignments and all 80 active predictions were compared with independent inference. |
| Calibration | Fit on FY2022 origins. Weighted XGBoost logit `m` maps to `sigmoid(0.5428277188 × m − 0.8435238503)`. The fitted positive weight is 9.8405797101. |
| Calibration holdout | Raw-to-calibrated Brier 0.072606 → 0.058535, log loss 0.228313 → 0.205068, mean score 18.59% → 15.43%. Observed proxy prevalence was 12.50%. |
| TreeSHAP | The base value plus all contributions reconstructs the raw margin to a maximum absolute error of `2.10688449e-06` on the held-out labels. |
| Stress simulator | AAPL with revenue −15%, margin −5 percentage points, liabilities +20%, and OCF −25% moved the proxy score from 1.850% to 4.886%. Altman Z fell by 0.929. ROE was outside the training P1–P99 range. SQLite bytes were identical before and after. |

The scope gate rejects depository institutions, insurers and REITs before the API
fetches companyfacts. The Altman decision rule uses 1.81 for manufacturing and
1.10 for nonmanufacturing. It treats missing scores as neutral and applies a strict
less-than cutoff. Manufacturing still uses a book-equity variant and operating income
as the EBIT proxy. Class weighting changes the ideal weighted logistic margin by
the natural log of the positive class weight. The calibrated score estimates the
annual financial distress proxy in this issuer panel.

The following forecast scores use identical held-out rows with reported current and
next-period target values. Blend candidates and weights were selected using only
validation. Raw persistence sets the forecast to the current reported value.
The level model supplies a prediction when persistence cannot be calculated.

| Indicator | N | Persistence R² | Model R² | Persistence MAE | Model MAE | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| ROA | 77 | −0.022787 | 0.234163 | 0.040333 | 0.036218 | Improves both |
| ROE | 54 | 0.499915 | 0.608431 | 0.116189 | 0.118813 | Improves R², higher MAE |
| EPS | 78 | 0.538523 | 0.670463 | 2.479487 | 2.382617 | Improves both |
| Liabilities / assets | 77 | 0.823081 | 0.823081 | 0.048250 | 0.048250 | Validation selected persistence |
| OCF / liabilities | 75 | 0.819935 | 0.867871 | 0.042296 | 0.040675 | Improves both |

The acceptance criterion of strictly improving R² and MAE on all five indicators
remains unmet. The same test window is now measured, so any later model selection
requires a new independent holdout.

| Evidence | Location |
| --- | --- |
| SQLite checks, metric coverage, figure DPI and full AAPL simulation | [verification.json](audit-logs/verification.json) |
| Chromium desktop and mobile checks | [browser-qa.json](audit-logs/browser-qa.json) |
| Dashboard capture and rendered one-page credit memo | [Dashboard](audit-logs/dashboard-credit-aapl.png), [PDF](audit-logs/aapl-credit-memo-qa.pdf) |
| Original gate outputs | [Ruff](audit-logs/ruff.txt), [mypy](audit-logs/mypy.txt), [pytest](audit-logs/pytest.txt) |
| Full training terminal transcript | [CLI output](../../training-stage8.txt) |

The SQLite and Parquet files from before Stage 8 are retained in
[the local archive](../../model_archive/v1.0.0-before-stage8/).
