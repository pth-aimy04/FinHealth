"""Offline real SQL/API security tests; SMTP is the sole replaced external boundary."""

import re
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finhealth.api.main import create_app
from finhealth.api.security import digest
from finhealth.core import mail
from finhealth.core.config import Settings
from finhealth.db.account_models import AccountActionToken, SecurityRateLimit, User, UserSession
from finhealth.db.action_code_models import AccountActionCode
from finhealth.db.base import Base, utc_now
from finhealth.db.lineage_models import IngestionRun
from finhealth.db.models import Company
from finhealth.db.session import create_db_engine
from finhealth.db.verification_models import EmailVerificationCode
from tests.account_helpers import TEST_PASSWORD, sign_in

Context = tuple[TestClient, Engine, list[dict[str, str]]]


@pytest.fixture
def accounts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Context]:
    """Create isolated relational state and capture only external outbound email delivery."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{tmp_path / 'accounts.sqlite3'}",
        data_dir=tmp_path,
        ingestion_worker_enabled=False,
        smtp_username="sender@example.com",
        smtp_password="test-only-smtp",
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    messages: list[dict[str, str]] = []

    def capture(settings: Settings, recipient: str, subject: str, body: str) -> None:
        """Capture the external mail transport, keeping token generation and SQL real."""
        messages.append({"recipient": recipient, "subject": subject, "body": body})

    monkeypatch.setattr(mail, "send_account_email", capture)
    with TestClient(create_app(settings)) as client:
        yield client, engine, messages
    engine.dispose()


def otp_from_email(messages: list[dict[str, str]]) -> str:
    """Read the code from the delivered email, never from persisted account state."""
    match = re.search(r"Mã OTP của bạn: ([0-9]{6})", messages[-1]["body"])
    assert match is not None
    assert "localhost" not in messages[-1]["body"]
    return match.group(1)


def register_and_verify(client: TestClient, messages: list[dict[str, str]], email: str) -> None:
    """Exercise registration and mailbox verification through their public contracts."""
    result = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "display_name": "Người dùng thử"},
    )
    assert result.status_code == 202
    code = otp_from_email(messages)
    assert (
        client.post(
            "/api/v1/auth/verify-email",
            json={
                "email": email,
                "challenge": result.json()["challenge"],
                "code": code,
                "new_password": TEST_PASSWORD,
            },
        ).status_code
        == 200
    )


def test_registration_mail_verification_login_logout(accounts: Context) -> None:
    """Roles cannot be injected; unverified and revoked identities cannot access private data."""
    client, engine, messages = accounts
    payload = {"email": "owner@example.com", "password": TEST_PASSWORD, "display_name": "Owner"}
    assert (
        client.post("/api/v1/auth/register", json={**payload, "role": "admin"}).status_code == 422
    )
    registered = client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 202
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": payload["email"], "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    raw = otp_from_email(messages)
    challenge = registered.json()["challenge"]
    verification = {
        "email": payload["email"],
        "challenge": challenge,
        "code": raw,
        "new_password": TEST_PASSWORD,
    }
    with Session(engine) as db:
        token = db.scalar(select(EmailVerificationCode))
        user = db.scalar(select(User))
        assert token.challenge_hash == digest(challenge)
        assert token.code_hash.startswith("$argon2id$") and token.code_hash != raw
        assert user.role == "user" and user.password_hash.startswith("$argon2id$")
        assert TEST_PASSWORD not in user.password_hash
    assert client.post("/api/v1/auth/verify-email", json=verification).status_code == 200
    assert client.post("/api/v1/auth/verify-email", json=verification).status_code == 400
    signed_in = client.post(
        "/api/v1/auth/login", json={"email": payload["email"], "password": TEST_PASSWORD}
    )
    assert signed_in.status_code == 200
    assert "HttpOnly" in signed_in.headers.get_list("set-cookie")[0]
    assert "samesite=strict" in signed_in.headers.get_list("set-cookie")[0].lower()
    raw_session = client.cookies.get("finhealth_session")
    assert client.post("/api/v1/auth/logout").status_code == 403
    client.headers["X-CSRF-Token"] = client.cookies.get("finhealth_csrf")
    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.set("finhealth_session", raw_session)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_guest_public_access_and_admin_denial_in_development(accounts: Context) -> None:
    """No environment fallback or legacy bearer secret can bypass role checks."""
    client, engine, _ = accounts
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/companies").status_code == 200
    for path in ("/api/v1/ingestion/AAPL", "/api/v1/companies/AAPL/analyze"):
        assert client.post(path).status_code == 401
        assert client.post(path, headers={"Authorization": "Bearer old-secret"}).status_code == 401
    assert client.get("/api/v1/admin/users").status_code == 401
    sign_in(client, engine, "user@example.com", "user")
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.post("/api/v1/ingestion/AAPL").status_code == 403


def test_owner_isolation_and_server_validation(accounts: Context) -> None:
    """A second user and an admin cannot read or delete another owner's saved records."""
    client, engine, _ = accounts
    sign_in(client, engine, "first@example.com", "user")
    created = client.post(
        "/api/v1/me/screeners",
        json={"name": "Rủi ro thấp", "filters": {"risk_level": "LOW", "min_roa": 0.1}},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    invalid = client.post(
        "/api/v1/me/screeners", json={"name": "bad", "filters": {"role": "admin"}}
    )
    assert invalid.status_code == 422
    assert (
        client.post(
            "/api/v1/me/screeners", json={"name": "bad", "filters": {}, "user_id": 1}
        ).status_code
        == 422
    )
    for email, role in (("second@example.com", "user"), ("admin@example.com", "admin")):
        sign_in(client, engine, email, role)
        assert client.get("/api/v1/me/screeners").json() == []
        assert client.delete(f"/api/v1/me/screeners/{item_id}").status_code == 404
    sign_in(client, engine, "first@example.com", "user")
    assert client.delete(f"/api/v1/me/screeners/{item_id}").status_code == 204


def test_csrf_origin_and_password_change_revocation(accounts: Context) -> None:
    """Foreign origins and bad CSRF are rejected; password changes revoke all sessions."""
    client, engine, messages = accounts
    sign_in(client, engine, "owner@example.com", "user")
    original = client.cookies.get("finhealth_session")
    assert (
        client.patch(
            "/api/v1/auth/profile", json={"display_name": "New"}, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/auth/profile",
            json={"display_name": "New"},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": TEST_PASSWORD},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": TEST_PASSWORD, "new_password": "Changed-strong-password-42!"},
    )
    assert changed.status_code == 202
    assert client.get("/api/v1/auth/me").status_code == 200
    confirmed = client.post(
        "/api/v1/auth/confirm-password-change",
        json={
            "email": "owner@example.com",
            "challenge": changed.json()["challenge"],
            "code": otp_from_email(messages),
            "new_password": "Changed-strong-password-42!",
        },
    )
    assert confirmed.status_code == 200
    assert messages[-1]["recipient"] == "owner@example.com"
    assert "Changed-strong" not in messages[-1]["body"]
    client.cookies.set("finhealth_session", original)
    assert client.get("/api/v1/auth/me").status_code == 401
    with Session(engine) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(UserSession)
                .where(UserSession.revoked_at.is_(None))
            )
            == 0
        )


