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
    job_title: Mapped[str | None] = mapped_column(Unicode(120))
    role: Mapped[str] = mapped_column(String(16), default="user")
    active: Mapped[bool] = mapped_column(default=True)
    email_verified: Mapped[bool] = mapped_column(default=False)


class Organization(TimestampMixin, Base):
    """A multi-tenant organization workspace isolating private financial records."""

    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Unicode(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    is_personal: Mapped[bool] = mapped_column(default=False, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)


class OrganizationMember(Base):
    """Server-verified organization membership and RBAC role assignment."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
        CheckConstraint(
            "role IN ('org_admin', 'analyst', 'viewer')",
            name="org_member_role",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OrganizationInvite(Base):
    """Single-use expiring invitation token stored only as a SHA-256 digest."""

    __tablename__ = "organization_invites"
    __table_args__ = (
        CheckConstraint(
            "role IN ('org_admin', 'analyst', 'viewer')",
            name="org_invite_role",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OrganizationAuditLog(Base):
    """Append-only organization governance audit trail without secrets or BCTC data."""

    __tablename__ = "organization_audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str] = mapped_column(String(120), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), default="succeeded", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserSession(Base):
    """A revocable opaque session; raw credentials are never persisted."""

    __tablename__ = "user_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    active_org_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )
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
    """A company followed within an authenticated workspace."""

    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "company_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SavedScreener(TimestampMixin, Base):
    """An explicitly saved, validated company screening configuration."""

    __tablename__ = "saved_screeners"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Unicode(120))
    filters: Mapped[dict[str, Any]] = mapped_column(JSON)


class SavedAnalysis(Base):
    """An owner's explicitly saved and server-computed prediction snapshot."""

    __tablename__ = "saved_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Unicode(120))
    model_version: Mapped[str] = mapped_column(String(64))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdminAuditLog(Base):
    """Append-only application audit, excluding credentials and private financial input."""

    __tablename__ = "admin_audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
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
