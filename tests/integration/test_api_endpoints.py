"""Real API/SQLite/ETL/ML integration with only external SEC HTTP replaced by fixtures."""

import json
import math
from collections.abc import AsyncGenerator, Generator, Iterator
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from finhealth.api.dependencies import ModelRegistryState, get_db, get_sec_edgar_client
from finhealth.api.main import create_app
from finhealth.api.schemas import ModelEvaluationResponseSchema, PredictionDetailSchema
from finhealth.core.config import Settings
from finhealth.db.base import Base
from finhealth.db.lineage_models import ForecastEvidence
from finhealth.db.models import Company, FinancialMetric, FinancialStatement, ModelPrediction
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.financial_ratios import compute_altman_z_score
from finhealth.ingestion.rate_limiter import AsyncRateLimiter
from finhealth.ingestion.sec_client import SecEdgarClient
from finhealth.ml.registry import ModelArtifactBundle, save_bundle
from tests.account_helpers import sign_in
from tests.unit.test_ml_pipeline import bundle as bundle
from tests.unit.test_ml_pipeline import panel as panel

ApiContext = tuple[TestClient, Engine, FastAPI, list[str]]

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_analyze_rejects_financial_sic_before_companyfacts(context: ApiContext) -> None:
    """Use the real SEC cache boundary and verify the structured endpoint rejection."""
    client, engine, app, calls = context
    settings = app.state.settings
    path = settings.raw_sec_path / "submissions/CIK0000320193.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads((FIXTURES / "sec_submissions_0000320193_sample.json").read_text())
    payload["sic"] = "6021"
    path.write_text(json.dumps(payload), encoding="utf-8")
    rejected = client.post("/api/v1/companies/320193/analyze")
    assert rejected.status_code == 422
    assert rejected.json()["error_type"] == "EtlProcessingError"
    assert "specialized regulatory capital" in rejected.json()["detail"]
    assert not any("companyfacts" in call for call in calls)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Company)) == 0


@pytest.fixture
def context(
    tmp_path: Path, bundle: ModelArtifactBundle
) -> Iterator[tuple[TestClient, Engine, FastAPI, list[str]]]:
    """Create real app dependencies with isolated SQL, models, and fixture transport."""
    settings = Settings(
        _env_file=None,
        app_env="test",
        sec_user_agent="FinHealthTests/1.0 (tests@example.com)",
        sec_rate_limit_per_sec=10,
        data_dir=tmp_path,
        raw_sec_dir=tmp_path / "raw",
        model_artifacts_dir=tmp_path / "models",
    )
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    app = create_app(settings)
    app.state.model_registry = ModelRegistryState()
    app.state.model_registry.set(bundle)
    calls: list[str] = []

    def database() -> Generator[Session, None, None]:
        """Inject actual request-scoped SQLAlchemy sessions, never repository mocks."""
        with factory() as session:
            try:
                yield session
            except BaseException:
                session.rollback()
                raise

    def handler(request: httpx.Request) -> httpx.Response:
        """Serve the actual three curated SEC contract fixtures at their real URL paths."""
        calls.append(request.url.path)
        assert request.headers["User-Agent"] == settings.sec_user_agent
        filenames = {
            "/files/company_tickers.json": "sec_company_tickers_sample.json",
            "/submissions/CIK0000320193.json": "sec_submissions_0000320193_sample.json",
            "/api/xbrl/companyfacts/CIK0000320193.json": "sec_companyfacts_0000320193_sample.json",
        }
        if request.url.path not in filenames:
            return httpx.Response(404)
        return httpx.Response(
            200, json=json.loads((FIXTURES / filenames[request.url.path]).read_text())
        )

    limiter = AsyncRateLimiter(10)

    async def sec_client() -> AsyncGenerator[SecEdgarClient, None]:
        """Replace HTTP transport only while keeping the real client/cache/parser behavior."""
        async with SecEdgarClient(
            settings, httpx.MockTransport(handler), rate_limiter=limiter
        ) as client:
            yield client

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_sec_edgar_client] = sec_client
    try:
        with TestClient(app) as client:
            sign_in(client, engine)
            yield client, engine, app, calls
    finally:
        engine.dispose()