def test_reset_expiration_replay_and_generic_response(accounts: Context) -> None:
    """Only mailbox-delivered live tokens can reset; reset invalidates prior sessions."""
    client, engine, messages = accounts
    sign_in(client, engine, "owner@example.com", "user")
    original_session = client.cookies.get("finhealth_session")
    known = client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    raw = otp_from_email(messages)
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "absent@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json()["message"] == unknown.json()["message"]
    reset_payload = {
        "email": "owner@example.com",
        "challenge": known.json()["challenge"],
        "code": raw,
        "new_password": "Reset-strong-password-42!",
    }
    with Session(engine) as db:
        record = db.scalar(select(AccountActionCode))
        record.expires_at = utc_now() - timedelta(seconds=1)
        for counter in db.scalars(select(SecurityRateLimit)).all():
            db.delete(counter)
        db.commit()
    assert client.post("/api/v1/auth/reset-password", json=reset_payload).status_code == 400
    sent = client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    reset_payload.update(challenge=sent.json()["challenge"], code=otp_from_email(messages))
    assert client.post("/api/v1/auth/reset-password", json=reset_payload).status_code == 200
    assert client.post("/api/v1/auth/reset-password", json=reset_payload).status_code == 400
    client.cookies.set("finhealth_session", original_session)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": reset_payload["new_password"]},
        ).status_code
        == 200
    )


