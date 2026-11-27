# DESIGN.md — FinHealth Visual World ("Capital Institutional")

## 1. Visual World & Aesthetic Direction

**World:** *Capital Institutional* — a B2B corporate credit and financial intelligence workstation modeled on institutional research terminals (**S&P Capital IQ Pro**, **Moody's CreditView**, **FiinPro-X**).
**Mode:** Operate (primary application surfaces) + Read (`MethodologyPage`).

**Structural Signature:**
- **Two-Tier Deep Institutional Navy Masthead (`#0B1A30` / `#102442`)** replacing the legacy SaaS white sidebar, releasing 100% horizontal viewport width (`max-w-[1440px]`) for wide financial tables, 4-company comparison matrices, 20-ratio ledgers, and 3-part Vietnamese accounting forms.
- **Brass-Gold Active Module Indicator (`#E0A83B`)** paired with **Institutional Cobalt (`#1849A9`)** interactive controls on a crisp alabaster-paper canvas (`#F4F6F9`) with pure white hairline-ruled sheets (`#FFFFFF`) and **zero blurred card shadows**.
- **Institutional Credit Tearsheet Masthead** on company profiles: 3-column hairline-divided analytical grid featuring a calibrated 4-zone Health Score Spectrum (`0 | 35 | 60 | 80 | 100`), 12-month default probability + 4-layer confidence audit, and 3 executive takeaways.
- **Flush Two-Column Credit Factors Ledger** (`Điểm Tựa & Điểm Nghẽn`) and hairline-divided `MetricStrip` KPI ribbons — zero nested cards, zero consumer rounded-full pill soup, zero `Sparkles` icons, and zero `border-l-4` accent stripes.

## 2. Color Tokens

### Institutional Masthead Chrome (Persistent Chromatic Anchor)
- `--chrome-bg`: `#0B1A30` (Tier 1 brand, omnibox search `Ctrl+K`, workspace switcher, account)
- `--chrome-sub`: `#102442` (Tier 2 horizontal module navigation bar)
- `--chrome-surface`: `#173057` (controls inside masthead)
- `--chrome-border`: `rgba(255, 255, 255, 0.12)`
- `--chrome-accent`: `#E0A83B` (2px brass-gold active module indicator)

### Light Theme (Default)
- `--bg-canvas`: `#F4F6F9` (crisp alabaster ledger ground)
- `--bg-surface`: `#FFFFFF` (primary ledger sheets, tables, tearsheets)
- `--bg-header`: `#F8FAFC` (panel & table headers)
- `--bg-subtle`: `#EDF1F6` (filter ribbons, group headers)
- `--bg-hover`: `#E7EEF7` (table row hover)
- `--border-subtle`: `#D6DFE9` (1px hairline structural rules)
- `--border-strong`: `#B0BFCF` (inputs, table header rules, stamps)
- `--rule-heavy`: `#0B1A30` (2px top structural rule on primary ledgers & tearsheets)
- `--text-primary`: `#0B1526` (>= 16:1 on white)
- `--text-secondary`: `#3D4F68` (>= 7.5:1 on white)
- `--text-muted`: `#61738B` (>= 4.6:1 on white)
- `--accent-primary`: `#1849A9` (Institutional Capital Cobalt)
- `--accent-primary-hover`: `#123987`
- `--accent-soft`: `#EBF2FF`

### Dark Theme (Toggleable Capital Terminal)
- `--chrome-bg`: `#070E1A`, `--chrome-sub`: `#0C172B`, `--chrome-accent`: `#E8B24A`
- `--bg-canvas`: `#0A0F18`, `--bg-surface`: `#101724`, `--bg-header`: `#131C2C`, `--bg-subtle`: `#162133`, `--bg-hover`: `#1C2B42`
- `--border-subtle`: `#223047`, `--border-strong`: `#34496B`, `--rule-heavy`: `#4F86F7`
- `--text-primary`: `#EEF3FA`, `--text-secondary`: `#A1B4CD`, `--text-muted`: `#6F84A1`
- `--accent-primary`: `#4F86F7`, `--accent-primary-hover`: `#6E9DF9`

### Semantic Financial Risk & Chart Tokens
- `STRONG` / `LOW` / `SAFE`: Light `#0D6E4E` on `#E6F5EF` (`--risk-low-*`) / Dark `#34D399`
- `STABLE` / `ADEQUATE`: Light `#1849A9` on `#EBF2FF` (`--risk-stable-*`) / Dark `#60A5FA`
- `WATCH` / `MEDIUM` / `GREY`: Light `#9A5708` on `#FEF5E4` (`--risk-medium-*`) / Dark `#FBBF24`
- `HIGH` / `WEAK`: Light `#B84309` on `#FFF0E6` (`--risk-high-*`) / Dark `#FB923C`
- `CRITICAL` / `DISTRESS`: Light `#B41D2D` on `#FDECEF` (`--risk-critical-*`) / Dark `#F87171`
- Chart Series: `--chart-1` (`#1849A9`), `--chart-2` (`#0D6E4E`), `--chart-3` (`#B0791C`), `--chart-4` (`#B41D2D`), `--chart-5` (`#526680`).

## 3. Typography (100% Native Vietnamese Diacritics)

- **Editorial Headings (`--font-serif`):** `Source Serif 4` (400, 600, 700) — Page Masthead `h1` (`24px–28px`) and Company Tearsheet Entity Titles.
- **Institutional UI Sans (`--font-sans`):** `Source Sans 3` (400, 500, 600, 700) — `13px–14px` body & table cells, `14px–15px` panel titles, `11px` uppercase tracked column headers.
- **Financial Data & Identifiers (`--font-mono`):** `JetBrains Mono` (400, 500, 600) with `font-variant-numeric: tabular-nums` — every score, probability, ratio, MST, Ticker, CIK, Fiscal Year, and BCTC accounting line code (`270`, `100`, `400`).

## 4. Geometry, Elevation & Responsive Rules

- **Sharp Institutional Radii:** `2px` stamps & micro-bars, `3px` buttons & inputs, `4px` primary ledger panels.
- **Single-Declaration Elevation:** `1px solid var(--border-subtle)` for all workspace panels (`border-top: 2px solid var(--rule-heavy)` on lead ledgers). Only popovers/dialogs carry `--shadow-popover`.
- **Responsive Architecture:**
  - Desktop (`>= 1024px`): 2-tier sticky Deep Navy masthead (`56px` + `42px`), `1440px` full-width workspace grids.
  - Mobile & Tablet (`< 1024px`): Single compact Navy header + full-height slide-over Navy navigation drawer with `44px` minimum tap targets and horizontally scrollable financial ledgers.
