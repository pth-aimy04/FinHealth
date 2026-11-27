"""Wave 4 regression tests for handoff restore, config CSV, scoring, invalidation, and PDF."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.main import create_app
from finhealth.api.routers.reporting_v2 import _build_sec_assessment_view
from finhealth.core.config import Settings
from finhealth.db.account_models import Organization, OrganizationMember, User, UserSession
from finhealth.db.base import Base
from finhealth.db.batch_models import OrgBatchJob
from finhealth.db.handoff import copy_financial_tables, migrate
from finhealth.db.models import Company, FinancialStatement
from finhealth.db.session import create_db_engine
from finhealth.etl.driver_narrative import translate_drivers_to_business
from finhealth.ml.confidence import assess_confidence
from finhealth.reporting.batch_worker import recover_stale_batch_jobs
from finhealth.reporting.pdf_generator import generate_company_assessment_pdf


def _seed_authenticated_client(tmp_path: Path) -> tuple[TestClient, int, dict[str, str]]:
    """Build an isolated TestClient with a verified org_admin session and real model artifacts."""
    db_path = tmp_path / "wave4_test.sqlite3"
    settings = Settings(
        _env_file=None,
        app_env="test",
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
        model_artifacts_dir=Path("data/artifacts/models"),
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as db:
        import secrets
        from datetime import datetime, timedelta, timezone

        from finhealth.api.security import digest, hash_password

        user = User(
            email="wave4.tester@finhealth.local",
            display_name="Wave 4 Tester",
            password_hash=hash_password("StrongPass!2026"),
            role="user",
            active=True,
            email_verified=True,
        )
        db.add(user)
        db.flush()
        org = Organization(name="Wave 4 Org", slug="wave-4-org", is_personal=True)
        db.add(org)
        db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="org_admin"))

        raw_session = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)

        db.add(
            UserSession(
                user_id=user.id,
                active_org_id=org.id,
                token_hash=digest(raw_session),
                csrf_hash=digest(csrf_token),
                credential_stamp=user.password_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
            )
        )
        db.commit()
        org_id = org.id

    engine.dispose()
    app = create_app(settings=settings)
    client = TestClient(app)
    client.cookies.set("finhealth_session", raw_session)
    client.cookies.set("finhealth_csrf", csrf_token)
    headers = {"X-CSRF-Token": csrf_token}
    return client, org_id, headers


def test_handoff_restore_succeeds_against_real_seed_snapshot(tmp_path: Path) -> None:
    """Verify handoff restore intersects columns cleanly on the real checked-in SQLite seed."""
    seed_path = Path("data/seed/financial.sqlite3")
    if not seed_path.is_file():
        pytest.skip("Seed snapshot data/seed/financial.sqlite3 not present")

    target_db = tmp_path / "restored.sqlite3"
    source_engine = create_db_engine(f"sqlite:///{seed_path.resolve().as_posix()}")
    target_engine = create_db_engine(f"sqlite:///{target_db.resolve().as_posix()}")
    try:
        migrate(target_engine)
        counts = copy_financial_tables(source_engine, target_engine)
        assert counts["companies"] == 98
        assert counts["financial_statements"] > 0
        assert counts["financial_metrics"] > 0
    finally:
        source_engine.dispose()
        target_engine.dispose()


def test_cors_allowed_origins_accepts_csv_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CORS_ALLOWED_ORIGINS parses comma-separated strings without pydantic JSON error."""
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:8000")
    settings = Settings(_env_file=None)
    assert settings.cors_allowed_origins == ["http://localhost:3000", "http://127.0.0.1:8000"]


