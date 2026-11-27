"""Integration tests for org risk analytics, M11 history, S01 peers, and C03 compare."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.main import create_app
from finhealth.api.routers import org_analytics
from finhealth.api.schemas.analytics import LEGAL_DISCLAIMER_VI
from finhealth.core.config import Settings
from finhealth.db.account_models import Organization, OrganizationMember
from finhealth.db.base import Base
from finhealth.db.models import Company, FinancialMetric, FinancialStatement
from finhealth.db.org_models import OrgAssessment, OrgCompany, OrgFinancialStatement
from finhealth.db.session import create_db_engine
from tests.account_helpers import sign_in


def _add_statement(
    db: Session,
    *,
    org_id: int,
    company_id: int,
    fiscal_year: int,
    accounting_standard: str,
    revenues: float,
    net_income: float,
    ocf: float,
    total_assets: float = 1000.0,
    total_liabilities: float = 450.0,
    current_assets: float = 480.0,
    current_liabilities: float = 220.0,
    equity: float = 550.0,
    retained_earnings: float = 200.0,
    operating_income: float = 130.0,
    interest_expense: float = 15.0,
    audit_status: str = "audited_unqualified",
    status: str = "finalized",
) -> OrgFinancialStatement:
    """Insert a balanced organization financial statement for integration testing."""
    stmt = OrgFinancialStatement(
        organization_id=org_id,
        org_company_id=company_id,
        fiscal_year=fiscal_year,
        fiscal_period="FY",
        period_end_date=date(fiscal_year, 12, 31),
        accounting_standard=accounting_standard,
        currency="VND",
        unit_scale=1_000_000,
        display_unit="MILLION_VND",
        audit_status=audit_status,
        status=status,
        source_channel="web_form",
        total_assets=total_assets,
        current_assets=current_assets,
        cash_and_equivalents=140.0,
        accounts_receivable=110.0,
        inventory=120.0,
        total_liabilities=total_liabilities,
        current_liabilities=current_liabilities,
        short_term_debt=100.0,
        long_term_debt=150.0,
        stockholders_equity=equity,
        retained_earnings=retained_earnings,
        revenues=revenues,
        cost_of_goods_sold=revenues * 0.65,
        gross_profit=revenues * 0.35,
        operating_expenses=revenues * 0.15,
        operating_income=operating_income,
        depreciation_amortization=35.0,
        ebitda=operating_income + 35.0,
        interest_expense=interest_expense,
        net_income=net_income,
        operating_cash_flow=ocf,
        capex=25.0,
    )
    db.add(stmt)
    db.flush()
    return stmt


def _seed_sec_manufacturing_peers(db: Session, count: int = 6) -> None:
    """Seed SEC Manufacturing peer snapshots so S01 resolves benchmark_scope='sector'."""
    for idx in range(count):
        comp = Company(
            cik=f"000900000{idx}",
            ticker=f"MFG{idx}",
            name=f"Peer Manufacturer {idx}",
            sic_code="3571",
            sector="Manufacturing",
        )
        db.add(comp)
        db.flush()
        stmt = FinancialStatement(
            company_id=comp.id,
            accession_number=f"000900000{idx}-24-000001",
            form_type="10-K",
            fiscal_year=2024,
            fiscal_period="FY",
            period_end_date=date(2024, 12, 31),
            filed_date=date(2025, 2, 15),
            total_assets=1000.0,
            total_liabilities=500.0,
            stockholders_equity=500.0,
            revenues=800.0,
            net_income=60.0 + idx * 10.0,
            operating_cash_flow=80.0 + idx * 10.0,
        )
        db.add(stmt)
        db.flush()
        metric = FinancialMetric(
            statement_id=stmt.id,
            company_id=comp.id,
            fiscal_year=2024,
            fiscal_period="FY",
            roa=0.04 + idx * 0.02,
            roe=0.08 + idx * 0.03,
            debt_ratio=0.40 + idx * 0.05,
            current_ratio=1.20 + idx * 0.25,
            operating_margin=0.06 + idx * 0.02,
            ocf_ratio=0.10 + idx * 0.04,
            cash_ratio=0.20 + idx * 0.05,
            interest_coverage=3.0 + idx * 1.5,
            fcf_to_liabilities=0.05 + idx * 0.02,
            working_capital_ratio=0.10 + idx * 0.03,
            retained_earnings_ratio=0.12 + idx * 0.04,
            asset_turnover=0.60 + idx * 0.10,
        )
        db.add(metric)
    db.flush()


@pytest.fixture
def org_env() -> Iterator[dict[str, Any]]:
    """Create an isolated SQLite DB and mount org_analytics.router without modifying main.py."""
    with TemporaryDirectory(prefix="finhealth-org-analytics-") as tmp_dir:
        db_file = Path(tmp_dir) / "org_analytics.sqlite3"
        url = f"sqlite:///{db_file.as_posix()}"
        engine = create_db_engine(url)
        try:
            Base.metadata.create_all(engine)

            app = create_app(Settings(_env_file=None, DATABASE_URL=url, app_env="test"))
            app.state.model_registry = ModelRegistryState()
            app.include_router(org_analytics.router)

            with TestClient(app) as client:
                analyst_id = sign_in(client, engine, email="analyst@org-a.vn", role="user")
                with Session(engine) as db:
                    org_a = Organization(
                        name="Org A Capital", slug="org-a-capital", is_personal=False
                    )
                    org_b = Organization(
                        name="Org B Holdings", slug="org-b-holdings", is_personal=False
                    )
                    db.add_all([org_a, org_b])
                    db.flush()

                    db.add(
                        OrganizationMember(
                            organization_id=org_a.id,
                            user_id=analyst_id,
                            role="analyst",
                        )
                    )
                    _seed_sec_manufacturing_peers(db, count=6)

                    # 5 companies in Org A (4 normal + 1 financial institution) and 1 in Org B
                    c1 = OrgCompany(
                        organization_id=org_a.id,
                        name="Công ty CP Sản xuất Minh An",
                        tax_code="0101234561",
                        sector_code="C28",
                        sector_name="Sản xuất máy móc",
                        business_type="manufacturing",
                        listing_status="unlisted",
                        relationship_tag="customer",
                    )
                    c2 = OrgCompany(
                        organization_id=org_a.id,
                        name="Công ty TNHH Thương mại Hoàng Long",
                        tax_code="0101234562",
                        sector_code="G46",
                        sector_name="Thương mại bán buôn",
                        business_type="trade_service",
                        listing_status="unlisted",
                        relationship_tag="supplier",
                    )
                    c3 = OrgCompany(
                        organization_id=org_a.id,
                        name="Công ty CP Xây lắp Đại Phát",
                        tax_code="0101234563",
                        sector_code="F41",
                        sector_name="Xây dựng",
                        business_type="trade_service",
                        listing_status="unlisted",
                        relationship_tag="competitor",
                    )
                    c4 = OrgCompany(
                        organization_id=org_a.id,
                        name="Công ty CP Cơ khí Việt Phát",
                        tax_code="0101234564",
                        sector_code="C25",
                        sector_name="Sản xuất kim loại",
                        business_type="manufacturing",
                        listing_status="unlisted",
                        relationship_tag="portfolio",
                    )
                    c5 = OrgCompany(
                        organization_id=org_a.id,
                        name="Ngân hàng TMCP Mẫu",
                        tax_code="0101234565",
                        sector_code="K64",
                        sector_name="Ngân hàng",
                        business_type="financial_institution",
                        listing_status="listed",
                        relationship_tag="other",
                    )
                    c_other_org = OrgCompany(
                        organization_id=org_b.id,
                        name="Công ty Riêng Tổ Chức B",
                        tax_code="0309999999",
                        sector_code="C10",
                        sector_name="Sản xuất thực phẩm",
                        business_type="manufacturing",
                        listing_status="unlisted",
                        relationship_tag="own_company",
                    )
                    db.add_all([c1, c2, c3, c4, c5, c_other_org])
                    db.flush()

                    # 4 consecutive years for c1 bridging TT200_2014 (2022-2024) -> TT99_2025
                    for yr, std, rev, ni, ocf in (
                        (2022, "TT200_2014", 820.0, 68.0, 82.0),
                        (2023, "TT200_2014", 890.0, 76.0, 94.0),
                        (2024, "TT200_2014", 960.0, 88.0, 108.0),
                        (2025, "TT99_2025", 1040.0, 102.0, 122.0),
                    ):
                        _add_statement(
                            db,
                            org_id=org_a.id,
                            company_id=c1.id,
                            fiscal_year=yr,
                            accounting_standard=std,
                            revenues=rev,
                            net_income=ni,
                            ocf=ocf,
                        )

                    # c2: 2 years with negative OCF streak to exercise CashFlowOverlay
                    _add_statement(
                        db,
                        org_id=org_a.id,
                        company_id=c2.id,
                        fiscal_year=2024,
                        accounting_standard="TT200_2014",
                        revenues=700.0,
                        net_income=25.0,
                        ocf=-35.0,
                    )
                    _add_statement(
                        db,
                        org_id=org_a.id,
                        company_id=c2.id,
                        fiscal_year=2025,
                        accounting_standard="TT99_2025",
                        revenues=740.0,
                        net_income=20.0,
                        ocf=-45.0,
                    )

                    # c3, c4, c5, c_other_org: finalized statements in 2024 & 2025
                    for comp, org_id in (
                        (c3, org_a.id),
                        (c4, org_a.id),
                        (c5, org_a.id),
                        (c_other_org, org_b.id),
                    ):
                        _add_statement(
                            db,
                            org_id=org_id,
                            company_id=comp.id,
                            fiscal_year=2024,
                            accounting_standard="TT200_2014",
                            revenues=600.0,
                            net_income=40.0,
                            ocf=55.0,
                        )
                        _add_statement(
                            db,
                            org_id=org_id,
                            company_id=comp.id,
                            fiscal_year=2025,
                            accounting_standard="TT99_2025",
                            revenues=650.0,
                            net_income=45.0,
                            ocf=60.0,
                        )
                    db.commit()

                    env = {
                        "client": client,
                        "engine": engine,
                        "org_a_id": org_a.id,
                        "org_b_id": org_b.id,
                        "c1_id": c1.id,
                        "c2_id": c2.id,
                        "c3_id": c3.id,
                        "c4_id": c4.id,
                        "c5_fi_id": c5.id,
                        "c_other_org_id": c_other_org.id,
                    }
                yield env
        finally:
            engine.dispose()


def test_org_analysis_multi_period_tt200_to_tt99_and_peer_context(
    org_env: dict[str, Any],
) -> None:
    """Verify M11 4-year TT200->TT99 history, 5 pillars, S01 peers, drivers, and disclaimer."""
    client: TestClient = org_env["client"]
    engine: Engine = org_env["engine"]
    c1_id: int = org_env["c1_id"]

    res = client.get(f"/api/v1/org/companies/{c1_id}/analysis")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["legal_disclaimer_vi"] == LEGAL_DISCLAIMER_VI
    assert "88/2014" in body["summary"]["legal_disclaimer_vi"]
    assert body["summary"]["scoring_eligible"] is True
    assert body["summary"]["scoring_mode"] == "multi_period"
    assert 0.0 <= body["summary"]["health_score"] <= 100.0
    assert 0.0 <= body["summary"]["pd_12m"] <= 1.0
    assert body["summary"]["risk_tier"] in ("STRONG", "STABLE", "WATCH", "CRITICAL")
    assert 1 <= len(body["summary"]["top_3_takeaways_vi"]) <= 3

    # Altman Z' for unlisted manufacturing
    assert body["altman"]["applicable"] is True
    assert body["altman"]["variant"] == "Z'"
    assert body["altman"]["cutoff_low"] == 1.23
    assert body["altman"]["cutoff_high"] == 2.90
    assert body["altman"]["score"] is not None

    # 5 pillars & 20 contextual metrics
    assert len(body["pillars"]["pillars"]) == 5
    all_metrics = [m for p in body["pillars"]["pillars"] for m in p["metrics"]]
    assert len(all_metrics) == 20
    assert all(m["tooltip_vi"] and m["label_vi"] for m in all_metrics)

    # S01 sector peer context resolved against 6 SEC Manufacturing peers
    assert body["peer_context"]["benchmark_scope"] == "sector"
    assert body["peer_context"]["mapped_sector"] == "Manufacturing"
    assert body["peer_context"]["cohort_size"] == 6

    # M11 multi-period history seamlessly bridging TT200_2014 -> TT99_2025
    history = body["history"]
    assert len(history) == 4
    assert [pt["fiscal_year"] for pt in history] == [2022, 2023, 2024, 2025]
    assert [pt["accounting_standard"] for pt in history] == [
        "TT200_2014",
        "TT200_2014",
        "TT200_2014",
        "TT99_2025",
    ]
    for pt in history:
        assert pt["health_score"] is not None
        assert pt["pd_12m"] is not None
        assert pt["altman_z_score"] is not None

    # OrgAssessment rows persisted for all 4 periods
    with Session(engine) as db:
        saved = list(
            db.scalars(select(OrgAssessment).where(OrgAssessment.org_company_id == c1_id))
        )
        assert len(saved) == 4

    # Analyst can recompute
    recompute = client.post(f"/api/v1/org/companies/{c1_id}/recompute")
    assert recompute.status_code == 200, recompute.text


def test_financial_institution_exclusion_and_cash_flow_overlay(
    org_env: dict[str, Any],
) -> None:
    """Confirm FI blocking and 2-year negative OCF cash-flow overlay enforcement."""
    client: TestClient = org_env["client"]

    fi_res = client.get(f"/api/v1/org/companies/{org_env['c5_fi_id']}/analysis")
    assert fi_res.status_code == 200, fi_res.text
    fi_body = fi_res.json()
    assert fi_body["summary"]["scoring_eligible"] is False
    assert fi_body["summary"]["scoring_mode"] == "excluded"
    assert fi_body["summary"]["pd_12m"] is None
    assert fi_body["summary"]["health_score"] is None
    assert fi_body["altman"]["applicable"] is False
    assert fi_body["altman"]["score"] is None
    assert fi_body["legal_disclaimer_vi"] == LEGAL_DISCLAIMER_VI

    overlay_res = client.get(f"/api/v1/org/companies/{org_env['c2_id']}/analysis")
    assert overlay_res.status_code == 200, overlay_res.text
    overlay_body = overlay_res.json()
    assert overlay_body["summary"]["cash_flow_overlay"]["triggered"] is True
    assert "NEGATIVE_OCF_STREAK" in overlay_body["summary"]["cash_flow_overlay"]["flags"]
    assert overlay_body["summary"]["risk_tier"] in ("WATCH", "CRITICAL")


def test_org_compare_2_to_4_limits_and_cross_org_isolation(
    org_env: dict[str, Any],
) -> None:
    """Verify C03 compare accepts 2-4 org companies, rejects >4 (422), and rejects other org."""
    client: TestClient = org_env["client"]
    c1, c2, c3, c4, c5 = (
        org_env["c1_id"],
        org_env["c2_id"],
        org_env["c3_id"],
        org_env["c4_id"],
        org_env["c5_fi_id"],
    )
    other_org_id = org_env["c_other_org_id"]

    # Valid 3-company comparison
    res = client.get("/api/v1/org/companies/compare", params={"ids": f"{c1},{c2},{c3}"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["period_policy"] == "latest_finalized"
    assert [item["company"]["id"] for item in body["companies"]] == [c1, c2, c3]
    assert body["legal_disclaimer_vi"] == LEGAL_DISCLAIMER_VI
    assert "health_score" in body["cohort_medians"]
    assert str(c1) in body["historical_series"]

    # Common fiscal year comparison
    common = client.get(
        "/api/v1/org/companies/compare",
        params={"ids": f"{c1},{c2}", "common_fiscal_year": 2024},
    )
    assert common.status_code == 200, common.text
    common_body = common.json()
    assert common_body["period_policy"] == "common_fiscal_year"
    assert all(item["fiscal_year"] == 2024 for item in common_body["companies"])

    # >4 companies -> 422
    too_many = client.get(
        "/api/v1/org/companies/compare", params={"ids": f"{c1},{c2},{c3},{c4},{c5}"}
    )
    assert too_many.status_code == 422

    # <2 unique companies -> 422
    too_few = client.get("/api/v1/org/companies/compare", params={"ids": f"{c1},{c1}"})
    assert too_few.status_code == 422

    # Cross-org ID included in compare -> 404
    cross_compare = client.get(
        "/api/v1/org/companies/compare", params={"ids": f"{c1},{other_org_id}"}
    )
    assert cross_compare.status_code == 404

    # Direct analysis of another org's company -> 404
    cross_direct = client.get(f"/api/v1/org/companies/{other_org_id}/analysis")
    assert cross_direct.status_code == 404
