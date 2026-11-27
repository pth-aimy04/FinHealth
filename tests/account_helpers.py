"""Real account provisioning helpers for isolated integration databases."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finhealth.api.security import hash_password
from finhealth.db.account_models import User

TEST_PASSWORD = "FinHealth-test-password-42!"


def sign_in(
    client: TestClient,
    engine: Engine,
    email: str = "admin@example.com",
    role: str = "admin",
) -> int:
    """Provision a verified fixture identity, then exercise the real login endpoint."""
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                display_name="Integration User",
                role=role,
                password_hash=hash_password(TEST_PASSWORD),
                email_verified=True,
            )
            db.add(user)
            db.commit()
        user_id = user.id
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = client.cookies.get("finhealth_csrf")
    return user_id