def test_health_endpoint_reports_db_and_model_status(context: ApiContext) -> None:
    """Read live SQLite connectivity and the actual activated model version."""
    client, _, app, _ = context
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "test",
        "database_connected": True,
        "active_model_version": app.state.model_registry.get().model_version,
    }


def test_analyze_company_end_to_end_by_ticker_and_cik(context: ApiContext) -> None:
    """Resolve, ingest, calculate, infer, commit, and re-read exact annual Apple records."""
    client, engine, _, calls = context
    response = client.post("/api/v1/companies/AAPL/analyze")
    assert response.status_code == 200, response.text
    result = response.json()
    assert (result["company"]["cik"], result["company"]["ticker"], result["company"]["sector"]) == (
        "0000320193",
        "AAPL",
        "Manufacturing",
    )
    assert [row["fiscal_year"] for row in result["history"]] == [2022, 2023]
    annual = result["history"][-1]
    assert annual["roa"] == pytest.approx(96995000000 / 352583000000)
    assert annual["debt_ratio"] == pytest.approx(290437000000 / 352583000000)
    assert annual["roa_yoy_delta"] == pytest.approx(
        96995000000 / 352583000000 - 99803000000 / 352755000000
    )
    assert annual["altman_z_score"] == pytest.approx(
        compute_altman_z_score(
            {
                **annual,
                "current_assets": 143566000000,
                "current_liabilities": 145308000000,
                "retained_earnings": -214000000,
            }
        )["altman_z_score"]
    )
    forecast = result["latest_prediction"]
    assert forecast["target_fiscal_year"] == 2024
    assert forecast["target_fiscal_period"] == "FY"
    assert all(
        math.isfinite(forecast[f"pred_{column}"])
        for column in ("roa", "roe", "eps", "debt_ratio", "ocf_ratio")
    )
    assert 0 <= forecast["distress_probability"] <= 1
    assert forecast["top_drivers"]
    assert forecast["output_space"] in {"log_odds", "probability"}
    assert forecast["contributions"]
    assert len(calls) == 3
    repeated = client.post("/api/v1/companies/320193/analyze")
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == result
    assert len(calls) == 3  # Actual disk cache serves the second request.
    with Session(engine) as session:
        [evidence] = session.scalars(select(ForecastEvidence)).all()
        assert evidence.input_status == "verified_inputs"
        assert evidence.fitted_inputs == forecast["feature_values"]
        assert evidence.reported_inputs is not None
        assert evidence.reported_inputs["roa"] == annual["roa"]
        assert session.scalar(select(func.count()).select_from(Company)) == 1
        assert session.scalar(select(func.count()).select_from(FinancialStatement)) == 3
        assert session.scalar(select(func.count()).select_from(FinancialMetric)) == 3
        assert session.scalar(select(func.count()).select_from(ModelPrediction)) == 1


def test_get_company_and_list_companies_after_ingestion(context: ApiContext) -> None:
    """Query durable history and keep screener and cluster snapshots on the annual origin."""
    client, _, _, calls = context
    analyzed = client.post("/api/v1/companies/AAPL/analyze").json()
    fetched = client.get("/api/v1/companies/0000320193")
    assert fetched.status_code == 200
    assert fetched.json() == analyzed
    summaries = client.get("/api/v1/companies").json()
    assert len(summaries) == 1
    assert summaries[0]["latest_fiscal_year"] == 2023
    assert summaries[0]["accession_number"] == analyzed["history"][-1]["accession_number"]
    assert summaries[0]["roa"] == pytest.approx(96995000000 / 352583000000)
    points = client.get("/api/v1/clusters/map").json()
    assert len(points) == 1
    assert points[0]["pca_comp_1"] == analyzed["history"][-1]["pca_comp_1"]
    assert points[0]["cluster_id"] == analyzed["company"]["cluster_id"]
    assert (
        points[0]["distress_probability"] == analyzed["latest_prediction"]["distress_probability"]
    )
    quarterly = client.get("/api/v1/companies/aapl?form_type=10-Q").json()
    assert len(quarterly["history"]) == 1
    assert quarterly["history"][0]["roa"] == pytest.approx(33916000000 / 353514000000)
    assert quarterly["latest_prediction"] is None
    assert len(calls) == 3
    assert client.get("/api/v1/companies?limit=0").status_code == 422
    assert client.get("/api/v1/companies/aapl?form_type=8-K").status_code == 422