def test_driver_narrative_blocks_imputed_medians_and_adverse_strengths() -> None:
    """Never fabricate missing features from fitted_inputs or put adverse ratios into Strengths."""
    shap_payload = {
        "output_space": "log_odds",
        "base_value": -4.0,
        "model_name": "xgboost",
        "contributions": {
            "gross_margin": -0.60,
            "receivables_to_revenue": -0.50,
            "roa": -0.40,
            "debt_ratio": 0.70,
        },
        "fitted_inputs": {
            "gross_margin": 0.348,
            "receivables_to_revenue": 0.537,
            "roa": 0.12,
            "debt_ratio": 0.85,
        },
    }
    record = {
        "gross_margin": None,  # Unobserved — must NOT appear in strengths!
        "receivables_to_revenue": 0.537,  # Economically adverse (>25%) — must NOT be a Strength!
        "roa": 0.12,  # Healthy — valid Strength
        "debt_ratio": 0.85,  # High debt — valid Bottleneck
        "is_negative_equity": 0.0,
    }
    res = translate_drivers_to_business(shap_payload, record)
    strength_codes = {item["factor_code"] for item in res["strengths"]}
    bottleneck_codes = {item["factor_code"] for item in res["bottlenecks"]}

    assert "gross_margin" not in strength_codes
    assert "receivables_to_revenue" not in strength_codes
    assert "roa" in strength_codes
    assert "debt_ratio" in bottleneck_codes
    assert res["total_impact_share_pct"] == pytest.approx(100.0, abs=0.1)


def test_confidence_reasons_translate_ood_features_to_vietnamese() -> None:
    """User-facing confidence reasons_vi must not leak raw snake_case feature names."""
    bounds = {
        "opex_to_revenue": [0.37, 2.0],
        "debt_ratio": [0.05, 0.95],
        "current_ratio": [0.3, 10.0],
    }
    raw = {
        "opex_to_revenue": 0.10,
        "debt_ratio": 1.40,
        "current_ratio": 0.10,
    }
    conf = assess_confidence(raw, feature_ood_bounds=bounds)
    assert conf.is_ood is True
    joined = " ".join(conf.reasons_vi)
    assert "opex_to_revenue" not in joined
    assert "debt_ratio" not in joined
    assert "Tổng chi phí hoạt động / Doanh thu" in joined


def test_org_samples_opex_alignment_and_cache_invalidation(tmp_path: Path) -> None:
    """Verify Kaggle-aligned opex_to_revenue (zero OOD), 100% completeness, and cache expiry."""
    client, _org_id, headers = _seed_authenticated_client(tmp_path)
    with client:
        seed_resp = client.post("/api/v1/org/samples/seed", headers=headers)
        assert seed_resp.status_code == 200
        companies = seed_resp.json()["companies"]
        assert len(companies) == 3

        # Run analysis for all 3 samples
        for comp in companies:
            ana_resp = client.get(f"/api/v1/org/companies/{comp['id']}/analysis")
            assert ana_resp.status_code == 200
            body = ana_resp.json()
            conf = body["summary"]["confidence"]
            assert conf["input_completeness"] == pytest.approx(1.0, abs=1e-4)
            assert "opex_to_revenue" not in conf["ood_features"]

        # Verify list_org_companies now includes latest_health_score & latest_risk_tier
        list_resp = client.get("/api/v1/org/companies")
        assert list_resp.status_code == 200
        listed = list_resp.json()
        assert all(item["latest_health_score"] is not None for item in listed)
        assert all(item["latest_risk_tier"] is not None for item in listed)

        # Verify PATCH statement immediately invalidates cached OrgAssessment
        cid = companies[0]["id"]
        before = client.get(f"/api/v1/org/companies/{cid}/analysis").json()
        stmts = client.get(f"/api/v1/org/companies/{cid}/statements").json()
        latest_stmt = stmts[0]

        # Degrade the latest statement severely (high liabilities, deep net loss, negative OCF)
        patch_resp = client.patch(
            f"/api/v1/org/companies/{cid}/statements/{latest_stmt['id']}",
            headers=headers,
            json={
                "unit_scale": 1_000_000,
                "total_assets": 400_000,
                "current_assets": 150_000,
                "total_liabilities": 460_000,
                "current_liabilities": 390_000,
                "stockholders_equity": -60_000,
                "retained_earnings": -180_000,
                "revenues": 220_000,
                "cost_of_goods_sold": 230_000,
                "gross_profit": -10_000,
                "operating_expenses": 30_000,
                "operating_income": -40_000,
                "net_income": -85_000,
                "operating_cash_flow": -65_000,
                "status": "finalized",
            },
        )
        assert patch_resp.status_code == 200
        after = client.get(f"/api/v1/org/companies/{cid}/analysis").json()
        assert after["summary"]["health_score"] < before["summary"]["health_score"]

        # Verify switching business_type to financial_institution invalidates cache immediately
        fi_resp = client.patch(
            f"/api/v1/org/companies/{cid}",
            headers=headers,
            json={"business_type": "financial_institution"},
        )
        assert fi_resp.status_code == 200
        fi_analysis = client.get(f"/api/v1/org/companies/{cid}/analysis").json()
        assert fi_analysis["summary"]["scoring_eligible"] is False
        assert fi_analysis["summary"]["health_score"] is None


