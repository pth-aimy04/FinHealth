"""Phase 3 tests: isolated ModelRegistryState, CompositeBenchmark cache, and dynamic CORS."""

from dataclasses import replace
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.main import create_app
from finhealth.api.services import (
    _BENCHMARK_CACHE,
    FinancialAnalysisService,
    invalidate_benchmark_cache,
)
from finhealth.core.config import Settings
from finhealth.db.base import Base
from finhealth.db.lineage import backfill_legacy_evidence
from finhealth.db.models import Company, FinancialMetric, FinancialStatement
from finhealth.db.session import create_db_engine
from finhealth.etl.corporate_finance import CompositeBenchmark
from finhealth.ingestion.sec_client import atomic_write_json
from finhealth.ml.registry import ModelArtifactBundle, save_bundle
from tests.unit.test_ml_pipeline import bundle as bundle
from tests.unit.test_ml_pipeline import panel as panel


def _publish_bundle(model_dir: Path, source: ModelArtifactBundle, version: str) -> None:
    """Persist a real bundle with an explicit version and latest.json pointer."""
    variant = replace(source, model_version=version)
    save_bundle(variant, model_dir)
    atomic_write_json(
        model_dir / "latest.json",
        {
            "model_version": version,
            "bundle_dir": version,
            "created_at": variant.created_at,
            "mode": "test",
        },
    )


def _seed_company(
    session: Session,
    *,
    cik: str,
    ticker: str,
    sector: str,
    roa: float,
    ocf_ratio: float,
    current_ratio: float,
    debt_ratio: float,
    fiscal_year: int = 2024,
) -> Company:
    """Insert a real industrial company with one annual statement and composite metrics."""
    company = Company(cik=cik, ticker=ticker, name=f"{ticker} Corp", sic_code="3571", sector=sector)
    session.add(company)
    session.flush()
    statement = FinancialStatement(
        company_id=company.id,
        accession_number=f"{cik}-{fiscal_year}-10K",
        form_type="10-K",
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        period_end_date=date(fiscal_year, 12, 31),
        filed_date=date(fiscal_year + 1, 2, 15),
        total_assets=1_000.0,
        total_liabilities=debt_ratio * 1_000.0,
        stockholders_equity=(1.0 - debt_ratio) * 1_000.0,
        revenues=800.0,
        net_income=roa * 1_000.0,
        operating_cash_flow=ocf_ratio * 1_000.0,
    )
    session.add(statement)
    session.flush()
    metric = FinancialMetric(
        company_id=company.id,
        statement_id=statement.id,
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        roa=roa,
        ocf_ratio=ocf_ratio,
        current_ratio=current_ratio,
        debt_ratio=debt_ratio,
    )
    session.add(metric)
    session.commit()
    return company


def test_model_registry_isolated_per_app_instance(
    tmp_path: Path, bundle: ModelArtifactBundle
) -> None:
    """Two create_app() instances with distinct model dirs must load isolated registries."""
    dir_a = tmp_path / "models_a"
    dir_b = tmp_path / "models_b"
    _publish_bundle(dir_a, bundle, "iso-a-v1")
    _publish_bundle(dir_b, bundle, "iso-b-v2")

    settings_a = Settings(
        _env_file=None,
        app_env="test",
        data_dir=tmp_path / "data_a",
        model_artifacts_dir=dir_a,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'a.sqlite3').as_posix()}",
    )
    settings_b = Settings(
        _env_file=None,
        app_env="test",
        data_dir=tmp_path / "data_b",
        model_artifacts_dir=dir_b,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'b.sqlite3').as_posix()}",
    )

    app_a = create_app(settings_a)
    app_b = create_app(settings_b)
    assert app_a.state.model_registry is not app_b.state.model_registry

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        resp_a = client_a.get("/api/v1/models/evaluation")
        resp_b = client_b.get("/api/v1/models/evaluation")
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        assert resp_a.json()["model_version"] == "iso-a-v1"
        assert resp_b.json()["model_version"] == "iso-b-v2"

    # Also verify a single ModelRegistryState reloads when initialized with a different directory.
    reusable = ModelRegistryState()
    reusable.initialize(dir_a)
    loaded_a = reusable.get()
    assert loaded_a is not None and loaded_a.model_version == "iso-a-v1"
    reusable.initialize(dir_b)
    loaded_b = reusable.get()
    assert loaded_b is not None and loaded_b.model_version == "iso-b-v2"


