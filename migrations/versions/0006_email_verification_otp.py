"""Add hashed registration OTPs without changing existing account action links."""

from alembic import op

from finhealth.db.verification_models import EmailVerificationCode

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create isolated, expiring registration challenges."""
    EmailVerificationCode.__table__.create(op.get_bind())


def downgrade() -> None:
    """Remove OTP challenges only on an explicit operator downgrade."""
    EmailVerificationCode.__table__.drop(op.get_bind())