def test_smtp_unconfigured_or_failed_does_not_mutate_account(
    accounts: Context,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing or failed external delivery returns 503 and does not leave a new account."""
    client, engine, _ = accounts
    client.app.state.settings.smtp_password = None
    payload = {"email": "owner@example.com", "password": TEST_PASSWORD, "display_name": "Owner"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 503
    client.app.state.settings.smtp_password = "test-only"

    def fail(*args: Any, **kwargs: Any) -> None:
        """Simulate only an unavailable external SMTP service."""
        raise mail.EmailDeliveryError("Email delivery failed; please retry later")

    monkeypatch.setattr(mail, "send_account_email", fail)
    assert client.post("/api/v1/auth/register", json=payload).status_code == 503
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(AccountActionToken)) == 0


def test_ingestion_queue_deduplication_and_account_lock(accounts: Context) -> None:
    """Admin queue history is persistent; duplicate submissions and account locking are real SQL."""
    client, engine, _ = accounts
    sign_in(client, engine)
    # Enable submission without launching the worker or making SEC network requests.
    client.app.state.settings.ingestion_worker_enabled = True
    first = client.post("/api/v1/ingestion/AAPL")
    second = client.post("/api/v1/ingestion/AAPL")
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert client.get("/api/v1/admin/ingestion").json()[0]["requested_by"] is not None
    assert (
        client.get(f"/api/v1/admin/ingestion/{first.json()['id']}/events").json()[0]["stage"]
        == "queued"
    )
    with Session(engine) as db:
        job = db.get(IngestionRun, first.json()["id"])
        job.status, job.active_key = "failed", None
        db.commit()
    retried = client.post(f"/api/v1/ingestion/{first.json()['id']}/retry")
    assert retried.status_code == 202 and retried.json()["retry_of"] == first.json()["id"]
    target_id = sign_in(client, engine, "target@example.com", "user")
    target_cookie = client.cookies.get("finhealth_session")
    sign_in(client, engine)
    assert (
        client.patch(f"/api/v1/admin/users/{target_id}", json={"active": False}).status_code == 200
    )
    assert any(
        row["action"] == "account.deactivate" for row in client.get("/api/v1/admin/audit").json()
    )
    client.cookies.clear()
    client.cookies.set("finhealth_session", target_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_ingestion_history_exposes_requester_only_to_admin(accounts: Context) -> None:
    """Join requester identity for admin while retaining historical jobs without actors."""
    client, engine, _ = accounts
    assert client.get("/api/v1/admin/ingestion").status_code == 401
    admin_id = sign_in(client, engine)
    with Session(engine) as db:
        db.add_all([
            IngestionRun(identifier="AAPL", status="succeeded", requested_by=admin_id),
            IngestionRun(identifier="LEGACY", status="succeeded", requested_by=None),
        ])
        db.commit()
    response = client.get("/api/v1/admin/ingestion?limit=1&offset=0")
    assert response.status_code == 200
    assert response.json()[0]["identifier"] == "LEGACY"
    assert response.json()[0]["requested_by"] is None
    assert response.json()[0]["requested_by_name"] is None
    assert response.json()[0]["requested_by_email"] is None
    response = client.get("/api/v1/admin/ingestion?limit=1&offset=1")
    assert response.status_code == 200
    entry = response.json()[0]
    assert entry["requested_by"] == admin_id
    assert entry["requested_by_name"] == "Integration User"
    assert entry["requested_by_email"] == "admin@example.com"
    assert "password_hash" not in entry
    sign_in(client, engine, "normal@example.com", "user")
    assert client.get("/api/v1/admin/ingestion").status_code == 403


def test_following_is_idempotent_and_body_limit(accounts: Context) -> None:
    """Following does not duplicate rows and body limits apply before schema processing."""
    client, engine, _ = accounts
    with Session(engine) as db:
        db.add(Company(cik="0000320193", name="Apple", ticker="AAPL"))
        db.commit()
    sign_in(client, engine, "owner@example.com", "user")
    first = client.post("/api/v1/me/watchlist/0000320193")
    second = client.post("/api/v1/me/watchlist/0000320193")
    assert first.status_code == second.status_code == 201 and first.json() == second.json()
    assert len(client.get("/api/v1/me/watchlist").json()) == 1
    large = client.post("/api/v1/auth/login", content=b"x" * 2_000_001)
    assert large.status_code == 413


def test_login_throttle_and_session_expiry(
    accounts: Context, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated login failures are bounded and an expired session cannot be reused."""
    # Keep requests in one quota window even when execution crosses a ten-minute boundary.
    monkeypatch.setattr(
        "finhealth.api.security.time", SimpleNamespace(time=lambda: 1_800_000_100.0),
    )
    client, engine, _ = accounts
    sign_in(client, engine, "owner@example.com", "user")
    with Session(engine) as db:
        session = db.scalar(select(UserSession))
        session.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    for _ in range(9):
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong"}
        ).status_code
        == 429
    )


