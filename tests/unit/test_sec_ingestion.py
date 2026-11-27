"""Offline tests of real HTTP parsing, pacing, retry transitions, and atomic caches."""

import asyncio
import json
import time
from itertools import pairwise
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from finhealth.core.config import Settings
from finhealth.core.exceptions import (
    SecIngestionError,
    SecRateLimitError,
    SecResourceNotFoundError,
)
from finhealth.ingestion.rate_limiter import AsyncRateLimiter
from finhealth.ingestion.schemas import SecTickerEntry, is_manufacturing_sic, map_sic_to_sector
from finhealth.ingestion.sec_client import SecEdgarClient, atomic_write_json

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _fixture(name: str) -> dict[str, Any]:
    """Read an explicitly curated SEC-shaped fixture from disk."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Supply explicit offline configuration without consulting any real `.env`."""
    return Settings(
        _env_file=None,
        sec_user_agent="FinHealthTests/1.0 (tests@example.com)",
        sec_rate_limit_per_sec=10.0,
        data_dir=tmp_path,
        raw_sec_dir=tmp_path / "raw",
    )


@pytest.mark.asyncio
async def test_rate_limiter_enforces_minimum_interval() -> None:
    """Concurrent callers get separated admissions rather than an initial token burst."""
    limiter = AsyncRateLimiter(10.0)
    admissions: list[float] = []

    async def acquire() -> float:
        """Record the real admission timestamp before caller-side scheduling can skew it."""
        slept = await limiter.acquire()
        admitted = limiter._last_request_time
        assert admitted is not None
        admissions.append(admitted)
        return slept

    started = time.monotonic()
    slept = await asyncio.gather(*(acquire() for _ in range(4)))
    assert time.monotonic() - started >= 0.28
    assert all(b - a >= 0.099 for a, b in pairwise(admissions))
    assert slept[0] == 0.0


