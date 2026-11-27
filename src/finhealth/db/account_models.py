"""Account, private workspace and operational audit persistence."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from finhealth.db.base import Base, TimestampMixin, utc_now


class User(TimestampMixin, Base):
    """A verified identity with a server-controlled application role."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="user_role"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(Unicode(120))
    role: Mapped[str] = mapped_column(String(16), default="user")
    active: Mapped[bool] = mapped_column(default=True)
    email_verified: Mapped[bool] = mapped_column(default=False)


class UserSession(Base):
    """A revocable opaque session; raw credentials are never persisted."""

    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    credential_stamp: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountActionToken(Base):
    """Single-use, expiring verification, email-change and reset tokens."""

    __tablename__ = "account_action_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str] = mapped_column(String(24))
    pending_email: Mapped[str | None] = mapped_column(String(254))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WatchlistItem(Base):
    """A company followed by exactly one owner."""

    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "company_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SavedScreener(TimestampMixin, Base):
    """An explicitly saved, validated company screening configuration."""

    __tablename__ = "saved_screeners"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(Unicode(120))
    filters: Mapped[dict[str, Any]] = mapped_column(JSON)


class SavedAnalysis(Base):
    """An owner's explicitly saved and server-computed prediction snapshot."""

    __tablename__ = "saved_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(Unicode(120))
    model_version: Mapped[str] = mapped_column(String(64))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdminAuditLog(Base):
    """Append-only application audit, excluding credentials and private financial input."""

    __tablename__ = "admin_audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(24), default="succeeded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SecurityRateLimit(Base):
    """Database-wide fixed-window counters shared by API processes."""

    __tablename__ = "security_rate_limits"
    bucket: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IngestionRunEvent(Base):
    """Persist actual worker transitions with sanitized operational messages."""

    __tablename__ = "ingestion_run_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Unicode(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