def test_email_change_invalidates_old_recovery_tokens(accounts: Context) -> None:
    """Changing mailbox ownership revokes old sessions and previously delivered reset links."""
    client, engine, messages = accounts
    sign_in(client, engine, "old@example.com", "user")
    old = client.post("/api/v1/auth/forgot-password", json={"email": "old@example.com"})
    old_reset = {
        "email": "old@example.com",
        "challenge": old.json()["challenge"],
        "code": otp_from_email(messages),
        "new_password": "Compromised-password-42!",
    }
    requested = client.post(
        "/api/v1/auth/change-email",
        json={"email": "new@example.com", "current_password": TEST_PASSWORD},
    )
    assert requested.status_code == 202
    change_code = otp_from_email(messages)
    assert messages[-1]["recipient"] == "new@example.com"
    assert client.get("/api/v1/auth/me").json()["email"] == "old@example.com"
    confirmed = client.post(
        "/api/v1/auth/confirm-email",
        json={
            "email": "new@example.com",
            "challenge": requested.json()["challenge"],
            "code": change_code,
        },
    )
    assert confirmed.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json=old_reset,
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "new@example.com", "password": TEST_PASSWORD}
        ).status_code
        == 200
    )


def test_verification_cannot_preserve_attacker_selected_password(accounts: Context) -> None:
    """The mailbox owner chooses the final password even if somebody pre-registered the email."""
    client, _, messages = accounts
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": TEST_PASSWORD, "display_name": "Pending"},
    )
    code = otp_from_email(messages)
    owner_password = "Owner-chosen-password-42!"
    assert (
        client.post(
            "/api/v1/auth/verify-email",
            json={
                "email": "owner@example.com",
                "challenge": registered.json()["challenge"],
                "code": code,
                "new_password": owner_password,
            },
        ).status_code
        == 200
    )

    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": owner_password}
        ).status_code
        == 200
    )


