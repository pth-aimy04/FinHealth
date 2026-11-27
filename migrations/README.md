Run from the repository root with the virtual environment active. Copy `.env.example`
to `.env` and configure PostgreSQL credentials and the application's SEC contact.

```powershell
alembic upgrade head
alembic revision --autogenerate -m "Describe schema change"
alembic downgrade -1
```

Review generated revisions before applying them. Online migrations read the URL from
`get_settings().database_url`. `alembic upgrade head --sql` emits dialect-specific DDL without
a live connection. Programmatic migration callers may supply a SQLAlchemy connection
via `Config.attributes["connection"]` to use their own transaction (used by offline
SQLite integration tests). Do not put credentials in `alembic.ini`.

Repositories flush but do not commit. Wrap complete operations in `with session.begin():`
so related writes succeed or roll back together. Upserts use transactional lookups;
concurrent natural-key insert conflicts surface as `IntegrityError` and require a
caller-controlled transaction retry. SQLite tests verify constraints and cascades,
but do not replace deployment verification against PostgreSQL or SQL Server. SQL Server
uses one delete cascade per dependent table via the composite statement/company key.
SQLite does not retain timezone offsets in DateTime storage.

Statements retain the latest accepted filing only. Raw SEC responses must preserve
older accessions and amendments for point-in-time reconstruction before ML backtests.
