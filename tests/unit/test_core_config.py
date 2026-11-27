"""Offline settings validation and accounting vocabulary invariants."""

from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from pydantic import ValidationError

from finhealth.core.config import Settings
from finhealth.core.constants import RANDOM_SEED, SUPPORTED_FORMS, US_GAAP_TAG_FALLBACKS

VALID_AGENT = "FinHealthResearch/1.0 (research@example.com)"


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent developer environment variables or `.env` from affecting tests."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.delenv(field.lower(), raising=False)


def test_valid_configuration_and_database_url() -> None:
    """Check defaults and a PostgreSQL URL built from explicit components."""
    settings = Settings(
        sec_user_agent=VALID_AGENT,
        postgres_user="analyst",
        postgres_password="test-secret",
        postgres_host="db.example.com",
        postgres_port=5433,
        postgres_db="research",
    )
    assert settings.database_url == (
        "postgresql+psycopg://analyst:test-secret@db.example.com:5433/research"
    )
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.random_seed == RANDOM_SEED == 42
    assert settings.sec_rate_limit_per_sec == 8.0
    assert settings.raw_sec_dir == Path("data/raw/sec_edgar")
    assert settings.processed_parquet_dir == Path("data/processed/parquet")
    assert settings.model_artifacts_dir == Path("data/artifacts/models")
    assert "test-secret" not in repr(settings)


def test_database_url_escapes_credentials() -> None:
    """Reserved characters cannot change the host or credential boundaries."""
    settings = Settings(
        sec_user_agent=VALID_AGENT,
        postgres_user="analyst@example.com",
        postgres_password="p@ss:/?#% word",
    )
    parsed = urlsplit(settings.database_url)
    assert parsed.hostname == "localhost"
    assert parsed.port == 5432
    assert unquote(parsed.username or "") == "analyst@example.com"
    assert unquote(parsed.password or "") == "p@ss:/?#% word"
    assert parsed.path == "/finhealth_db"
    assert parsed.query == ""
    assert parsed.fragment == ""


def test_database_url_defaults_to_sql_server(tmp_path: Path) -> None:
    """Use SQL Server by default until another database is explicitly configured."""
    data = tmp_path / "data"
    settings = Settings(sec_user_agent=VALID_AGENT, data_dir=data)
    assert settings.database_url == (
        "mssql+pyodbc://ADMIN-PC/finhealth_db"
        "?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes"
    )
    assert not data.exists()


