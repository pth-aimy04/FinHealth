"""Async SEC JSON retrieval with bounded retries and validated atomic disk caches."""

import asyncio
import json
import math
import os
from hashlib import sha256
from pathlib import Path
from threading import RLock
from types import TracebackType
from typing import Any

import httpx
from pydantic import ValidationError

from finhealth.core.config import Settings, get_settings
from finhealth.core.exceptions import (
    SecIngestionError,
    SecRateLimitError,
    SecResourceNotFoundError,
)
from finhealth.db.repositories import normalize_cik
from finhealth.ingestion.rate_limiter import AsyncRateLimiter
from finhealth.ingestion.schemas import (
    CompanyMetadata,
    SecTickerEntry,
    map_sic_to_sector,
    sec_report_dates,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANY_FACTS_URL_TEMPLATE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_WRITE_LOCK = RLock()


def atomic_write_json(target_path: Path, payload: dict[str, Any]) -> Path:
    """Flush a same-directory temporary file and atomically replace a JSON cache.

    A process-local lock serializes threads writing the specified .json.tmp path.
    Cache directories must have a single writer process (see ingestion README).
    """
    temporary = target_path.with_suffix(".json.tmp")
    with _WRITE_LOCK:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with temporary.open("w", encoding="utf-8") as stream:
                    json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(target_path)
            finally:
                temporary.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError) as error:
            raise SecIngestionError(f"Cannot persist SEC JSON cache: {target_path}") from error
    return target_path


def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object or fail explicitly rather than silently trusting corrupt caches."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SecIngestionError(f"Cannot read SEC JSON cache: {path}") from error
    if not isinstance(payload, dict):
        raise SecIngestionError(f"SEC JSON cache must contain an object: {path}")
    return payload


def _capture_version(path: Path, payload: dict[str, Any]) -> None:
    """Keep each distinct validated source response before refreshing the cache pointer."""
    with _WRITE_LOCK:
        snapshots = [_read_json(path), payload] if path.is_file() else [payload]
        for snapshot in snapshots:
            encoded = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False)
            digest = sha256(encoded.encode()).hexdigest()
            archive = path.parent / "versions" / path.stem / f"{digest}.json"
            if not archive.is_file():
                atomic_write_json(archive, snapshot)
        atomic_write_json(path, payload)


