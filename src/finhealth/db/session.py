"""Lazy engine creation and explicit request-scoped transaction ownership."""

from collections.abc import Iterator
from functools import lru_cache
from sqlite3 import Connection as SqliteConnection

from sqlalchemy import Connection, Engine, create_engine, event, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from finhealth.core.config import get_settings


def _enable_sqlite_foreign_keys(
    dbapi_connection: SqliteConnection, connection_record: ConnectionPoolEntry
) -> None:
    """Enable real FK enforcement and let SQLAlchemy control SQLite transactions."""
    dbapi_connection.isolation_level = None
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _begin_sqlite_transaction(connection: Connection) -> None:
    """Make SQLite DDL, savepoints, and rollback participate in explicit transactions."""
    connection.exec_driver_sql("BEGIN")


def create_db_engine(database_url: str | None = None, echo: bool = False) -> Engine:
    """Create a lazy engine; SQLite additionally enforces FK and transaction semantics."""
    url = make_url(database_url if database_url is not None else get_settings().database_url)
    if url.get_backend_name() == "sqlite" and url.database in (None, "", ":memory:"):
        engine = create_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(url, echo=echo, pool_pre_ping=True)
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        event.listen(engine, "begin", _begin_sqlite_transaction)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create sessions whose repositories flush while callers own commit or rollback."""
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def _default_session_factory() -> sessionmaker[Session]:
    """Create the default engine and session factory on first request only."""
    return create_session_factory(create_db_engine())


def get_db_session() -> Iterator[Session]:
    """Yield a request transaction, commit success, and roll back failures before closing."""
    session = _default_session_factory()()
    try:
        with session.begin():
            yield session
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
