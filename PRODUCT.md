# PRODUCT.md — FinHealth Production V1.0

## Product Summary

**FinHealth Production V1.0** is a multi-tenant corporate financial health and 12-month bankruptcy risk analytics platform built for Vietnamese B2B credit teams, CFOs, and institutional analysts. It pairs a **0%-leakage, scale-free 12-month Bankruptcy ML Engine (`v2.0.0-kaggle`)** with an **SEC EDGAR (`10-K`/`10-Q`) Cash-Flow Overlay & Peer Benchmark layer**, full **Vietnamese Accounting Standards support (TT99/2025/TT-BTC, TT200/2014, TT133/2016 + HTKK XML & Excel)**, **A4 Vietnamese PDF Executive Reports**, **Async Batch Excel Screening**, and full compliance with **Vietnam Personal Data Protection Law 91/2025/QH15** and **Decree 88/2014/NĐ-CP** (non-credit-rating disclaimer).

## Core Architecture Pillars

1. **Two-Tier Data & ML Routing:**
   - **Core 12-Month Bankruptcy Engine (`v2.0.0-kaggle`):** Trained on Kaggle US Bankruptcy (`american_bankruptcy.csv`, 8,971 companies, 78,682 rows, 609 strictly forward `year == max_year` events: 490 Train / 62 Val / 57 Test, **0% entity leakage**). Uses 19 scale-free dimensionless ratios (`CORE_BANKRUPTCY_FEATURES`, currency-invariant VND = USD) + 5 YoY features, Platt-calibrated across all 4 models (LR, RF, XGBoost, LightGBM), 4-layer Confidence indicator, monotonic `PD ↔ 0–100 Health Score` mapping (`STRONG / STABLE / WATCH / CRITICAL`), and a Cash-Flow Overlay.
   - **SEC EDGAR Dual Role:** Provides the **US Market (SEC)** research workspace (`/us-market`) and serves as the industry peer benchmark & cash-flow reference cohort (S01).
2. **Multi-Tenant Organization Workspace & RBAC (`identity-privacy`):**
   - Email + Password + OTP authentication, revocable cookie sessions + CSRF, auto-provisioned personal organization on verification.
   - Organization switching (`active_org_id` server-side), SHA-256 single-use invites (72h TTL), monotonic RBAC (`org_admin`, `analyst`, `viewer`), strict `org_id` tenant isolation (anti-IDOR), and Law 91/2025/QH15 self-service data export (`GET /api/v1/auth/me/export`) and hard account deletion (`POST /api/v1/auth/delete-account`).
3. **Vietnamese Financial Data Ingestion (`financial-data`):**
   - Supports **TT99/2025/TT-BTC** (FY2026+), **TT200/2014**, and **TT133/2016** (SME) via 3-part Web Editor (with Draft/Finalized workflow and VND/Million/Billion scaling), Excel templates (`openpyxl`), and **HTKK XML import (`defusedxml`, XXE-safe ≤ 5 MB)**.
   - Real-time Balance Sheet equation validation (`TA = TL + E` within 0.5%), negative-equity safe ratios, explicit Financial Institution exclusion (`applicable=False`), and 1-click idempotent seeding of 3 Vietnamese sample companies.
4. **Risk Analytics & Business UX (`risk-analytics` & `product-ui-governance`):**
   - Unified single **0–100 Health Score** across Overview, Portfolio, Compare, Batch, Detail, and PDF; no `AAA..CCC` credit-rating labels on customer UI; Decree 88/2014/NĐ-CP disclaimer on all assessments and PDFs.
   - Full Altman $Z / Z' / Z''$ with dynamic cutoffs, 5 Financial Pillars & 20 ratios with Vietnamese tooltips, 2-column plain-business **Điểm Tựa & Điểm Nghẽn** (no ML jargon leaked to end users), 3–5 year multi-period trajectory, and 2–4 company side-by-side comparison.
5. **Reporting & Batch Screening (`batch-and-reporting`):**
   - Server-side A4 Vietnamese PDF report (`reportlab` + `matplotlib` Agg + embedded `BeVietnamPro` TTF fonts, zero GTK dependency).
   - Asynchronous DB-backed Batch Excel screening (up to 500 rows, ≤ 10 MB) with row-level error isolation and risk-ranked `.xlsx` export.

## Core Surface Map (React SPA)

- `/` — Workspace Overview & 1-Click 3-Company Vietnamese Sample Onboarding
- `/portfolio` — Organization Private Company Portfolio (MST, VSIC, tags, FI gate, Draft/Finalized BCTC, HTKK XML & Excel Import)
- `/portfolio/:id` — Organization Company Deep Dive (Health Hero, 2-Column Drivers, 5 Pillars / 20 Ratios, Dynamic Altman $Z/Z'/Z''$, 3–5Y History, A4 PDF Export)
- `/batch` — Asynchronous Batch Excel Portfolio Screening & Risk-Ranked Export
- `/compare` — Side-by-Side Comparison (2–4 Organization or SEC Companies, Latest vs Common Fiscal Year)
- `/us-market` — US Market (SEC EDGAR) Screener & Reference Universe
- `/us-market/:identifier` — SEC Issuer Deep Dive (Unified Health Hero, Drivers, Dynamic Altman, Filings & Alerts)
- `/stress` — Interactive What-If Stress Simulator
- `/methodology` — B2B Methodology, Out-of-Time Validation & Decree 88/2014/NĐ-CP Disclosure
- `/organization` — Organization Management, Invites, RBAC Roles & Audit Log
- `/workspace` — Organization-Scoped Watchlist, Saved Screeners & Saved Analyses
- `/account` — Account Security, OTP Verification, Password/Email Change, Data Export & Account Deletion (Law 91/2025/QH15)
- `/admin` & `/admin/*` — Admin-Only Console (System Health, SEC Ingestion Jobs, Users, Audit Log, Model Lab & PCA Cluster Map)
