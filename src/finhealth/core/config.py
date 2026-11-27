"""Validated environment settings without import-time side effects."""

import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote, quote_plus

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from finhealth.core.constants import RANDOM_SEED


class Settings(BaseSettings):
    """Load typed settings from explicit values, the environment, and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
        allow_inf_nan=False,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    data_dir: Path = Path("data")
    raw_sec_dir: Path | None = None
    processed_parquet_dir: Path | None = None
    model_artifacts_dir: Path | None = None
    frontend_dir: Path = Path(__file__).resolve().parents[3] / "frontend"
    random_seed: int = RANDOM_SEED
    public_base_url: str = "http://localhost:8000"
    session_hours: int = Field(default=8, ge=1, le=72)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = Field(default=None, repr=False)
    mail_from_name: str = "FinHealth"
    mail_timeout_seconds: float = Field(default=15, gt=0, le=60)
    ingestion_worker_enabled: bool = False
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Documentation placeholder: configure a monitored contact before SEC requests.
    sec_user_agent: str = "FinHealthAcademicResearch/1.0 (research@example.com)"
    sec_rate_limit_per_sec: float = 8.0

    mssql_host: str = Field(default="ADMIN-PC", min_length=1)
    mssql_db: str = Field(default="finhealth_db", min_length=1)
    mssql_driver: str = Field(default="ODBC Driver 17 for SQL Server", min_length=1)
    postgres_user: str = Field(default="finhealth", min_length=1)
    postgres_password: SecretStr = SecretStr("finhealth_secret")
    postgres_host: str = Field(default="localhost", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = Field(default="finhealth_db", min_length=1)
    database_url_override: str | None = Field(
        default=None, validation_alias="DATABASE_URL", repr=False
    )

    @field_validator("sec_user_agent")
    @classmethod
    def validate_sec_user_agent(cls, value: str) -> str:
        """Require an application/version identifier and a contact email."""
        value = value.strip()
        match = re.fullmatch(
            r"([A-Za-z][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.+-]*)"
            r" \(([^\s@()<>]+@[^\s@()<>]+\.[^\s@()<>]+)\)",
            value,
        )
        generic_apps = {"python-requests", "python-httpx", "python-urllib", "curl", "wget"}
        if match is None or match.group(1).lower() in generic_apps:
            raise ValueError(
                "SEC_USER_AGENT must be AppName/Version (ContactEmail), "
                "with a non-generic application name and email contact"
            )
        return value

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        """Restrict account links to an explicit origin without user-controlled paths."""
        from urllib.parse import urlsplit

        parts = urlsplit(value)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or parts.path not in ("", "/")
            or (parts.scheme != "https" and parts.hostname not in ("localhost", "127.0.0.1"))
        ):
            raise ValueError("PUBLIC_BASE_URL must be an HTTPS origin (HTTP only on localhost)")
        return value.rstrip("/")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def validate_cors_allowed_origins(cls, value: object) -> object:
        """Accept a list or comma-separated string of non-empty CORS origin URLs."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return value

    @field_validator("sec_rate_limit_per_sec")
    @classmethod
    def validate_sec_rate_limit(cls, value: float) -> float:
        """Enforce a finite request rate within SEC Fair Access limits."""
        if not math.isfinite(value) or not 0 < value <= 10.0:
            raise ValueError("SEC_RATE_LIMIT_PER_SEC must be finite and > 0 and <= 10")
        return value

    def model_post_init(self, context: object) -> None:
        """Derive unset data paths from the configured data directory."""
        if self.app_env in ("staging", "production") and not self.public_base_url.startswith(
            "https://"
        ):
            raise ValueError("PUBLIC_BASE_URL must use HTTPS in staging and production")
        if self.raw_sec_dir is None:
            self.raw_sec_dir = self.data_dir / "raw" / "sec_edgar"
        if self.processed_parquet_dir is None:
            self.processed_parquet_dir = self.data_dir / "processed" / "parquet"
        if self.model_artifacts_dir is None:
            self.model_artifacts_dir = self.data_dir / "artifacts" / "models"

    @property
    def raw_sec_path(self) -> Path:
        """Return the resolved SEC cache path."""
        return self.raw_sec_dir or self.data_dir / "raw/sec_edgar"

    @property
    def parquet_path(self) -> Path:
        """Return the resolved processed data path."""
        return self.processed_parquet_dir or self.data_dir / "processed/parquet"

    @property
    def model_path(self) -> Path:
        """Return the resolved model registry path."""
        return self.model_artifacts_dir or self.data_dir / "artifacts/models"

    @property
    def database_url(self) -> str:
        """Select an explicit URL, explicit PostgreSQL settings, or the default SQL Server."""
        if self.database_url_override:
            return self.database_url_override
        if any(field.startswith("postgres_") for field in self.model_fields_set):
            return str(
                PostgresDsn.build(
                    scheme="postgresql+psycopg",
                    username=quote(self.postgres_user, safe=""),
                    password=quote(self.postgres_password.get_secret_value(), safe=""),
                    host=self.postgres_host,
                    port=self.postgres_port,
                    path=quote(self.postgres_db, safe=""),
                )
            )
        driver = quote_plus(self.mssql_driver)
        return (
            f"mssql+pyodbc://{quote(self.mssql_host, safe='')}/{quote(self.mssql_db, safe='')}"
            f"?driver={driver}&Encrypt=yes&TrustServerCertificate=yes"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings lazily; clear the cache after reconfiguration."""
    return Settings()
