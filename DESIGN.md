# DESIGN.md — FinHealth Visual World ("Ledger & Signal")

## 1. Visual World & Aesthetic Direction

**World:** *Ledger & Signal* — an institutional financial research aesthetic inspired by Swiss financial ledgers, modern equity terminals (Koyfin, Quartr), and calm fintech operational tools (Mercury, Stripe).
**Mode Split:**
- **Public Landing (`/`):** Persuade mode — editorial confidence, real system numbers, live interactive product preview, restrained single entrance animation.
- **Application Workspace (`/app/*`):** Operate mode — high scanability, earned familiarity, hairline borders, compact/comfortable data density, zero decorative noise.

**Absolute Bans:**
- No purple/indigo/lavender AI defaults anywhere in UI chrome or accents.
- No eyebrow/kicker labels above headings.
- No nested cards or ghost cards (never combine a `1px` border with a heavy blurred shadow).
- No one-sided colored stripe bars on rounded boxes.
- No decorative scroll fade-ins, card tilts, or emoji icons.

## 2. Color Tokens

### Light Theme (Default)
- `--bg-canvas`: `#F6F7F8` (cool stone-paper canvas)
- `--bg-surface`: `#FFFFFF` (primary panels, tables, inputs)
- `--bg-subtle`: `#EEF1F4` (sidebar, secondary toolbar, table header)
- `--bg-hover`: `#E7ECEF` (row hover, subtle button hover)
- `--border-subtle`: `#E2E7EC` (hairline dividers)
- `--border-strong`: `#C5CFD8` (input borders, focus boundaries)
- `--text-primary`: `#0E1720` (deep ink, >= 14:1 on white)
- `--text-secondary`: `#475569` (labels, metadata, >= 6.5:1 on white)
- `--text-muted`: `#64748B` (table units, `—` missing values, >= 4.6:1 on white)
- `--accent-primary`: `#0B5D52` (institutional deep teal — primary actions, active nav)
- `--accent-primary-hover`: `#08473F`
- `--accent-soft`: `#E6F4F1` (active nav tint, selected chip)

### Dark Theme (Toggleable)
- `--bg-canvas`: `#0B0F14` (deep charcoal slate, never pure black)
- `--bg-surface`: `#111720` (elevated work panels)
- `--bg-subtle`: `#161E29` (sidebar, table headers)
- `--bg-hover`: `#1D2736`
- `--border-subtle`: `#233042`
- `--border-strong`: `#33455E`
- `--text-primary`: `#F1F5F9`
- `--text-secondary`: `#94A3B8`
- `--text-muted`: `#64748B`
- `--accent-primary`: `#14B8A6`
- `--accent-primary-hover`: `#2DD4BF`
- `--accent-soft`: `rgba(20, 184, 166, 0.14)`

### Semantic Risk & Signal Tokens (Always paired with icon + text label)
- `LOW` / Strong / Mitigating SHAP: `#0F766E` (bg `#E6F4F1` / dark `rgba(20,184,166,0.16)`)
- `MEDIUM` / Watch / Adequate: `#B45309` (bg `#FEF3C7` / dark `rgba(245,158,11,0.16)`)
- `HIGH` / Weak: `#C2410C` (bg `#FFEDD5` / dark `rgba(249,115,22,0.16)`)
- `CRITICAL` / Distress / Risk-Increasing SHAP: `#B91C1C` (bg `#FEE2E2` / dark `rgba(239,68,68,0.16)`)
- Neutral / Unscored / Missing (`null`): `#475569` (bg `#EEF1F4`)

## 3. Typography

- **UI Sans (`--font-sans`):** `IBM Plex Sans`, system-ui, sans-serif (weights 400, 500, 600, 700)
- **Financial Data & Code (`--font-mono`):** `IBM Plex Mono`, ui-monospace, monospace
- **Landing Display (`--font-display`):** `IBM Plex Serif` (used strictly for Landing hero headline)
- **Strict Numeric Rule:** Every table cell, KPI value, percentage, ratio, CIK, and axis tick uses `font-variant-numeric: tabular-nums` and right alignment in tables.
- **Operate Mode Fixed Scale:**
  - Page Title (`h1`): `1.375rem` (22px), weight `600`, tracking `-0.02em`
  - Section Title (`h2`): `1rem` (16px), weight `600`, tracking `-0.01em`
  - Subheading (`h3`): `0.875rem` (14px), weight `600`
  - Body / Table Cell: `0.875rem` (14px) comfortable / `0.8125rem` (13px) compact
  - Caption / Table Header: `0.75rem` (12px), weight `500`, uppercase where appropriate

## 4. Geometry, Spacing & Motion

- **Sharp Fintech Radii:** `--radius-sm: 2px`, `--radius-md: 4px`, `--radius-lg: 6px`, `--radius-pill: 9999px` (badges only).
- **Spacing Scale:** Strict `4px` increments (`4, 8, 12, 16, 20, 24, 32, 48`).
- **Elevation:** Single declaration via `1px solid var(--border-subtle)`. Popovers/dialogs use `1px solid var(--border-strong)` + `0 8px 24px -8px rgba(14, 23, 32, 0.14)`.
- **Motion:** `150ms–200ms cubic-bezier(0.16, 1, 0.3, 1)` for state transitions in Operate mode; single calm entrance on Landing hero; full `prefers-reduced-motion` support.
- **Browser Surfaces:** Themed `::selection`, `caret-color`, `:focus-visible` (`2px solid var(--accent-primary)` with `2px` offset), and subtle custom scrollbars.

## 5. Layout & Responsive Rules

- **Desktop (`>= 1024px`):** Fixed collapsible left navigation rail (`232px` expanded / `64px` collapsed) + sticky `52px` top command bar (Global Ticker Search `Ctrl+K`, Health Status pill, Theme toggle, Account menu).
- **Tablet (`768px–1023px`):** Collapsible drawer sidebar + 2-column analytic grids.
- **Mobile (`390px–767px`):** Slide-over navigation drawer, single-column stacked panels, horizontally scrollable tables with sticky first column (`Ticker / Company`), `44px` minimum tap targets.
