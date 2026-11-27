"""Offline transfer tests with real SQLite transactions and deliberately private rows."""

from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select

from finhealth.db.account_models import User
from finhealth.db.handoff import (
    PUBLIC_TABLES,
    HandoffError,
    copy_financial_tables,
    export_financial_snapshot,
    migrate,
)
from finhealth.db.models import Company
from finhealth.db.session import create_db_engine


def test_export_excludes_accounts_and_restore_refuses_existing_rows(tmp_path: Path) -> None:
    """Financial IDs survive transfer; account tables do not cross the export boundary."""
    source = create_db_engine(f"sqlite:///{(tmp_path / 'source.sqlite3').as_posix()}")
    restored = create_db_engine(f"sqlite:///{(tmp_path / 'restored.sqlite3').as_posix()}")
    snapshot_path = tmp_path / "financial.sqlite3"
    try:
        migrate(source)
        migrate(restored)
        with source.begin() as connection:
            connection.execute(Company.__table__.insert(), {
                "id": 17, "cik": "0000320193", "name": "Public issuer", "ticker": "AAPL",
            })
            connection.execute(User.__table__.insert(), {
                "email": "private@example.com", "display_name": "Private owner",
                "password_hash": "private-credential-must-not-leave-source",
            })
        counts = export_financial_snapshot(source, snapshot_path)
        assert counts["companies"] == 1
        snapshot = create_db_engine(f"sqlite:///{snapshot_path.as_posix()}")
        try:
            assert set(inspect(snapshot).get_table_names()) == {t.name for t in PUBLIC_TABLES}
            assert b"private-credential" not in snapshot_path.read_bytes()
            assert copy_financial_tables(snapshot, restored) == counts
            with restored.connect() as connection:
                assert connection.scalar(select(Company.id)) == 17
                assert connection.scalar(select(func.count()).select_from(User)) == 0
            with pytest.raises(HandoffError, match="not empty"):
                copy_financial_tables(snapshot, restored)
            with restored.connect() as connection:
                assert connection.scalar(select(func.count()).select_from(Company)) == 1
        finally:
            snapshot.dispose()
        with pytest.raises(HandoffError, match="already exists"):
            export_financial_snapshot(source, snapshot_path)
    finally:
        source.dispose()
        restored.dispose()
