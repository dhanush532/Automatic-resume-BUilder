import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.auth.crypto import decrypt
from app.core.config import get_settings
from app.integrations.email import DeliveryError, OutboundEmail, ResendProvider
from app.services.email_delivery import process_delivery, publish_email, queue_email


def queued(db, *, ttl=300):
    row = queue_email(db, user_id=None, purpose="TEST_ONLY", email=OutboundEmail("test@example.com", "Test", "Test-only sensitive message"),
                      expires_at=datetime.now(UTC) + timedelta(seconds=ttl))
    db.commit()
    return row


class FailingProvider:
    name = "test-only"
    is_configured = True
    supports_idempotency = True
    def __init__(self, error):
        self.error, self.calls = error, 0
    async def send(self, message):
        self.calls += 1
        raise self.error


def test_outbox_encryption_redaction_and_idempotency(db_session, test_email_provider):
    row = queued(db_session)
    assert "sensitive message" not in row.encrypted_payload
    assert "sensitive message" in decrypt(row.encrypted_payload)
    assert "sensitive" not in repr(OutboundEmail("private@example.com", "subject", "sensitive"))
    assert process_delivery(db_session, row.id, provider=test_email_provider, rate_check=lambda _: True) == "ACCEPTED"
    assert process_delivery(db_session, row.id, provider=test_email_provider, rate_check=lambda _: True) == "SKIPPED"
    assert len(test_email_provider.messages) == 1
    db_session.refresh(row)
    assert row.encrypted_payload is None and row.provider_message_id == "test-provider-accepted"


@pytest.mark.parametrize("ttl", [-1, 10])
def test_expired_or_nearly_expired_email_is_never_sent(db_session, test_email_provider, ttl):
    row = queued(db_session, ttl=ttl)
    assert process_delivery(db_session, row.id, provider=test_email_provider, rate_check=lambda _: True) == "EXPIRED"
    assert test_email_provider.messages == []
    db_session.refresh(row)
    assert row.encrypted_payload is None and row.attempts == 0


def test_bounded_exponential_retries_preserve_provider_key(db_session):
    row = queued(db_session, ttl=3600)
    provider = FailingProvider(DeliveryError("PROVIDER_OUTAGE", retryable=True, uncertain=True))
    delays = []
    for attempt in range(4):
        before = datetime.now(UTC)
        result = process_delivery(db_session, row.id, provider=provider, rate_check=lambda _: True)
        db_session.refresh(row)
        assert row.attempts == attempt + 1
        if attempt < 3:
            assert result == "RETRYING"
            delays.append((row.next_attempt_at - before).total_seconds())
            row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            db_session.commit()
        else:
            assert result == "UNCERTAIN"
    assert delays[0] < delays[1] < delays[2]
    assert provider.calls == 4
    assert process_delivery(db_session, row.id, provider=provider, rate_check=lambda _: True) == "SKIPPED"


def test_ambiguous_nonidempotent_delivery_is_not_retried(db_session):
    row = queued(db_session)
    provider = FailingProvider(DeliveryError("DELIVERY_UNCERTAIN", retryable=True, uncertain=True))
    provider.supports_idempotency = False
    assert process_delivery(db_session, row.id, provider=provider, rate_check=lambda _: True) == "UNCERTAIN"
    assert provider.calls == 1


def test_quota_retry_that_would_outlive_code_is_expired(db_session):
    row = queued(db_session)
    provider = FailingProvider(DeliveryError("PROVIDER_QUOTA", retryable=True, retry_after=3600))
    assert process_delivery(db_session, row.id, provider=provider, rate_check=lambda _: True) == "EXPIRED"
    assert provider.calls == 1


def test_shared_rate_limit_and_redis_outage_do_not_send(db_session, test_email_provider):
    row = queued(db_session)
    assert process_delivery(db_session, row.id, provider=test_email_provider, rate_check=lambda _: False) == "RETRYING"
    assert test_email_provider.messages == []
    db_session.refresh(row)
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    def unavailable(name):
        raise OSError("Test-only broker outage")
    assert process_delivery(db_session, row.id, provider=test_email_provider, rate_check=unavailable) == "RETRYING"
    assert test_email_provider.messages == []
    assert row.error_code == "RATE_STORE_UNAVAILABLE"


def test_active_lease_prevents_second_send(db_session, test_email_provider):
    row = queued(db_session)
    row.status = "SENDING"
    row.locked_until = datetime.now(UTC) + timedelta(seconds=60)
    row.lease = uuid4()
    db_session.commit()
    assert process_delivery(db_session, row.id, provider=test_email_provider, rate_check=lambda _: True) == "LEASED"
    assert test_email_provider.messages == []


