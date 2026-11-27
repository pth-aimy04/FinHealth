"""Submit and track persistent ingestion jobs."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db, require_write_access
from finhealth.api.security import request_limit, require_admin
from finhealth.db.account_models import AdminAuditLog, IngestionRunEvent, User
from finhealth.db.lineage_models import IngestionRun
from finhealth.db.repositories import CompanyRepository, normalize_cik
from finhealth.ingestion.jobs import job_status

router = APIRouter(tags=["ingestion"], dependencies=[Depends(require_write_access)])


@router.post("/ingestion/{identifier}", status_code=202)
def submit_ingestion(
    request: Request, identifier: Annotated[str, Path(pattern=r"^[A-Za-z0-9.-]{1,30}$")],
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> dict[str, object]:
    """Queue a refresh or return an already pending request for the same identifier."""
    if not request.app.state.settings.ingestion_worker_enabled:
        raise HTTPException(503, "Ingestion dispatcher is disabled")
    request_limit(db, request, "ingestion-submit", 30)
    return queue_job(db, identifier, actor.id)


def queue_job(
    db: Session, identifier: str, actor_id: int, retry_of: int | None = None,
) -> dict[str, object]:
    """Use a filtered unique database key to deduplicate submissions across processes."""
    try:
        normalized = normalize_cik(identifier)
    except ValueError:
        company = CompanyRepository(db).get_by_ticker(identifier)
        normalized = company.cik if company else identifier.upper()
    existing = db.scalar(select(IngestionRun).where(
        IngestionRun.identifier == normalized,
        IngestionRun.status.in_(("queued", "running")),
    ).order_by(IngestionRun.id.desc()).limit(1))
    if existing is not None:
        return job_status(existing)
    job = IngestionRun(identifier=normalized, status="queued", stage="queued",
                       active_key=normalized, requested_by=actor_id, retry_of=retry_of)
    db.add(job)
    try:
        db.flush()
        db.add(IngestionRunEvent(run_id=job.id, stage="queued", message="Đang chờ worker"))
        db.add(AdminAuditLog(actor_id=actor_id, action="ingestion.retry" if retry_of else
                             "ingestion.submit", target=str(job.id)))
        db.commit()
        return job_status(job)
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(IngestionRun).where(IngestionRun.active_key == normalized))
        if existing is None:
            raise
        return job_status(existing)


@router.post("/ingestion/{job_id}/retry", status_code=202)
def retry_ingestion(
    job_id: int, request: Request, db: Annotated[Session, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> dict[str, object]:
    """Preserve failed history and link a new bounded retry request to its predecessor."""
    if not request.app.state.settings.ingestion_worker_enabled:
        raise HTTPException(503, "Ingestion dispatcher is disabled")
    request_limit(db, request, "ingestion-submit", 30)
    previous = db.get(IngestionRun, job_id)
    if previous is None:
        raise HTTPException(404, "Unknown ingestion job")
    if previous.status != "failed":
        raise HTTPException(409, "Only failed jobs can be retried")
    return queue_job(db, previous.identifier, actor.id, previous.id)


@router.get("/ingestion/status/{job_id}")
def ingestion_status(job_id: int, db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    """Get persisted progress without resubmitting the SEC job."""
    job = db.get(IngestionRun, job_id)
    if job is None:
        raise HTTPException(404, "Unknown ingestion job")
    return job_status(job)
