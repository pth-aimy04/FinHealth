"""Stage 9 endpoint and CSV checks against a real local cache or isolated SQLite."""

import csv
import io
import json
import shutil
import sqlite3
import subprocess
from collections.abc import Iterator
from contextlib import closing
from datetime import date
from pathlib import Path
from statistics import median

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from finhealth.api.dependencies import ModelRegistryState
from finhealth.api.main import create_app
from finhealth.core.config import Settings
from finhealth.db.models import Company, FinancialMetric, FinancialStatement, ModelPrediction
from finhealth.db.session import create_db_engine, create_session_factory
from finhealth.etl.corporate_finance import RESEARCH_GRADE_LABEL
from finhealth.ml.registry import load_bundle
from finhealth.ml.splitter import ML_FEATURE_COLUMNS, RATIO_FEATURE_COLUMNS
from tests.account_helpers import sign_in

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SQLITE = DATA / "processed/parquet/finhealth.sqlite3"
MODEL_DIR = DATA / "artifacts/models"
RATIOS = (*RATIO_FEATURE_COLUMNS, "cash_ratio", "interest_coverage", "fcf_to_liabilities")


@pytest.fixture(scope="module")
def real_api() -> Iterator[TestClient]:
    """Exercise all comparison reads against the published snapshot without mutation."""
    if not SQLITE.is_file():
        pytest.skip("The Stage 8 local SQLite snapshot is required")
    app = create_app(
        Settings(
            _env_file=None,
            data_dir=DATA,
            DATABASE_URL=f"sqlite:///file:{SQLITE.as_posix()}?mode=ro&uri=true",
        )
    )
    app.state.model_registry = ModelRegistryState()
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    ("symbols", "expected"),
    [
        ("AAL,DAL,UAL", ["AAL", "DAL", "UAL"]),
        ("AAPL,MSFT,NVDA", ["AAPL", "MSFT", "NVDA"]),
        ("AAPL,aapl,0000320193,MSFT", ["AAPL", "MSFT"]),
    ],
)
def test_head_to_head_compare_endpoint_valid_and_edge_cases(
    real_api: TestClient, symbols: str, expected: list[str]
) -> None:
    """Verify route precedence, identity deduplication, complete snapshots and aligned medians."""
    response = real_api.get("/api/v1/companies/compare", params={"identifiers": symbols})
    assert response.status_code == 200, response.text
    body = response.json()
    companies = body["companies"]
    assert [row["ticker"] for row in companies] == expected
    assert body["requested_identifiers"] == symbols.split(",")
    assert body["period_policy"] == "latest_annual" and body["active_model_version"] == "v1.2.0"
    for row in companies:
        history = body["historical_series"][row["cik"]]
        assert row["accession_number"] == history[-1]["accession_number"]
        assert row["target_fiscal_year"] == row["fiscal_year"] + 1
        assert row["distress_probability"] is not None and row["cluster_id"] is not None
        assert row["internal_research_grade_label"] == RESEARCH_GRADE_LABEL
        assert all(metric in row and row[metric] == history[-1][metric] for metric in RATIOS)
    assert body["cohort_medians"]["roa"] == median(row["roa"] for row in companies)
    if symbols.startswith("AAL"):
        for values, status in (
            ("AAPL,aapl", 422),
            ("AAPL,,MSFT", 422),
            ("AAPL,MSFT,NVDA,WMT,TGT", 422),
            ("AAPL,unknown", 404),
        ):
            assert (
                real_api.get(
                    "/api/v1/companies/compare", params={"identifiers": values}
                ).status_code
                == status
            )


