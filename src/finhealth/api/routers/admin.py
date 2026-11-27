"""Administrative account and operational views, excluding private financial workspace."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_db
from finhealth.api.schemas.accounts import AccountStatusInput
from finhealth.api.security import aware_time, public_user, require_admin, revoke_sessions
from finhealth.db.account_models import AdminAuditLog, IngestionRunEvent, User
from finhealth.db.lineage_models import IngestionRun
from finhealth.ingestion.jobs import job_status

router = APIRouter(prefix="/admin", tags=["administration"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[User, Depends(require_admin)]


@router.get("/overview")
def overview(request: Request, user: Admin, db: Db) -> dict[str, Any]:
    """Report actual job counts and dispatcher configuration without connection strings."""
    counts = dict(
        db.execute(
            select(IngestionRun.status, func.count()).group_by(
                IngestionRun.status,
            )
        ).all()
    )
    last = db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.status == "succeeded",
        )
        .order_by(IngestionRun.finished_at.desc())
        .limit(1)
    )
    return {
        "database_connected": True,
        "worker_enabled": request.app.state.settings.ingestion_worker_enabled,
        "counts": counts,
        "last_success": aware_time(last.finished_at) if last else None,
        "email_configured": bool(
            request.app.state.settings.smtp_username and request.app.state.settings.smtp_password
        ),
    }


@router.get("/users")
def users(
    user: Admin,
    db: Db,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, object]]:
    """List safe account metadata with bounded pagination."""
    return [
        public_user(row)
        for row in db.scalars(select(User).order_by(User.id).offset(offset).limit(limit)).all()
    ]


@router.patch("/users/{user_id}")
def account_status(user_id: int, payload: AccountStatusInput, actor: Admin, db: Db) -> dict:
    """Lock normal accounts and revoke sessions; administrator recovery stays out of band."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "Không tìm thấy tài khoản")
    if target.role == "admin":
        raise HTTPException(409, "Không thể khóa quản trị viên qua giao diện này")
    target.active = payload.active
    if not payload.active:
        revoke_sessions(db, target.id)
    db.add(
        AdminAuditLog(
            actor_id=actor.id,
            action="account.activate" if payload.active else "account.deactivate",
            target=str(target.id),
        )
    )
    db.commit()
    return public_user(target)


@router.get("/ingestion")
def ingestion_runs(
    user: Admin,
    db: Db,
    status: str | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, Any]]:
    """List actual refresh history, including legacy jobs without an actor."""
    query = select(IngestionRun, User.display_name, User.email).outerjoin(
        User, IngestionRun.requested_by == User.id,
    )
    if status:
        query = query.where(IngestionRun.status == status)
    return [
        {**job_status(run), "requested_by_name": name, "requested_by_email": email}
        for run, name, email in db.execute(
            query.order_by(IngestionRun.id.desc()).offset(offset).limit(limit),
        ).all()
    ]


@router.get("/ingestion/{run_id}/events")
def events(run_id: int, user: Admin, db: Db) -> list[dict[str, object]]:
    """Return bounded operational transitions without SQL parameters or raw SEC payloads."""
    rows = db.scalars(
        select(IngestionRunEvent)
        .where(
            IngestionRunEvent.run_id == run_id,
        )
        .order_by(IngestionRunEvent.id)
        .limit(200)
    ).all()
    return [
        {"stage": row.stage, "message": row.message, "created_at": aware_time(row.created_at)}
        for row in rows
    ]


@router.get("/audit")
def audit(
    user: Admin,
    db: Db,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, object]]:
    """Expose sanitized append-only audit entries to administrators only."""
    rows = db.scalars(
        select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).offset(offset).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "target": row.target,
            "outcome": row.outcome,
            "created_at": aware_time(row.created_at),
        }
        for row in rows
    ]