class SecEdgarClient:
    """Retrieve SEC resources; reuse one client across concurrent tasks per SEC identity."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
        *,
        rate_limiter: AsyncRateLimiter | None = None,
    ) -> None:
        """Initialize a bounded HTTP client without issuing any network requests."""
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise ValueError("max_retries must be a nonnegative integer")
        if not math.isfinite(retry_base_delay) or retry_base_delay < 0:
            raise ValueError("retry_base_delay must be finite and nonnegative")
        self.settings = settings if settings is not None else get_settings()
        self.rate_limiter = rate_limiter or AsyncRateLimiter(self.settings.sec_rate_limit_per_sec)
        if self.rate_limiter.min_interval < 1 / self.settings.sec_rate_limit_per_sec:
            raise ValueError("Shared limiter cannot be faster than the configured SEC rate")
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
            headers={
                "User-Agent": self.settings.sec_user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            },
        )

    async def __aenter__(self) -> "SecEdgarClient":
        """Open the async HTTP client's context."""
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close pooled HTTP connections without suppressing errors."""
        await self._client.__aexit__(exc_type, exc, traceback)

    async def aclose(self) -> None:
        """Close connections when the client was used without an async context."""
        await self._client.aclose()

    async def _get_json(self, url: str) -> dict[str, Any]:
        """Throttle every attempt and retry only transient transport and HTTP failures."""
        for attempt in range(self.max_retries + 1):
            await self.rate_limiter.acquire()
            try:
                response = await self._client.get(url)
            except httpx.TransportError as error:
                if attempt == self.max_retries:
                    raise SecIngestionError(f"SEC transport retries exhausted: {url}") from error
            else:
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError as error:
                        raise SecIngestionError(f"Invalid SEC JSON: {url}") from error
                    if not isinstance(payload, dict):
                        raise SecIngestionError(f"SEC JSON must contain an object: {url}")
                    return payload
                if response.status_code == 404:
                    raise SecResourceNotFoundError(f"SEC resource not found: {url}")
                if response.status_code == 403:
                    raise SecRateLimitError(
                        f"SEC access forbidden (403) for {url}. Check User-Agent or IP block."
                    )
                if response.status_code not in {429, 500, 502, 503, 504}:
                    raise SecIngestionError(f"Unexpected SEC HTTP {response.status_code}: {url}")
                if attempt == self.max_retries:
                    error_type = (
                        SecRateLimitError if response.status_code == 429 else SecIngestionError
                    )
                    raise error_type(f"SEC HTTP {response.status_code} retries exhausted: {url}")
            await asyncio.sleep(self.retry_base_delay * (2**attempt))
        raise SecIngestionError(f"SEC retry loop ended unexpectedly: {url}")

    async def fetch_company_tickers(self, force_refresh: bool = False) -> list[SecTickerEntry]:
        """Fetch or read the actual string-indexed SEC ticker dictionary."""
        path = self.settings.raw_sec_path / "company_tickers.json"
        cached = path.exists() and not force_refresh
        payload = _read_json(path) if cached else await self._get_json(TICKERS_URL)
        try:
            if any(not key.isascii() or not key.isdigit() for key in payload):
                raise ValueError("SEC ticker dictionary keys must be string indices")
            if any(not isinstance(raw, dict) for raw in payload.values()):
                raise ValueError("SEC ticker dictionary entries must be objects")
            entries = [SecTickerEntry.from_sec_raw(raw) for raw in payload.values()]
        except (ValueError, ValidationError) as error:
            raise SecIngestionError("Invalid SEC company tickers payload") from error
        if not cached:
            atomic_write_json(path, payload)
        return entries

    async def resolve_cik(self, ticker_or_cik: str) -> SecTickerEntry:
        """Resolve an exact ticker or canonical CIK through the cached SEC universe."""
        query = ticker_or_cik.strip()
        try:
            cik = normalize_cik(query)
        except ValueError:
            cik = None
        for entry in await self.fetch_company_tickers():
            if entry.ticker == query.upper() or entry.cik == cik:
                return entry
        raise SecResourceNotFoundError(f"SEC ticker or CIK not found: {ticker_or_cik}")

    async def fetch_company_metadata(
        self, cik: str | int, force_refresh: bool = False
    ) -> CompanyMetadata:
        """Validate submissions identity and extract primary ticker and SIC sector."""
        cik = normalize_cik(cik)
        path = self.settings.raw_sec_path / "submissions" / f"CIK{cik}.json"
        cached = path.exists() and not force_refresh
        payload = (
            _read_json(path)
            if cached
            else await self._get_json(SUBMISSIONS_URL_TEMPLATE.format(cik=cik))
        )
        try:
            if normalize_cik(payload.get("cik")) != cik:
                raise ValueError("Submissions CIK does not match the requested registrant")
            tickers = payload.get("tickers", [])
            if not isinstance(tickers, list) or any(not isinstance(t, str) for t in tickers):
                raise ValueError("Submissions tickers must be a list of strings")
            sic = payload.get("sic")
            if sic is not None and (isinstance(sic, bool) or not isinstance(sic, (str, int))):
                raise ValueError("Submissions SIC must be a string or integer")
            metadata = CompanyMetadata(
                cik=cik,
                name=payload.get("name") or "",
                ticker=tickers[0] if tickers else None,
                sic_code=str(sic).strip() if sic is not None else None,
                sic_description=payload.get("sicDescription"),
                sector=map_sic_to_sector(sic),
                quarter_report_dates=sec_report_dates(payload, "10-Q"),
                amendment_report_dates=sec_report_dates(payload, "10-K/A", "10-Q/A"),
            )
        except (AttributeError, KeyError, TypeError, ValueError, ValidationError) as error:
            raise SecIngestionError("Invalid SEC submissions payload") from error
        if not cached:
            atomic_write_json(path, payload)
        return metadata

    async def fetch_company_facts(
        self, cik: str | int, force_refresh: bool = False
    ) -> tuple[Path, dict[str, Any]]:
        """Return validated raw companyfacts and its atomically persisted cache path."""
        cik = normalize_cik(cik)
        path = self.settings.raw_sec_path / "companyfacts" / f"CIK{cik}.json"
        cached = path.exists() and not force_refresh
        payload = (
            _read_json(path)
            if cached
            else await self._get_json(COMPANY_FACTS_URL_TEMPLATE.format(cik=cik))
        )
        try:
            if normalize_cik(payload.get("cik")) != cik:
                raise ValueError("Companyfacts CIK does not match the requested registrant")
            if not isinstance(payload.get("entityName"), str):
                raise ValueError("Companyfacts must contain entityName")
            if not isinstance(payload.get("facts"), dict):
                raise ValueError("Companyfacts must contain a facts object")
        except ValueError as error:
            raise SecIngestionError("Invalid SEC companyfacts payload") from error
        if not cached:
            _capture_version(path, payload)
        return path, payload
