"""Integration tests for Batch Excel API (S03) and Executive PDF endpoints (M12)."""

from collections.abc import Iterator
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook  # type: ignore[import-untyped]
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from finhealth.api.main import create_app
from finhealth.api.routers import reporting_v2
from finhealth.core.config import Settings
from finhealth.db.account_models import Organization, OrganizationMember, UserSession
from finhealth.db.base import Base
from finhealth.db.models import Company, FinancialStatement
from finhealth.db.org_models import OrgCompany, OrgFinancialStatement
from finhealth.db.session import create_db_engine
from finhealth.reporting.batch_excel import BATCH_COLUMNS, BATCH_DATA_SHEET
from tests.account_helpers import sign_in


def _build_batch_xlsx(rows: list[dict[str, Any]]) -> bytes:
    """Create a valid .xlsx upload payload for batch API tests."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = BATCH_DATA_SHEET
    headers = [c[0] for c in BATCH_COLUMNS]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(c) for c in headers])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _provision_org_membership(
    engine: Engine,
    *,
    user_id: int,
    org_id: int,
    role: str,
) -> None:
    """Attach a user to an organization with the given role and activate it on their session."""
    with Session(engine) as db:
        existing = db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        if existing is None:
            db.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role))
        else:
            existing.role = role
        sessions = db.scalars(select(UserSession).where(UserSession.user_id == user_id)).all()
        for sess in sessions:
            sess.active_org_id = org_id
        db.commit()


@pytest.fixture()
def reporting_app_env() -> Iterator[dict[str, Any]]:
    """Spin up an isolated FastAPI app with reporting_v2 mounted and two seeded organizations."""
    with TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "reporting_test.sqlite3"
        db_url = f"sqlite:///{db_path.as_posix()}"
        settings = Settings(
            app_env="test",
            database_url=db_url,
            data_dir=Path(tmp) / "data",
            model_dir=Path(tmp) / "models",
            frontend_dir=Path(tmp) / "frontend",
            ingestion_worker_enabled=False,
        )
        engine = create_db_engine(db_url)
        Base.metadata.create_all(engine)

        with Session(engine) as db:
            org1 = Organization(name="Alpha Corp", slug="alpha-corp")
            org2 = Organization(name="Beta Corp", slug="beta-corp")
            db.add_all([org1, org2])
            db.flush()

            org1_company = OrgCompany(
                organization_id=org1.id,
                name="Công ty CP Cơ khí Alpha",
                tax_code="0109988776",
                sector_code="C",
                sector_name="Sản xuất cơ khí",
                business_type="manufacturing",
                listing_status="unlisted",
                relationship_tag="customer",
            )
            db.add(org1_company)
            db.flush()

            for yr in (2024, 2025):
                db.add(
                    OrgFinancialStatement(
                        organization_id=org1.id,
                        org_company_id=org1_company.id,
                        fiscal_year=yr,
                        fiscal_period="FY",
                        period_end_date=date(yr, 12, 31),
                        accounting_standard="TT200_2014" if yr == 2024 else "TT99_2025",
                        currency="VND",
                        unit_scale=1_000_000,
                        display_unit="MILLION_VND",
                        audit_status="audited_unqualified",
                        status="finalized",
                        source_channel="web_form",
                        total_assets=1000.0,
                        current_assets=480.0,
                        cash_and_equivalents=150.0,
                        accounts_receivable=120.0,
                        inventory=130.0,
                        total_liabilities=420.0,
                        current_liabilities=210.0,
                        stockholders_equity=580.0,
                        retained_earnings=220.0,
                        revenues=950.0,
                        cost_of_goods_sold=610.0,
                        gross_profit=340.0,
                        operating_expenses=170.0,
                        operating_income=170.0,
                        depreciation_amortization=30.0,
                        ebitda=200.0,
                        interest_expense=14.0,
                        net_income=125.0,
                        operating_cash_flow=145.0,
                        capex=30.0,
                    )
                )

            sec_comp = Company(
                cik="0000320193",
                ticker="AAPL",
                name="Apple Inc.",
                sic_code="3571",
                sector="Manufacturing",
            )
            db.add(sec_comp)
            db.flush()
            for yr in (2023, 2024):
                db.add(
                    FinancialStatement(
                        company_id=sec_comp.id,
                        accession_number=f"0000320193-{yr % 100:02d}-000001",
                        form_type="10-K",
                        fiscal_year=yr,
                        fiscal_period="FY",
                        period_end_date=date(yr, 9, 30),
                        filed_date=date(yr, 11, 1),
                        total_assets=350_000.0,
                        current_assets=140_000.0,
                        cash_and_equivalents=60_000.0,
                        accounts_receivable=30_000.0,
                        inventory=7_000.0,
                        total_liabilities=280_000.0,
                        current_liabilities=130_000.0,
                        long_term_debt=95_000.0,
                        stockholders_equity=70_000.0,
                        retained_earnings=20_000.0,
                        revenues=385_000.0,
                        operating_income=115_000.0,
                        interest_expense=3_500.0,
                        net_income=97_000.0,
                        operating_cash_flow=110_000.0,
                        capex=11_000.0,
                    )
                )
            db.commit()
            org1_id = org1.id
            org2_id = org2.id
            org1_company_id = org1_company.id

        app = create_app(settings)
        # Mount reporting_v2 directly in test app (Wave 3 mounts it in main.py).
        app.include_router(reporting_v2.router)

        with TestClient(app) as client:
            yield {
                "app": app,
                "client": client,
                "engine": engine,
                "org1_id": org1_id,
                "org2_id": org2_id,
                "org1_company_id": org1_company_id,
            }
        engine.dispose()


def test_batch_excel_rbac_isolation_and_export(reporting_app_env: dict[str, Any]) -> None:
    """Verify template, 202 upload, viewer 403, org isolation 404, and ranked Excel export."""
    app = reporting_app_env["app"]
    engine: Engine = reporting_app_env["engine"]
    org1_id: int = reporting_app_env["org1_id"]
    org2_id: int = reporting_app_env["org2_id"]

    # 1. Viewer in Org 1 can download template, but gets 403 on upload.
    with TestClient(app) as viewer_client:
        viewer_uid = sign_in(viewer_client, engine, "viewer@alpha.vn", role="user")
        _provision_org_membership(engine, user_id=viewer_uid, org_id=org1_id, role="viewer")

        tpl_res = viewer_client.get("/api/v1/org/batch/template.xlsx")
        assert tpl_res.status_code == 200
        assert "spreadsheetml" in tpl_res.headers["content-type"]

        sample_xlsx = _build_batch_xlsx(
            [
                {
                    "company_name": "DN A",
                    "fiscal_year": 2025,
                    "total_assets": 1000.0,
                    "total_liabilities": 400.0,
                    "stockholders_equity": 600.0,
                }
            ]
        )
        forbidden_res = viewer_client.post(
            "/api/v1/org/batch/jobs",
            files={
                "file": (
                    "batch.xlsx",
                    sample_xlsx,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert forbidden_res.status_code == 403

    # 2. Analyst in Org 1 uploads 10 rows (8 valid + 2 bad) -> 202 Accepted -> completes cleanly.
    rows: list[dict[str, Any]] = []
    for idx in range(8):
        liab = 300.0 + idx * 75.0
        rows.append(
            {
                "company_name": f"DN Hợp Lệ {idx + 1}",
                "tax_code": f"03000000{idx:02d}",
                "fiscal_year": 2025,
                "total_assets": 1000.0,
                "current_assets": 450.0,
                "total_liabilities": liab,
                "current_liabilities": liab * 0.5,
                "stockholders_equity": 1000.0 - liab,
                "revenues": 800.0,
                "operating_income": 120.0 - idx * 20.0,
                "net_income": 90.0 - idx * 20.0,
                "operating_cash_flow": 100.0 - idx * 18.0,
            }
        )
    rows.append({"company_name": "DN Lỗi 1", "fiscal_year": 2025, "total_assets": -10.0})
    rows.append(
        {
            "company_name": "DN Lỗi 2",
            "fiscal_year": 2025,
            "total_assets": 1000.0,
            "total_liabilities": 200.0,
            "stockholders_equity": 200.0,
        }
    )
    batch_bytes = _build_batch_xlsx(rows)

    with TestClient(app) as analyst_client:
        analyst_uid = sign_in(analyst_client, engine, "analyst@alpha.vn", role="user")
        _provision_org_membership(engine, user_id=analyst_uid, org_id=org1_id, role="analyst")

        # Invalid file payload returns 422.
        bad_res = analyst_client.post(
            "/api/v1/org/batch/jobs",
            files={"file": ("broken.xlsx", b"not-an-excel-file", "application/octet-stream")},
        )
        assert bad_res.status_code == 422

        up_res = analyst_client.post(
            "/api/v1/org/batch/jobs",
            files={
                "file": (
                    "portfolio_10.xlsx",
                    batch_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert up_res.status_code == 202, up_res.text
        job_id = up_res.json()["id"]

        list_res = analyst_client.get("/api/v1/org/batch/jobs")
        assert list_res.status_code == 200
        assert any(item["id"] == job_id for item in list_res.json())

        detail_res = analyst_client.get(f"/api/v1/org/batch/jobs/{job_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["status"] == "completed"
        assert detail["total_rows"] == 10
        assert detail["succeeded_rows"] == 8
        assert detail["failed_rows"] == 2
        succ_pds = [r["pd_12m"] for r in detail["rows"] if r["status"] == "succeeded"]
        assert len(succ_pds) == 8
        assert succ_pds == sorted(succ_pds, reverse=True)

    # 3. Org 1 viewer can inspect & export the completed job; Org 2 gets 404.
    with TestClient(app) as viewer_client:
        viewer_uid = sign_in(viewer_client, engine, "viewer@alpha.vn", role="user")
        _provision_org_membership(engine, user_id=viewer_uid, org_id=org1_id, role="viewer")

        exp_res = viewer_client.get(f"/api/v1/org/batch/jobs/{job_id}/export.xlsx")
        assert exp_res.status_code == 200
        assert "spreadsheetml" in exp_res.headers["content-type"]
        wb = load_workbook(BytesIO(exp_res.content), read_only=True)
        try:
            assert "TomTatDanhMuc" in wb.sheetnames
            assert "KetQuaXepHang" in wb.sheetnames
        finally:
            wb.close()

    with TestClient(app) as org2_client:
        org2_uid = sign_in(org2_client, engine, "admin@beta.vn", role="user")
        _provision_org_membership(engine, user_id=org2_uid, org_id=org2_id, role="org_admin")

        assert org2_client.get(f"/api/v1/org/batch/jobs/{job_id}").status_code == 404
        assert org2_client.get(f"/api/v1/org/batch/jobs/{job_id}/export.xlsx").status_code == 404
        assert org2_client.get("/api/v1/org/batch/jobs").json() == []


def test_org_and_sec_pdf_endpoints_isolation_and_rate_limit(
    reporting_app_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Org PDF (200/404/429) and SEC PDF (401/200) endpoints."""
    app = reporting_app_env["app"]
    engine: Engine = reporting_app_env["engine"]
    org1_id: int = reporting_app_env["org1_id"]
    org2_id: int = reporting_app_env["org2_id"]
    org1_company_id: int = reporting_app_env["org1_company_id"]

    # Unauthenticated SEC PDF request is rejected with 401.
    with TestClient(app) as anon_client:
        assert anon_client.get("/api/v1/companies/AAPL/report.pdf").status_code == 401

    # Org 2 cannot access Org 1 company PDF -> 404.
    with TestClient(app) as org2_client:
        org2_uid = sign_in(org2_client, engine, "admin@beta.vn", role="user")
        _provision_org_membership(engine, user_id=org2_uid, org_id=org2_id, role="org_admin")
        assert (
            org2_client.get(f"/api/v1/org/companies/{org1_company_id}/report.pdf").status_code
            == 404
        )

    # Org 1 viewer downloads Org PDF & SEC PDF, and hits 429 after rate limit.
    monkeypatch.setattr(reporting_v2, "_PDF_RATE_LIMIT", 2)
    with TestClient(app) as viewer_client:
        viewer_uid = sign_in(viewer_client, engine, "pdfviewer@alpha.vn", role="user")
        _provision_org_membership(engine, user_id=viewer_uid, org_id=org1_id, role="viewer")

        org_pdf = viewer_client.get(f"/api/v1/org/companies/{org1_company_id}/report.pdf")
        assert org_pdf.status_code == 200
        assert org_pdf.headers["content-type"] == "application/pdf"
        assert "attachment; filename=" in org_pdf.headers["content-disposition"]
        assert org_pdf.content.startswith(b"%PDF-")
        assert len(org_pdf.content) > 10_000

        sec_pdf = viewer_client.get("/api/v1/companies/AAPL/report.pdf")
        assert sec_pdf.status_code == 200
        assert sec_pdf.headers["content-type"] == "application/pdf"
        assert sec_pdf.content.startswith(b"%PDF-")

        # 3rd PDF request within the same window hits 429 rate limit.
        throttled = viewer_client.get(f"/api/v1/org/companies/{org1_company_id}/report.pdf")
        assert throttled.status_code == 429
