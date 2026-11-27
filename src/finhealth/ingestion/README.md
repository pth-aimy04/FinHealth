Use one `SecEdgarClient` in an async context for all concurrent ingestion tasks.
Every HTTP attempt, including retries, uses its shared monotonic limiter. If multiple
clients are necessary on the same event loop, pass the same `rate_limiter=` instance
to all of them. A supplied limiter cannot exceed the client's configured rate.

This limiter coordinates one event loop, not independent processes or machines.
Run a single ingestion dispatcher per SEC identity, routing all worker requests
through it. Multi-machine deployments require a central dispatcher or distributed
limiter before enabling independent HTTP clients. The <=10 requests/second SEC
cap applies to the aggregate traffic, not to each client separately.

The raw cache also requires a single writer process. Writes use a process-local
thread lock, a flushed/fsynced `.json.tmp` file, and an atomic same-directory
replacement. Existing valid files survive validation or replacement failures.
Corrupt caches fail explicitly; use `force_refresh=True` to replace them. There is
no automatic cache expiry. Raw responses remain unchanged for provenance.

`max_retries` counts additional attempts (three means at most four HTTP attempts).
403 and 404 fail immediately. Only 429, 500, 502, 503, 504 and HTTPX transport errors
retry, using exponential backoff and the limiter on each attempt. Redirects are
not followed automatically, so an unthrottled redirected request cannot escape
the limiter. Call `aclose()` if not using the async context manager.
