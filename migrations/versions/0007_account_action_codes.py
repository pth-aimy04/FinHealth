"""Replace sensitive email action links with purpose-bound OTP challenges."""

from alembic import op
from sqlalchemy import text

from finhealth.db.action_code_models import AccountActionCode

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create action OTP storage and invalidate legacy links without modifying accounts."""
    AccountActionCode.__table__.create(op.get_bind())
    op.execute(
        text("UPDATE account_action_tokens SET used_at = CURRENT_TIMESTAMP WHERE used_at IS NULL")
    )


def downgrade() -> None:
    """Remove OTP action state without re-enabling old recovery links."""
    AccountActionCode.__table__.drop(op.get_bind())
