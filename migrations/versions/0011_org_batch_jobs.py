"""Create organization-scoped asynchronous Excel batch assessment job tables."""

from alembic import op

from finhealth.db import batch_models

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create org_batch_jobs and org_batch_job_rows with single-path tenant cascade."""
    bind = op.get_bind()
    batch_models.OrgBatchJob.__table__.create(bind)
    batch_models.OrgBatchJobRow.__table__.create(bind)


def downgrade() -> None:
    """Drop org_batch_job_rows and org_batch_jobs in foreign-key order."""
    bind = op.get_bind()
    batch_models.OrgBatchJobRow.__table__.drop(bind)
    batch_models.OrgBatchJob.__table__.drop(bind)
