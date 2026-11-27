# FinHealth UI/UX Research Benchmark

## 1. Domain & Benchmark Products

FinHealth is a corporate financial health and distress prediction platform built on SEC EDGAR filings (`10-K` / `10-Q`), corporate finance diagnostics (Altman Z-Score, DuPont bridge, Quality of Earnings, 8-signal accounting checklist, 4-pillar health score), PCA peer clustering, what-if stress simulation, and calibrated TreeSHAP explainability.

We benchmarked four real-world product classes to ground every layout and interaction decision:

| Benchmark | Surface Role | Patterns Adopted | Patterns Rejected |
|---|---|---|---|
| **Koyfin / Quartr** | Dense equity & filing research | Tabular monospaced numerals (`tabular-nums`), right-aligned numeric columns, compact financial statement tables, instant ticker/CIK command search (`Ctrl+K`), explicit `10-K` vs `10-Q` period toggles | Cluttered multi-panel chrome that overwhelms first-time analysts |
| **Mercury / Stripe Dashboard** | Modern fintech operations | Calm high-contrast light ground (`#F8F9FA` / `#FFFFFF`), hairline `1px` borders instead of heavy shadows, restrained single institutional accent, crisp sidebar + topbar shell, URL-synced filters | Soft consumer rounded-2xl bubbles or decorative purple gradients |
| **Explainable Credit Risk (XUI)** | ML risk & SHAP forensics | Horizontal diverging SHAP bars (risk-increasing crimson right, risk-mitigating teal left) with explicit `log_odds` unit labels, plain-language feature labels, interactive What-If stress sliders with live delta comparison, OOD warnings | Raw data-science beeswarm plots without context; unlabelled model scores |
| **figma.com / x.ai (tasteskill bar)** | Public product landing (`/`) | Plain copy with real system facts, live HTML product UI preview (`app-frame`), sharp fintech geometry, restrained hover micro-interactions, zero AI slop | Generic hero buzzwords, scroll-fade cards, violet accents, fake testimonials |

## 2. Non-Negotiable Financial Data UX Rules

1. **Missingness Preservation:** Backend schemas sanitize nonfinite values to `null`. Every table cell, KPI, and chart tooltip renders `null` as `—` (muted), never `0` or `0.0%`.
2. **Period & Form Clarity:** Latest company snapshots may reflect a recent `10-Q`, while annual history, `t+1` distress forecasts, and PCA cluster positions reflect `10-K`. Period badges (`FY2024 · 10-K` vs `Q3 2025 · 10-Q`) remain visible beside every headline figure.
3. **Model Transparency:** TreeSHAP attributions are displayed in `log-odds` (`output_space`) alongside base value, raw margin, and `model_version`.
4. **Same-Origin Security Contract:** Session cookies (`finhealth_session`, `finhealth_csrf`) and `X-CSRF-Token` headers are sent over same-origin `/api/v1/*` routes via Vite dev proxy in development and FastAPI static hosting in production.
