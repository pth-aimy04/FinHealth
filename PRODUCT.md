# PRODUCT.md — FinHealth

## Product Summary

**FinHealth** is an institutional-grade corporate financial distress analytics and SEC EDGAR research platform. It ingests audited `10-K` and `10-Q` filings, computes leakage-safe financial ratios and fundamental diagnostics (Altman Z-Score, DuPont decomposition, Quality of Earnings, Accounting Checklist, Four-Pillar Health), clusters issuers via PCA, and produces calibrated `t+1` distress forecasts with TreeSHAP explainability and What-If stress testing.

## Primary Users & Scenes

1. **Credit & Equity Analysts (Operate Mode):** Screen issuers by distress risk, leverage, profitability, and cluster; inspect multi-year filing histories; compare peers side by side; run What-If revenue/margin/debt/cash-flow shocks; save watchlists, screeners, and manual assessments.
2. **Risk & ML Researchers (Operate / Read Mode):** Audit active and historical model bundles, temporal evaluation metrics, and figures; score custom or batch corporate statements; inspect filing lineage, report alerts, and forecast evidence.
3. **Platform Administrators (Operate Mode):** Monitor database and worker health, submit/retry SEC EDGAR ingestion runs, inspect run event logs, manage user accounts, and review append-only audit logs.
4. **Prospective Users & Reviewers (Persuade Mode — `/`):** Understand FinHealth's capabilities, data provenance, and explainable risk workflow in seconds and enter the workspace directly.

## Core Surface Map

- `/` — Public Landing Page (Persuade mode, anti-slop fintech showcase with live product frame)
- `/app` — Overview Dashboard & Data Quality Monitor
- `/app/screener` — Filterable Company Screener (URL-synced filters, saved screeners, watchlist)
- `/app/companies/:identifier` — Company Deep Dive (`10-K`/`10-Q` history, Health Pillars, TreeSHAP, Altman Z, DuPont, QoE, Checklist, Reports, Alerts, Forecast Evidence, Trigger SEC Analyze)
- `/app/compare` — Multi-Company Peer Comparison (Latest Annual vs Common Fiscal Year)
- `/app/clusters` — Interactive PCA Peer Cluster Map
- `/app/stress` — Interactive What-If Stress Simulator
- `/app/models` — ML Model Lab (Versions, Evaluation Report & Figures, Manual Scoring, Batch Portfolio Scoring, Admin Retrain)
- `/app/workspace` — Personal Workspace (Watchlist, Saved Screeners, Saved Manual Analyses)
- `/app/account` — Account & Security (Login, Register + Email OTP, Forgot/Reset Password, Profile, Change Email/Password)
- `/app/admin` — Admin Console (System Overview, SEC Ingestion Jobs & Live Events, User Management, Audit Log)
