"""Add account isolation, hashed sessions and ingestion administration."""

import sqlalchemy as sa
from alembic import context, op

from finhealth.db.base import NAMING_CONVENTION

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _frozen_0005_tables() -> tuple[tuple[sa.Table, ...], sa.Table]:
    """Freeze the revision-0005 schema so later revisions (0008+) evolve cleanly."""
    meta = sa.MetaData(naming_convention=NAMING_CONVENTION)
    # Stub parent tables solely for ForeignKey resolution in this local metadata.
    sa.Table("companies", meta, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("ingestion_runs", meta, sa.Column("id", sa.Integer(), primary_key=True))

    users = sa.Table(
        "users",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.Unicode(120), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name="user_role"),
    )
    user_sessions = sa.Table(
        "user_sessions",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("credential_stamp", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    account_action_tokens = sa.Table(
        "account_action_tokens",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("pending_email", sa.String(254), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    watchlist_items = sa.Table(
        "watchlist_items",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "company_id"),
    )
    saved_screeners = sa.Table(
        "saved_screeners",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.Unicode(120), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    saved_analyses = sa.Table(
        "saved_analyses",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.Unicode(120), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    admin_audit_logs = sa.Table(
        "admin_audit_logs",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(120), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    security_rate_limits = sa.Table(
        "security_rate_limits",
        meta,
        sa.Column("bucket", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    ingestion_run_events = sa.Table(
        "ingestion_run_events",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id", sa.Integer(), sa.ForeignKey("ingestion_runs.id"), nullable=False, index=True
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("message", sa.Unicode(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    return (
        (
            users,
            user_sessions,
            account_action_tokens,
            watchlist_items,
            saved_screeners,
            saved_analyses,
            admin_audit_logs,
            security_rate_limits,
        ),
        ingestion_run_events,
    )


def upgrade() -> None:
    """Add tables without rewriting financial data or assigning fabricated legacy actors."""
    tables, run_events = _frozen_0005_tables()
    for table in tables:
        create_or_validate(table)
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
    create_or_validate(run_events)


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
    tables, run_events = _frozen_0005_tables()
    run_events.drop(op.get_bind())
    op.drop_index("uq_ingestion_active_key", table_name="ingestion_runs")
    with op.batch_alter_table("ingestion_runs") as batch:
        batch.drop_constraint("fk_ingestion_runs_requested_by_users", type_="foreignkey")
        for name in ("retry_of", "active_key", "stage", "started_at", "requested_by"):
            batch.drop_column(name)
    for table in reversed(tables):
        table.drop(op.get_bind())
