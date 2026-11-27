"""Integration tests for multi-tenant organizations, RBAC, invites and Law 91/2025 privacy."""

import re
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finhealth.api.main import create_app
from finhealth.api.routers import organizations
from finhealth.api.security import digest, hash_password
from finhealth.core import mail
from finhealth.core.config import Settings
from finhealth.db.account_models import (
    AccountActionToken,
    AdminAuditLog,
    Organization,
    OrganizationAuditLog,
    OrganizationInvite,
    OrganizationMember,
    SavedAnalysis,
    SavedScreener,
    User,
    UserSession,
    WatchlistItem,
)
from finhealth.db.action_code_models import AccountActionCode
from finhealth.db.base import Base, utc_now
from finhealth.db.models import Company
from finhealth.db.session import create_db_engine
from finhealth.db.verification_models import EmailVerificationCode
from tests.account_helpers import TEST_PASSWORD, sign_in

Context = tuple[TestClient, Engine, list[dict[str, str]]]


@pytest.fixture
def org_ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Context]:
    """Create isolated DB and mount organizations router onto app without modifying main.py."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{tmp_path / 'org_privacy.sqlite3'}",
        data_dir=tmp_path,
        ingestion_worker_enabled=False,
        smtp_username="sender@example.com",
        smtp_password="test-only-smtp",
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    messages: list[dict[str, str]] = []

    def capture(settings: Settings, recipient: str, subject: str, body: str) -> None:
        """Capture outbound email messages without hitting external SMTP."""
        messages.append({"recipient": recipient, "subject": subject, "body": body})

    monkeypatch.setattr(mail, "send_account_email", capture)
    app = create_app(settings)
    app.include_router(organizations.router, prefix="/api/v1")
    with TestClient(app) as client:
        yield client, engine, messages
    engine.dispose()


def _otp_from_email(messages: list[dict[str, str]]) -> str:
    """Extract the 6-digit OTP from the latest captured email."""
    match = re.search(r"Mã OTP của bạn: ([0-9]{6})", messages[-1]["body"])
    assert match is not None
    return match.group(1)


def _login_as(client: TestClient, email: str, password: str = TEST_PASSWORD) -> None:
    """Sign in via the real login endpoint and sync the CSRF header."""
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    csrf = client.cookies.get("finhealth_csrf")
    assert csrf is not None
    client.headers["X-CSRF-Token"] = csrf


def test_verify_email_auto_creates_personal_org_and_profile_job_title(org_ctx: Context) -> None:
    """Verify email preserves owner password, creates personal org, and supports job_title."""
    client, engine, messages = org_ctx
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "founder@example.com",
            "password": TEST_PASSWORD,
            "display_name": "Nguyễn Minh An",
        },
    )
    assert reg.status_code == 202
    owner_password = "Owner-Verified-Password-99!"
    verify = client.post(
        "/api/v1/auth/verify-email",
        json={
            "email": "founder@example.com",
            "challenge": reg.json()["challenge"],
            "code": _otp_from_email(messages),
            "new_password": owner_password,
        },
    )
    assert verify.status_code == 200

    # Pre-registration password must NOT work; owner-chosen password must work.
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "founder@example.com", "password": TEST_PASSWORD},
        ).status_code
        == 401
    )
    _login_as(client, "founder@example.com", owner_password)

    orgs = client.get("/api/v1/organizations")
    assert orgs.status_code == 200
    org_list = orgs.json()
    assert len(org_list) == 1
    assert org_list[0]["is_personal"] is True
    assert org_list[0]["role"] == "org_admin"
    assert org_list[0]["is_active_workspace"] is True
    assert "Nguyễn Minh An" in org_list[0]["name"]

    updated = client.patch(
        "/api/v1/auth/profile",
        json={"display_name": "Nguyễn Minh An", "job_title": "Giám đốc Tài chính"},
    )
    assert updated.status_code == 200
    assert updated.json()["job_title"] == "Giám đốc Tài chính"
    assert client.get("/api/v1/auth/me").json()["job_title"] == "Giám đốc Tài chính"

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Organization)) == 1


def test_org_creation_limit_5_and_member_limit_50(org_ctx: Context) -> None:
    """Enforce max 5 active orgs per creator and max 50 members per organization."""
    client, engine, _ = org_ctx
    sign_in(client, engine, "creator@example.com", "user")

    # User already has 1 personal org; creating 4 more reaches the 5-org cap.
    created_ids: list[int] = []
    for idx in range(4):
        res = client.post("/api/v1/organizations", json={"name": f"Tổ chức {idx + 1}"})
        assert res.status_code == 201, res.text
        created_ids.append(res.json()["id"])

    overflow = client.post("/api/v1/organizations", json={"name": "Tổ chức thứ 6"})
    assert overflow.status_code == 409

    target_org_id = created_ids[0]
    with Session(engine) as db:
        for idx in range(49):
            extra_user = User(
                email=f"member{idx}@example.com",
                display_name=f"Member {idx}",
                password_hash=hash_password(TEST_PASSWORD),
                email_verified=True,
                active=True,
            )
            db.add(extra_user)
            db.flush()
            db.add(
                OrganizationMember(
                    organization_id=target_org_id,
                    user_id=extra_user.id,
                    role="viewer",
                )
            )
        db.commit()

    invite_51 = client.post(
        f"/api/v1/organizations/{target_org_id}/invites",
        json={"email": "overflow@example.com", "role": "viewer"},
    )
    assert invite_51.status_code == 409


def test_org_invite_hashing_email_match_expiry_and_replay(org_ctx: Context) -> None:
    """Invite tokens are SHA-256 hashed, single-use, email-bound (403) and expire after 72h."""
    client, engine, _ = org_ctx
    sign_in(client, engine, "admin-a@example.com", "user")
    org = client.post("/api/v1/organizations", json={"name": "Công ty Minh An"}).json()
    org_id = org["id"]

    inv = client.post(
        f"/api/v1/organizations/{org_id}/invites",
        json={"email": "analyst-b@example.com", "role": "analyst"},
    )
    assert inv.status_code == 201, inv.text
    raw_token = inv.json()["token"]

    with Session(engine) as db:
        row = db.scalar(select(OrganizationInvite).where(OrganizationInvite.id == inv.json()["id"]))
        assert row is not None
        assert row.token_hash == digest(raw_token)
        assert row.token_hash != raw_token
        audits = db.scalars(
            select(OrganizationAuditLog).where(OrganizationAuditLog.organization_id == org_id)
        ).all()
        assert any(a.action == "member.invite" for a in audits)
        assert all(raw_token not in a.target for a in audits)

    # Wrong email user must be rejected with 403.
    sign_in(client, engine, "intruder@example.com", "user")
    assert (
        client.post("/api/v1/organizations/invites/accept", json={"token": raw_token}).status_code
        == 403
    )

    # Intended recipient accepts once; replay is rejected with 400.
    sign_in(client, engine, "analyst-b@example.com", "user")
    accepted = client.post("/api/v1/organizations/invites/accept", json={"token": raw_token})
    assert accepted.status_code == 200
    assert accepted.json()["organization_id"] == org_id
    assert accepted.json()["role"] == "analyst"
    assert (
        client.post("/api/v1/organizations/invites/accept", json={"token": raw_token}).status_code
        == 400
    )

    # Expired invite (>72h) must fail with 400.
    _login_as(client, "admin-a@example.com")
    exp_inv = client.post(
        f"/api/v1/organizations/{org_id}/invites",
        json={"email": "late@example.com", "role": "viewer"},
    )
    assert exp_inv.status_code == 201
    with Session(engine) as db:
        row = db.get(OrganizationInvite, exp_inv.json()["id"])
        assert row is not None
        row.expires_at = utc_now() - timedelta(seconds=5)
        db.commit()

    sign_in(client, engine, "late@example.com", "user")
    assert (
        client.post(
            "/api/v1/organizations/invites/accept",
            json={"token": exp_inv.json()["token"]},
        ).status_code
        == 400
    )


def test_multi_tenant_isolation_and_rbac_on_workspace_and_org(org_ctx: Context) -> None:
    """Non-members get 403/404 (anti-IDOR); viewer is read-only (403); analyst writes workspace."""
    client, engine, _ = org_ctx
    with Session(engine) as db:
        db.add(Company(cik="0000320193", name="Apple Inc", ticker="AAPL"))
        db.commit()

    user_a_id = sign_in(client, engine, "owner-a@example.com", "user")
    org1 = client.post("/api/v1/organizations", json={"name": "Org Alpha"}).json()
    org1_id = org1["id"]

    # User A creates workspace records in Org Alpha.
    wl = client.post("/api/v1/me/watchlist/0000320193")
    assert wl.status_code == 201
    scr = client.post(
        "/api/v1/me/screeners",
        json={"name": "Alpha Screener", "filters": {"risk_level": "LOW"}},
    )
    assert scr.status_code == 201
    scr_id = scr.json()["id"]

    # Persist a SavedAnalysis directly in Org Alpha to verify anti-IDOR read/delete isolation.
    with Session(engine) as db:
        analysis = SavedAnalysis(
            user_id=user_a_id,
            organization_id=org1_id,
            name="Alpha Analysis",
            model_version="v1.0",
            inputs={"revenues": 100.0},
            outputs={"risk_level": "LOW"},
        )
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id

    # User B (in Org 2, not a member of Org Alpha) cannot access Org Alpha or its items.
    user_b_id = sign_in(client, engine, "colleague-b@example.com", "user")
    assert client.get(f"/api/v1/organizations/{org1_id}").status_code == 404
    assert client.get(f"/api/v1/organizations/{org1_id}/members").status_code == 404
    assert (
        client.post("/api/v1/organizations/switch", json={"organization_id": org1_id}).status_code
        == 403
    )
    assert client.get("/api/v1/me/screeners").json() == []
    assert client.get(f"/api/v1/me/analyses/{analysis_id}").status_code == 404
    assert client.delete(f"/api/v1/me/screeners/{scr_id}").status_code == 404

    # User A invites User B as viewer.
    _login_as(client, "owner-a@example.com")
    inv = client.post(
        f"/api/v1/organizations/{org1_id}/invites",
        json={"email": "colleague-b@example.com", "role": "viewer"},
    )
    assert inv.status_code == 201

    # User B accepts and switches active_org_id server-side to Org Alpha.
    _login_as(client, "colleague-b@example.com")
    assert (
        client.post(
            "/api/v1/organizations/invites/accept",
            json={"token": inv.json()["token"]},
        ).status_code
        == 200
    )
    switched = client.post("/api/v1/organizations/switch", json={"organization_id": org1_id})
    assert switched.status_code == 200
    assert switched.json()["active_org_id"] == org1_id

    # Viewer can read shared org data, but all writes & org admin actions return 403.
    assert len(client.get("/api/v1/me/screeners").json()) == 1
    assert len(client.get("/api/v1/me/watchlist").json()) == 1
    assert client.get(f"/api/v1/me/analyses/{analysis_id}").status_code == 200
    assert (
        client.post(
            "/api/v1/me/screeners",
            json={"name": "Viewer Write", "filters": {}},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/me/watchlist/0000320193").status_code == 403
    assert client.delete(f"/api/v1/me/screeners/{scr_id}").status_code == 403
    assert (
        client.patch(f"/api/v1/organizations/{org1_id}", json={"name": "Hijack"}).status_code == 403
    )
    assert client.get(f"/api/v1/organizations/{org1_id}/audit").status_code == 403

    # User A upgrades User B to analyst.
    _login_as(client, "owner-a@example.com")
    promoted = client.patch(
        f"/api/v1/organizations/{org1_id}/members/{user_b_id}",
        json={"role": "analyst"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "analyst"

    # Analyst can write workspace items in Org Alpha, but still cannot manage org/members.
    _login_as(client, "colleague-b@example.com")
    assert (
        client.post("/api/v1/organizations/switch", json={"organization_id": org1_id}).status_code
        == 200
    )
    created_by_analyst = client.post(
        "/api/v1/me/screeners",
        json={"name": "Analyst Screener", "filters": {"risk_level": "MEDIUM"}},
    )
    assert created_by_analyst.status_code == 201
    created_id = created_by_analyst.json()["id"]
    assert client.delete(f"/api/v1/me/screeners/{created_id}").status_code == 204
    assert (
        client.post(
            f"/api/v1/organizations/{org1_id}/invites",
            json={"email": "another@example.com", "role": "viewer"},
        ).status_code
        == 403
    )


def test_last_org_admin_protection_and_audit_log(org_ctx: Context) -> None:
    """Cannot demote or remove the last org_admin (409) until another org_admin exists."""
    client, engine, _ = org_ctx
    admin1_id = sign_in(client, engine, "admin1@example.com", "user")
    org = client.post("/api/v1/organizations", json={"name": "Governance Org"}).json()
    org_id = org["id"]

    assert (
        client.patch(
            f"/api/v1/organizations/{org_id}/members/{admin1_id}",
            json={"role": "analyst"},
        ).status_code
        == 409
    )
    assert client.delete(f"/api/v1/organizations/{org_id}/members/{admin1_id}").status_code == 409

    # Add second member and promote to org_admin.
    inv = client.post(
        f"/api/v1/organizations/{org_id}/invites",
        json={"email": "admin2@example.com", "role": "analyst"},
    ).json()
    admin2_id = sign_in(client, engine, "admin2@example.com", "user")
    assert (
        client.post(
            "/api/v1/organizations/invites/accept", json={"token": inv["token"]}
        ).status_code
        == 200
    )

    _login_as(client, "admin1@example.com")
    assert (
        client.patch(
            f"/api/v1/organizations/{org_id}/members/{admin2_id}",
            json={"role": "org_admin"},
        ).status_code
        == 200
    )
    # Now admin1 can be demoted to analyst.
    assert (
        client.patch(
            f"/api/v1/organizations/{org_id}/members/{admin1_id}",
            json={"role": "analyst"},
        ).status_code
        == 200
    )

    # Admin2 is now the sole org_admin and cannot be removed, and can view audit logs.
    _login_as(client, "admin2@example.com")
    assert client.delete(f"/api/v1/organizations/{org_id}/members/{admin2_id}").status_code == 409
    audit = client.get(f"/api/v1/organizations/{org_id}/audit")
    assert audit.status_code == 200
    actions = {entry["action"] for entry in audit.json()}
    assert {"org.create", "member.invite", "member.invite_accept", "member.role_change"} <= actions


def test_law_91_export_and_delete_account_lifecycle(org_ctx: Context) -> None:
    """Export returns only own data; delete-account blocks sole admin (409), then purges PII."""
    client, engine, messages = org_ctx
    user_a_id = sign_in(client, engine, "alice@example.com", "admin")
    client.patch(
        "/api/v1/auth/profile",
        json={"display_name": "Alice Nguyen", "job_title": "Chuyên viên Rủi ro"},
    )
    client.post("/api/v1/me/screeners", json={"name": "Alice Personal", "filters": {}})
    shared_org = client.post("/api/v1/organizations", json={"name": "Shared Team"}).json()
    shared_org_id = shared_org["id"]

    # Record an AdminAuditLog authored by Alice to verify actor_id becomes NULL after deletion.
    with Session(engine) as db:
        db.add(AdminAuditLog(actor_id=user_a_id, action="account.check", target="user:1"))
        db.commit()

    # Invite Bob into Shared Team as viewer.
    inv = client.post(
        f"/api/v1/organizations/{shared_org_id}/invites",
        json={"email": "bob@example.com", "role": "viewer"},
    ).json()
    bob_id = sign_in(client, engine, "bob@example.com", "user")
    client.post("/api/v1/me/screeners", json={"name": "Bob Secret Screener", "filters": {}})
    assert (
        client.post(
            "/api/v1/organizations/invites/accept", json={"token": inv["token"]}
        ).status_code
        == 200
    )

    # Alice exports her personal data: must contain only Alice's data, never Bob's or secrets.
    _login_as(client, "alice@example.com")
    exported = client.get("/api/v1/auth/me/export")
    assert exported.status_code == 200
    body = exported.json()
    assert body["profile"]["email"] == "alice@example.com"
    assert body["profile"]["job_title"] == "Chuyên viên Rủi ro"
    assert "password_hash" not in body["profile"]
    assert all("token_hash" not in s and "csrf_hash" not in s for s in body["sessions"])
    assert "bob@example.com" not in str(body)
    assert "Bob Secret Screener" not in str(body)
    assert any(s["name"] == "Alice Personal" for s in body["workspace"]["screeners"])

    # Step 1: Alice is sole org_admin of Shared Team (which has Bob) -> delete-account returns 409.
    req1 = client.post(
        "/api/v1/auth/delete-account/request",
        json={"current_password": TEST_PASSWORD},
    )
    assert req1.status_code == 202
    blocked = client.post(
        "/api/v1/auth/delete-account",
        json={
            "current_password": TEST_PASSWORD,
            "challenge": req1.json()["challenge"],
            "code": _otp_from_email(messages),
        },
    )
    assert blocked.status_code == 409

    # Step 2: Promote Bob to org_admin, then delete Alice's account cleanly.
    assert (
        client.patch(
            f"/api/v1/organizations/{shared_org_id}/members/{bob_id}",
            json={"role": "org_admin"},
        ).status_code
        == 200
    )

    # Clear fixture rate limits to request a fresh OTP immediately in the same second.
    with Session(engine) as db:
        from finhealth.db.account_models import SecurityRateLimit

        for counter in db.scalars(select(SecurityRateLimit)).all():
            db.delete(counter)
        db.commit()

    old_session_cookie = client.cookies.get("finhealth_session")
    assert old_session_cookie is not None

    req2 = client.post(
        "/api/v1/auth/delete-account/request",
        json={"current_password": TEST_PASSWORD},
    )
    assert req2.status_code == 202
    deleted = client.post(
        "/api/v1/auth/delete-account",
        json={
            "current_password": TEST_PASSWORD,
            "challenge": req2.json()["challenge"],
            "code": _otp_from_email(messages),
        },
    )
    assert deleted.status_code == 200

    # Old cookie immediately returns 401.
    client.cookies.set("finhealth_session", old_session_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401

    # Verify complete PII purge and audit log anonymization in DB.
    with Session(engine) as db:
        assert db.get(User, user_a_id) is None
        assert db.scalar(select(User).where(User.email == "alice@example.com")) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(UserSession)
                .where(UserSession.user_id == user_a_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AccountActionCode)
                .where(AccountActionCode.user_id == user_a_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(EmailVerificationCode)
                .where(EmailVerificationCode.user_id == user_a_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AccountActionToken)
                .where(AccountActionToken.user_id == user_a_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SavedScreener)
                .where(SavedScreener.name == "Alice Personal")
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(WatchlistItem)
                .where(WatchlistItem.user_id == user_a_id)
            )
            == 0
        )
        # Shared Team remains alive for Bob; Alice's AdminAuditLog is preserved with actor_id=NULL.
        assert db.get(Organization, shared_org_id) is not None
        audit_row = db.scalar(
            select(AdminAuditLog).where(AdminAuditLog.action == "account.check")
        )
        assert audit_row is not None
        assert audit_row.actor_id is None
