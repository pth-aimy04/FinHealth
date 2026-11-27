"""Revocable cookie authentication, CSRF and database-shared abuse limits."""

import hashlib
import secrets
import time
from datetime import timedelta, timezone
from typing import Annotated
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select, true, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db
from finhealth.db.account_models import SecurityRateLimit, User, UserSession
from finhealth.db.base import utc_now

SESSION_COOKIE = "finhealth_session"
CSRF_COOKIE = "finhealth_csrf"


def digest(value: str) -> str:
    """Hash a high-entropy opaque credential for database lookup."""
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    """Hash with Argon2id and a unique library-generated salt."""
    return PasswordHasher().hash(password)


def verify_password(encoded: str, password: str) -> bool:
    """Treat mismatches and corrupted hashes as authentication failure."""
    try:
        return PasswordHasher().verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def consume_limit(
    db: Session,
    action: str,
    identity: str,
    limit: int,
    seconds: int = 600,
) -> None:
    """Atomically enforce a bounded counter across workers using the database clock window."""
    now = utc_now()
    window = int(time.time()) // seconds
    key = digest(f"{action}:{identity}:{window}")
    # Cleanup uses an indexed expiration bound; callers invoke limits before mutations.
    db.execute(delete(SecurityRateLimit).where(SecurityRateLimit.expires_at < now))
    db.commit()
    for _ in range(2):
        changed = db.execute(
            update(SecurityRateLimit)
            .where(
                SecurityRateLimit.bucket == key,
                SecurityRateLimit.attempts < limit,
            )
            .values(attempts=SecurityRateLimit.attempts + 1)
        ).rowcount
        if changed:
            db.commit()
            return
        if db.get(SecurityRateLimit, key) is not None:
            db.rollback()
            raise HTTPException(
                429, "Too many requests; please retry later", headers={"Retry-After": str(seconds)}
            )
        db.add(
            SecurityRateLimit(
                bucket=key,
                attempts=1,
                expires_at=now + timedelta(seconds=seconds * 2),
            )
        )
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
    raise HTTPException(429, "Too many concurrent requests; please retry later")


def request_limit(db: Session, request: Request, action: str, limit: int) -> None:
    """Use the direct peer, never an untrusted forwarded header, for anonymous quotas."""
    consume_limit(db, action, request.client.host if request.client else "unknown", limit)


def optional_identity(request: Request, db: Session) -> tuple[User, UserSession] | None:
    """Resolve only active, verified users with a live server-side session."""
    raw = request.cookies.get(SESSION_COOKIE, "")
    if not raw or len(raw) > 128:
        return None
    pair = db.execute(
        select(User, UserSession)
        .join(
            UserSession,
            UserSession.user_id == User.id,
        )
        .where(
            UserSession.token_hash == digest(raw),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utc_now(),
            User.active == true(),
            User.email_verified == true(),
            UserSession.credential_stamp == User.password_hash,
        )
    ).first()
    return (pair[0], pair[1]) if pair else None


def require_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Authenticate private routes and require CSRF on every state-changing request."""
    identity = optional_identity(request, db)
    if identity is None:
        raise HTTPException(401, "Please sign in to continue")
    user, session = identity
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        supplied = request.headers.get("X-CSRF-Token", "")
        if not supplied or not secrets.compare_digest(digest(supplied), session.csrf_hash):
            raise HTTPException(403, "Invalid CSRF token")
        check_origin(request)
    return user


def check_origin(request: Request) -> None:
    """Reject foreign browser mutation requests against the canonical public origin."""
    origin = request.headers.get("Origin")
    expected = request.app.state.settings.public_base_url
    local_alias = False
    if origin and request.app.state.settings.app_env in ("development", "test"):
        left, right = urlsplit(origin), urlsplit(expected)
        local_alias = (
            left.hostname in ("localhost", "127.0.0.1")
            and right.hostname in ("localhost", "127.0.0.1")
            and left.scheme == right.scheme
            and left.port == right.port
        )
    if origin is not None and origin.rstrip("/") != expected and not local_alias:
        raise HTTPException(403, "Request origin is not allowed")
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        raise HTTPException(403, "Cross-site account request is not allowed")


def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    """Authorize administrators separately from authentication."""
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user


def revoke_sessions(db: Session, user_id: int) -> None:
    """Invalidate every session after credential changes or account deactivation."""
    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )


def public_user(user: User) -> dict[str, object]:
    """Expose only safe profile fields, never hashes or action tokens."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "active": user.active,
        "email_verified": user.email_verified,
    }


def check_prediction_rate(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Bound public CPU-heavy prediction endpoints without requiring login."""
    request_limit(db, request, "prediction", 30)


def aware_time(value: object) -> str:
    """Serialize UTC database timestamps consistently, including SQLite test timestamps."""
    return value.replace(tzinfo=timezone.utc).isoformat() if value is not None else ""
