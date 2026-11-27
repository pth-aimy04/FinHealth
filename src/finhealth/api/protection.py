"""Bound request bodies before JSON decoding and apply browser security headers."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestProtection:
    """Reject oversized buffered API bodies without trusting Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int = 2_000_000) -> None:
        """Configure a fixed two-megabyte limit for account and financial JSON requests."""
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Read a bounded API body, then replay it once to the downstream application."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        buffered: list[Message] = []
        if scope["method"] in ("POST", "PUT", "PATCH"):
            length = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                length += len(message.get("body", b""))
                if length > self.max_bytes:
                    await JSONResponse({"detail": "Request body exceeds 2 MB"}, 413)(
                        scope,
                        receive,
                        send,
                    )
                    return
                buffered.append(message)
                if not message.get("more_body", False):
                    break

        async def replay() -> Message:
            """Replay captured frames without reading the request into memory twice."""
            return buffered.pop(0) if buffered else await receive()

        async def secure_send(message: Message) -> None:
            """Set conservative headers without requiring unsafe inline JavaScript."""
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                    ]
                )
                if scope["path"].startswith("/api/v1/"):
                    headers.append((b"cache-control", b"no-store"))
                if scope["scheme"] == "https":
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                if not scope["path"].startswith(("/docs", "/redoc")):
                    headers.append(
                        (
                            b"content-security-policy",
                            b"default-src 'self'; "
                            b"script-src 'self'; style-src 'self' 'unsafe-inline'; "
                            b"img-src 'self' data: blob:; connect-src 'self'; "
                            b"object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
                            b"form-action 'self'",
                        )
                    )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, replay, secure_send)
