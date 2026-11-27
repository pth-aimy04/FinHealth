"""Purpose-bound email OTPs for recovery and sensitive account changes."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from finhealth.db.base import Base


class AccountActionCode(Base):
    """A single-use OTP bound to purpose, recipient and the current password version."""

    __tablename__ = "account_action_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    recipient: Mapped[str] = mapped_column(String(254))
    credential_stamp: Mapped[str] = mapped_column(String(255))
    challenge_hash: Mapped[str] = mapped_column(String(64), unique=True)
    code_hash: Mapped[str] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
