"""Offline SMTP boundary tests for verified TLS and Gmail app-password formatting."""

import ssl
from email.message import EmailMessage
from types import TracebackType

import pytest

from finhealth.core import mail
from finhealth.core.config import Settings


def test_gmail_delivery_uses_verified_tls_and_normalized_app_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Send through the real email builder while replacing only external SMTP transport."""
    observed: dict[str, object] = {}

    class SmtpTransport:
        """Capture only the actual external network boundary."""

        def __init__(self, host: str, port: int, timeout: float) -> None:
            """Record connection parameters without establishing a network connection."""
            observed.update(host=host, port=port, timeout=timeout)

        def __enter__(self) -> "SmtpTransport":
            """Return this context-managed transport."""
            return self

        def __exit__(
            self,
            error_type: type[BaseException] | None,
            error: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            """Close the fake transport without swallowing errors."""

        def starttls(self, context: ssl.SSLContext) -> None:
            """Verify certificate validation cannot silently be disabled."""
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
            observed["tls"] = True

        def login(self, username: str, password: str) -> None:
            """Check grouping spaces are removed from a fictitious Gmail app password."""
            assert observed["tls"] is True
            assert username == "sender@example.com" and password == "aaaabbbbccccdddd"

        def send_message(self, message: EmailMessage) -> None:
            """Capture a fully formed recipient-specific email."""
            observed["recipient"] = message["To"]
            observed["body"] = message.get_content()

    monkeypatch.setattr(mail.smtplib, "SMTP", SmtpTransport)
    settings = Settings(
        _env_file=None, smtp_username="sender@example.com", smtp_password="aaaa bbbb cccc dddd"
    )
    mail.send_account_email(settings, "recipient@example.com", "FinHealth", "Verification link")
    assert observed["host"] == "smtp.gmail.com" and observed["port"] == 587
    assert observed["recipient"] == "recipient@example.com"
    assert observed["body"].strip() == "Verification link"
