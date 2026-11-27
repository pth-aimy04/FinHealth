"""FastAPI application factory with explicit dependencies and structured domain failures."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from functools import lru_cache
from threading import RLock

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from finhealth import __version__
from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.protection import RequestProtection
from finhealth.api.routers import (
    accounts,
    admin,
    companies,
    dashboard,
    health,
    ingestion,
    models,
    reports,
    workspace,
)
from finhealth.api.services import invalidate_benchmark_cache
from finhealth.api.static import DashboardStaticFiles
from finhealth.core.config import Settings, get_settings
from finhealth.core.exceptions import (
    EtlProcessingError,
    ModelPipelineError,
    SecIngestionError,
    SecRateLimitError,
    SecResourceNotFoundError,
)
from finhealth.ingestion.jobs import run_dispatcher


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an app without opening database connections or issuing SEC requests."""
    configured = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Initialize trusted model state and dispose owned database resources on shutdown."""
        app.state.model_registry.initialize(configured.model_path)
        dispatcher = (
            asyncio.create_task(run_dispatcher(app))
            if configured.ingestion_worker_enabled else None
        )
        try:
            yield
        finally:
            if dispatcher is not None:
                dispatcher.cancel()
                with suppress(asyncio.CancelledError):
                    await dispatcher
            if app.state.engine is not None:
                invalidate_benchmark_cache(app.state.engine)
                app.state.engine.dispose()
                app.state.engine = None
                app.state.session_factory = None
            app.state.sec_limiter = None

    app = FastAPI(title="FinHealth", version=__version__, lifespan=lifespan)
    app.state.settings = configured
    app.state.engine = None
    app.state.session_factory = None
    app.state.resource_lock = RLock()
    app.state.model_registry = ModelRegistryState()
    app.state.sec_limiter = None
    if settings is not None:

        def app_settings() -> Settings:
            """Return explicit factory settings consistently for all dependency consumers."""
            return configured

        app.dependency_overrides[get_settings] = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestProtection)

    async def domain_error_handler(request: Request, error: Exception) -> JSONResponse:
        """Translate explicit domain errors into stable client-visible JSON contracts."""
        status = (
            404
            if isinstance(error, SecResourceNotFoundError)
            else 429
            if isinstance(error, SecRateLimitError)
            else 502
            if isinstance(error, SecIngestionError)
            else 422
        )
        return JSONResponse(
            status_code=status, content={"detail": str(error), "error_type": type(error).__name__}
        )

    async def database_error_handler(request: Request, error: Exception) -> JSONResponse:
        """Report database failures without leaking SQL parameters or connection credentials."""
        return JSONResponse(
            status_code=503,
            content={"detail": "Database operation failed", "error_type": "DatabaseError"},
        )

    for exception_type in (
        SecResourceNotFoundError,
        SecRateLimitError,
        SecIngestionError,
        EtlProcessingError,
        ModelPipelineError,
    ):
        app.add_exception_handler(exception_type, domain_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    routers = (
        health.router, companies.router, models.router, dashboard.router, reports.router,
        ingestion.router, accounts.router, admin.router, workspace.router,
    )
    for router in routers:
        app.include_router(router, prefix="/api/v1")
    spa_dist = configured.frontend_dir / "dist"
    app.mount(
        "/assets",
        DashboardStaticFiles(directory=spa_dist / "assets", check_dir=False),
        name="spa-assets",
    )
    app.mount(
        "/static",
        DashboardStaticFiles(directory=configured.frontend_dir, check_dir=False),
        name="static",
    )
    app.mount(
        "/api/v1/figures",
        DashboardStaticFiles(directory=configured.data_dir / "artifacts/figures", check_dir=False),
        name="figures",
    )

    def _resolve_index_html() -> FileResponse:
        """Serve the built React SPA index when present, falling back to frontend_dir/index.html."""
        built_index = spa_dist / "index.html"
        raw_index = configured.frontend_dir / "index.html"
        target = built_index if built_index.is_file() else raw_index
        if not target.is_file():
            raise HTTPException(
                503, "Frontend files missing. Restore the configured frontend directory."
            )
        return FileResponse(
            target,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/", response_class=FileResponse, include_in_schema=False)
    def dashboard_index() -> FileResponse:
        """Serve the local dashboard through the same origin as the financial API."""
        return _resolve_index_html()

    @app.get("/app/{full_path:path}", response_class=FileResponse, include_in_schema=False)
    @app.get("/app", response_class=FileResponse, include_in_schema=False)
    @app.get("/screener", response_class=FileResponse, include_in_schema=False)
    @app.get("/companies/{full_path:path}", response_class=FileResponse, include_in_schema=False)
    @app.get("/compare", response_class=FileResponse, include_in_schema=False)
    @app.get("/clusters", response_class=FileResponse, include_in_schema=False)
    @app.get("/stress", response_class=FileResponse, include_in_schema=False)
    @app.get("/models", response_class=FileResponse, include_in_schema=False)
    @app.get("/workspace", response_class=FileResponse, include_in_schema=False)
    @app.get("/account", response_class=FileResponse, include_in_schema=False)
    @app.get("/admin", response_class=FileResponse, include_in_schema=False)
    def dashboard_spa_routes(full_path: str = "") -> FileResponse:
        """Serve the React SPA entry for client-side financial workspace routes."""
        _ = full_path
        return _resolve_index_html()

    return app


@lru_cache(maxsize=1)
def _default_app() -> FastAPI:
    """Create the default application when the ASGI server requests it."""
    return create_app()


def __getattr__(name: str) -> FastAPI:
    """Expose uvicorn's app entry point without instantiating settings during import."""
    if name == "app":
        return _default_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
