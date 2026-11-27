"""Request transaction success, error rollback, and connection-level SQLite enforcement."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from finhealth.db import session as session_module
from finhealth.db.base import Base
from finhealth.db.models import Company
from finhealth.db.repositories import CompanyRepository
from finhealth.db.session import create_db_engine, create_session_factory, get_db_session


@pytest.fixture
def request_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """Replace only the default factory boundary; sessions and transactions remain real."""
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    def default_factory() -> session_module.sessionmaker[Session]:
        """Return the test database's actual session factory."""
        return factory

    monkeypatch.setattr(session_module, "_default_session_factory", default_factory)
    try:
        yield engine
    finally:
        engine.dispose()


def test_request_session_commits_success(request_engine: Engine) -> None:
    """Exhausting a successful dependency commits its complete transaction."""
    dependency = get_db_session()
    session = next(dependency)
    CompanyRepository(session).upsert_company(320193, "Apple")
    with pytest.raises(StopIteration):
        next(dependency)
    assert not session.in_transaction()
    with Session(request_engine) as verifier:
        assert verifier.scalar(select(Company.cik)) == "0000320193"


def test_request_session_rolls_back_failure(request_engine: Engine) -> None:
    """A handler failure propagates and leaves no committed rows."""
    dependency = get_db_session()
    session = next(dependency)
    CompanyRepository(session).upsert_company(320193, "Apple")
    with pytest.raises(RuntimeError, match="handler failed"):
        dependency.throw(RuntimeError("handler failed"))
    assert not session.in_transaction()
    with Session(request_engine) as verifier:
        assert verifier.scalar(select(func.count()).select_from(Company)) == 0


def test_request_session_close_rolls_back(request_engine: Engine) -> None:
    """Closing an interrupted generator cannot commit a partial request."""
    dependency = get_db_session()
    session = next(dependency)
    CompanyRepository(session).upsert_company(320193, "Apple")
    dependency.close()
    assert not session.in_transaction()
    with Session(request_engine) as verifier:
        assert verifier.scalar(select(func.count()).select_from(Company)) == 0


def test_sqlite_foreign_keys_on_every_connection(tmp_path: Path) -> None:
    """Fresh physical connections all enable foreign keys through the engine listener."""
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'connections.db').as_posix()}")
    try:
        with engine.connect() as first, engine.connect() as second:
            assert first.scalar(text("PRAGMA foreign_keys")) == 1
            assert second.scalar(text("PRAGMA foreign_keys")) == 1
    finally:
        engine.dispose()
