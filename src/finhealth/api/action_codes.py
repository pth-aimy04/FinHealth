"""Hashed email OTPs for password recovery, password change and email replacement."""

import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finhealth.api.security import digest, hash_password, verify_password
from finhealth.api.verification import OTP_ATTEMPTS, OTP_MINUTES
from finhealth.db.account_models import AccountActionToken, User
from finhealth.db.action_code_models import AccountActionCode
from finhealth.db.base import utc_now
from finhealth.db.verification_models import EmailVerificationCode


def issue_code(db: Session, user: User, purpose: str, recipient: str) -> tuple[str, str]:
    """Replace older challenges for this purpose and store only a slow salted code hash."""
    db.execute(
        update(AccountActionCode)
        .where(
            AccountActionCode.user_id == user.id,
            AccountActionCode.purpose == purpose,
            AccountActionCode.used_at.is_(None),
        )
        .values(used_at=utc_now())
    )
    challenge, code = secrets.token_urlsafe(32), f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        AccountActionCode(
            user_id=user.id,
            purpose=purpose,
            recipient=recipient,
            credential_stamp=user.password_hash,
            challenge_hash=digest(challenge),
            code_hash=hash_password(code),
            expires_at=utc_now() + timedelta(minutes=OTP_MINUTES),
        )
    )
    db.flush()
    return challenge, code


def consume_code(
    db: Session,
    email: str,
    challenge: str,
    code: str,
    purpose: str,
    actor_id: int | None = None,
) -> tuple[User, AccountActionCode]:
    """Reserve a guess under a row lock; consume once and reject cross-purpose credentials."""
    invalid = "Mã OTP không đúng, đã hết hạn hoặc đã dùng. Hãy kiểm tra mã mới nhất."
    pair = db.execute(
        select(AccountActionCode, User)
        .join(
            User,
            User.id == AccountActionCode.user_id,
        )
        .where(
            AccountActionCode.challenge_hash == digest(challenge),
            AccountActionCode.purpose == purpose,
            AccountActionCode.recipient == email,
        )
    ).first()
    if pair is None:
        raise HTTPException(400, invalid)
    record, user = pair
    reserved = db.execute(
        update(AccountActionCode)
        .where(
            AccountActionCode.id == record.id,
            AccountActionCode.used_at.is_(None),
            AccountActionCode.expires_at > utc_now(),
            AccountActionCode.attempts < OTP_ATTEMPTS,
        )
        .values(attempts=AccountActionCode.attempts + 1),
        execution_options={"synchronize_session": False},
    ).rowcount
    if reserved != 1:
        db.rollback()
        raise HTTPException(400, invalid)
    if (
        not user.active
        or not user.email_verified
        or record.credential_stamp != user.password_hash
        or (actor_id is not None and user.id != actor_id)
        or (purpose != "change-email" and user.email != email)
        or not verify_password(record.code_hash, code)
    ):
        db.commit()
        raise HTTPException(400, invalid)
    changed = db.execute(
        update(AccountActionCode)
        .where(
            AccountActionCode.id == record.id,
            AccountActionCode.used_at.is_(None),
            AccountActionCode.expires_at > utc_now(),
        )
        .values(used_at=utc_now()),
        execution_options={"synchronize_session": False},
    ).rowcount
    if changed != 1:
        db.rollback()
        raise HTTPException(400, invalid)
    return user, record


def invalidate_codes(db: Session, user_id: int) -> None:
    """Revoke all OTPs and legacy links after a completed credential or mailbox change."""
    for model in (AccountActionCode, EmailVerificationCode, AccountActionToken):
        db.execute(
            update(model)
            .where(model.user_id == user_id, model.used_at.is_(None))
            .values(used_at=utc_now())
        )