def test_get_unknown_company_returns_404(context: ApiContext) -> None:
    """Missing persisted identity has a structured domain error and performs no SEC traffic."""
    client, _, _, calls = context
    response = client.get("/api/v1/companies/INVALID_TICKER_999")
    assert response.status_code == 404
    assert response.json()["error_type"] == "SecResourceNotFoundError"
    assert "Company not found" in response.json()["detail"]
    assert calls == []


def test_model_evaluation_endpoint_returns_benchmark_metrics(context: ApiContext) -> None:
    """Expose the actual bundle's complete fitted evaluation report, then verify unloaded state."""
    client, _, app, _ = context
    response = client.get("/api/v1/models/evaluation")
    assert response.status_code == 200
    report = response.json()["evaluation_report"]
    assert set(report) >= {
        "clustering",
        "forecasting",
        "classification_xgboost",
        "classification_baselines",
        "global_shap_importance",
    }
    assert set(report["classification_baselines"]) == {"logistic_regression", "altman_z_baseline"}
    app.state.model_registry.set(None)
    assert client.get("/api/v1/models/evaluation").status_code == 404
    health = client.get("/api/v1/health").json()
    assert health["active_model_version"] is None
    response = client.post("/api/v1/companies/320193/analyze")
    assert response.status_code == 200
    assert response.json()["latest_prediction"] is None