def test_dispatch_published_task_is_immediately_claimable(db_session, test_email_provider, monkeypatch):
    from contextlib import nullcontext

    from app.workers import email as worker

    row = queued(db_session)
    row.updated_at = datetime.now(UTC) - timedelta(seconds=10)
    db_session.commit()
    monkeypatch.setattr(worker, "Session", lambda *args, **kwargs: nullcontext(db_session))
    results = []

    def immediate_worker(identifier, **kwargs):
        if identifier == row.id:
            results.append(process_delivery(db_session, identifier, provider=test_email_provider, rate_check=lambda _: True))
        return True

    monkeypatch.setattr(worker, "publish_email", immediate_worker)
    worker.dispatch_pending.run()
    assert results == ["ACCEPTED"]
    assert len(test_email_provider.messages) == 1


def test_interrupted_smtp_lease_requires_reconciliation(db_session):
    row = queued(db_session)
    row.status, row.locked_until = "SENDING", datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    provider = FailingProvider(DeliveryError("DELIVERY_UNCERTAIN"))
    provider.supports_idempotency = False
    assert process_delivery(db_session, row.id, provider=provider, rate_check=lambda _: True) == "UNCERTAIN"
    assert provider.calls == 0


def test_failover_only_for_definite_nonacceptance(db_session, test_email_provider, monkeypatch):
    test_email_provider.name = "test-secondary"
    settings = get_settings()
    monkeypatch.setattr(settings, "email_failover_provider", "smtp")
    monkeypatch.setattr("app.services.email_delivery.provider_for", lambda _: test_email_provider)
    provider = FailingProvider(DeliveryError("PROVIDER_QUOTA", retryable=True))
    row = queued(db_session)
    assert process_delivery(db_session, row.id, provider=provider, rate_check=lambda _: True) == "ACCEPTED"
    assert len(test_email_provider.messages) == 1
    provider = FailingProvider(DeliveryError("PROVIDER_OUTAGE", retryable=True, uncertain=True))
    row = queued(db_session)
    assert process_delivery(db_session, row.id, provider=provider, rate_check=lambda _: True) == "RETRYING"
    assert len(test_email_provider.messages) == 1


def test_broker_publish_failure_is_safe_and_has_no_secret_logs(db_session, monkeypatch, caplog):
    row = queued(db_session)
    def unavailable(*args, **kwargs):
        raise RuntimeError("SECRET-MUST-NOT-LOG")
    monkeypatch.setattr("app.workers.email.deliver_email.apply_async", unavailable)
    assert publish_email(row.id) is False
    assert "SECRET-MUST-NOT-LOG" not in caplog.text
    db_session.refresh(row)
    assert row.status == "QUEUED" and row.encrypted_payload


def test_uncertain_failover_retries_only_that_same_provider(db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "email_failover_provider", "resend")
    smtp = FailingProvider(DeliveryError("PROVIDER_AUTHENTICATION"))
    smtp.name, smtp.supports_idempotency = "smtp", False
    resend = FailingProvider(DeliveryError("PROVIDER_OUTAGE", retryable=True, uncertain=True))
    resend.name = "resend"
    monkeypatch.setattr("app.services.email_delivery.get_email_provider", lambda: smtp)
    monkeypatch.setattr("app.services.email_delivery.provider_for", lambda name: resend if name == "resend" else smtp)
    row = queued(db_session)
    assert process_delivery(db_session, row.id, rate_check=lambda _: True) == "RETRYING"
    db_session.refresh(row)
    assert row.provider == "resend"
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert process_delivery(db_session, row.id, rate_check=lambda _: True) == "RETRYING"
    assert smtp.calls == 1 and resend.calls == 2


@pytest.mark.parametrize("status,expected", [(429,"PROVIDER_QUOTA"),(500,"PROVIDER_OUTAGE"),(401,"PROVIDER_REJECTED")])
def test_resend_contract_never_surfaces_response_secrets(status, expected, monkeypatch):
    import httpx
    settings = get_settings()
    monkeypatch.setattr(settings, "email_api_key", "test-only-key")
    monkeypatch.setattr(settings, "email_from", "test@example.com")
    real_client = httpx.AsyncClient
    def handler(request):
        assert request.url == "https://api.resend.com/emails"
        assert request.headers["idempotency-key"] == "test-request-key"
        return httpx.Response(status, json={"error": "SECRET-MUST-NOT-LOG"}, headers={"Retry-After": "60"})
    monkeypatch.setattr("app.integrations.email.httpx.AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(handler)))
    with pytest.raises(DeliveryError) as caught:
        asyncio.run(ResendProvider().send(OutboundEmail("test@example.com", "Test", "test body", "test-request-key")))
    assert caught.value.code == expected
    assert "SECRET" not in str(caught.value)
