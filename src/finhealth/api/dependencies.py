"""Injectable database, SEC client, settings, and thread-safe model activation state."""

import json
import logging
import re
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from threading import RLock
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from finhealth.core.config import Settings, get_settings
from finhealth.core.exceptions import ModelPipelineError
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.ingestion.rate_limiter import AsyncRateLimiter
from finhealth.ingestion.sec_client import SecEdgarClient
from finhealth.ml.registry import ModelArtifactBundle, load_bundle

logger = logging.getLogger(__name__)


class ModelRegistryState:
    """Atomically expose complete immutable bundles to concurrent request threads."""

    def __init__(self) -> None:
        """Initialize empty activation state without filesystem or model loading side effects."""
        self._lock = RLock()
        self.training_lock = RLock()
        self._bundle: ModelArtifactBundle | None = None
        self._initialized = False
        self._directory: Path | None = None

    def get(self) -> ModelArtifactBundle | None:
        """Return a consistent reference to the currently active complete bundle."""
        with self._lock:
            return self._bundle

    def set(self, bundle: ModelArtifactBundle | None) -> None:
        """Publish or clear the active model without exposing partially fitted estimators."""
        with self._lock:
            self._bundle, self._initialized, self._directory = bundle, True, None

    def initialize(self, directory: Path) -> None:
        """Load the published pointer, reloading automatically if the target directory changes."""
        resolved = directory.resolve()
        with self._lock:
            if self._initialized and (self._directory is None or self._directory == resolved):
                return
            self._bundle = None
            self._directory = resolved
            pointer = resolved / "latest.json"
            if pointer.is_file():
                try:
                    target = json.loads(pointer.read_text(encoding="utf-8"))
                    name = target["bundle_dir"]
                    if (
                        not isinstance(name, str)
                        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name)
                        or target["model_version"] != name
                    ):
                        raise ValueError("Invalid published bundle name")
                    bundle = load_bundle(resolved / name)
                    if bundle.model_version != name:
                        raise ValueError("Published bundle version mismatch")
                    self._bundle, self._initialized = bundle, True
                    return
                except (OSError, KeyError, TypeError, ValueError, ModelPipelineError) as error:
                    logger.warning("Cannot load published model: %s", error)
                    self._initialized = True
                    return
            candidates: list[ModelArtifactBundle] = []
            if resolved.is_dir():
                for child in sorted(resolved.iterdir()):
                    if child.is_dir() and not child.name.startswith(".") and not (
                        child / ".unpublished"
                    ).exists():
                        try:
                            candidates.append(load_bundle(child))
                        except ModelPipelineError as error:
                            logger.warning(
                                "Skipping invalid model artifact %s: %s", child.name, error
                            )
            if candidates:
                self._bundle = max(
                    candidates, key=lambda item: (item.created_at, item.model_version)
                )
            self._initialized = True


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
