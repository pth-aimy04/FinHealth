"""Integration tests for org_companies router: isolation, RBAC, draft/finalize, XML/Excel, seed."""

import secrets
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from threading import RLock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finhealth.api.routers import org_companies
from finhealth.api.security import SESSION_COOKIE, digest, hash_password
from finhealth.core.config import Settings
from finhealth.db.account_models import Organization, OrganizationMember, User, UserSession
from finhealth.db.base import Base, utc_now
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.excel_templates import generate_bctc_template_bytes


def _build_test_app(settings: Settings) -> FastAPI:
    """Mount org_companies.router onto a standalone FastAPI test app without editing main.py."""
    app = FastAPI()
    app.state.settings = settings
    app.state.engine = None
    app.state.session_factory = None
    app.state.resource_lock = RLock()
    app.include_router(org_companies.router, prefix="/api/v1")
    return app


def _create_member_session(
    db: Session,
    *,
    org: Organization,
    email: str,
    role: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Create a verified user, org membership, and live cookie/CSRF session."""
    pw_hash = hash_password("FinHealth-Test-Password-2026!")
    user = User(
        email=email,
        password_hash=pw_hash,
        display_name=email.split("@")[0],
        role="user",
        active=True,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=role))
    raw_token = secrets.token_urlsafe(32)
    raw_csrf = secrets.token_urlsafe(24)
    db.add(
        UserSession(
            user_id=user.id,
            active_org_id=org.id,
            token_hash=digest(raw_token),
            csrf_hash=digest(raw_csrf),
            credential_stamp=pw_hash,
            expires_at=utc_now() + timedelta(hours=2),
        )
    )
    db.commit()
    return {SESSION_COOKIE: raw_token}, {"X-CSRF-Token": raw_csrf}


@pytest.fixture
def org_env(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, Engine, dict[str, tuple[dict[str, str], dict[str, str]]]]]:
    """Spin up an isolated SQLite DB and two organizations with admin/analyst/viewer sessions."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{tmp_path / 'org_financials.sqlite3'}",
        data_dir=tmp_path,
        app_env="test",
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as db:
        org_a = Organization(name="Alpha Corp Workspace", slug="alpha-org", is_personal=False)
        org_b = Organization(name="Beta Corp Workspace", slug="beta-org", is_personal=False)
        db.add_all([org_a, org_b])
        db.flush()
        creds = {
            "admin_a": _create_member_session(
                db, org=org_a, email="admin@alpha.test", role="org_admin"
            ),
            "analyst_a": _create_member_session(
                db, org=org_a, email="analyst@alpha.test", role="analyst"
            ),
            "viewer_a": _create_member_session(
                db, org=org_a, email="viewer@alpha.test", role="viewer"
            ),
            "admin_b": _create_member_session(
                db, org=org_b, email="admin@beta.test", role="org_admin"
            ),
        }

    app = _build_test_app(settings)
    with TestClient(app) as client:
        yield client, engine, creds
    engine.dispose()


def test_org_company_crud_isolation_rbac_and_fi_gate(
    org_env: tuple[TestClient, Engine, dict[str, tuple[dict[str, str], dict[str, str]]]],
) -> None:
    """Enforce org_id isolation, viewer/analyst/org_admin RBAC, and FI exclusion gate."""
    client, _engine, creds = org_env
    admin_a_cookies, admin_a_hdr = creds["admin_a"]
    analyst_a_cookies, analyst_a_hdr = creds["analyst_a"]
    viewer_a_cookies, viewer_a_hdr = creds["viewer_a"]
    admin_b_cookies, admin_b_hdr = creds["admin_b"]

    payload = {
        "name": "Công ty CP Sản xuất Thành Công",
        "tax_code": "0101234567",
        "ticker": "tcm",
        "sector_code": "C13",
        "sector_name": "Dệt may",
        "business_type": "manufacturing",
        "listing_status": "listed",
        "relationship_tag": "customer",
    }

    # Viewer is blocked from creating
    res_viewer = client.post(
        "/api/v1/org/companies",
        json=payload,
        cookies=viewer_a_cookies,
        headers=viewer_a_hdr,
    )
    assert res_viewer.status_code == 403

    # Analyst creates company
    res_create = client.post(
        "/api/v1/org/companies",
        json=payload,
        cookies=analyst_a_cookies,
        headers=analyst_a_hdr,
    )
    assert res_create.status_code == 201
    created = res_create.json()
    company_id = created["id"]
    assert created["ticker"] == "TCM"
    assert created["scoring_eligible"] is True
    assert created["scoring_exclusion_reason"] is None

    # Duplicate tax_code in same org returns 409
    res_dup = client.post(
        "/api/v1/org/companies",
        json=payload,
        cookies=analyst_a_cookies,
        headers=analyst_a_hdr,
    )
    assert res_dup.status_code == 409

    # Financial Institution exclusion gate
    fi_res = client.post(
        "/api/v1/org/companies",
        json={
            "name": "Ngân hàng TMCP Mẫu",
            "tax_code": "0107654321",
            "business_type": "financial_institution",
            "listing_status": "listed",
            "relationship_tag": "other",
        },
        cookies=analyst_a_cookies,
        headers=analyst_a_hdr,
    )
    assert fi_res.status_code == 201
    fi_data = fi_res.json()
    assert fi_data["scoring_eligible"] is False
    assert "Tổ chức tài chính" in fi_data["scoring_exclusion_reason"]

    # Viewer can read & search inside Org A
    res_list = client.get(
        "/api/v1/org/companies",
        params={"q": "0101234567"},
        cookies=viewer_a_cookies,
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1

    # Org B cannot see or mutate Org A's company (strict org_id isolation)
    assert (
        client.get(f"/api/v1/org/companies/{company_id}", cookies=admin_b_cookies).status_code
        == 404
    )
    assert (
        client.get("/api/v1/org/companies", cookies=admin_b_cookies).json() == []
    )
    assert (
        client.delete(
            f"/api/v1/org/companies/{company_id}",
            cookies=admin_b_cookies,
            headers=admin_b_hdr,
        ).status_code
        == 404
    )

    # Analyst can soft-archive, but CANNOT hard-delete
    res_archive = client.patch(
        f"/api/v1/org/companies/{company_id}",
        json={"archived": True},
        cookies=analyst_a_cookies,
        headers=analyst_a_hdr,
    )
    assert res_archive.status_code == 200
    assert res_archive.json()["archived"] is True

    res_del_analyst = client.delete(
        f"/api/v1/org/companies/{company_id}",
        cookies=analyst_a_cookies,
        headers=analyst_a_hdr,
    )
    assert res_del_analyst.status_code == 403

    # Org admin can hard-delete
    res_del_admin = client.delete(
        f"/api/v1/org/companies/{company_id}",
        cookies=admin_a_cookies,
        headers=admin_a_hdr,
    )
    assert res_del_admin.status_code == 204
    assert (
        client.get(f"/api/v1/org/companies/{company_id}", cookies=admin_a_cookies).status_code
        == 404
    )


def test_statement_draft_to_finalized_units_and_multiperiod(
    org_env: tuple[TestClient, Engine, dict[str, tuple[dict[str, str], dict[str, str]]]],
) -> None:
    """Draft allows imbalanced input; finalized blocks hard errors; unit scales normalize to VND."""
    client, _engine, creds = org_env
    analyst_cookies, analyst_hdr = creds["analyst_a"]
    viewer_cookies, _ = creds["viewer_a"]

    comp = client.post(
        "/api/v1/org/companies",
        json={"name": "Công ty Đa Kỳ", "business_type": "manufacturing"},
        cookies=analyst_cookies,
        headers=analyst_hdr,
    ).json()
    cid = comp["id"]

    # Imbalanced draft in Billion VND (100 != 40 + 40) succeeds as draft
    imbalanced_draft = {
        "fiscal_year": 2025,
        "fiscal_period": "FY",
        "accounting_standard": "TT200_2014",
        "currency": "VND",
        "unit_scale": 1_000_000_000,
        "status": "draft",
        "total_assets": 100.0,
        "current_assets": 50.0,
        "total_liabilities": 40.0,
        "current_liabilities": 20.0,
        "stockholders_equity": 40.0,
        "revenues": 120.0,
        "cost_of_goods_sold": 80.0,
        "net_income": 15.0,
    }
    res_draft = client.post(
        f"/api/v1/org/companies/{cid}/statements",
        json=imbalanced_draft,
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert res_draft.status_code == 201
    draft_data = res_draft.json()
    stmt_id = draft_data["id"]
    assert draft_data["status"] == "draft"
    assert draft_data["display_unit"] == "BILLION_VND"
    assert draft_data["total_assets"] == pytest.approx(100_000_000_000.0)
    assert draft_data["validation"]["is_balanced"] is False

    # Attempting to finalize imbalanced draft returns 422
    res_bad_fin = client.post(
        f"/api/v1/org/companies/{cid}/statements/{stmt_id}/finalize",
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert res_bad_fin.status_code == 422

    # Fix equity to 60 Billion VND and finalize
    res_fix = client.patch(
        f"/api/v1/org/companies/{cid}/statements/{stmt_id}",
        json={"stockholders_equity": 60.0, "status": "finalized"},
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert res_fix.status_code == 200
    fixed = res_fix.json()
    assert fixed["status"] == "finalized"
    assert fixed["validation"]["is_balanced"] is True
    assert fixed["stockholders_equity"] == pytest.approx(60_000_000_000.0)

    # Add FY2026 under TT99_2025 in Million VND
    res_2026 = client.post(
        f"/api/v1/org/companies/{cid}/statements",
        json={
            "fiscal_year": 2026,
            "fiscal_period": "FY",
            "accounting_standard": "TT99_2025",
            "currency": "VND",
            "unit_scale": 1_000_000,
            "status": "finalized",
            "total_assets": 110_000.0,
            "current_assets": 55_000.0,
            "total_liabilities": 44_000.0,
            "current_liabilities": 22_000.0,
            "stockholders_equity": 66_000.0,
            "revenues": 135_000.0,
            "cost_of_goods_sold": 90_000.0,
            "net_income": 18_000.0,
        },
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert res_2026.status_code == 201

    # Viewer lists multi-period history newest first
    history = client.get(
        f"/api/v1/org/companies/{cid}/statements",
        cookies=viewer_cookies,
    ).json()
    assert [row["fiscal_year"] for row in history] == [2026, 2025]
    assert [row["accounting_standard"] for row in history] == ["TT99_2025", "TT200_2014"]


def test_template_download_excel_xml_import_and_idempotent_seed(
    org_env: tuple[TestClient, Engine, dict[str, tuple[dict[str, str], dict[str, str]]]],
) -> None:
    """Exercise template download, Excel/HTKK XML import (with XXE block), and sample seed."""
    client, _engine, creds = org_env
    analyst_cookies, analyst_hdr = creds["analyst_a"]
    viewer_cookies, viewer_hdr = creds["viewer_a"]

    # 1. Template download works for viewer
    tpl = client.get("/api/v1/templates/bctc/TT99_2025", cookies=viewer_cookies)
    assert tpl.status_code == 200
    assert "spreadsheetml" in tpl.headers["content-type"]
    assert tpl.content[:2] == b"PK"

    # 2. Seed 3 VN samples idempotently (viewer blocked, analyst succeeds twice)
    assert (
        client.post(
            "/api/v1/org/samples/seed",
            cookies=viewer_cookies,
            headers=viewer_hdr,
        ).status_code
        == 403
    )
    first_seed = client.post(
        "/api/v1/org/samples/seed",
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert first_seed.status_code == 200
    assert first_seed.json()["created_companies"] == 3
    assert first_seed.json()["created_statements"] == 15

    second_seed = client.post(
        "/api/v1/org/samples/seed",
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert second_seed.status_code == 200
    assert second_seed.json()["created_companies"] == 0
    assert second_seed.json()["existing_companies"] == 3
    assert second_seed.json()["created_statements"] == 0

    cid = first_seed.json()["companies"][0]["id"]

    # 3. Import Excel into draft
    xlsx_bytes = generate_bctc_template_bytes(
        "TT133_2016",
        fiscal_year=2024,
        unit_scale=1_000_000,
        prefill={
            "total_assets": 500_000_000_000.0,
            "current_assets": 250_000_000_000.0,
            "cash_and_equivalents": 80_000_000_000.0,
            "total_liabilities": 200_000_000_000.0,
            "current_liabilities": 100_000_000_000.0,
            "stockholders_equity": 300_000_000_000.0,
            "revenues": 600_000_000_000.0,
            "net_income": 70_000_000_000.0,
        },
    )
    excel_res = client.post(
        f"/api/v1/org/companies/{cid}/statements/import-excel",
        files={
            "file": (
                "bctc_2024.xlsx",
                xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert excel_res.status_code == 201
    excel_body = excel_res.json()
    assert excel_body["status"] == "draft"
    assert excel_body["source_channel"] == "excel_upload"
    assert excel_body["accounting_standard"] == "TT133_2016"
    assert excel_body["total_assets"] == pytest.approx(500_000_000_000.0)
    assert excel_body["validation"]["is_balanced"] is True

    # 4. Import valid HTKK XML into draft
    htkk_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <HSoThueDTu>
      <HSoKhaiThue>
        <TTinChung>
          <TTinTKhaiThue>
            <TKhaiThue>
              <maTKhai>405</maTKhai>
              <tenTKhai>BCTC TT200/2014/TT-BTC</tenTKhai>
              <KyKKhaiThue>
                <kieuKy>Y</kieuKy>
                <kyKKhai>2023</kyKKhai>
                <kyKKhaiDenNgay>31/12/2023</kyKKhaiDenNgay>
              </KyKKhaiThue>
            </TKhaiThue>
            <NNT><mst>0109990001</mst></NNT>
          </TTinTKhaiThue>
        </TTinChung>
        <CTieuTKhaiChinh>
          <CDKT>
            <ct100>200000000</ct100>
            <ct270>400000000</ct270>
            <ct300>150000000</ct300>
            <ct310>80000000</ct310>
            <ct400>250000000</ct400>
          </CDKT>
          <KQHDSXKD>
            <ct10>500000000</ct10>
            <ct60>55000000</ct60>
          </KQHDSXKD>
        </CTieuTKhaiChinh>
      </HSoKhaiThue>
    </HSoThueDTu>
    """
    xml_res = client.post(
        f"/api/v1/org/companies/{cid}/statements/import-xml",
        files={"file": ("htkk_2023.xml", htkk_xml, "application/xml")},
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert xml_res.status_code == 201
    xml_body = xml_res.json()
    assert xml_body["status"] == "draft"
    assert xml_body["source_channel"] == "htkk_xml"
    assert xml_body["fiscal_year"] == 2023
    assert xml_body["accounting_standard"] == "TT200_2014"
    assert xml_body["validation"]["is_balanced"] is True

    # 5. XXE XML upload is rejected with 422
    xxe_xml = b"""<?xml version="1.0"?>
    <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
    <HSoThueDTu><CDKT><ct270>&xxe;</ct270></CDKT></HSoThueDTu>
    """
    xxe_res = client.post(
        f"/api/v1/org/companies/{cid}/statements/import-xml",
        files={"file": ("evil.xml", xxe_xml, "application/xml")},
        cookies=analyst_cookies,
        headers=analyst_hdr,
    )
    assert xxe_res.status_code == 422