def test_sec_assessment_multi_period_and_pdf_localization(tmp_path: Path) -> None:
    """SEC assessment must run multi_period with >=2 annual statements and localize PDF labels."""
    db_path = tmp_path / "sec_test.sqlite3"
    engine = create_db_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    registry = ModelRegistryState()
    registry.initialize(Path("data/artifacts/models"))

    with factory() as db:
        comp = Company(
            cik="0000320193",
            ticker="AAPL",
            name="Apple Inc.",
            sic_code="3571",
            sector="Manufacturing",
        )
        db.add(comp)
        db.flush()
        for yr, rev, ni in ((2023, 383_285e6, 96_995e6), (2024, 391_035e6, 93_736e6)):
            db.add(
                FinancialStatement(
                    company_id=comp.id,
                    accession_number=f"0000320193-{yr}-000001",
                    form_type="10-K",
                    fiscal_year=yr,
                    fiscal_period="FY",
                    filed_date=date(yr, 11, 1),
                    period_end_date=date(yr, 9, 30),
                    total_assets=364_980e6,
                    current_assets=152_987e6,
                    cash_and_equivalents=29_943e6,
                    accounts_receivable=33_410e6,
                    inventory=7_286e6,
                    total_liabilities=308_030e6,
                    current_liabilities=176_392e6,
                    long_term_debt=85_750e6,
                    stockholders_equity=56_950e6,
                    retained_earnings=-19_154e6,
                    revenues=rev,
                    operating_income=123_216e6,
                    interest_expense=3_933e6,
                    net_income=ni,
                    operating_cash_flow=118_254e6,
                    capex=9_447e6,
                )
            )
        db.commit()

        view = _build_sec_assessment_view(db, company=comp, model_registry=registry)
        assert view.summary.scoring_eligible is True
        assert view.summary.scoring_mode == "multi_period"
        # Unobserved gross_margin / opex_to_revenue must not be fabricated as strengths/bottlenecks
        driver_codes = {
            item.factor_code for item in [*view.drivers.strengths, *view.drivers.bottlenecks]
        }
        assert "gross_margin" not in driver_codes
        assert "opex_to_revenue" not in driver_codes

        pdf_bytes = generate_company_assessment_pdf(view, assessment_ref="SEC-AAPL-FY2024")
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 10_000

    engine.dispose()


def test_recover_stale_batch_jobs(tmp_path: Path) -> None:
    """Interrupted 'running' jobs must be reset to 'queued' and returned by recovery helper."""
    db_path = tmp_path / "batch_recover.sqlite3"
    engine = create_db_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    with factory() as db:
        org = Organization(name="Batch Org", slug="batch-org", is_personal=True)
        db.add(org)
        db.flush()
        j1 = OrgBatchJob(
            organization_id=org.id, filename="a.xlsx", status="running", total_rows=10
        )
        j2 = OrgBatchJob(
            organization_id=org.id, filename="b.xlsx", status="queued", total_rows=5
        )
        j3 = OrgBatchJob(
            organization_id=org.id, filename="c.xlsx", status="completed", total_rows=3
        )
        db.add_all([j1, j2, j3])
        db.commit()

        pending_ids = recover_stale_batch_jobs(db)
        assert pending_ids == [j1.id, j2.id]
        refreshed = db.scalar(select(OrgBatchJob).where(OrgBatchJob.id == j1.id))
        assert refreshed is not None and refreshed.status == "queued"

    engine.dispose()