def test_dotenv_loading_and_environment_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Load typed `.env` values while respecting environment and init overrides."""
    (tmp_path / ".env").write_text(
        f'SEC_USER_AGENT="{VALID_AGENT}"\n'
        "APP_ENV=test\nRANDOM_SEED=17\nSEC_RATE_LIMIT_PER_SEC=4.5\n"
        "POSTGRES_HOST=dotenv-db\nPOSTGRES_PASSWORD=dotenv-secret\n"
        "POSTGRES_PORT=5434\nPOSTGRES_DB=dotenv_db\nDATA_DIR=financial-data\n",
        encoding="utf-8",
    )
    loaded = Settings()
    assert loaded.sec_user_agent == VALID_AGENT
    assert loaded.app_env == "test"
    assert loaded.random_seed == 17
    assert loaded.sec_rate_limit_per_sec == 4.5
    assert loaded.postgres_port == 5434
    assert loaded.raw_sec_dir == Path("financial-data/raw/sec_edgar")
    assert loaded.database_url == (
        "postgresql+psycopg://finhealth:dotenv-secret@dotenv-db:5434/dotenv_db"
    )
    monkeypatch.setenv("SEC_RATE_LIMIT_PER_SEC", "6")
    assert Settings().sec_rate_limit_per_sec == 6.0
    assert Settings(sec_rate_limit_per_sec=7.0).sec_rate_limit_per_sec == 7.0


def test_data_paths_derive_from_root_with_explicit_override(tmp_path: Path) -> None:
    """Custom roots propagate without overwriting explicit paths or creating data."""
    root = tmp_path / "custom-data"
    override = tmp_path / "external-raw"
    settings = Settings(sec_user_agent=VALID_AGENT, data_dir=root, raw_sec_dir=override)
    assert settings.raw_sec_dir == override
    assert settings.processed_parquet_dir == root / "processed" / "parquet"
    assert settings.model_artifacts_dir == root / "artifacts" / "models"
    assert not root.exists()
    assert not override.exists()


def test_example_environment_loads() -> None:
    """The committed onboarding example must load using the actual settings model."""
    example = Path(__file__).resolve().parents[2] / ".env.example"
    settings = Settings(_env_file=example)
    assert settings.sec_user_agent == "FinHealthAcademicResearch/1.0 (research@example.com)"
    assert settings.database_url == (
        "mssql+pyodbc://ADMIN-PC/finhealth_db"
        "?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes"
    )


@pytest.mark.parametrize(
    "agent",
    [
        "",
        "   ",
        "FinHealth/1.0",
        "research@example.com",
        "python-requests",
        "python-requests/2.31.0 (research@example.com)",
        "python-httpx/0.27.0 (research@example.com)",
        "curl/8.0 (research@example.com)",
        "FinHealth/1.0 (missing-email)",
        "FinHealth/1.0 (@example.com)",
        "FinHealth/1.0 (research@)",
        "FinHealth/1.0 (research@example.com)\r\nInjected: header",
    ],
)
def test_invalid_sec_user_agent_is_rejected(agent: str) -> None:
    """Reject missing contact information, generic clients, and header injection."""
    with pytest.raises(ValidationError) as error:
        Settings(sec_user_agent=agent)
    assert error.value.errors()[0]["loc"] == ("sec_user_agent",)


def test_sec_user_agent_uses_documentation_default() -> None:
    """Keep the default free of personal contact details."""
    assert Settings().sec_user_agent == (
        "FinHealthAcademicResearch/1.0 (research@example.com)"
    )


def test_sec_user_agent_trims_surrounding_whitespace() -> None:
    """Normalize surrounding whitespace without changing the declared identity."""
    assert Settings(sec_user_agent=f"  {VALID_AGENT}  ").sec_user_agent == VALID_AGENT


@pytest.mark.parametrize("rate", [10.01, 11.0, 0.0, -1.0, float("inf"), float("nan")])
def test_invalid_sec_rate_is_rejected(rate: float) -> None:
    """Rates must be positive, finite, and within SEC's maximum."""
    with pytest.raises(ValidationError) as error:
        Settings(sec_user_agent=VALID_AGENT, sec_rate_limit_per_sec=rate)
    assert error.value.errors()[0]["loc"] == ("sec_rate_limit_per_sec",)


@pytest.mark.parametrize("rate", [0.001, 8.0, 10.0])
def test_valid_sec_rate_boundaries(rate: float) -> None:
    """Allow positive fractional rates and the inclusive upper boundary."""
    settings = Settings(sec_user_agent=VALID_AGENT, sec_rate_limit_per_sec=rate)
    assert settings.sec_rate_limit_per_sec == rate


def test_assignment_cannot_bypass_sec_rate_validation() -> None:
    """Reject invalid runtime updates as well as invalid initial settings."""
    settings = Settings(sec_user_agent=VALID_AGENT)
    with pytest.raises(ValidationError):
        settings.sec_rate_limit_per_sec = 11.0
    assert settings.sec_rate_limit_per_sec == 8.0


def test_accounting_concepts_have_nonempty_ordered_tag_candidates() -> None:
    """Require every Stage 1 concept and valid local-name candidate tuples."""
    required = {
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
        "revenues",
        "net_income",
        "operating_income",
        "operating_cash_flow",
        "current_assets",
        "current_liabilities",
        "retained_earnings",
        "eps_basic",
        "eps_diluted",
        "cash_and_equivalents",
        "interest_expense",
        "capex",
    }
    assert set(US_GAAP_TAG_FALLBACKS) == required
    for concept, tags in US_GAAP_TAG_FALLBACKS.items():
        assert isinstance(tags, tuple), concept
        assert len(tags) > 0, concept
        assert len(tags) == len(set(tags)), concept
        for tag in tags:
            assert isinstance(tag, str), concept
            assert tag and tag.isidentifier() and tag[0].isupper(), (concept, tag)
    assert US_GAAP_TAG_FALLBACKS["total_liabilities"] == ("Liabilities",)
    assert US_GAAP_TAG_FALLBACKS["stockholders_equity"] == ("StockholdersEquity",)
    assert US_GAAP_TAG_FALLBACKS["revenues"][0] == (
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    )
    assert US_GAAP_TAG_FALLBACKS["operating_cash_flow"] == (
        "NetCashProvidedByUsedInOperatingActivities",
    )
    assert SUPPORTED_FORMS == ("10-K", "10-Q")
