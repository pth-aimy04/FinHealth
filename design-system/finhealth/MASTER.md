> Inactive: the user reverted to the original interface on 2026-11-27. This file records the rejected React migration.

# FinHealth · Financial Research Workspace

Status: implemented in `frontend/src/styles/global.css` and React components.

## Design decision

Professional Vietnamese corporate financial research. Dark default, fully paired light
theme, trust blue navigation/actions, restrained surfaces and typography. Product search
matched **Financial Dashboard** (products.csv); color search matched **Financial Dashboard**;
typography search matched **Vietnamese Friendly**. Design-system searches returned marketing
patterns (Enterprise Gateway, then Hero + Features + CTA); those patterns are rejected.
The verified dashboard guidance and explicit project requirements govern this implementation.
No landing hero, sales CTA, glow, decorative gradients, or glass panels.

## Semantic tokens

| Role | Dark | Light |
| --- | --- | --- |
| background | #0b1120 | #f3f6fb |
| sidebar | #0e1627 | #ffffff |
| surface | #111c2f | #ffffff |
| raised surface | #18253b | #eaf0f8 |
| foreground | #edf2fa | #152238 |
| secondary text | #a5b3c8 | #52627a |
| border | #2c3c55 | #c9d4e3 |
| link / primary | #82afff | #245cc7 |
| button fill / text | #2962d9 / #ffffff | #245cc7 / #ffffff |
| positive | #64d8b3 | #087a56 |
| caution | #f6c76f | #906000 |
| danger | #ff929e | #bd3046 |
| purple series | #bea3ff | #7445b6 |
| focus | #a7cbff | #245cc7 |

Charts read the same CSS semantic series tokens at runtime and redraw on theme changes.
Use labels/symbols alongside risk colors. Internal score is not an external credit rating.

- Font: self-hosted Be Vietnam Pro, weights 400/500/600/700, Vietnamese subset.
- Body: 14px desktop, 16px mobile; data tables 12px; secondary labels 12px; h1 24–32px.
- Numbers: tabular numerals. Vietnamese number/date formatting. Financial units explicit.
- Space scale: 4, 8, 12, 16, 24, 32px; panel padding 16–22px.
- Radius: controls 6px, panels 8px, dialogs 12px.
- Border: 1px semantic border. Modal shadow only; no decorative card shadows.
- Motion: feedback 140ms, entry 220ms; reduced motion disables transitions and chart animation.
- Layers: header 20, scrim 40, modal 50, skip-link 100.
- Focus: 3px semantic outline with 3px offset, no focus suppression.

## Architecture and interactions

React 19 / strict TypeScript / Vite 8 / Tailwind 4. Radix-based shadcn primitives use
CVA, Slot, Dialog and Tabs. React Router owns routes/URL filters; TanStack Query owns
server state; TanStack Table owns table transformations; React Hook Form and Zod validate
forms. ECharts uses modular SVG rendering. Lucide is the sole structural icon family.

Sidebar on desktop, accessible modal navigation below 768px. Layout switches at 768,
1100 and 1500px, tested at 375/768/1024/1440px. Tables scroll inside named regions.
Route changes focus main content. Dialog traps focus and supports Escape.

Financial series break on null/missing fiscal years. Actual is solid, forecast dashed,
simulation explicitly labelled. No invented confidence bands. Charts include summaries,
legends and table alternatives. Source identifiers are retained in evidence disclosures.

## Data and permission contracts

Runtime observations come only from same-origin APIs. Cookie session remains HttpOnly;
CSRF is read from finhealth_csrf and sent in X-CSRF-Token. localStorage holds theme only.
Workspace is owner-scoped. Admin UI is role-gated and backend authorization is unchanged.
Missing facts remain em dashes. SEC is never called from the browser.

Ingestion and training are explicit administrative actions. No ingestion, migration or
training is performed to populate the interface. Browser acceptance uses a disposable
SQLite copy of public financial records; private source accounts are never copied.
