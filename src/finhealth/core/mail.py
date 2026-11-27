"""Explicit SMTP delivery; no connections or credentials are created during import."""

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from finhealth.core.config import Settings


class EmailDeliveryError(Exception):
    """Account email could not be delivered; configure SMTP or retry later."""


def require_mail_configuration(settings: Settings) -> None:
    """Fail explicitly before account mutations when delivery is unavailable."""
    if not settings.smtp_username or not settings.smtp_password:
        raise EmailDeliveryError("Email is not configured; contact the FinHealth administrator")


def send_account_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    """Send only through authenticated STARTTLS with a verified server certificate."""
    require_mail_configuration(settings)
    username = settings.smtp_username
    secret = settings.smtp_password
    if not username or secret is None:
        raise EmailDeliveryError("Email is not configured; contact the FinHealth administrator")
    message = EmailMessage()
    message["From"] = formataddr((settings.mail_from_name, username))
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.mail_timeout_seconds,
        ) as server:
            server.starttls(context=ssl.create_default_context())
            password = secret.get_secret_value()
            if settings.smtp_host.lower() == "smtp.gmail.com":
                # Google displays app passwords in four-character groups for readability.
                password = password.replace(" ", "")
            server.login(username, password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        raise EmailDeliveryError("Email delivery failed; please retry later") from error