def test_otp_wrong_attempts_expiration_and_resend(accounts: Context) -> None:
    """A challenge permits five guesses; resending replaces it, and expiration is enforced."""
    client, engine, messages = accounts
    email = "otp@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "display_name": "OTP owner"},
    )
    assert registered.status_code == 202
    challenge, code = registered.json()["challenge"], otp_from_email(messages)
    payload = {"email": email, "challenge": challenge, "code": code, "new_password": TEST_PASSWORD}
    assert registered.json()["expires_in"] == 600
    assert client.post("/api/v1/auth/resend-verification", json={"email": email}).status_code == 429
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        assert (
            client.post("/api/v1/auth/verify-email", json={**payload, "code": wrong}).status_code
            == 400
        )
    assert client.post("/api/v1/auth/verify-email", json=payload).status_code == 400
    with Session(engine) as db:
        record = db.scalar(select(EmailVerificationCode))
        assert record.attempts == 5
        assert not db.scalar(select(User)).email_verified
        # Reset only fixture quota state to simulate waiting for a fresh send window.
        for counter in db.scalars(select(SecurityRateLimit)).all():
            db.delete(counter)
        db.commit()
    resent = client.post("/api/v1/auth/resend-verification", json={"email": email})
    assert resent.status_code == 202
    next_code = otp_from_email(messages)
    assert resent.json()["challenge"] != challenge
    assert client.post("/api/v1/auth/verify-email", json=payload).status_code == 400
    fresh = {**payload, "challenge": resent.json()["challenge"], "code": next_code}
    with Session(engine) as db:
        record = db.scalar(
            select(EmailVerificationCode).where(
                EmailVerificationCode.challenge_hash == digest(resent.json()["challenge"])
            )
        )
        record.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/v1/auth/verify-email", json=fresh).status_code == 400


def test_otp_email_and_challenge_binding(accounts: Context) -> None:
    """A delivered code cannot verify a different mailbox or a different browser challenge."""
    client, _, messages = accounts
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "otp@example.com", "password": TEST_PASSWORD, "display_name": "OTP owner"},
    )
    payload = {
        "email": "otp@example.com",
        "challenge": registered.json()["challenge"],
        "code": otp_from_email(messages),
        "new_password": TEST_PASSWORD,
    }
    assert (
        client.post(
            "/api/v1/auth/verify-email", json={**payload, "email": "other@example.com"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/verify-email", json={**payload, "challenge": "a" * 43}
        ).status_code
        == 400
    )
    assert (
        client.post("/api/v1/auth/verify-email", json={**payload, "code": "12345"}).status_code
        == 422
    )
    assert client.post("/api/v1/auth/verify-email", json=payload).status_code == 200
    assert client.post("/api/v1/auth/verify-email", json=payload).status_code == 400


def test_recovery_otp_is_not_a_password_change_otp(accounts: Context) -> None:
    """Codes are purpose-bound, attempts persist and changing passwords needs confirmation."""
    client, engine, messages = accounts
    sign_in(client, engine, "owner@example.com", "user")
    sent = client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    code = otp_from_email(messages)
    payload = {
        "email": "owner@example.com",
        "challenge": sent.json()["challenge"],
        "code": code,
        "new_password": "New-owner-password-42!",
    }
    assert client.post("/api/v1/auth/confirm-password-change", json=payload).status_code == 400
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={**payload, "email": "other@example.com"}
        ).status_code
        == 400
    )
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        assert (
            client.post("/api/v1/auth/reset-password", json={**payload, "code": wrong}).status_code
            == 400
        )
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 400
    with Session(engine) as db:
        record = db.scalar(select(AccountActionCode))
        assert record.attempts == 5


def test_unverified_admin_mailbox_can_be_verified_without_role_loss(accounts: Context) -> None:
    """Operator-corrected admin email must prove mailbox ownership before privileged access."""
    client, engine, messages = accounts
    admin_id = sign_in(client, engine, "admin@example.com", "admin")
    with Session(engine) as db:
        db.get(User, admin_id).email_verified = False
        db.commit()
    assert client.get("/api/v1/admin/users").status_code == 401
    sent = client.post("/api/v1/auth/resend-verification", json={"email": "admin@example.com"})
    assert sent.status_code == 202
    assert (
        client.post(
            "/api/v1/auth/verify-email",
            json={
                "email": "admin@example.com",
                "challenge": sent.json()["challenge"],
                "code": otp_from_email(messages),
                "new_password": TEST_PASSWORD,
            },
        ).status_code
        == 200
    )
    sign_in(client, engine)
    assert client.get("/api/v1/admin/users").status_code == 200
