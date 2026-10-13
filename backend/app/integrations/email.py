"""Real transports; message bodies and credentials are never logged."""
import asyncio
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from html import escape
from typing import Protocol

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class OutboundEmail:
    recipient: str = field(repr=False)
    subject: str = field(repr=False)
    text_body: str = field(repr=False)
    message_key: str = ""
    expires_at: datetime | None = field(default=None, repr=False)


class DeliveryError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False, uncertain: bool = False, retry_after: int = 0):
        self.code, self.retryable, self.uncertain, self.retry_after = code, retryable, uncertain, retry_after
        super().__init__(code)


class TransactionalEmailProvider(Protocol):
    name: str
    supports_idempotency: bool
    @property
    def is_configured(self) -> bool: ...
    async def send(self, email: OutboundEmail) -> str: ...


class ResendProvider:
    name = "resend"
    supports_idempotency = True
    @property
    def is_configured(self):
        settings = get_settings()
        return bool(settings.email_from and settings.email_api_key)

    async def send(self, email: OutboundEmail) -> str:
        settings = get_settings()
        if email.expires_at and (email.expires_at - datetime.now(UTC)).total_seconds() <= 8:
            raise DeliveryError("MESSAGE_EXPIRED")
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
                response = await client.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {settings.email_api_key}",
                    "Idempotency-Key": email.message_key}, json={"from": settings.email_from, "to": [email.recipient],
                    "subject": email.subject, "text": email.text_body,
                    "html": f"<main style='font-family:Arial,sans-serif;max-width:600px'><h1>CareerPilot</h1><p style='white-space:pre-line'>{escape(email.text_body)}</p></main>"})
        except httpx.RequestError:
            raise DeliveryError("PROVIDER_UNREACHABLE", retryable=True, uncertain=True) from None
        if response.status_code == 429:
            value = response.headers.get("Retry-After", "60")
            wait = int(value) if value.isdigit() else 60
            raise DeliveryError("PROVIDER_QUOTA", retryable=True, retry_after=min(max(wait, 1), 3600))
        if response.status_code >= 500:
            raise DeliveryError("PROVIDER_OUTAGE", retryable=True, uncertain=True)
        if not response.is_success:
            raise DeliveryError("PROVIDER_REJECTED")
        try:
            identifier = response.json().get("id")
        except (ValueError, AttributeError):
            raise DeliveryError("PROVIDER_INVALID_RESPONSE", uncertain=True) from None
        if not isinstance(identifier, str) or len(identifier) > 200:
            raise DeliveryError("PROVIDER_INVALID_RESPONSE", uncertain=True)
        return identifier


class SMTPProvider:
    name = "smtp"
    supports_idempotency = False
    @property
    def is_configured(self):
        settings = get_settings()
        return bool(settings.email_from and settings.smtp_host and settings.smtp_username and settings.smtp_password)

    async def send(self, email: OutboundEmail) -> str:
        def deliver():
            settings = get_settings()
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = settings.email_from, email.recipient, email.subject
            message["Message-ID"] = f"<{email.message_key}@careerpilot.local>"
            message.set_content(email.text_body)
            factory = smtplib.SMTP_SSL if settings.smtp_tls == "ssl" else smtplib.SMTP
            try:
                with factory(settings.smtp_host, settings.smtp_port, timeout=8) as client:
                    if settings.smtp_tls == "starttls":
                        client.starttls(context=ssl.create_default_context())
                    client.login(settings.smtp_username, settings.smtp_password)
                    if email.expires_at and (email.expires_at - datetime.now(UTC)).total_seconds() <= 8:
                        raise DeliveryError("MESSAGE_EXPIRED")
                    client.send_message(message)
            except smtplib.SMTPAuthenticationError:
                raise DeliveryError("PROVIDER_AUTHENTICATION") from None
            except smtplib.SMTPResponseException as error:
                raise DeliveryError("PROVIDER_REJECTED", retryable=400 <= error.smtp_code < 500) from None
            except (OSError, smtplib.SMTPException):
                raise DeliveryError("DELIVERY_UNCERTAIN", uncertain=True) from None
            return email.message_key
        return await asyncio.to_thread(deliver)


class UnconfiguredEmailProvider:
    name = "unconfigured"
    supports_idempotency = False
    is_configured = False
    async def send(self, email):
        raise DeliveryError("PROVIDER_NOT_CONFIGURED")


def provider_for(name: str):
    return {"resend": ResendProvider, "smtp": SMTPProvider}.get(name, UnconfiguredEmailProvider)()


def get_email_provider():
    return provider_for(get_settings().email_provider)


transactional_email_provider = UnconfiguredEmailProvider()