def test_api_training_uses_persisted_panel_and_activates_saved_bundle(
    context: ApiContext, panel: pd.DataFrame
) -> None:
    """Train through the endpoint using real stored companies, statements, and metrics."""
    client, engine, app, _ = context
    assert (
        client.post(
            "/api/v1/models/train", json={"train_end_year": 2021, "model_version": "empty"}
        ).status_code
        == 422
    )
    with Session(engine) as session:
        for identifier, rows in panel.groupby("company_id"):
            company = Company(
                cik=str(int(identifier) + 1).zfill(10), name=f"Synthetic {identifier}"
            )
            session.add(company)
            session.flush()
            for row in rows.to_dict("records"):
                statement = FinancialStatement(
                    company_id=company.id,
                    accession_number=f"test-{row['fiscal_year']}",
                    form_type="10-K",
                    fiscal_year=row["fiscal_year"],
                    fiscal_period="FY",
                    period_end_date=row["period_end_date"],
                    filed_date=row["period_end_date"],
                )
                session.add(statement)
                session.flush()
                available = {
                    key: value
                    for key, value in row.items()
                    if key in FinancialMetric.__table__.columns
                    and key not in {"id", "company_id", "statement_id"}
                }
                session.add(
                    FinancialMetric(company_id=company.id, statement_id=statement.id, **available)
                )
        session.commit()
    response = client.post(
        "/api/v1/models/train", json={"train_end_year": 2021, "model_version": "api-v2"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["model_version"] == "api-v2"
    assert app.state.model_registry.get().model_version == "api-v2"
    assert (app.state.settings.model_artifacts_dir / "api-v2" / "metadata.json").is_file()
    assert client.get("/api/v1/models/evaluation").json() == response.json()
    # Duplicate versions fail before activation; the existing model remains active.
    assert (
        client.post(
            "/api/v1/models/train", json={"train_end_year": 2021, "model_version": "api-v2"}
        ).status_code
        == 422
    )
    smote_res = client.post(
        "/api/v1/models/train",
        json={
            "train_end_year": 2021,
            "model_version": "api-v2-smote",
            "imbalance_strategy": "smote",
        },
    )
    assert smote_res.status_code == 200, smote_res.text
    assert smote_res.json()["evaluation_report"]["imbalance_strategy"] == "smote"
    versions = {
        item["model_version"]: item for item in client.get("/api/v1/models/versions").json()
    }
    assert versions["api-v2"]["imbalance_strategy"] == "class_weight"
    assert versions["api-v2-smote"]["imbalance_strategy"] == "smote"
    assert versions["api-v2-smote"]["is_active"] is True


def test_schema_nonfinite_sanitization_and_registry_autoload(
    bundle: ModelArtifactBundle, tmp_path: Path
) -> None:
    """Sanitize nested SHAP/evaluation numbers and load real artifacts into fresh registry state."""
    prediction = PredictionDetailSchema(
        model_version="v1",
        target_fiscal_year=2024,
        target_fiscal_period="FY",
        pred_roa=float("nan"),
        base_value=float("inf"),
        contributions={"roa": float("-inf")},
        top_drivers=[
            {
                "feature": "roa",
                "feature_value": float("nan"),
                "shap_value": float("inf"),
                "direction": "INCREASES_RISK",
            }
        ],
    )
    json.dumps(prediction.model_dump(), allow_nan=False)
    assert prediction.pred_roa is prediction.base_value is prediction.contributions["roa"] is None
    evaluation = ModelEvaluationResponseSchema(
        model_version="v1", created_at="test", evaluation_report={"nested": [np.inf, np.nan]}
    )
    assert evaluation.evaluation_report == {"nested": [None, None]}
    save_bundle(bundle, tmp_path)
    state = ModelRegistryState()
    state.initialize(tmp_path)
    assert state.get().model_version == bundle.model_version


def test_sec_failures_are_structured_and_do_not_commit(context: ApiContext) -> None:
    """Only the HTTP boundary fails; actual exception handling and DB cleanup remain active."""
    client, engine, app, _ = context
    for status, expected in ((403, 429), (404, 404), (503, 502)):

        async def failed_sec(status: int = status) -> AsyncGenerator[SecEdgarClient, None]:
            """Inject an actual SEC client whose HTTP transport returns a failure status."""

            def handler(request: httpx.Request) -> httpx.Response:
                """Represent the unavailable external SEC service."""
                return httpx.Response(status)

            async with SecEdgarClient(
                app.state.settings, httpx.MockTransport(handler), max_retries=0
            ) as sec:
                yield sec

        # Bind a no-argument dependency so defaults cannot become request query parameters.
        async def dependency() -> AsyncGenerator[SecEdgarClient, None]:
            """Yield the selected external failure transport without altering the service."""
            async for sec in failed_sec():
                yield sec

        app.dependency_overrides[get_sec_edgar_client] = dependency
        response = client.post("/api/v1/companies/320193/analyze")
        assert response.status_code == expected
        assert "error_type" in response.json()
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(Company)) == 0


def test_analysis_transaction_rolls_back_database_failure(context: ApiContext) -> None:
    """An actual SQLite trigger rejects metric insertion and proves the entire batch rolls back."""
    client, engine, _, _ = context
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER reject_metric BEFORE INSERT ON financial_metrics "
            "BEGIN SELECT RAISE(ABORT, 'metric rejected'); END"
        )
    response = client.post("/api/v1/companies/320193/analyze")
    assert response.status_code == 503
    with Session(engine) as session:
        for model in (Company, FinancialStatement, FinancialMetric, ModelPrediction):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("endpoint", ("predict-manual", "predict-batch"))
def test_prediction_requires_verified_session_and_csrf(context: ApiContext, endpoint: str) -> None:
    """Deny guests and revoked sessions, and permit a normal verified user with CSRF."""
    client, engine, _, _ = context
    payload = {"company_name": "Test", "fiscal_year": 2024, "is_manufacturing": True,
               "total_assets": 1000, "total_liabilities": 500}
    body = {"items": [payload]} if endpoint == "predict-batch" else payload
    path = f"/api/v1/models/{endpoint}"
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    assert client.post(path, json=body).status_code == 401
    assert client.get("/api/v1/companies").status_code == 200
    sign_in(client, engine, email="normal@example.com", role="user")
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post(path, json=body).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.post(path, json=body).status_code == 401


