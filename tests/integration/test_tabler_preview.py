"""Restored original interface assets and static confinement, independent of financial services."""

from collections.abc import Iterator
from pathlib import Path
from re import findall

import pytest
from fastapi.testclient import TestClient

from finhealth.api.main import create_app
from finhealth.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def preview_client(tmp_path: Path) -> Iterator[TestClient]:
    """Serve the actual production bundle without database or model initialization."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL="sqlite://",
        frontend_dir=ROOT / "frontend/legacy",
        data_dir=tmp_path,
        ingestion_worker_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.mark.parametrize("route", ("/", "/static/index.html"))
def test_original_dashboard_restored(preview_client: TestClient, route: str) -> None:
    """Serve the exact pre-migration dashboard and its original navigation controls."""
    response = preview_client.get(route)
    assert response.status_code == 200
    assert response.content == (ROOT / "frontend/legacy/index.html").read_bytes()
    assert 'id="panel-screener"' in response.text
    assert '/static/vendor/tabler/' in response.text
    assert '/static/js/app.js' in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]


@pytest.mark.parametrize("route", (
    "/static/account.html", "/static/preview/index.html", "/static/preview/account.html",
))
def test_original_account_and_preview(preview_client: TestClient, route: str) -> None:
    """Keep account and preview documents available with all self-hosted dependencies."""
    response = preview_client.get(route)
    assert response.status_code == 200
    assert 'type="module"' in response.text
    assets = findall(r'(?:src|href)="(/static/[^\"]+\.(?:js|css))"', response.text)
    assert assets
    for asset in assets:
        assert preview_client.get(asset).status_code == 200


def test_production_assets_are_local_and_resolvable(preview_client: TestClient) -> None:
    """Check exact bundled resources and Windows-safe executable MIME types."""
    html = preview_client.get("/").text
    assets = findall(r'(?:src|href)="(/static/[^\"]+)"', html)
    assert any(asset.endswith('.js') for asset in assets)
    assert any(asset.endswith('.css') for asset in assets)
    for asset in assets:
        response = preview_client.get(asset)
        assert response.status_code == 200
        path = ROOT / "frontend/legacy" / asset.removeprefix("/static/")
        assert response.content == path.read_bytes()
        if asset.endswith(('.js', '.css')):
            expected = 'javascript' if asset.endswith('.js') else 'text/css'
            assert expected in response.headers['content-type']
            assert 'no-cache' in response.headers['cache-control']


@pytest.mark.parametrize("route", (
    "/api/v1/no-such-route", "/static/assets/missing.js", "/static/src/main.tsx",
    "/screener", "/company/AAPL", "/static/../.env", "/static/%2e%2e/.env",
    "/unknown-route", "/docs/missing.js", "/openapi.json/missing",
    "/api/v1/figures/no-such-figure.png",
))
def test_spa_does_not_swallow_missing_resources(preview_client: TestClient, route: str) -> None:
    """APIs, source code, secrets, unknown routes and missing assets must remain 404."""
    response = preview_client.get(route)
    assert response.status_code == 404
    assert 'id="root"' not in response.text


def test_openapi_docs_are_not_spa(preview_client: TestClient) -> None:
    """Keep FastAPI documentation and schema reachable independently of the SPA."""
    assert preview_client.get('/docs').status_code == 200
    schema = preview_client.get('/openapi.json').json()
    assert '/api/v1/companies' in schema['paths']


def test_missing_build_is_actionable(tmp_path: Path) -> None:
    """An unbuilt checkout explains the build requirement rather than leaking source."""
    settings = Settings(_env_file=None, frontend_dir=tmp_path, DATABASE_URL='sqlite://')
    with TestClient(create_app(settings)) as client:
        response = client.get('/')
        assert response.status_code == 503
        assert 'Restore the configured frontend' in response.json()['detail']
