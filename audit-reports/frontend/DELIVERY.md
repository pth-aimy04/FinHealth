# FinHealth React delivery

Implemented in D:/DATN. Primary UI: React 19 + strict TypeScript + Vite 8,
Tailwind 4, Radix/shadcn primitives, TanStack Query/Table, React Hook Form/Zod,
modular Apache ECharts, Lucide SVG icons. Package versions are locked.

## Delivered

- Vietnamese research shell, dark default and paired light theme.
- Overview, screener, company analysis, comparison, report lineage/as-of,
  model evaluation/PCA, manual/batch prediction, workspace, accounts and admin.
- Cookie/CSRF sessions preserved; no session tokens in localStorage.
- FastAPI serves frontend/dist; known deep links refresh correctly; missing
  API routes/assets remain 404; missing production build returns actionable 503.
- Vite development proxy verified with actual login and workspace mutation.
- Prior HTML/CSS/JS/Tabler preview preserved in frontend/legacy outside static root.
- Design rules: design-system/finhealth/MASTER.md.
- Feature/API/permission/verification matrix: docs/frontend-migration.md.
- Startup and Windows commands: README.md.

## Validation evidence

- ruff.txt: exact output of repository-root `ruff check .`.
- pytest.txt: exact full output of repository-root `pytest -v`.
- pytest-attempt-failed.txt and pytest-recheck.txt retain a transient temporary
  artifact publication failure and the passing focused rerun. The API wrapped
  the write failure as ModelPipelineError; the OS-level cause was not included
  in that HTTP response. No production model/artifact code was changed.
- lint.txt, typecheck.txt, unit.txt, build.txt: full frontend command outputs.
- e2e.txt: Playwright browser workflows and automated Axe WCAG AA checks.
- npm-audit.json: dependency audit, zero reported vulnerabilities at verification.
- overview-{dark,light}-{375,768,1024,1440}.png: full-page responsive/theme evidence.
- screener-mobile.png and company-desktop.png: additional research screens.

Browser tests use installed Chrome and an isolated SQLite copy of public financial
records read from the configured SQL Server. Test users and saved workspaces exist
only in the disposable database under .venv. Source credentials, users and private
workspace records are not copied. No SEC requests, production ingestion, migrations
or model training were run to populate the UI. Existing Python tests exercise their
own isolated ingestion/training boundaries as required by the repository gates.

## Practical limits

- 31 Python tests skip because the historical local SQLite snapshot is absent or
  SQL Server smoke testing requires explicit opt-in. These are reported by pytest;
  no test was disabled to achieve a passing result.
- Real SMTP delivery and OTP receipt were not exercised against a real mailbox.
  Account lifecycle, OTP binding, expiry and revocation are covered by existing
  offline integration tests; browser login uses disposable verified accounts.
- Administrative SEC queue execution and publication of a newly trained model
  were not triggered in browser acceptance. Role enforcement, read views and
  disabled-worker controls were verified.
- Automated Axe checks cover overview, screener, company overview, reports,
  account and models in both themes; they are not a claim of exhaustive manual
  assistive-technology certification. Responsive checks cover 375/768/1024/1440,
  landscape and 720 CSS-pixel reflow (equivalent layout viewport to 1440 at 200%).
- Forecast evidence is hidden under an as-of cutoff because the API does not
  expose inference timestamps sufficient to establish prediction availability.
- Research figures come from the published figures directory and are explicitly
  labelled independently of the model-version selector.
