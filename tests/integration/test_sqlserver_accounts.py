"""Requires FINHEALTH_SQLSERVER_TEST_ENABLED=1 and a migrated SQL Server in DATABASE_URL.

All fixture data is enclosed in a rolled-back transaction. No SMTP or SEC service is used.
"""

import os
import re
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db
from finhealth.api.main import create_app
from finhealth.api.security import hash_password
from finhealth.core import mail
from finhealth.core.config import Settings
from finhealth.db.account_models import User
from finhealth.db.session import create_db_engine
from tests.account_helpers import TEST_PASSWORD


def test_sqlserver_cookie_auth_and_queue_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise real ODBC writes, hashed sessions, CSRF, filtered uniqueness and rollback."""
    if os.getenv("FINHEALTH_SQLSERVER_TEST_ENABLED") != "1":
        pytest.skip("Requires explicit FINHEALTH_SQLSERVER_TEST_ENABLED=1 and migrated SQL Server")
    settings = Settings(
        data_dir=tmp_path,
        ingestion_worker_enabled=False,
        smtp_username="fixture@example.com",
        smtp_password="fixture-only",
    )
    messages: list[str] = []

    def capture(settings: Settings, recipient: str, subject: str, body: str) -> None:
        """Replace only the SMTP network boundary; verify actual SQL-backed OTP handling."""
        messages.append(body)

    monkeypatch.setattr(mail, "send_account_email", capture)
    engine = create_db_engine(settings.database_url)
    if engine.dialect.name != "mssql":
        engine.dispose()
        pytest.fail("The explicitly requested integration service must be SQL Server")
    email = f"security-smoke-{uuid4().hex}@example.com"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0007"
                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    db.add(
                        User(
                            email=email,
                            display_name="Kiểm thử SQL Server",
                            role="admin",
                            email_verified=True,
                            password_hash=hash_password(TEST_PASSWORD),
                        )
                    )
                    db.commit()

                def database() -> Generator[Session, None, None]:
                    """Isolate each API commit behind a real SQL Server savepoint."""
                    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                        yield db

                app = create_app(settings)
                # Surface actual ODBC failures in this opt-in service test, not to API users.
                app.exception_handlers.pop(SQLAlchemyError)
                app.dependency_overrides[get_db] = database
                with TestClient(app) as client:
                    assert client.get("/api/v1/admin/users").status_code == 401
                    logged_in = client.post(
                        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
                    )
                    assert logged_in.status_code == 200
                    client.headers["X-CSRF-Token"] = client.cookies.get("finhealth_csrf")
                    saved = client.post(
                        "/api/v1/me/screeners",
                        json={"name": "Bộ lọc kiểm thử", "filters": {"risk_level": "LOW"}},
                    )
                    assert saved.status_code == 201
                    assert client.get("/api/v1/me/screeners").json()[0]["name"] == "Bộ lọc kiểm thử"
                    app.state.settings.ingestion_worker_enabled = True
                    first = client.post("/api/v1/ingestion/SECURITY-TEST")
                    second = client.post("/api/v1/ingestion/SECURITY-TEST")
                    assert first.status_code == second.status_code == 202
                    assert first.json()["id"] == second.json()["id"]
                    assert client.post("/api/v1/auth/logout").status_code == 200
                    assert client.get("/api/v1/auth/me").status_code == 401
                    signup_email = f"otp-{uuid4().hex}@example.com"
                    registered = client.post(
                        "/api/v1/auth/register",
                        json={
                            "email": signup_email,
                            "password": TEST_PASSWORD,
                            "display_name": "Người dùng OTP SQL Server",
                        },
                    )
                    assert registered.status_code == 202
                    code = re.search(r"Mã OTP của bạn: ([0-9]{6})", messages[-1]).group(1)
                    verified = client.post(
                        "/api/v1/auth/verify-email",
                        json={
                            "email": signup_email,
                            "challenge": registered.json()["challenge"],
                            "code": code,
                            "new_password": TEST_PASSWORD,
                        },
                    )
                    assert verified.status_code == 200
                    recovery = client.post(
                        "/api/v1/auth/forgot-password", json={"email": signup_email}
                    )
                    assert recovery.status_code == 202
                    recovery_code = re.search(r"Mã OTP của bạn: ([0-9]{6})", messages[-1]).group(1)
                    recovered = client.post(
                        "/api/v1/auth/reset-password",
                        json={
                            "email": signup_email,
                            "challenge": recovery.json()["challenge"],
                            "code": recovery_code,
                            "new_password": "Recovered-SQL-password-42!",
                        },
                    )
                    assert recovered.status_code == 200
            finally:
                transaction.rollback()
        with Session(engine) as db:
            assert db.scalar(select(User.id).where(User.email == email)) is None
    finally:
        engine.dispose()
