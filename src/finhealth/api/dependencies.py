"""Injectable database, SEC client, settings, and thread-safe model activation state."""

from collections.abc import AsyncGenerator, Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from finhealth.core.config import Settings, get_settings
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.ingestion.rate_limiter import AsyncRateLimiter
from finhealth.ingestion.sec_client import SecEdgarClient
from finhealth.ml.registry import ModelArtifactBundle, ModelRegistryState

_MODEL_STATE = ModelRegistryState()


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield an app-scoped session; services commit mutations, cleanup rolls back all leftovers."""
    with request.app.state.resource_lock:
        if request.app.state.session_factory is None:
            engine = create_db_engine(request.app.state.settings.database_url)
            request.app.state.engine = engine
            request.app.state.session_factory = create_session_factory(engine)
    session = request.app.state.session_factory()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


def require_write_access(
    request: Request, db: Annotated[Session, Depends(get_db)],
) -> object:
    """Require a verified administrator session, including in development and tests."""
    from finhealth.api.security import require_admin, require_user

    return require_admin(require_user(request, db))


async def get_sec_edgar_client(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> AsyncGenerator[SecEdgarClient, None]:
    """Reuse one app limiter across request clients on the application's event loop."""
    if request.app.state.sec_limiter is None:
        request.app.state.sec_limiter = AsyncRateLimiter(settings.sec_rate_limit_per_sec)
    async with SecEdgarClient(settings, rate_limiter=request.app.state.sec_limiter) as client:
        yield client


def get_active_model_bundle(request: Request) -> ModelArtifactBundle | None:
    """Lazily auto-load trusted local artifacts and expose the active complete model."""
    request.app.state.model_registry.initialize(request.app.state.settings.model_path)
    return request.app.state.model_registry.get()


def set_active_model_bundle(bundle: ModelArtifactBundle | None) -> None:
    """Activate the default process-wide model, or clear it explicitly."""
    _MODEL_STATE.set(bundle)