@pytest.mark.asyncio
async def test_rate_limiter_cancellation_and_context() -> None:
    """Cancellation while waiting releases the lock and consumes no admission."""
    limiter = AsyncRateLimiter(10.0)
    await limiter.acquire()
    previous = limiter._last_request_time
    waiting = asyncio.create_task(limiter.acquire())
    await asyncio.sleep(0.01)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    assert limiter._last_request_time == previous
    with pytest.raises(RuntimeError, match="context error"):
        async with limiter:
            raise RuntimeError("context error")
    assert limiter._last_request_time > previous
    for rate in (0.0, -1.0, 10.01, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            AsyncRateLimiter(rate)


def test_sic_to_sector_mapping() -> None:
    """Check manufacturing, retail, finance, all range endpoints, and invalid SICs."""
    assert map_sic_to_sector("3571") == "Manufacturing"
    assert is_manufacturing_sic(3571)
    assert map_sic_to_sector(5411) == "Retail Trade"
    assert not is_manufacturing_sic(5411)
    assert map_sic_to_sector("6021") == "Finance, Insurance and Real Estate"
    for lower, upper, sector in (
        (100, 999, "Agriculture, Forestry and Fishing"),
        (1000, 1499, "Mining"),
        (1500, 1799, "Construction"),
        (2000, 3999, "Manufacturing"),
        (4000, 4999, "Transportation, Communications and Utilities"),
        (5000, 5199, "Wholesale Trade"),
        (5200, 5999, "Retail Trade"),
        (6000, 6799, "Finance, Insurance and Real Estate"),
        (7000, 8999, "Services"),
        (9100, 9999, "Public Administration"),
    ):
        assert map_sic_to_sector(lower) == map_sic_to_sector(upper) == sector
    for invalid in (
        None,
        "invalid",
        "",
        0,
        1800,
        6800,
        9000,
        10000,
        -2000,
        True,
        3571.5,
        "３５７１",
    ):
        assert map_sic_to_sector(invalid) == "Unknown"
        assert not is_manufacturing_sic(invalid)
    entry = SecTickerEntry.from_sec_raw({"cik_str": 320193, "ticker": " aapl ", "title": "Apple"})
    assert (entry.cik, entry.ticker) == ("0000320193", "AAPL")
    with pytest.raises(ValidationError):
        SecTickerEntry.from_sec_raw({"cik_str": "invalid", "ticker": "", "title": "Apple"})


@pytest.mark.asyncio
async def test_fetch_tickers_and_resolve_cik_with_cache(settings: Settings) -> None:
    """Assert exact headers/URL and that cache hits perform no further HTTP calls."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Provide the real SEC string-indexed contract at the HTTP boundary."""
        calls.append(request)
        assert str(request.url) == "https://www.sec.gov/files/company_tickers.json"
        assert request.headers["User-Agent"] == settings.sec_user_agent
        assert request.headers["Accept"] == "application/json"
        assert request.headers["Accept-Encoding"] == "gzip, deflate"
        return httpx.Response(200, json=_fixture("sec_company_tickers_sample.json"))

    async with SecEdgarClient(settings, httpx.MockTransport(handler)) as client:
        assert [entry.ticker for entry in await client.fetch_company_tickers()] == [
            "AAPL",
            "MSFT",
            "TSLA",
        ]
        assert (await client.resolve_cik("aapl")).cik == "0000320193"
        assert (await client.resolve_cik("320193")).cik == "0000320193"
        assert (await client.resolve_cik("CIK0000789019")).ticker == "MSFT"
        with pytest.raises(SecResourceNotFoundError):
            await client.resolve_cik("AAP")
        assert len(calls) == 1
        await client.fetch_company_tickers(force_refresh=True)
        assert len(calls) == 2
    assert (settings.raw_sec_dir / "company_tickers.json").is_file()


@pytest.mark.asyncio
async def test_fetch_company_metadata_cache_and_no_tickers(settings: Settings) -> None:
    """Extract true submissions fields and preserve registrants without listed tickers."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a submissions response with optional ticker absence on refresh."""
        nonlocal calls
        calls += 1
        assert request.url.path == "/submissions/CIK0000320193.json"
        payload = _fixture("sec_submissions_0000320193_sample.json")
        if calls == 2:
            payload["tickers"] = []
        return httpx.Response(200, json=payload)

    async with SecEdgarClient(settings, httpx.MockTransport(handler)) as client:
        metadata = await client.fetch_company_metadata(320193)
        assert (metadata.cik, metadata.name, metadata.ticker) == (
            "0000320193",
            "Apple Inc.",
            "AAPL",
        )
        assert (metadata.sic_code, metadata.sic_description, metadata.sector) == (
            "3571",
            "ELECTRONIC COMPUTERS",
            "Manufacturing",
        )
        assert await client.fetch_company_metadata("320193") == metadata
        assert calls == 1
        assert (await client.fetch_company_metadata(320193, force_refresh=True)).ticker is None
        assert calls == 2


@pytest.mark.asyncio
async def test_fetch_company_facts_retry_on_503_and_atomic_save(settings: Settings) -> None:
    """503 -> 503 -> 200 retries real requests, persists once, then serves cached facts."""
    calls: list[float] = []
    payload = _fixture("sec_companyfacts_0000320193_sample.json")
    limiter = AsyncRateLimiter(settings.sec_rate_limit_per_sec)

    def handler(request: httpx.Request) -> httpx.Response:
        """Model temporary SEC failures without mocking the client under test."""
        admitted = limiter._last_request_time
        assert admitted is not None
        calls.append(admitted)
        assert request.url.path == "/api/xbrl/companyfacts/CIK0000320193.json"
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json=payload)

    async with SecEdgarClient(
        settings, httpx.MockTransport(handler), retry_base_delay=0.01, rate_limiter=limiter
    ) as client:
        path, received = await client.fetch_company_facts(320193)
        assert received == payload
        assert len(calls) == 3
        assert all(b - a >= 0.099 for a, b in pairwise(calls))
        assert path == settings.raw_sec_dir / "companyfacts" / "CIK0000320193.json"
        assert json.loads(path.read_text(encoding="utf-8")) == payload
        assert not list(path.parent.glob("*.tmp"))
        assert await client.fetch_company_facts(320193) == (path, received)
        assert len(calls) == 3


