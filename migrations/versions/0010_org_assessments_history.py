"""Create frozen multi-period organization risk assessment history table."""

from alembic import op

from finhealth.db import org_models

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create org_assessments with composite tenant-safe cascade ownership."""
    org_models.OrgAssessment.__table__.create(op.get_bind())


def downgrade() -> None:
    """Drop org_assessments."""
    org_models.OrgAssessment.__table__.drop(op.get_bind())
