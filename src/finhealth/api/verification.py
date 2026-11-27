"""Registration OTP lifecycle with bounded attempts and atomic single consumption."""

import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finhealth.api.security import digest, hash_password, revoke_sessions, verify_password
from finhealth.db.account_models import AccountActionToken, User
from finhealth.db.base import utc_now
from finhealth.db.verification_models import EmailVerificationCode

OTP_MINUTES = 10
OTP_ATTEMPTS = 5


def create_code(db: Session, user: User) -> tuple[str, str]:
    """Invalidate earlier codes and persist a salted Argon2 hash, never six-digit plaintext."""
    now = utc_now()
    db.execute(
        update(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.used_at.is_(None),
        )
        .values(used_at=now)
    )
    # Old verification links must not outlive the switch to OTP.
    db.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.user_id == user.id,
            AccountActionToken.purpose == "verify",
            AccountActionToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    challenge = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        EmailVerificationCode(
            user_id=user.id,
            challenge_hash=digest(challenge),
            code_hash=hash_password(code),
            expires_at=now + timedelta(minutes=OTP_MINUTES),
        )
    )
    db.flush()
    return challenge, code


def confirm_code(
    db: Session,
    email: str,
    challenge: str,
    code: str,
    new_password: str,
) -> None:
    """Commit failed attempts before returning, and consume valid codes using an atomic guard."""
    invalid = "Mã OTP không đúng, đã hết hạn hoặc đã dùng. Hãy kiểm tra mã mới nhất."
    pair = db.execute(
        select(EmailVerificationCode, User)
        .join(
            User,
            User.id == EmailVerificationCode.user_id,
        )
        .where(EmailVerificationCode.challenge_hash == digest(challenge), User.email == email)
    ).first()
    if pair is None:
        raise HTTPException(400, invalid)
    record, user = pair
    reserved = db.connection().execute(
        update(EmailVerificationCode)
        .where(
            EmailVerificationCode.id == record.id,
            EmailVerificationCode.used_at.is_(None),
            EmailVerificationCode.expires_at > utc_now(),
            EmailVerificationCode.attempts < OTP_ATTEMPTS,
        )
        .values(attempts=EmailVerificationCode.attempts + 1),
    ).rowcount
    if reserved != 1:
        db.rollback()
        raise HTTPException(400, invalid)
    # Keep the row lock through verification so concurrent guesses cannot exceed the budget.
    if not user.active or user.email_verified or not verify_password(record.code_hash, code):
        db.commit()
        raise HTTPException(400, invalid)
    consumed = db.connection().execute(
        update(EmailVerificationCode)
        .where(
            EmailVerificationCode.id == record.id,
            EmailVerificationCode.used_at.is_(None),
            EmailVerificationCode.expires_at > utc_now(),
        )
        .values(used_at=utc_now()),
    ).rowcount
    if consumed != 1:
        db.rollback()
        raise HTTPException(400, invalid)
    user.password_hash = hash_password(new_password)
    user.email_verified = True
    revoke_sessions(db, user.id)
    db.execute(
        update(EmailVerificationCode)
        .where(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.used_at.is_(None),
        )
        .values(used_at=utc_now())
    )
    db.commit()