@pytest.mark.asyncio
async def test_refresh_archives_existing_cache_and_new_response(settings: Settings) -> None:
    """Retain an older pre-versioning cache when a real client receives a new snapshot."""
    original = _fixture("sec_companyfacts_0000320193_sample.json")
    replacement = {**original, "entityName": "Updated fixture issuer name"}
    path = settings.raw_sec_dir / "companyfacts" / "CIK0000320193.json"
    atomic_write_json(path, original)

    def handler(request: httpx.Request) -> httpx.Response:
        """Provide the replacement only at the external HTTP boundary."""
        return httpx.Response(200, json=replacement)

    async with SecEdgarClient(settings, httpx.MockTransport(handler)) as client:
        _, received = await client.fetch_company_facts(320193, force_refresh=True)
    assert received == replacement
    archive = path.parent / "versions" / path.stem
    snapshots = [json.loads(file.read_bytes()) for file in archive.glob("*.json")]
    assert len(snapshots) == 2 and original in snapshots and replacement in snapshots
    assert json.loads(path.read_bytes()) == replacement


@pytest.mark.asyncio
async def test_fetch_company_facts_no_retry_on_404_or_403(settings: Settings) -> None:
    """Permanent SEC errors must not consume retry attempts or create disk files."""
    for status, expected in ((404, SecResourceNotFoundError), (403, SecRateLimitError)):
        calls = 0

        def handler(request: httpx.Request, status: int = status) -> httpx.Response:
            """Return the permanent status for this HTTP test case."""
            nonlocal calls
            calls += 1
            return httpx.Response(status)

        async with SecEdgarClient(settings, httpx.MockTransport(handler)) as client:
            with pytest.raises(expected):
                await client.fetch_company_facts(320193)
        assert calls == 1
    assert not (settings.raw_sec_dir / "companyfacts").exists()


@pytest.mark.asyncio
async def test_retry_exhaustion_transport_and_exponential_backoff(settings: Settings) -> None:
    """Transport failures and 429 use bounded attempts and exponentially increasing delays."""
    for status in (429, 500, 502, 504, "timeout", "connection"):
        calls: list[float] = []

        def handler(
            request: httpx.Request, status: int | str = status, calls: list[float] = calls
        ) -> httpx.Response:
            """Simulate a repeated external failure while preserving HTTP client behavior."""
            calls.append(time.monotonic())
            if status == "timeout":
                raise httpx.ReadTimeout("SEC timeout", request=request)
            if status == "connection":
                raise httpx.ConnectError("SEC connection failure", request=request)
            return httpx.Response(status)

        async with SecEdgarClient(
            settings, httpx.MockTransport(handler), max_retries=2, retry_base_delay=0.11
        ) as client:
            expected = SecRateLimitError if status == 429 else SecIngestionError
            with pytest.raises(expected, match="retries exhausted"):
                await client.fetch_company_facts(320193)
        assert len(calls) == 3
        # Windows timer resolution can wake sleeps slightly early; retain a small tolerance.
        assert calls[1] - calls[0] >= 0.105
        assert calls[2] - calls[1] >= 0.21


@pytest.mark.asyncio
async def test_invalid_responses_and_cache_preserve_existing_data(settings: Settings) -> None:
    """Malformed HTTP data, wrong CIKs, redirects, and corrupt caches fail explicitly."""
    path = settings.raw_sec_dir / "companyfacts" / "CIK0000320193.json"
    original = _fixture("sec_companyfacts_0000320193_sample.json")
    atomic_write_json(path, original)
    responses = [
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"cik": 320193, "entityName": "Apple"}),
        httpx.Response(200, json={"cik": 1, "entityName": "Other", "facts": {}}),
        httpx.Response(400),
        httpx.Response(302, headers={"Location": "https://example.com"}),
    ]
    for response in responses:
        calls = 0

        def handler(request: httpx.Request, response: httpx.Response = response) -> httpx.Response:
            """Return an invalid response and count attempts at the HTTP boundary."""
            nonlocal calls
            calls += 1
            return response

        async with SecEdgarClient(settings, httpx.MockTransport(handler)) as client:
            with pytest.raises(SecIngestionError):
                await client.fetch_company_facts(320193, force_refresh=True)
        assert calls == 1
        assert json.loads(path.read_text(encoding="utf-8")) == original
    path.write_text("{broken", encoding="utf-8")
    async with SecEdgarClient(settings, httpx.MockTransport(handler)) as client:
        with pytest.raises(SecIngestionError, match="Cannot read"):
            await client.fetch_company_facts(320193)