def test_common_year_cuts_history_and_does_not_borrow_forecasts(real_api: TestClient) -> None:
    """Historic comparison retains its annual facts and omits unavailable origin forecasts."""
    url = "/api/v1/companies/compare"
    params = {"identifiers": "AAPL,MSFT", "common_fiscal_year": 2024}
    response = real_api.get(url, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period_policy"] == "common_fiscal_year"
    for row in body["companies"]:
        assert row["fiscal_year"] == 2024
        assert row["model_version"] is None and row["pred_roa"] is None
        assert all(point["fiscal_year"] <= 2024 for point in body["historical_series"][row["cik"]])
    assert real_api.get(url, params={**params, "common_fiscal_year": 1999}).status_code == 422


def test_screener_annual_alignment_and_api_train_validation(tmp_path: Path) -> None:
    """Keep a newer quarter and its forecast out of screen, and calibrate an explicit API fit."""
    if not SQLITE.is_file():
        pytest.skip("The Stage 8 local SQLite snapshot is required")
    local = tmp_path / "test.sqlite3"
    with (
        closing(sqlite3.connect(SQLITE.as_uri() + "?mode=ro", uri=True)) as source,
        closing(sqlite3.connect(local)) as target,
    ):
        source.backup(target)
    url = f"sqlite:///{local.as_posix()}"
    engine = create_db_engine(url)
    try:
        with engine.begin() as connection:
            migration = Config(str(ROOT / "alembic.ini"))
            migration.attributes["connection"] = connection
            command.upgrade(migration, "head")
        with create_session_factory(engine).begin() as session:
            cider = session.scalar(select(Company).where(Company.ticker == "AAPL"))
            assert cider is not None
            quarter = FinancialStatement(
                company_id=cider.id,
                form_type="10-Q",
                fiscal_year=2026,
                fiscal_period="Q1",
                accession_number="quarter-fixture",
                period_end_date=date(2025, 12, 31),
                filed_date=date(2026, 2, 5),
            )
            session.add(quarter)
            session.flush()
            session.add(
                FinancialMetric(
                    company_id=cider.id,
                    statement_id=quarter.id,
                    fiscal_year=2026,
                    fiscal_period="Q1",
                    roa=10.0,
                    cluster_id=3,
                    pca_comp_1=10.0,
                )
            )
            session.add(
                ModelPrediction(
                    company_id=cider.id,
                    source_statement_id=quarter.id,
                    model_version="v1.1.0",
                    target_fiscal_year=2026,
                    target_fiscal_period="Q2",
                    distress_probability=0.99,
                )
            )
    finally:
        engine.dispose()
    app = create_app(
        Settings(
            _env_file=None,
            data_dir=tmp_path,
            DATABASE_URL=url,
            frontend_dir=ROOT / "frontend/legacy",
        )
    )
    app.state.model_registry = ModelRegistryState()
    app.state.model_registry.set(load_bundle(MODEL_DIR / "v1.1.0"))
    with TestClient(app) as client:
        sign_in(client, engine)
        apple = client.get("/api/v1/companies/AAPL").json()
        screens = client.get("/api/v1/companies").json()
        aapl = next(row for row in screens if row["ticker"] == "AAPL")
        assert aapl["latest_fiscal_year"] == 2025
        assert aapl["accession_number"] == apple["history"][-1]["accession_number"]
        assert aapl["roa"] == apple["history"][-1]["roa"] != 10.0
        assert aapl["distress_probability"] == apple["latest_prediction"]["distress_probability"]
        assert aapl["composite_health_score"] == apple["company"]["composite_health_score"]
        cluster = next(
            row for row in client.get("/api/v1/clusters/map").json() if row["ticker"] == "AAPL"
        )
        assert cluster["fiscal_year"] == 2025 and cluster["pca_comp_1"] != 10.0
        payload = {"train_end_year": 2021, "model_version": "isolated-stage9"}
        assert (
            client.post(
                "/api/v1/models/train", json={**payload, "validation_end_year": 2021}
            ).status_code
            == 422
        )
        response = client.post(
            "/api/v1/models/train", json={**payload, "validation_end_year": 2022}
        )
        assert response.status_code == 200, response.text
        report = response.json()["evaluation_report"]
        assert report["split_summary"]["validation_rows"] == 97
        assert report["split_summary"]["threshold_source"] == "validation_fiscal_years_2022_2022"
        assert report["probability_calibration"] is not None
        assert report["shap_margin_max_abs_error"] < 1e-5
        assert len(ML_FEATURE_COLUMNS) == 17
        default = client.post(
            "/api/v1/models/train",
            json={
                **payload,
                "model_version": "isolated-stage9-default",
            },
        )
        assert default.status_code == 200, default.text
        assert (
            default.json()["evaluation_report"]["probability_calibration"]
            == (report["probability_calibration"])
        )


def test_history_provenance_and_ui_controls(real_api: TestClient) -> None:
    """Expose full historical provenance on explicit export reads and deliver the controls."""
    result = real_api.get("/api/v1/companies/AAPL", params={"include_provenance": "true"})
    assert result.status_code == 200
    history = result.json()["history"]
    assert len(history) == 16
    assert all(
        row["field_provenance"]["total_assets"]["accn"] == row["accession_number"]
        for row in history
    )
    assert result.json()["quality_of_earnings"]["cash_conversion_qoe"] == pytest.approx(0.995286)
    all_companies = real_api.get("/api/v1/companies").json()
    first = real_api.get("/api/v1/companies", params={"limit": 1}).json()[0]
    assert first == all_companies[0]
    second = real_api.get("/api/v1/companies", params={"limit": 1, "offset": 1}).json()[0]
    assert second == all_companies[1]
    html = real_api.get("/").text
    assert '<html lang="vi">' in html
    assert 'id="panel-compare"' in html
    assert real_api.get("/static/account.html").status_code == 200
    assert real_api.get("/static/js/csv.js").status_code == 200


def test_csv_escaping_formula_protection_and_signed_numbers() -> None:
    """Execute the actual browser serializer using Node when the runtime is installed."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the browser serializer test")
    script = """
import fs from 'node:fs';
const source = fs.readFileSync('frontend/legacy/js/csv.js');
const {serializeCsv} = await import('data:text/javascript;base64,' + source.toString('base64'));
const {columns, rows} = JSON.parse(fs.readFileSync(0, 'utf8'));
const headings = {cik: 'CIK', name: 'Tên công ty'};
process.stdout.write(serializeCsv(columns, rows, (column) => headings[column] ?? column));
"""
    columns = ["cik", "name", "roa", "extra", "missing"]
    rows = [
        {
            "cik": "0000320193",
            "name": 'Issuer, "quoted"\r\nline',
            "roa": -0.125,
            "extra": formula,
            "missing": None,
        }
        for formula in ("=2+2", "+2+2", "-2+2", "@SUM(1,2)", " \t=2+2")
    ]
    output = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        input=json.dumps({"columns": columns, "rows": rows}).encode(),
        capture_output=True,
    ).stdout.decode()
    assert output.count("\r\n") == 11
    parsed = list(csv.DictReader(io.StringIO(output, newline="")))
    for actual, expected in zip(parsed, rows, strict=True):
        assert actual == {
            "CIK": "'0000320193",
            "Tên công ty": expected["name"],
            "roa": "-0.125",
            "extra": "'" + str(expected["extra"]),
            "missing": "",
        }
