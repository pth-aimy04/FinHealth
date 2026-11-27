"""True end-to-end Go-Live V1.0 integration test exercising the real wired FastAPI app.

Only the external SMTP transport (`finhealth.core.mail.send_account_email`) is captured in-memory.
All routers, ORM models, SQLite database, HTKK XML parser, openpyxl batch engine, reportlab PDF
generator, and the real `v2.0.0-kaggle` ML artifact bundle run end-to-end without mocks.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finhealth.api.main import create_app
from finhealth.core import mail
from finhealth.core.config import Settings
from finhealth.db.account_models import (
    Organization,
    OrganizationMember,
    User,
    UserSession,
)
from finhealth.db.action_code_models import AccountActionCode
from finhealth.db.base import Base
from finhealth.db.session import create_db_engine
from finhealth.db.verification_models import EmailVerificationCode
from finhealth.reporting.batch_excel import BATCH_COLUMNS, BATCH_DATA_SHEET

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "data" / "artifacts" / "models"

USER_A_EMAIL = "lead.golive@finhealth-test.vn"
USER_A_INIT_PW = "InitPass-UserA-2026!"
USER_A_PW = "OwnerPass-UserA-2026!"

USER_B_EMAIL = "analyst.golive@finhealth-test.vn"
USER_B_INIT_PW = "InitPass-UserB-2026!"
USER_B_PW = "OwnerPass-UserB-2026!"

FORBIDDEN_ML_TERMS = ("shap", "log-odds", "xgboost", "random forest", "smote")


def _extract_otp(messages: list[dict[str, str]], recipient: str) -> str:
    """Return the latest 6-digit OTP sent to the given recipient."""
    for msg in reversed(messages):
        if msg["recipient"] == recipient:
            match = re.search(r"Mã OTP của bạn: ([0-9]{6})", msg["body"])
            if match is not None:
                return match.group(1)
    raise AssertionError(f"No OTP email captured for {recipient}")


def _login_client(client: TestClient, email: str, password: str) -> None:
    """Authenticate via real /auth/login and sync the CSRF header."""
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    csrf = client.cookies.get("finhealth_csrf")
    assert csrf is not None
    client.headers["X-CSRF-Token"] = csrf


def _build_batch_excel_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Create a valid .xlsx upload payload matching the official batch column contract."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = BATCH_DATA_SHEET
    headers = [col[0] for col in BATCH_COLUMNS]
    ws.append(headers)
    for item in rows:
        ws.append([item.get(col) for col in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_e2e_v10_golive_full_customer_journey(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the complete 12-step FinHealth Production V1.0 journey on the real wired app."""
    if not (MODEL_DIR / "v2.0.0-kaggle" / "models.joblib").is_file():
        pytest.skip("v2.0.0-kaggle model bundle is required for live E2E scoring")

    db_path = tmp_path / "e2e_v10_golive.sqlite3"
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
        data_dir=ROOT / "data",
        ingestion_worker_enabled=False,
        cors_allowed_origins=["https://app.finhealth.vn"],
        smtp_username="noreply@finhealth-test.vn",
        smtp_password="test-only-smtp-secret",
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)

    captured_emails: list[dict[str, str]] = []

    def capture_smtp(_cfg: Settings, recipient: str, subject: str, body: str) -> None:
        captured_emails.append({"recipient": recipient, "subject": subject, "body": body})

    monkeypatch.setattr(mail, "send_account_email", capture_smtp)
    app = create_app(settings)

    try:
        with TestClient(app) as client_a, TestClient(app) as client_b:
            # ------------------------------------------------------------------
            # Step 1: User A registers -> OTP -> verify-email (new_password) ->
            #         login -> verify auto-created personal org (org_admin)
            # ------------------------------------------------------------------
            reg_a = client_a.post(
                "/api/v1/auth/register",
                json={
                    "email": USER_A_EMAIL,
                    "password": USER_A_INIT_PW,
                    "display_name": "Nguyễn Quang Huy",
                },
            )
            assert reg_a.status_code == 202, reg_a.text
            ver_a = client_a.post(
                "/api/v1/auth/verify-email",
                json={
                    "email": USER_A_EMAIL,
                    "challenge": reg_a.json()["challenge"],
                    "code": _extract_otp(captured_emails, USER_A_EMAIL),
                    "new_password": USER_A_PW,
                },
            )
            assert ver_a.status_code == 200, ver_a.text
            _login_client(client_a, USER_A_EMAIL, USER_A_PW)

            orgs_a = client_a.get("/api/v1/organizations")
            assert orgs_a.status_code == 200
            orgs_a_list = orgs_a.json()
            assert len(orgs_a_list) == 1
            personal_org_a_id = orgs_a_list[0]["id"]
            assert orgs_a_list[0]["is_personal"] is True
            assert orgs_a_list[0]["role"] == "org_admin"

            # Create a company inside User A's personal org to test cross-org isolation later.
            personal_comp_res = client_a.post(
                "/api/v1/org/companies",
                json={
                    "name": "Công ty Riêng Tư A",
                    "tax_code": "0101234567",
                    "business_type": "manufacturing",
                },
            )
            assert personal_comp_res.status_code == 201, personal_comp_res.text
            personal_org_a_company_id = personal_comp_res.json()["id"]

            # ------------------------------------------------------------------
            # Step 2: Create Team Org -> invite User B as viewer -> User B
            #         registers/verifies/logs in -> accepts invite -> viewer
            #         reads OK but receives 403 on writes
            # ------------------------------------------------------------------
            team_org_res = client_a.post(
                "/api/v1/organizations",
                json={"name": "Khối Thẩm Định Tín Dụng V1"},
            )
            assert team_org_res.status_code == 201, team_org_res.text
            team_org_id = team_org_res.json()["id"]

            switch_a = client_a.post(
                "/api/v1/organizations/switch",
                json={"organization_id": team_org_id},
            )
            assert switch_a.status_code == 200, switch_a.text

            invite_res = client_a.post(
                f"/api/v1/organizations/{team_org_id}/invites",
                json={"email": USER_B_EMAIL, "role": "viewer"},
            )
            assert invite_res.status_code == 201, invite_res.text
            invite_token = invite_res.json()["token"]

            reg_b = client_b.post(
                "/api/v1/auth/register",
                json={
                    "email": USER_B_EMAIL,
                    "password": USER_B_INIT_PW,
                    "display_name": "Trần Thu Hà",
                },
            )
            assert reg_b.status_code == 202, reg_b.text
            ver_b = client_b.post(
                "/api/v1/auth/verify-email",
                json={
                    "email": USER_B_EMAIL,
                    "challenge": reg_b.json()["challenge"],
                    "code": _extract_otp(captured_emails, USER_B_EMAIL),
                    "new_password": USER_B_PW,
                },
            )
            assert ver_b.status_code == 200, ver_b.text
            _login_client(client_b, USER_B_EMAIL, USER_B_PW)
            user_b_id = client_b.get("/api/v1/auth/me").json()["id"]

            accept_res = client_b.post(
                "/api/v1/organizations/invites/accept",
                json={"token": invite_token},
            )
            assert accept_res.status_code == 200, accept_res.text
            assert accept_res.json()["organization_id"] == team_org_id
            assert accept_res.json()["role"] == "viewer"

            switch_b = client_b.post(
                "/api/v1/organizations/switch",
                json={"organization_id": team_org_id},
            )
            assert switch_b.status_code == 200, switch_b.text

            # Viewer can read org companies, but gets 403 on write operations.
            assert client_b.get("/api/v1/org/companies").status_code == 200
            assert (
                client_b.post(
                    "/api/v1/org/companies",
                    json={"name": "Viewer Blocked Co", "business_type": "services"},
                ).status_code
                == 403
            )
            assert client_b.post("/api/v1/org/samples/seed").status_code == 403

            # ------------------------------------------------------------------
            # Step 3: User A promotes User B to analyst -> User B seeds 3 VN
            #         sample companies (idempotent)
            # ------------------------------------------------------------------
            promote_res = client_a.patch(
                f"/api/v1/organizations/{team_org_id}/members/{user_b_id}",
                json={"role": "analyst"},
            )
            assert promote_res.status_code == 200, promote_res.text
            assert promote_res.json()["role"] == "analyst"

            seed1 = client_b.post("/api/v1/org/samples/seed")
            assert seed1.status_code == 200, seed1.text
            assert seed1.json()["created_companies"] == 3
            assert seed1.json()["created_statements"] == 15
            sample_ids = [c["id"] for c in seed1.json()["companies"]]
            assert len(sample_ids) == 3

            seed2 = client_b.post("/api/v1/org/samples/seed")
            assert seed2.status_code == 200, seed2.text
            assert seed2.json()["created_companies"] == 0
            assert seed2.json()["existing_companies"] == 3

            # ------------------------------------------------------------------
            # Step 4: User B creates 1 new VN company (valid MST) + imports
            #         BCTC via HTKK XML (TT99/2025) -> balance check -> finalized
            # ------------------------------------------------------------------
            new_comp_res = client_b.post(
                "/api/v1/org/companies",
                json={
                    "name": "Công ty CP Cơ Khí Toàn Cầu",
                    "tax_code": "0312345678",
                    "business_type": "manufacturing",
                    "listing_status": "unlisted",
                    "relationship_tag": "customer",
                },
            )
            assert new_comp_res.status_code == 201, new_comp_res.text
            xml_company_id = new_comp_res.json()["id"]

            htkk_xml_tt99 = b"""<?xml version="1.0" encoding="UTF-8"?>
            <HSoThueDTu>
              <HSoKhaiThue>
                <TTinChung>
                  <TTinTKhaiThue>
                    <TKhaiThue>
                      <maTKhai>405</maTKhai>
                      <tenTKhai>BCTC TT99/2025/TT-BTC</tenTKhai>
                      <KyKKhaiThue>
                        <kieuKy>Y</kieuKy>
                        <kyKKhai>2026</kyKKhai>
                        <kyKKhaiDenNgay>31/12/2026</kyKKhaiDenNgay>
                      </KyKKhaiThue>
                    </TKhaiThue>
                    <NNT><mst>0312345678</mst></NNT>
                  </TTinTKhaiThue>
                </TTinChung>
                <CTieuTKhaiChinh>
                  <CDKT>
                    <ct100>320000000000</ct100>
                    <ct110>95000000000</ct110>
                    <ct130>110000000000</ct130>
                    <ct140>115000000000</ct140>
                    <ct270>600000000000</ct270>
                    <ct300>240000000000</ct300>
                    <ct310>140000000000</ct310>
                    <ct330>100000000000</ct330>
                    <ct400>360000000000</ct400>
                    <ct421>110000000000</ct421>
                  </CDKT>
                  <KQHDSXKD>
                    <ct10>750000000000</ct10>
                    <ct11>510000000000</ct11>
                    <ct20>240000000000</ct20>
                    <ct23>14000000000</ct23>
                    <ct30>115000000000</ct30>
                    <ct60>92000000000</ct60>
                  </KQHDSXKD>
                  <LCTT>
                    <ct20>105000000000</ct20>
                  </LCTT>
                </CTieuTKhaiChinh>
              </HSoKhaiThue>
            </HSoThueDTu>
            """
            xml_import = client_b.post(
                f"/api/v1/org/companies/{xml_company_id}/statements/import-xml",
                files={"file": ("bctc_tt99_2026.xml", htkk_xml_tt99, "application/xml")},
            )
            assert xml_import.status_code == 201, xml_import.text
            stmt_body = xml_import.json()
            assert stmt_body["status"] == "draft"
            assert stmt_body["source_channel"] == "htkk_xml"
            assert stmt_body["accounting_standard"] == "TT99_2025"
            assert stmt_body["validation"]["is_balanced"] is True

            finalize_res = client_b.post(
                f"/api/v1/org/companies/{xml_company_id}/statements/{stmt_body['id']}/finalize"
            )
            assert finalize_res.status_code == 200, finalize_res.text
            assert finalize_res.json()["status"] == "finalized"

            # ------------------------------------------------------------------
            # Step 5: Financial institution is explicitly blocked from Altman/ML
            # ------------------------------------------------------------------
            fi_comp_res = client_b.post(
                "/api/v1/org/companies",
                json={
                    "name": "Ngân hàng TMCP Mẫu Việt",
                    "tax_code": "0100112233",
                    "business_type": "financial_institution",
                },
            )
            assert fi_comp_res.status_code == 201, fi_comp_res.text
            fi_company_id = fi_comp_res.json()["id"]
            assert fi_comp_res.json()["scoring_eligible"] is False

            fi_stmt_res = client_b.post(
                f"/api/v1/org/companies/{fi_company_id}/statements",
                json={
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "accounting_standard": "TT200_2014",
                    "currency": "VND",
                    "unit_scale": 1_000_000_000,
                    "status": "finalized",
                    "total_assets": 5000.0,
                    "current_assets": 1000.0,
                    "total_liabilities": 4400.0,
                    "current_liabilities": 3000.0,
                    "stockholders_equity": 600.0,
                    "revenues": 400.0,
                    "net_income": 80.0,
                },
            )
            assert fi_stmt_res.status_code == 201, fi_stmt_res.text
            fi_analysis = client_b.get(f"/api/v1/org/companies/{fi_company_id}/analysis")
            assert fi_analysis.status_code == 200, fi_analysis.text
            fi_body = fi_analysis.json()
            assert fi_body["summary"]["scoring_eligible"] is False
            assert fi_body["summary"]["pd_12m"] is None
            assert fi_body["summary"]["health_score"] is None
            assert fi_body["altman"]["applicable"] is False

            # ------------------------------------------------------------------
            # Step 6: Full analysis on seeded multi-period VN company using real
            #         v2.0.0-kaggle model
            # ------------------------------------------------------------------
            target_sample_id = sample_ids[0]
            analysis_res = client_b.get(f"/api/v1/org/companies/{target_sample_id}/analysis")
            assert analysis_res.status_code == 200, analysis_res.text
            analysis = analysis_res.json()

            summary = analysis["summary"]
            assert summary["scoring_eligible"] is True
            assert summary["model_version"] == "v2.0.0-kaggle"
            assert 0.0 <= summary["health_score"] <= 100.0
            assert summary["risk_tier"] in {"STRONG", "STABLE", "WATCH", "CRITICAL"}
            assert 0.0 <= summary["pd_12m"] <= 1.0

            confidence = summary["confidence"]
            assert confidence["level"] in {"HIGH", "MEDIUM", "LOW"}
            assert 0.0 <= confidence["input_completeness"] <= 1.0
            assert isinstance(confidence["is_ood"], bool)
            assert confidence["ensemble_spread"] is not None
            assert isinstance(confidence["audit_status"], str)

            altman = analysis["altman"]
            assert altman["applicable"] is True
            assert altman["variant"] in {"Z", "Z'", "Z''"}
            assert altman["cutoff_low"] is not None
            assert altman["cutoff_high"] is not None
            assert altman["cutoff_low"] < altman["cutoff_high"]

            pillars = analysis["pillars"]["pillars"]
            assert len(pillars) == 5
            all_metrics = [m for p in pillars for m in p["metrics"]]
            assert len(all_metrics) == 20
            assert all(m.get("tooltip_vi") for m in all_metrics)

            drivers = analysis["drivers"]
            driver_texts = " ".join(
                f"{item['headline_vi']} {item['detail_vi']}"
                for item in (drivers["strengths"] + drivers["bottlenecks"])
            ).lower()
            for forbidden in FORBIDDEN_ML_TERMS:
                assert forbidden not in driver_texts, f"Leaked ML term '{forbidden}' in drivers"

            history = analysis["history"]
            assert 3 <= len(history) <= 5
            assert all(
                point["health_score"] is not None and point["pd_12m"] is not None
                for point in history
            )
            assert "88/2014" in analysis["legal_disclaimer_vi"]

            # ------------------------------------------------------------------
            # Step 7: Compare 2-3 org companies; >4 -> 422; cross-org ID -> 404
            # ------------------------------------------------------------------
            compare_ok = client_b.get(
                f"/api/v1/org/companies/compare?ids={sample_ids[0]},{sample_ids[1]},{sample_ids[2]}"
            )
            assert compare_ok.status_code == 200, compare_ok.text
            assert len(compare_ok.json()["companies"]) == 3

            compare_too_many = client_b.get(
                f"/api/v1/org/companies/compare?ids="
                f"{sample_ids[0]},{sample_ids[1]},{sample_ids[2]},{xml_company_id},{fi_company_id}"
            )
            assert compare_too_many.status_code == 422

            compare_cross_org = client_b.get(
                f"/api/v1/org/companies/compare?ids={sample_ids[0]},{personal_org_a_company_id}"
            )
            assert compare_cross_org.status_code == 404

            # ------------------------------------------------------------------
            # Step 8: Batch Excel upload -> completed -> export.xlsx ranked by
            #         pd_12m descending
            # ------------------------------------------------------------------
            batch_xlsx = _build_batch_excel_bytes(
                [
                    {
                        "company_name": "DN Batch Vững Mạnh",
                        "tax_code": "0301112221",
                        "fiscal_year": 2025,
                        "total_assets": 1000.0,
                        "current_assets": 550.0,
                        "cash_and_equivalents": 220.0,
                        "total_liabilities": 250.0,
                        "current_liabilities": 120.0,
                        "stockholders_equity": 750.0,
                        "retained_earnings": 300.0,
                        "revenues": 950.0,
                        "operating_income": 180.0,
                        "net_income": 140.0,
                        "operating_cash_flow": 165.0,
                    },
                    {
                        "company_name": "DN Batch Rủi Ro Cao",
                        "tax_code": "0301112222",
                        "fiscal_year": 2025,
                        "total_assets": 1000.0,
                        "current_assets": 180.0,
                        "cash_and_equivalents": 15.0,
                        "total_liabilities": 920.0,
                        "current_liabilities": 680.0,
                        "stockholders_equity": 80.0,
                        "retained_earnings": -250.0,
                        "revenues": 320.0,
                        "operating_income": -80.0,
                        "net_income": -110.0,
                        "operating_cash_flow": -95.0,
                    },
                ]
            )
            batch_create = client_b.post(
                "/api/v1/org/batch/jobs",
                files={
                    "file": (
                        "golive_batch.xlsx",
                        batch_xlsx,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
            assert batch_create.status_code == 202, batch_create.text
            job_id = batch_create.json()["id"]

            job_detail = client_b.get(f"/api/v1/org/batch/jobs/{job_id}")
            assert job_detail.status_code == 200, job_detail.text
            detail_body = job_detail.json()
            assert detail_body["status"] == "completed"
            assert detail_body["succeeded_rows"] == 2
            pds = [row["pd_12m"] for row in detail_body["rows"] if row["pd_12m"] is not None]
            assert len(pds) == 2
            assert pds[0] >= pds[1]

            export_xlsx = client_b.get(f"/api/v1/org/batch/jobs/{job_id}/export.xlsx")
            assert export_xlsx.status_code == 200, export_xlsx.text
            assert "spreadsheetml" in export_xlsx.headers["content-type"]
            assert export_xlsx.content[:2] == b"PK"

            # ------------------------------------------------------------------
            # Step 9: Executive PDF report -> 200, application/pdf, %PDF-
            # ------------------------------------------------------------------
            pdf_res = client_b.get(f"/api/v1/org/companies/{target_sample_id}/report.pdf")
            assert pdf_res.status_code == 200, pdf_res.text
            assert "application/pdf" in pdf_res.headers["content-type"]
            assert pdf_res.content.startswith(b"%PDF-")
            assert len(pdf_res.content) > 2_000

            # ------------------------------------------------------------------
            # Step 10: CORS preflight OPTIONS accepts PATCH and DELETE
            # ------------------------------------------------------------------
            for method in ("PATCH", "DELETE"):
                preflight = client_a.options(
                    f"/api/v1/organizations/{team_org_id}",
                    headers={
                        "Origin": "https://app.finhealth.vn",
                        "Access-Control-Request-Method": method,
                    },
                )
                assert preflight.status_code == 200, preflight.text
                assert (
                    preflight.headers.get("access-control-allow-origin")
                    == "https://app.finhealth.vn"
                )
                assert preflight.headers.get("access-control-allow-credentials") == "true"
                allow_methods = preflight.headers.get("access-control-allow-methods", "")
                assert method in allow_methods

            # ------------------------------------------------------------------
            # Step 11: User B exports personal data (Law 91/2025/QH15)
            # ------------------------------------------------------------------
            export_me = client_b.get("/api/v1/auth/me/export")
            assert export_me.status_code == 200, export_me.text
            export_payload = export_me.json()
            assert export_payload["profile"]["email"] == USER_B_EMAIL
            assert "password_hash" not in export_payload["profile"]
            assert USER_A_EMAIL not in str(export_payload)

            # ------------------------------------------------------------------
            # Step 12: User B deletes account (password + OTP) -> old cookie
            #          immediately 401 -> PII purged from DB
            # ------------------------------------------------------------------
            old_cookie_b = client_b.cookies.get("finhealth_session")
            assert old_cookie_b is not None

            del_req = client_b.post(
                "/api/v1/auth/delete-account/request",
                json={"current_password": USER_B_PW},
            )
            assert del_req.status_code == 202, del_req.text

            del_confirm = client_b.post(
                "/api/v1/auth/delete-account",
                json={
                    "current_password": USER_B_PW,
                    "challenge": del_req.json()["challenge"],
                    "code": _extract_otp(captured_emails, USER_B_EMAIL),
                },
            )
            assert del_confirm.status_code == 200, del_confirm.text

            client_b.cookies.set("finhealth_session", old_cookie_b)
            assert client_b.get("/api/v1/auth/me").status_code == 401

            with Session(engine) as db:
                assert db.get(User, user_b_id) is None
                assert db.scalar(select(User).where(User.email == USER_B_EMAIL)) is None
                assert (
                    db.scalar(
                        select(func.count())
                        .select_from(UserSession)
                        .where(UserSession.user_id == user_b_id)
                    )
                    == 0
                )
                assert (
                    db.scalar(
                        select(func.count())
                        .select_from(AccountActionCode)
                        .where(AccountActionCode.user_id == user_b_id)
                    )
                    == 0
                )
                assert (
                    db.scalar(
                        select(func.count())
                        .select_from(EmailVerificationCode)
                        .where(EmailVerificationCode.user_id == user_b_id)
                    )
                    == 0
                )
                assert (
                    db.scalar(
                        select(func.count())
                        .select_from(OrganizationMember)
                        .where(OrganizationMember.user_id == user_b_id)
                    )
                    == 0
                )
                # User A's team org and personal org remain intact.
                assert db.get(Organization, team_org_id) is not None
                assert db.get(Organization, personal_org_a_id) is not None
    finally:
        engine.dispose()


def test_spa_routes_serve_index_without_swallowing_api(tmp_path: Path) -> None:
    """Verify all V1.0 React SPA routes serve index.html while /api/* stays JSON."""
    dist_dir = tmp_path / "frontend" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!doctype html><html><body>FinHealth V1.0 SPA</body></html>", encoding="utf-8"
    )
    db_path = tmp_path / "spa_routes.sqlite3"
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
        frontend_dir=tmp_path / "frontend",
        data_dir=tmp_path,
        ingestion_worker_enabled=False,
    )
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            for path in (
                "/",
                "/portfolio",
                "/portfolio/42",
                "/batch",
                "/compare",
                "/us-market",
                "/us-market/AAPL",
                "/methodology",
                "/organization",
                "/account",
                "/admin",
                "/admin/models",
            ):
                resp = client.get(path)
                assert resp.status_code == 200, f"SPA route {path} failed: {resp.status_code}"
                assert "text/html" in resp.headers["content-type"]
                assert "FinHealth V1.0 SPA" in resp.text

            api_health = client.get("/api/v1/health")
            assert api_health.status_code == 200
            assert "application/json" in api_health.headers["content-type"]
            assert client.get("/api/v1/nonexistent-endpoint").status_code == 404
    finally:
        engine.dispose()
