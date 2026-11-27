"""Persistent asynchronous SEC refresh jobs, claimed by a single dispatcher."""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from fastapi import FastAPI
from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from finhealth.api.services import FinancialAnalysisService
from finhealth.core.exceptions import FinHealthError
from finhealth.db.account_models import AdminAuditLog, IngestionRunEvent
from finhealth.db.base import utc_now
from finhealth.db.lineage_models import IngestionRun
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.ingestion.rate_limiter import AsyncRateLimiter
from finhealth.ingestion.sec_client import SecEdgarClient

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
LEASE = timedelta(minutes=15)


def _claim(factory: sessionmaker[Session]) -> tuple[int, str, int] | None:
    """Claim a queued job or recover a job left behind by an interrupted dispatcher."""
    now = utc_now()
    ready = or_(
        IngestionRun.status == "queued",
        (IngestionRun.status == "running") & (IngestionRun.lease_until <= now),
    )
    with factory.begin() as session:
        session.execute(update(IngestionRun).where(
            ready, IngestionRun.attempts >= MAX_ATTEMPTS,
        ).values(status="failed", stage="failed", active_key=None,
                 error_code="RetryLimit", finished_at=now, lease_until=None))
        row = session.execute(select(
            IngestionRun.id, IngestionRun.identifier, IngestionRun.attempts
        ).where(ready).order_by(IngestionRun.id).limit(1)).first()
        if row is None:
            return None
        claimed = session.connection().execute(update(IngestionRun).where(
            IngestionRun.id == row.id, ready, IngestionRun.attempts == row.attempts,
        ).values(status="running", stage="processing", started_at=now,
                 attempts=row.attempts + 1, lease_until=now + LEASE))
        if claimed.rowcount == 1:
            session.add(IngestionRunEvent(run_id=row.id, stage="processing",
                                          message="Đang lấy SEC, kiểm tra và lưu dữ liệu"))
        return (row.id, row.identifier, row.attempts + 1) if claimed.rowcount == 1 else None


def _finish(
    factory: sessionmaker[Session], job_id: int, attempt: int,
    cik: str | None, error: str | None, recoverable: bool = False,
) -> None:
    """Record a final outcome or requeue a transient failure."""
    retry = recoverable and attempt < MAX_ATTEMPTS
    stage = "queued" if retry else "failed" if error else "succeeded"
    with factory.begin() as session:
        changed = session.connection().execute(update(IngestionRun).where(
            IngestionRun.id == job_id, IngestionRun.attempts == attempt,
        ).values(
            status="queued" if retry else "failed" if error else "succeeded",
            company_cik=cik, error_code=error, finished_at=None if retry else utc_now(),
            lease_until=None, stage=stage,
            **({"active_key": None} if not retry else {}),
        )).rowcount
        if changed:
            session.add(IngestionRunEvent(run_id=job_id, stage=stage,
                                          message=error or "Đã lưu dữ liệu và kết quả phân tích"))
            job = session.get(IngestionRun, job_id)
            if job and job.requested_by and not retry:
                session.add(AdminAuditLog(actor_id=job.requested_by, action="ingestion.finish",
                                          target=str(job_id), outcome=stage))


async def run_dispatcher(app: FastAPI) -> None:
    """Process one SEC job at a time with the same limiter as optional compatibility calls."""
    settings = app.state.settings
    engine = create_db_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        if app.state.sec_limiter is None:
            app.state.sec_limiter = AsyncRateLimiter(settings.sec_rate_limit_per_sec)
        async with SecEdgarClient(settings, rate_limiter=app.state.sec_limiter) as client:
            while True:
                try:
                    item = await run_in_threadpool(_claim, factory)
                    if item is None:
                        await asyncio.sleep(1.5)
                        continue
                    await _execute(app, client, factory, item)
                except SQLAlchemyError:
                    logger.warning("SEC dispatcher database operation failed; retrying")
                    await asyncio.sleep(5)
    finally:
        engine.dispose()


async def _execute(
    app: FastAPI, client: SecEdgarClient, factory: sessionmaker[Session],
    item: tuple[int, str, int],
) -> None:
    """Run the normal analysis service and persist outcome without logging sensitive details."""
    job_id, identifier, attempt = item
    try:
        with factory() as session:
            result = await FinancialAnalysisService().ingest_and_analyze_company(
                session, client, identifier, app.state.model_registry.get(), force_refresh=True,
            )
        await run_in_threadpool(_finish, factory, job_id, attempt, result.company.cik, None)
    except (FinHealthError, SQLAlchemyError, ValueError) as error:
        code = type(error).__name__
        recoverable = code in {"SecIngestionError", "SecRateLimitError", "OperationalError"}
        await run_in_threadpool(_finish, factory, job_id, attempt, None, code, recoverable)
        if recoverable:
            await asyncio.sleep(2 ** attempt)


def job_status(job: IngestionRun) -> dict[str, Any]:
    """Serialize only operational fields required to poll a submitted refresh."""
    return {
        "id": job.id, "status": job.status, "attempts": job.attempts,
        "company_cik": job.company_cik, "error_code": job.error_code,
        "identifier": job.identifier, "requested_by": job.requested_by,
        "stage": job.stage, "retry_of": job.retry_of,
        "requested_at": job.requested_at.isoformat() if job.requested_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