def test_composite_benchmark_cache_reuse_and_invalidation(tmp_path: Path) -> None:
    """Verify repeated reads reuse CompositeBenchmark and writes invalidate it cleanly."""
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'bench.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    service = FinancialAnalysisService()
    invalidate_benchmark_cache(engine)

    with Session(engine) as session:
        _seed_company(
            session,
            cik="0000000001",
            ticker="AAA",
            sector="Technology",
            roa=0.20,
            ocf_ratio=0.25,
            current_ratio=2.5,
            debt_ratio=0.20,
        )
        _seed_company(
            session,
            cik="0000000002",
            ticker="BBB",
            sector="Technology",
            roa=0.05,
            ocf_ratio=0.08,
            current_ratio=1.2,
            debt_ratio=0.60,
        )

        hits_before = _BENCHMARK_CACHE.hits
        misses_before = _BENCHMARK_CACHE.misses
        first = service.list_company_summaries(session)
        assert _BENCHMARK_CACHE.misses == misses_before + 1
        assert _BENCHMARK_CACHE.hits == hits_before
        assert len(first) == 2
        first_scores = {row.ticker: row.composite_health_score for row in first}

        # Subsequent summary list and full analysis reuse the cached benchmark without recomputing.
        second = service.list_company_summaries(session)
        assert _BENCHMARK_CACHE.hits == hits_before + 1
        assert _BENCHMARK_CACHE.misses == misses_before + 1
        assert [row.composite_health_score for row in second] == [
            row.composite_health_score for row in first
        ]

        detail = service.get_company_full_analysis(session, "AAA")
        assert _BENCHMARK_CACHE.hits == hits_before + 2
        assert detail.company.composite_health_score == first_scores["AAA"]

        # Add a third company and trigger write invalidation (via backfill_legacy_evidence).
        _seed_company(
            session,
            cik="0000000003",
            ticker="CCC",
            sector="Technology",
            roa=0.35,
            ocf_ratio=0.40,
            current_ratio=4.0,
            debt_ratio=0.10,
        )
        invalidations_before = _BENCHMARK_CACHE.invalidations
        backfill_legacy_evidence(session)
        session.commit()
        assert _BENCHMARK_CACHE.invalidations == invalidations_before + 1

        recomputed = service.list_company_summaries(session)
        assert _BENCHMARK_CACHE.misses == misses_before + 2
        assert len(recomputed) == 3
        recomputed_scores = {row.ticker: row.composite_health_score for row in recomputed}
        # Adding a stronger peer shifts AAA's empirical midrank down from 75.0 to 50.0.
        assert recomputed_scores["AAA"] != first_scores["AAA"]
        assert recomputed_scores["CCC"] is not None
        assert recomputed_scores["AAA"] is not None
        assert recomputed_scores["CCC"] > recomputed_scores["AAA"]

        # Direct computation matches the cached benchmark identically.
        direct = CompositeBenchmark.from_rows(service._annual_metrics(session))
        peers, cached_bench = service._benchmark_and_peers(session)
        assert len(peers) == 3
        assert cached_bench == direct

    engine.dispose()


def test_dynamic_cors_allowed_origins(tmp_path: Path) -> None:
    """Allowed origin receives CORS header; disallowed origin does not."""
    settings = Settings(
        _env_file=None,
        app_env="production",
        public_base_url="https://testserver",
        data_dir=tmp_path,
        cors_allowed_origins=["https://allowed.finhealth.local"],
        DATABASE_URL=f"sqlite:///{tmp_path / 'cors.sqlite3'}",
    )
    settings.parquet_path.mkdir(parents=True, exist_ok=True)
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(settings)
    with TestClient(app) as client:
        allowed_preflight = client.options(
            "/api/v1/companies",
            headers={
                "Origin": "https://allowed.finhealth.local",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed_preflight.status_code == 200
        assert (
            allowed_preflight.headers.get("access-control-allow-origin")
            == "https://allowed.finhealth.local"
        )

        allowed_get = client.get(
            "/api/v1/companies",
            headers={"Origin": "https://allowed.finhealth.local"},
        )
        assert allowed_get.status_code == 200
        assert (
            allowed_get.headers.get("access-control-allow-origin")
            == "https://allowed.finhealth.local"
        )

        disallowed_get = client.get(
            "/api/v1/companies",
            headers={"Origin": "https://evil.example.com"},
        )
        assert disallowed_get.status_code == 200
        assert "access-control-allow-origin" not in disallowed_get.headers

    # Settings defaults and comma-separated string parsing.
    default_settings = Settings(_env_file=None)
    assert default_settings.cors_allowed_origins == ["http://localhost:3000"]
    csv_settings = Settings(
        _env_file=None,
        cors_allowed_origins="https://one.example.com, https://two.example.com",  # type: ignore[arg-type]
    )
    assert csv_settings.cors_allowed_origins == [
        "https://one.example.com",
        "https://two.example.com",
    ]
