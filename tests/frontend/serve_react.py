"""Run browser acceptance against an isolated copy; never change the development database."""

import shutil
from pathlib import Path

import uvicorn
from sqlalchemy import select
from sqlalchemy.orm import Session

from finhealth.api.main import create_app
from finhealth.api.security import hash_password
from finhealth.core.config import Settings
from finhealth.db.account_models import User
from finhealth.db.base import Base
from finhealth.db.session import create_db_engine


def main() -> None:
    """Copy local evidence and provision disposable browser-test accounts."""
    root = Path(__file__).resolve().parents[2]
    target = root / ".venv" / "react-preview.sqlite3"
    source = root / "data/processed/parquet/finhealth.sqlite3"
    target.unlink(missing_ok=True)
    if source.is_file():
        shutil.copy2(source, target)
    url = f"sqlite:///{target.as_posix()}"
    engine = create_db_engine(url)
    Base.metadata.create_all(engine)
    if not source.is_file():
        # Only public financial records are copied. The source connection executes SELECTs only.
        source_engine = create_db_engine(Settings().database_url)
        public_tables = {
            "companies", "financial_statements", "financial_metrics", "model_predictions",
            "filing_versions", "forecast_evidence",
        }
        try:
            with source_engine.connect() as reader, engine.begin() as writer:
                for table in Base.metadata.sorted_tables:
                    if table.name in public_tables:
                        rows = reader.execute(select(table)).mappings().all()
                        if rows:
                            writer.execute(table.insert(), [dict(row) for row in rows])
        finally:
            source_engine.dispose()
    with Session(engine) as db:
        for role in ("user", "admin"):
            db.add(User(
                email=f"react-{role}@example.com",
                display_name=f"React {role}",
                role=role,
                password_hash=hash_password("FinHealth-browser-fixture-42!"),
                email_verified=True,
            ))
        db.commit()
    engine.dispose()
    app = create_app(Settings(
        _env_file=None,
        DATABASE_URL=url,
        data_dir=root / "data",
        frontend_dir=root / "frontend/dist",
        public_base_url="http://127.0.0.1:8765",
        ingestion_worker_enabled=False,
    ))
    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
