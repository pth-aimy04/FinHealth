"""Dashboard, assets and real SQLite integration. Requires the local audited SEC artifacts."""

import hashlib
import json
import math
import shutil
import struct
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from finhealth.api import main
from finhealth.api.dependencies import ModelRegistryState
from finhealth.core.config import Settings
from finhealth.db.base import Base
from finhealth.db.session import create_db_engine
from finhealth.ml.registry import load_bundle
from tests.account_helpers import sign_in

ROOT = Path(__file__).resolve().parents[2]
FIGURES = (
    "01_correlation_heatmap.png",
    "02_pca_scree_and_clusters.png",
    "03_roc_pr_curves_comparison.png",
    "04_confusion_matrices.png",
    "05_forecasting_actual_vs_predicted.png",
    "06_shap_global_importance.png",
    "07_reliability_calibration.png",
)


@pytest.fixture(scope="module")
def dashboard(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    """Read audited SQLite artifacts independently of mutable local SQL Server settings."""
    database = ROOT / "data/processed/parquet/finhealth.sqlite3"
    if not database.is_file():
        pytest.skip("The Stage 8 local SQLite snapshot is required")
    copy = tmp_path_factory.mktemp("dashboard") / "snapshot.sqlite3"
    shutil.copy2(database, copy)
    database = copy
    engine = create_db_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(engine)
    engine.dispose()
    app = main.create_app(
        Settings(
            _env_file=None,
            DATABASE_URL=f"sqlite:///{database.as_posix()}",
            ingestion_worker_enabled=False,
        )
    )
    app.state.model_registry = ModelRegistryState()
    with TestClient(app) as client:
        yield client


def test_dashboard_index_and_lazy_asgi_entry(dashboard: TestClient) -> None:
    """Serve the four workspaces and the ES module using the documented ASGI entry point."""
    response = dashboard.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.content == (ROOT / "frontend/legacy/index.html").read_bytes()
    assert 'id="panel-screener"' in response.text
    assert '/static/vendor/tabler/' in response.text
    assert '/static/js/app.js' in response.text
    assert isinstance(main.app, FastAPI)
    assert main.app is main.app


def test_dashboard_static_assets(dashboard: TestClient) -> None:
    """Serve bundled production assets with stable JavaScript MIME types."""
    from re import findall

    assets = findall(r'(?:src|href)="(/static/[^"]+\.(?:js|css))"',
                     dashboard.get("/").text)
    assert assets
    for asset in assets:
        response = dashboard.get(asset)
        assert response.status_code == 200
        path = ROOT / "frontend/legacy" / asset.removeprefix("/static/")
        assert response.content == path.read_bytes()
        expected = "text/css" if asset.endswith(".css") else "javascript"
        assert expected in response.headers["content-type"]


@pytest.mark.parametrize("filename", FIGURES)
def test_publication_figures(dashboard: TestClient, filename: str) -> None:
    """Serve the genuine publication PNG at its original dimensions and resolution."""
    path = ROOT / "data/artifacts/figures" / filename
    response = dashboard.get(f"/api/v1/figures/{filename}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == path.read_bytes()
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", response.content[16:24])
    assert width >= 1000 and height >= 1000
    physical = response.content.index(b"pHYs")
    x_resolution, y_resolution, units = struct.unpack(
        ">IIB", response.content[physical + 4 : physical + 13]
    )
    assert units == 1
    assert x_resolution * 0.0254 == pytest.approx(300, abs=0.1)
    assert y_resolution * 0.0254 == pytest.approx(300, abs=0.1)


def test_default_real_universe_and_evaluation(dashboard: TestClient) -> None:
    """Read the complete audited universe and exact bundle report through default settings."""
    companies = dashboard.get("/api/v1/companies")
    points = dashboard.get("/api/v1/clusters/map")
    assert companies.status_code == points.status_code == 200
    assert len(companies.json()) == len(points.json()) == 98
    assert {row["cik"] for row in companies.json()} == {row["cik"] for row in points.json()}
    assert dashboard.get("/api/v1/dashboard/overview").json() == {
        "company_count": 98,
        "annual_statement_count": 1506,
    }
    saved = json.loads((ROOT / "data/artifacts/models/v1.2.0/evaluation_report.json").read_text())
    response = dashboard.get("/api/v1/models/evaluation")
    assert response.status_code == 200
    assert response.json()["model_version"] == "v1.2.0"
    assert response.json()["evaluation_report"] == saved
    health = dashboard.get("/api/v1/health")
    assert health.status_code == 200 and health.json()["database_connected"]
    assert health.json()["active_model_version"] == "v1.2.0"


@pytest.mark.parametrize("ticker", ("AAPL", "AAL"))
def test_company_features_explanations_and_altman(dashboard: TestClient, ticker: str) -> None:
    """Expose every model input, reconcile real SHAP, and retain audited Altman components."""
    response = dashboard.get(f"/api/v1/companies/{ticker}")
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["ticker"] == ticker
    assert len(body["history"]) >= 10
    latest = body["history"][-1]
    assert latest["accession_number"] and latest["filed_date"]
    prediction = body["latest_prediction"]
    assert prediction["model_version"] == "v1.2.0"
    assert prediction["target_fiscal_year"] == latest["fiscal_year"] + 1
    assert len(prediction["feature_values"]) == len(prediction["contributions"]) == 17
    assert set(prediction["feature_values"]) == set(prediction["contributions"])
    assert all(math.isfinite(value) for value in prediction["feature_values"].values())
    reconstructed = prediction["base_value"] + sum(prediction["contributions"].values())
    if prediction.get("output_space") == "probability":
        assert abs(prediction["raw_probability"] - reconstructed) < 1e-5
    else:
        assert abs(prediction["raw_margin"] - reconstructed) < 1e-5
        assert prediction["raw_probability"] == pytest.approx(1 / (1 + math.exp(-reconstructed)))
    components = body["altman_components"]
    weights = (1.2, 1.4, 3.3, 0.6, 1.0) if ticker == "AAPL" else (6.56, 3.26, 6.72, 1.05)
    score = sum(components[f"X{index}"] * weight for index, weight in enumerate(weights, 1))
    assert abs(score - latest["altman_z_score"]) < 1e-12


def test_static_roots_are_configurable_and_confined(tmp_path: Path) -> None:
    """Keep source files and database contents outside the static route namespace."""
    public = tmp_path / "public"
    public.mkdir()
    (public / "index.html").write_text("<html>Isolated dashboard</html>")
    (tmp_path / "private.txt").write_text("private")
    app = main.create_app(Settings(_env_file=None, frontend_dir=public, data_dir=tmp_path))
    app.state.model_registry = ModelRegistryState()
    with TestClient(app) as client:
        assert client.get("/").text == "<html>Isolated dashboard</html>"
        assert client.get("/static/%2e%2e/private.txt").status_code == 404
        assert client.get("/api/v1/figures/%2e%2e/models/v1.0.0/models.joblib").status_code == 404
        assert client.get("/static/.env").status_code == 404


def test_aapl_simulation_preserves_accounts_and_database(dashboard: TestClient) -> None:
    """Exercise live inference on the saved bundle and compare the before/after SQLite bytes."""
    path = ROOT / "data/processed/parquet/finhealth.sqlite3"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    url = "/api/v1/companies/AAPL/simulate"
    neutral = dashboard.post(url, json={})
    assert neutral.status_code == 200, neutral.text
    assert neutral.json()["probability_delta"] == 0
    assert neutral.json()["baseline"] == neutral.json()["stressed"]
    response = dashboard.post(
        url,
        json={
            "revenue_shock_pct": -0.15,
            "operating_margin_delta_pct": -0.05,
            "debt_change_pct": 0.20,
            "ocf_shock_pct": -0.25,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    original, stressed = result["baseline"]["metrics"], result["stressed"]["metrics"]
    assert stressed["revenues"] == pytest.approx(original["revenues"] * 0.85)
    assert stressed["operating_margin"] == pytest.approx(original["operating_margin"] - 0.05)
    assert stressed["total_liabilities"] == pytest.approx(original["total_liabilities"] * 1.2)
    assert stressed["operating_cash_flow"] == pytest.approx(original["operating_cash_flow"] * 0.75)
    assert stressed["total_assets"] - stressed["total_liabilities"] - stressed[
        "stockholders_equity"
    ] == pytest.approx(
        original["total_assets"] - original["total_liabilities"] - original["stockholders_equity"],
        abs=1e-3,
    )
    assert stressed["net_income"] - original["net_income"] == pytest.approx(
        0.75 * (stressed["operating_income"] - original["operating_income"])
    )
    baseline, scenario = result["baseline"]["prediction"], result["stressed"]["prediction"]
    assert result["probability_delta"] == pytest.approx(
        scenario["distress_probability"] - baseline["distress_probability"]
    )
    for driver in result["top_shifted_shap_drivers"]:
        feature = driver["feature"]
        assert driver["delta"] == pytest.approx(
            scenario["contributions"][feature] - baseline["contributions"][feature]
        )
    assert dashboard.post(url, json={"revenue_shock_pct": -0.51}).status_code == 422
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize(("ticker", "cohort"), [("AAPL", "sector"), ("OXY", "sector")])
def test_peer_ratios_match_latest_annual_snapshots(
    dashboard: TestClient, ticker: str, cohort: str
) -> None:
    """Independently compute percentiles and missing-denominator counts from SQLite."""
    import sqlite3
    from statistics import median

    response = dashboard.get(f"/api/v1/companies/{ticker}")
    assert response.status_code == 200
    body = response.json()
    context = body["sector_peer_context"]
    assert context["cohort"] == cohort
    path = ROOT / "data/processed/parquet/finhealth.sqlite3"
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT c.sector, m.* FROM companies c JOIN financial_metrics m ON c.id=m.company_id "
            "JOIN financial_statements s ON m.statement_id=s.id WHERE s.form_type='10-K' "
            "AND s.fiscal_year=(SELECT MAX(t.fiscal_year) FROM financial_statements t "
            "WHERE t.company_id=c.id AND t.form_type='10-K')"
        ).fetchall()
    peers = [row for row in rows if cohort == "universe" or row["sector"] == context["sector"]]
    assert context["cohort_size"] == len(peers)
    latest = body["history"][-1]
    for metric, stat in context["metrics"].items():
        observations = [row[metric] for row in peers if row[metric] is not None]
        assert stat["n_observed"] == len(observations)
        if observations:
            assert stat["median"] == median(observations)
        else:
            assert stat["median"] is None
        value = latest[metric]
        if value is None:
            assert stat["percentile"] is None
        else:
            rank = sum(1 if peer < value else 0.5 if peer == value else 0 for peer in observations)
            assert stat["percentile"] == pytest.approx(100 * rank / len(observations))


def test_dashboard_leaves_audited_model_unchanged() -> None:
    """Verify the published artifact still satisfies its original integrity contract."""
    folder = ROOT / "data/artifacts/models/v1.0.0"
    metadata = json.loads((folder / "metadata.json").read_text())
    assert hashlib.sha256((folder / "models.joblib").read_bytes()).hexdigest() == metadata["sha256"]
    assert load_bundle(folder).model_version == "v1.0.0"


def test_production_analyze_requires_admin_session(tmp_path: Path) -> None:
    """Legacy bearer secrets cannot bypass the verified administrator session boundary."""
    settings = Settings(
        _env_file=None,
        app_env="production",
        public_base_url="https://testserver",
        DATABASE_URL=f"sqlite:///{tmp_path / 'production.sqlite3'}",
        data_dir=tmp_path,
        ingestion_worker_enabled=False,
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = main.create_app(settings)
    try:
        with TestClient(app, base_url="https://testserver") as client:
            assert client.post("/api/v1/companies/AAPL/analyze").status_code == 401
            assert (
                client.post(
                    "/api/v1/companies/AAPL/analyze",
                    headers={
                        "Authorization": "Bearer legacy-test-admin-token-0123456789",
                    },
                ).status_code
                == 401
            )
            sign_in(client, engine)
            assert client.post("/api/v1/ingestion/AAPL").status_code == 503
            app.state.settings.ingestion_worker_enabled = True
            assert client.post("/api/v1/companies/AAPL/analyze").status_code == 409
    finally:
        engine.dispose()


def test_manual_prediction_computes_ratios_altman_and_treeshap(dashboard: TestClient) -> None:
    """Manual financial input must score statelessly with exact ratios and TreeSHAP additivity."""
    engine = create_db_engine(dashboard.app.state.settings.database_url)
    try:
        sign_in(dashboard, engine, email="dashboard-user@example.com", role="user")
    finally:
        engine.dispose()
    aapl = dashboard.get("/api/v1/companies/AAPL").json()
    latest = aapl["history"][-1]
    prior = aapl["history"][-2]
    payload = {
        "company_name": "Manual AAPL Verification",
        "fiscal_year": latest["fiscal_year"],
        "is_manufacturing": True,
        "total_assets": latest["total_assets"],
        "current_assets": latest["current_assets"],
        "total_liabilities": latest["total_liabilities"],
        "current_liabilities": latest["current_liabilities"],
        "stockholders_equity": latest["stockholders_equity"],
        "retained_earnings": latest["retained_earnings"],
        "revenues": latest["revenues"],
        "operating_income": latest["operating_income"],
        "net_income": latest["net_income"],
        "operating_cash_flow": latest["operating_cash_flow"],
        "cash_and_equivalents": latest["cash_and_equivalents"],
        "capex": latest["capex"],
        "eps_diluted": latest["eps"],
        "prior_total_assets": prior["total_assets"],
        "prior_total_liabilities": prior["total_liabilities"],
        "prior_stockholders_equity": prior["stockholders_equity"],
        "prior_net_income": prior["net_income"],
        "prior_operating_cash_flow": prior["operating_cash_flow"],
    }
    response = dashboard.post("/api/v1/models/predict-manual", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "Manual AAPL Verification"
    assert body["ratios"]["roa"] == pytest.approx(latest["roa"], rel=1e-6)
    assert body["ratios"]["debt_ratio"] == pytest.approx(latest["debt_ratio"], rel=1e-6)
    assert body["altman_z_score"] == pytest.approx(latest["altman_z_score"], rel=1e-6)
    pred = body["prediction"]
    assert pred["model_version"] == aapl["latest_prediction"]["model_version"]
    assert pred["output_space"] == "probability"
    assert pred["distress_probability"] == pytest.approx(
        aapl["latest_prediction"]["distress_probability"], abs=1e-4
    )
    shap_sum = pred["base_value"] + sum(pred["contributions"].values())
    assert shap_sum == pytest.approx(pred["raw_probability"], abs=1e-6)

    invalid = dashboard.post(
        "/api/v1/models/predict-manual",
        json={"total_assets": 0, "total_liabilities": 100},
    )
    assert invalid.status_code == 422


def test_kaggle_model_evaluation_and_manual_prediction(dashboard: TestClient) -> None:
    """Verify Kaggle bankruptcy bundle discovery, evaluation, manual scoring, and path safety."""
    engine = create_db_engine(dashboard.app.state.settings.database_url)
    try:
        sign_in(dashboard, engine, email="dashboard-user@example.com", role="user")
    finally:
        engine.dispose()
    versions = dashboard.get("/api/v1/models/versions").json()
    by_version = {item["model_version"]: item for item in versions}
    assert "v1.2.0" in by_version and by_version["v1.2.0"]["is_active"] is True
    assert "kaggle-v1.2.0" in by_version
    assert by_version["kaggle-v1.2.0"]["dataset"] == "kaggle"
    assert by_version["kaggle-v1.2.0"]["selected_model_name"] == "xgboost"

    kaggle_eval = dashboard.get("/api/v1/models/evaluation?model_version=kaggle-v1.2.0")
    assert kaggle_eval.status_code == 200
    report = kaggle_eval.json()["evaluation_report"]
    assert report["selected_model_name"] == "xgboost"
    assert report["classification_selected"]["roc_auc"] == pytest.approx(0.8075, abs=1e-3)

    aapl = dashboard.get("/api/v1/companies/AAPL").json()
    latest = aapl["history"][-1]
    scored = dashboard.post(
        "/api/v1/models/predict-manual",
        json={
            "model_version": "kaggle-v1.2.0",
            "company_name": "Kaggle Bankruptcy Check",
            "fiscal_year": latest["fiscal_year"],
            "is_manufacturing": True,
            "total_assets": latest["total_assets"],
            "current_assets": latest["current_assets"],
            "total_liabilities": latest["total_liabilities"],
            "current_liabilities": latest["current_liabilities"],
            "stockholders_equity": latest["stockholders_equity"],
            "retained_earnings": latest["retained_earnings"],
            "revenues": latest["revenues"],
            "operating_income": latest["operating_income"],
            "net_income": latest["net_income"],
            "operating_cash_flow": latest["operating_cash_flow"],
        },
    )
    assert scored.status_code == 200
    assert scored.json()["classification_threshold"] == pytest.approx(
        report["classification_selected"]["threshold"], abs=1e-6
    )
    pred = scored.json()["prediction"]
    assert pred["model_version"] == "kaggle-v1.2.0"
    assert 0.0 <= pred["distress_probability"] <= 1.0
    assert pred["output_space"] == "log_odds"
    shap_sum = pred["base_value"] + sum(pred["contributions"].values())
    assert shap_sum == pytest.approx(pred["raw_margin"], abs=1e-5)

    traversal = dashboard.get("/api/v1/models/evaluation?model_version=../v1.2.0")
    assert traversal.status_code == 422
