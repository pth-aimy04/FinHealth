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
                "organizations",
                "organization_members",
                "organization_invites",
                "organization_audit_logs",
                "org_companies",
                "org_financial_statements",
                "org_assessments",
                "org_batch_jobs",
                "org_batch_job_rows",
            }
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0011"
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


def test_migration_0008_backfills_personal_org_and_sets_audit_null() -> None:
    """Backfill a personal workspace for pre-0008 users and preserve audit logs on user purge."""
    engine = create_db_engine("sqlite:///:memory:")
    config = Config(str(ROOT / "alembic.ini"))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "0007")
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, display_name, role, active, "
                    "email_verified, created_at, updated_at) VALUES "
                    "(1, 'legacy@example.com', 'hash', 'Legacy User', 'user', 1, 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO companies (id, cik, ticker, name, created_at, updated_at) VALUES "
                    "(1, '0000320193', 'AAPL', 'Apple', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO user_sessions (id, user_id, token_hash, csrf_hash, "
                    "credential_stamp, expires_at, created_at) VALUES "
                    "(1, 1, 'tok1', 'csrf1', 'hash', '2099-01-01 00:00:00', CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO watchlist_items (id, user_id, company_id, created_at) "
                    "VALUES (1, 1, 1, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO saved_screeners (id, user_id, name, filters, created_at, "
                    "updated_at) VALUES (1, 1, 'Tech', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO saved_analyses (id, user_id, name, model_version, inputs, "
                    "outputs, created_at) VALUES "
                    "(1, 1, 'Snap', 'v1', '{}', '{}', CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO admin_audit_logs (id, actor_id, action, target, outcome, "
                    "created_at) VALUES (1, 1, 'login', 'user:1', 'succeeded', CURRENT_TIMESTAMP)"
                )
            )

        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            org_id = connection.scalar(
                text("SELECT id FROM organizations WHERE created_by = 1 AND is_personal = 1")
            )
            assert org_id is not None
            role = connection.scalar(
                text(
                    "SELECT role FROM organization_members "
                    "WHERE organization_id = :org_id AND user_id = 1"
                ),
                {"org_id": org_id},
            )
            assert role == "org_admin"
            assert (
                connection.scalar(text("SELECT active_org_id FROM user_sessions WHERE id = 1"))
                == org_id
            )
            assert (
                connection.scalar(text("SELECT organization_id FROM watchlist_items WHERE id = 1"))
                == org_id
            )
            assert (
                connection.scalar(text("SELECT organization_id FROM saved_screeners WHERE id = 1"))
                == org_id
            )
            assert (
                connection.scalar(text("SELECT organization_id FROM saved_analyses WHERE id = 1"))
                == org_id
            )
            # Clean up child rows pointing to user without CASCADE, then delete user.
            connection.execute(text("DELETE FROM user_sessions WHERE user_id = 1"))
            connection.execute(
                text("DELETE FROM organizations WHERE id = :org_id"), {"org_id": org_id}
            )
            connection.execute(text("DELETE FROM users WHERE id = 1"))
            audit_actor = connection.scalar(
                text("SELECT actor_id FROM admin_audit_logs WHERE id = 1")
            )
            assert audit_actor is None
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
        assert "ON DELETE SET NULL" in sql
        assert "0001" in sql
        assert "0011" in sql
        assert "ALTER TABLE financial_metrics ADD COLUMN interest_coverage" in sql
        assert "ALTER TABLE financial_statements ADD COLUMN field_provenance" in sql
        assert "ALTER TABLE financial_statements ADD COLUMN cost_of_goods_sold" in sql
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
    assert "FOREIGN KEY(org_company_id, organization_id)" in sql
    assert "FOREIGN KEY(org_statement_id, org_company_id, organization_id)" in sql
    assert "FOREIGN KEY(job_id, organization_id)" in sql
    assert "ON DELETE SET NULL" in sql
    assert "CREATE INDEX ix_prediction_company_created_lookup" in sql
    # Single cascade path per table: 3 (SEC) + 7 (0008) + 2 (0009) + 1 (0010) + 2 (0011) = 15.
    assert sql.count("ON DELETE CASCADE") == 15