def test_predict_manual_and_batch_portfolio_endpoints(context: ApiContext) -> None:
    """Verify manual prediction with 4-pillar health & batch portfolio scoring."""
    client, _, _, _ = context
    hpg_payload = {
        "company_name": "VN:HPG",
        "fiscal_year": 2025,
        "is_manufacturing": True,
        "total_assets": 257899200817547,
        "current_assets": 112450000000000,
        "total_liabilities": 126679189940972,
        "current_liabilities": 94186268324508,
        "stockholders_equity": 131220010876575,
        "retained_earnings": 48650000000000,
        "revenues": 156116094618482,
        "operating_income": 18420000000000,
        "net_income": 15514931571606,
        "operating_cash_flow": 17365859056591,
        "prior_total_assets": 224489707553981,
        "prior_current_assets": 96500000000000,
        "prior_total_liabilities": 109842249570282,
        "prior_current_liabilities": 75225243262689,
        "prior_stockholders_equity": 114647457983699,
        "prior_revenues": 138855112131387,
        "prior_operating_income": 14500000000000,
        "prior_net_income": 12020023621271,
        "prior_operating_cash_flow": 6608320655215,
    }
    manual_res = client.post("/api/v1/models/predict-manual", json=hpg_payload)
    assert manual_res.status_code == 200, manual_res.text
    manual_data = manual_res.json()
    assert manual_data["health_pillars"]["overall_score"] is not None
    assert manual_data["dupont"]["roe_dupont_avg"] is not None
    assert manual_data["accounting_checklist"]["observed_checks"] == 8
    assert len(manual_data["recommendations"]) >= 1

    distressed_payload = {
        "company_name": "Distressed Corp",
        "fiscal_year": 2025,
        "is_manufacturing": True,
        "total_assets": 1000.0,
        "current_assets": 200.0,
        "total_liabilities": 950.0,
        "current_liabilities": 600.0,
        "stockholders_equity": 50.0,
        "retained_earnings": -300.0,
        "revenues": 400.0,
        "operating_income": -120.0,
        "net_income": -150.0,
        "operating_cash_flow": -90.0,
    }
    batch_res = client.post(
        "/api/v1/models/predict-batch",
        json={"items": [hpg_payload, distressed_payload]},
    )
    assert batch_res.status_code == 200, batch_res.text
    batch_data = batch_res.json()
    assert batch_data["total_companies"] == 2
    assert sum(batch_data["risk_counts"].values()) == 2
    assert len(batch_data["results"]) == 2
    assert batch_data["results"][0]["company_name"] == "VN:HPG"
    assert batch_data["results"][1]["company_name"] == "Distressed Corp"


def test_private_saved_analysis_recomputes_and_enforces_ownership(context: ApiContext) -> None:
    """Persist a real model output, reject injected output and deny cross-account access."""
    client, engine, _, _ = context
    payload = {
        "company_name": "Scenario fixture",
        "fiscal_year": 2025,
        "is_manufacturing": True,
        "total_assets": 1000.0,
        "total_liabilities": 400.0,
        "stockholders_equity": 600.0,
        "revenues": 800.0,
        "net_income": 60.0,
        "operating_cash_flow": 80.0,
    }
    predicted = client.post("/api/v1/models/predict-manual", json=payload)
    assert predicted.status_code == 200
    request = {"name": "Saved scenario", "inputs": payload}
    assert client.post("/api/v1/me/analyses", json={**request, "outputs": {}}).status_code == 422
    saved = client.post("/api/v1/me/analyses", json=request)
    assert saved.status_code == 201
    item_id = saved.json()["id"]
    detail = client.get(f"/api/v1/me/analyses/{item_id}").json()
    assert detail["outputs"] == predicted.json()
    assert detail["inputs"]["total_assets"] == payload["total_assets"]
    sign_in(client, engine, "other@example.com", "user")
    assert client.get("/api/v1/me/analyses").json() == []
    assert client.get(f"/api/v1/me/analyses/{item_id}").status_code == 404
    assert client.delete(f"/api/v1/me/analyses/{item_id}").status_code == 404
