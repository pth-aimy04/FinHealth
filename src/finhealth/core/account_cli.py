"""Out-of-band administrator provisioning and recovery without public registration."""

import argparse
from getpass import getpass

from sqlalchemy import select

from finhealth.api.action_codes import invalidate_codes
from finhealth.api.schemas.accounts import RegisterInput
from finhealth.api.security import hash_password, revoke_sessions
from finhealth.db.account_models import AdminAuditLog, User
from finhealth.db.session import create_db_engine, create_session_factory


def main() -> None:
    """Create an admin or recover its password through an interactive local terminal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create-admin", "reset-admin"))
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="FinHealth Administrator")
    args = parser.parse_args()
    password = getpass("New password (at least 12 characters): ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match")
    payload = RegisterInput(email=args.email, password=password, display_name=args.name)
    engine = create_db_engine()
    try:
        with create_session_factory(engine).begin() as db:
            user = db.scalar(select(User).where(User.email == payload.email))
            if args.action == "create-admin":
                if user is not None:
                    parser.error("Account already exists; public users cannot be promoted here")
                user = User(
                    email=payload.email,
                    display_name=payload.display_name,
                    password_hash=hash_password(payload.password),
                    role="admin",
                    email_verified=True,
                    active=True,
                )
                db.add(user)
                db.flush()
            else:
                if user is None or user.role != "admin":
                    parser.error("Administrator not found")
                user.password_hash = hash_password(payload.password)
                user.active = True
                revoke_sessions(db, user.id)
                invalidate_codes(db, user.id)
            db.add(
                AdminAuditLog(actor_id=user.id, action=f"cli.{args.action}", target=str(user.id))
            )
        print("Administrator account updated. No password was written to logs.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
