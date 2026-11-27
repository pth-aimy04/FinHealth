"""Alembic environment using application settings and the complete model metadata."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from finhealth.core.config import get_settings
from finhealth.db import account_models, batch_models, org_models
from finhealth.db.action_code_models import AccountActionCode
from finhealth.db.lineage_models import FilingVersion, ForecastEvidence, IngestionRun
from finhealth.db.models import Base
from finhealth.db.session import create_db_engine
from finhealth.db.verification_models import EmailVerificationCode

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata
_LINEAGE_TABLES = (FilingVersion, ForecastEvidence, IngestionRun)
_ACCOUNT_TABLES = account_models.User
_ORG_TABLES = (org_models.OrgCompany, org_models.OrgFinancialStatement, org_models.OrgAssessment)
_BATCH_TABLES = (batch_models.OrgBatchJob, batch_models.OrgBatchJobRow)
_VERIFICATION_TABLE = EmailVerificationCode
_ACTION_CODE_TABLE = AccountActionCode


def run_migrations_offline() -> None:
    """Emit SQL for the configured database dialect without opening a connection."""
    url = config.attributes.get("database_url") or get_settings().database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection: Connection) -> None:
    """Apply migrations inside Alembic's transaction on a supplied live connection."""
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Use a caller-supplied connection or lazily connect with application settings."""
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_with_connection(connection)
        return
    engine = create_db_engine(get_settings().database_url)
    try:
        with engine.connect() as connection:
            _run_with_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
