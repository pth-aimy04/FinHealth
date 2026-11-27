"""Offline integration tests for the actual Alembic revisions on a relational engine."""

import io
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from finhealth.core.config import get_settings
from finhealth.db.base import Base
from finhealth.db.repositories import CompanyRepository
from finhealth.db.session import create_db_engine, create_session_factory

ROOT = Path(__file__).resolve().parents[2]


def test_migration_upgrade_matches_metadata_and_downgrade() -> None:
    """Apply all revisions, verify schema parity and writes, then reverse them."""
    engine = create_db_engine("sqlite:///:memory:")
    config = Config(str(ROOT / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert set(inspect(connection).get_table_names()) == {
                "alembic_version",
                "companies",
                "financial_statements",
                "financial_metrics",
                "model_predictions",
                "filing_versions",
                "forecast_evidence",
                "ingestion_runs",
                "users",
                "user_sessions",
                "account_action_tokens",
                "watchlist_items",
                "saved_screeners",
                "saved_analyses",
                "admin_audit_logs",
                "security_rate_limits",
                "ingestion_run_events",
                "email_verification_codes",
                "account_action_codes",
            }
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0007"
            migration_context = MigrationContext.configure(connection)
            assert compare_metadata(migration_context, Base.metadata) == []
        with create_session_factory(engine).begin() as session:
            company = CompanyRepository(session).upsert_company(320193, "Apple")
            assert company.cik == "0000320193"
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "base")
            assert set(inspect(connection).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()


def test_postgresql_offline_migration_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compile the real revision to PostgreSQL SQL without a live database or credentials."""
    # The configuration-only contact is never used for a network request.
    monkeypatch.setenv("SEC_USER_AGENT", "FinHealthTests/1.0 (tests@example.com)")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/finhealth")
    get_settings.cache_clear()
    output = io.StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    try:
        command.upgrade(config, "head", sql=True)
        sql = output.getvalue()
        for table in Base.metadata.tables:
            assert f"CREATE TABLE {table}" in sql
        assert "TIMESTAMP WITH TIME ZONE" in sql
        assert "ck_prediction_prob_bounds" in sql
        assert "ON DELETE CASCADE" in sql
        assert "0001" in sql
        assert "ALTER TABLE financial_metrics ADD COLUMN interest_coverage" in sql
        assert "ALTER TABLE financial_statements ADD COLUMN field_provenance" in sql
    finally:
        get_settings.cache_clear()


def test_sqlserver_offline_migration_uses_one_cascade_path() -> None:
    """Compile SQL Server DDL without ODBC and preserve each composite ownership key."""
    output = io.StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    config.attributes["database_url"] = "mssql+pyodbc://localhost/finhealth"
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "LEN(cik) = 10" in sql
    assert "name NVARCHAR(255)" in sql
    assert "field_provenance NVARCHAR(max)" in sql
    assert "FOREIGN KEY(statement_id, company_id)" in sql
    assert "FOREIGN KEY(source_statement_id, company_id)" in sql
    assert sql.count("ON DELETE CASCADE") == 3
    assert "CREATE INDEX ix_prediction_company_created_lookup" in sql
