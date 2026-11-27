"""Live database and model readiness route."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from finhealth.api.dependencies import get_active_model_bundle, get_db
from finhealth.api.schemas import HealthCheckSchema
from finhealth.core.config import Settings, get_settings
from finhealth.ml.registry import ModelArtifactBundle

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthCheckSchema, response_model_exclude_unset=True)
def health(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    bundle: Annotated[ModelArtifactBundle | None, Depends(get_active_model_bundle)],
) -> HealthCheckSchema:
    """Execute an actual SQL probe and report degraded readiness when it fails."""
    try:
        connected = db.scalar(text("SELECT 1")) == 1
    except SQLAlchemyError:
        db.rollback()
        connected = False
    if not connected:
        response.status_code = 503
    return HealthCheckSchema(
        status="ok" if connected else "degraded",
        environment=settings.app_env,
        database_connected=connected,
        active_model_version=bundle.model_version if bundle else None,
        **({"ingestion_queue_enabled": True} if settings.ingestion_worker_enabled else {}),
    )
