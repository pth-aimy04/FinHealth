"""Portable static-file responses for browser ES modules and optional figure directories."""

from pathlib import Path

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class DashboardStaticFiles(StaticFiles):
    """Keep JavaScript media types stable across Windows registry configurations."""

    async def check_config(self) -> None:
        """Allow absent optional assets to return ordinary per-file 404 responses."""
        if self.directory is not None and Path(self.directory).exists():
            await super().check_config()

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Retain Starlette path confinement, conditional requests and file streaming."""
        response = await super().get_response(path, scope)
        if path.endswith(".js") and response.status_code == 200:
            response.headers["content-type"] = "text/javascript; charset=utf-8"
        if path.endswith((".js", ".css")) and response.status_code in (200, 304):
            response.headers["cache-control"] = "no-cache"
        return response
