"""Export public financial tables and restore them to an empty migrated database."""

import argparse
from pathlib import Path
from typing import cast

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, Table, func, select
from sqlalchemy.exc import SQLAlchemyError

from finhealth.core.config import Settings
from finhealth.core.exceptions import FinHealthError
from finhealth.db.lineage_models import FilingVersion, ForecastEvidence
from finhealth.db.models import Base, Company, FinancialMetric, FinancialStatement, ModelPrediction
from finhealth.db.session import create_db_engine

# Explicit allowlist: never export users, credentials, private workspaces or job logs.
PUBLIC_TABLES: tuple[Table, ...] = cast(
    tuple[Table, ...],
    (
        Company.__table__,
        FinancialStatement.__table__,
        FinancialMetric.__table__,
        ModelPrediction.__table__,
        FilingVersion.__table__,
        ForecastEvidence.__table__,
    ),
)


class HandoffError(FinHealthError):
    """A financial handoff could not be completed without risking existing data."""


def copy_financial_tables(source: Engine, target: Engine) -> dict[str, int]:
    """Copy only allowlisted rows atomically, preserving IDs and rejecting populated targets."""
    counts: dict[str, int] = {}
    try:
        with source.connect() as reader, target.begin() as writer:
            for table in PUBLIC_TABLES:
                if writer.scalar(select(func.count()).select_from(table)):
                    raise HandoffError(
                        f"Target table {table.name} is not empty; use a new database."
                    )
            for table in PUBLIC_TABLES:
                count = 0
                result = reader.execute(select(table).order_by(table.c.id)).mappings()
                for rows in result.partitions(50):
                    writer.execute(table.insert(), [dict(row) for row in rows])
                    count += len(rows)
                actual = writer.scalar(select(func.count()).select_from(table))
                if actual != count:
                    raise HandoffError(f"Row-count verification failed for {table.name}.")
                counts[table.name] = count
    except SQLAlchemyError as error:
        raise HandoffError(
            "Financial transfer failed and was rolled back; check schema, driver and permissions."
        ) from error
    return counts


def migrate(engine: Engine) -> None:
    """Apply all repository migrations using an explicit engine connection."""
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def export_financial_snapshot(source: Engine, path: Path) -> dict[str, int]:
    """Create a new SQLite file containing only the public financial schema and rows."""
    if path.exists():
        raise HandoffError(f"Snapshot already exists: {path}; choose a new output path.")
    path.parent.mkdir(parents=True, exist_ok=True)
    target = create_db_engine(f"sqlite:///{path.resolve().as_posix()}")
    try:
        Base.metadata.create_all(target, tables=list(PUBLIC_TABLES))
        return copy_financial_tables(source, target)
    finally:
        target.dispose()


def main() -> None:
    """Export from configured SQL Server or restore the checked-in financial snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "restore"))
    parser.add_argument("--snapshot", type=Path, default=Path("data/seed/financial.sqlite3"))
    args = parser.parse_args()
    configured = create_db_engine(Settings().database_url)
    try:
        if args.action == "export":
            counts = export_financial_snapshot(configured, args.snapshot)
        else:
            if not args.snapshot.is_file():
                raise HandoffError(f"Snapshot not found: {args.snapshot}")
            source = create_db_engine(f"sqlite:///{args.snapshot.resolve().as_posix()}")
            try:
                migrate(configured)
                counts = copy_financial_tables(source, configured)
            finally:
                source.dispose()
        for name, count in counts.items():
            print(f"{name}: {count} rows")
    finally:
        configured.dispose()


if __name__ == "__main__":
    main()
