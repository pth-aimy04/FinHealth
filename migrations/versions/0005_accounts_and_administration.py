"""Add account isolation, hashed sessions and ingestion administration."""

import sqlalchemy as sa
from alembic import context, op

from finhealth.db import account_models as accounts

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

MODELS = (
    accounts.User,
    accounts.UserSession,
    accounts.AccountActionToken,
    accounts.WatchlistItem,
    accounts.SavedScreener,
    accounts.SavedAnalysis,
    accounts.AdminAuditLog,
    accounts.SecurityRateLimit,
)


def upgrade() -> None:
    """Add tables without rewriting financial data or assigning fabricated legacy actors."""
    for model in MODELS:
        create_or_validate(model.__table__)
    # Batch mode recreates only on SQLite, allowing a portable named foreign key.
    with op.batch_alter_table("ingestion_runs") as batch:
        batch.add_column(sa.Column("requested_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("stage", sa.String(32), nullable=True))
        batch.add_column(sa.Column("active_key", sa.String(40), nullable=True))
        batch.add_column(sa.Column("retry_of", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_ingestion_runs_requested_by_users", "users", ["requested_by"], ["id"]
        )
    op.create_index(
        "uq_ingestion_active_key",
        "ingestion_runs",
        ["active_key"],
        unique=True,
        mssql_where=sa.text("active_key IS NOT NULL"),
        sqlite_where=sa.text("active_key IS NOT NULL"),
        postgresql_where=sa.text("active_key IS NOT NULL"),
    )
    create_or_validate(accounts.IngestionRunEvent.__table__)


def create_or_validate(table: sa.Table) -> None:
    """Adopt pre-created matching tables, but fail explicitly on any incompatible column."""
    bind = op.get_bind()
    if context.is_offline_mode() or not sa.inspect(bind).has_table(table.name):
        table.create(bind)
        return
    inspector = sa.inspect(bind)
    actual = {column["name"]: column for column in inspector.get_columns(table.name)}
    expected = {column.name: column for column in table.columns}
    if set(actual) != set(expected):
        raise RuntimeError(f"Existing table {table.name} does not match account migration")
    for name, column in expected.items():
        stored = actual[name]
        stored_type = stored["type"].copy()
        if isinstance(stored_type, sa.String) and getattr(column.type, "collation", None) is None:
            # SQL Server reflection supplies its database-default collation explicitly.
            stored_type.collation = None
        if stored["nullable"] != column.nullable or str(
            stored_type.compile(dialect=bind.dialect)
        ) != str(column.type.compile(dialect=bind.dialect)):
            raise RuntimeError(f"Existing column {table.name}.{name} is incompatible")
    if inspector.get_pk_constraint(table.name)["constrained_columns"] != [
        column.name for column in table.primary_key
    ]:
        raise RuntimeError(f"Existing table {table.name} has an incompatible primary key")
    actual_unique = (
        {
            tuple(item["column_names"])
            for item in inspector.get_indexes(table.name)
            if item["unique"]
        }
        if bind.dialect.name == "mssql"
        else {tuple(item["column_names"]) for item in inspector.get_unique_constraints(table.name)}
    )
    expected_unique = {
        tuple(column.name for column in item.columns)
        for item in table.constraints
        if isinstance(item, sa.UniqueConstraint)
    }
    if not expected_unique.issubset(actual_unique):
        raise RuntimeError(f"Existing table {table.name} is missing unique constraints")


def downgrade() -> None:
    """Remove account data only when an operator explicitly requests downgrade."""
    accounts.IngestionRunEvent.__table__.drop(op.get_bind())
    op.drop_index("uq_ingestion_active_key", table_name="ingestion_runs")
    with op.batch_alter_table("ingestion_runs") as batch:
        batch.drop_constraint("fk_ingestion_runs_requested_by_users", type_="foreignkey")
        for name in ("retry_of", "active_key", "stage", "started_at", "requested_by"):
            batch.drop_column(name)
    for model in reversed(MODELS):
        model.__table__.drop(op.get_bind())