def test_atomic_write_failure_preserves_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure at the atomic replacement boundary leaves the previous JSON intact."""
    path = tmp_path / "cache.json"
    atomic_write_json(path, {"old": 1})

    def fail_replace(self: Path, target: Path) -> Path:
        """Simulate an OS failure at the disk boundary rather than bypassing persistence."""
        raise OSError("replacement failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(SecIngestionError) as error:
        atomic_write_json(path, {"new": 2})
    assert isinstance(error.value.__cause__, OSError)
    assert json.loads(path.read_text(encoding="utf-8")) == {"old": 1}
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.asyncio
async def test_shared_limiter_and_transport_recovery(settings: Settings) -> None:
    """Two clients sharing a limiter pace transport-error retries as well as successes."""
    admissions: list[float] = []
    requests: list[httpx.Request] = []

    class RecordingLimiter(AsyncRateLimiter):
        """Observe admissions at the limiter boundary before HTTPX builds the request."""

        async def acquire(self) -> float:
            """Record the timestamp assigned by the real limiter."""
            slept = await super().acquire()
            assert self._last_request_time is not None
            admissions.append(self._last_request_time)
            return slept

    limiter = RecordingLimiter(10.0)

    def handler(request: httpx.Request) -> httpx.Response:
        """Fail the first transport attempt, then return authentic ticker-shaped fixtures."""
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ConnectError("transient", request=request)
        return httpx.Response(200, json=_fixture("sec_company_tickers_sample.json"))

    async with (
        SecEdgarClient(
            settings, httpx.MockTransport(handler), retry_base_delay=0, rate_limiter=limiter
        ) as first,
        SecEdgarClient(settings, httpx.MockTransport(handler), rate_limiter=limiter) as second,
    ):
        results = await asyncio.gather(
            first.fetch_company_tickers(force_refresh=True),
            second.fetch_company_tickers(force_refresh=True),
        )
    assert results[0] == results[1]
    assert len(admissions) == len(requests) == 3
    assert all(b - a >= 0.099 for a, b in pairwise(admissions))


@pytest.mark.asyncio
async def test_invalid_metadata_and_ticker_contracts(settings: Settings) -> None:
    """Reject malformed indexed dictionaries and submissions before writing any cache."""
    for payload in ({"tickers": []}, {"0": []}, {"0": {"cik_str": "invalid"}}):

        def ticker_handler(
            request: httpx.Request, payload: dict[str, Any] = payload
        ) -> httpx.Response:
            """Serve a broken external ticker contract."""
            return httpx.Response(200, json=payload)

        async with SecEdgarClient(settings, httpx.MockTransport(ticker_handler)) as client:
            with pytest.raises(SecIngestionError, match="tickers payload"):
                await client.fetch_company_tickers()
        assert not (settings.raw_sec_dir / "company_tickers.json").exists()
    for updates in ({"cik": 1}, {"name": None}, {"tickers": "AAPL"}, {"sic": []}):
        payload = _fixture("sec_submissions_0000320193_sample.json") | updates

        def metadata_handler(
            request: httpx.Request, payload: dict[str, Any] = payload
        ) -> httpx.Response:
            """Serve submissions with an invalid required field or identity."""
            return httpx.Response(200, json=payload)

        async with SecEdgarClient(settings, httpx.MockTransport(metadata_handler)) as client:
            with pytest.raises(SecIngestionError, match="submissions payload"):
                await client.fetch_company_metadata(320193)
        assert not (settings.raw_sec_dir / "submissions").exists()
