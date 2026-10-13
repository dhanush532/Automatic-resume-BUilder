"""Database outbox + leased workers; Redis loss never discards an email request."""
import asyncio
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from redis import Redis
from sqlalchemy import select

from app.auth.crypto import decrypt, encrypt
from app.core.config import get_settings
from app.integrations.email import DeliveryError, OutboundEmail, get_email_provider, provider_for
from app.models.account_security import EmailChallenge, EmailDelivery

logger = logging.getLogger(__name__)
SEND_MARGIN_SECONDS = 30
TERMINAL = {"ACCEPTED", "FAILED", "EXPIRED", "CANCELLED", "UNCERTAIN"}


def queue_email(db, *, user_id, email: OutboundEmail, purpose: str, expires_at: datetime, challenge_id=None, priority=0):
    now = datetime.now(UTC)
    delivery = EmailDelivery(user_id=user_id, challenge_id=challenge_id, purpose=purpose, priority=priority,
        encrypted_payload=encrypt(json.dumps({"recipient": email.recipient, "subject": email.subject, "text_body": email.text_body})),
        status="QUEUED", attempts=0, created_at=now, updated_at=now, next_attempt_at=now, expires_at=expires_at)
    db.add(delivery)
    db.flush()
    return delivery


def publish_email(delivery_id: UUID, *, priority=0):
    try:
        from app.workers.email import deliver_email
        deliver_email.apply_async(args=[str(delivery_id)], queue="emails_auth" if priority == 0 else "emails_default", priority=priority, retry=False)
        return True
    except Exception:
        # Only an identifier is logged; no exception representation/traceback.
        logger.warning("email_queue_unavailable delivery_id=%s", delivery_id)
        return False


def _provider_slot(name: str) -> bool:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
    # Atomic shared minute bucket; outage fails closed so workers do not exceed quota.
    script = """
    local minute=tonumber(redis.call('GET',KEYS[1]) or '0')
    local second=tonumber(redis.call('GET',KEYS[2]) or '0')
    if minute>=tonumber(ARGV[1]) then return 60 end
    if second>=tonumber(ARGV[2]) then return 1 end
    if redis.call('INCR',KEYS[1])==1 then redis.call('EXPIRE',KEYS[1],60) end
    if redis.call('INCR',KEYS[2])==1 then redis.call('EXPIRE',KEYS[2],1) end
    return 0
    """
    try:
        # Braced hash tag also keeps both keys in one Redis Cluster slot.
        prefix = f"careerpilot:email-rate:{{{name}}}"
        wait = client.eval(script, 2, prefix + ":minute", prefix + ":second", settings.email_provider_per_minute, settings.email_provider_per_second)
        if wait:
            raise DeliveryError("PROVIDER_RATE_LIMIT", retryable=True, retry_after=int(wait))
        return True
    finally:
        client.close()


def _finish(db, row, status, *, error=None):
    row.status, row.error_code = status, error
    row.locked_until = row.lease = None
    row.updated_at = datetime.now(UTC)
    if status in TERMINAL:
        row.encrypted_payload = None
    db.commit()


def process_delivery(db, delivery_id: UUID, *, provider=None, rate_check=None):
    settings = get_settings()
    now = datetime.now(UTC)
    row = db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id).with_for_update().execution_options(populate_existing=True))
    if row is None or row.status in TERMINAL or row.next_attempt_at > now:
        db.rollback()
        return "SKIPPED"
    if row.locked_until and row.locked_until > now:
        db.rollback()
        return "LEASED"
    # Pin recovery to the transport that may already have accepted this message.
    # Switching providers after an ambiguous outcome can create duplicate mail.
    primary = provider or (provider_for(row.provider) if row.provider else get_email_provider())
    if row.status == "SENDING" and not primary.supports_idempotency:
        _finish(db, row, "UNCERTAIN", error="WORKER_INTERRUPTED")
        return "UNCERTAIN"
    challenge = db.get(EmailChallenge, row.challenge_id) if row.challenge_id else None
    if challenge and (challenge.consumed_at or challenge.attempts >= 5):
        _finish(db, row, "CANCELLED")
        return "CANCELLED"
    if row.expires_at <= now + timedelta(seconds=SEND_MARGIN_SECONDS):
        _finish(db, row, "EXPIRED", error="MESSAGE_EXPIRED")
        return "EXPIRED"
    if row.attempts >= settings.email_max_attempts:
        _finish(db, row, "FAILED", error="RETRY_LIMIT")
        return "FAILED"
    lease = uuid4()
    row.lease, row.locked_until, row.status = lease, now + timedelta(seconds=90), "SENDING"
    row.provider = primary.name
    row.attempts += 1
    encrypted = row.encrypted_payload
    db.commit()
    error = None
    message_id = None
    used_provider = primary
    try:
        if not primary.is_configured:
            raise DeliveryError("PROVIDER_NOT_CONFIGURED")
        limiter = rate_check or _provider_slot
        try:
            available = limiter(primary.name)
        except DeliveryError:
            raise
        except Exception:
            raise DeliveryError("RATE_STORE_UNAVAILABLE", retryable=True, retry_after=15) from None
        if not available:
            raise DeliveryError("PROVIDER_RATE_LIMIT", retryable=True, retry_after=60)
        payload = json.loads(decrypt(encrypted))
        email = OutboundEmail(**payload, message_key=str(delivery_id), expires_at=row.expires_at)
        # Reload right before the handoff, so a superseded/consumed code is not sent.
        row = db.get(EmailDelivery, delivery_id, populate_existing=True)
        challenge = db.get(EmailChallenge, row.challenge_id, populate_existing=True) if row.challenge_id else None
        if (challenge and (challenge.consumed_at or challenge.attempts >= 5)) or row.expires_at <= datetime.now(UTC) + timedelta(seconds=SEND_MARGIN_SECONDS):
            _finish(db, row, "CANCELLED" if challenge and challenge.consumed_at else "EXPIRED")
            return row.status
        db.commit()
        try:
            message_id = asyncio.run(primary.send(email))
        except DeliveryError as failure:
            # Fail over only for a definite nonacceptance; never ambiguous HTTP/SMTP outcomes.
            fallback = provider_for(settings.email_failover_provider)
            if not failure.uncertain and failure.code in {"PROVIDER_QUOTA", "PROVIDER_AUTHENTICATION", "PROVIDER_REJECTED"} and fallback.name != primary.name and fallback.is_configured and limiter(fallback.name):
                used_provider = fallback
                row = db.get(EmailDelivery, delivery_id, populate_existing=True)
                row.provider = fallback.name
                db.commit()  # interrupted failover must recover with this provider/key
                message_id = asyncio.run(fallback.send(email))
            else:
                raise
    except DeliveryError as failure:
        error = failure
    except Exception:
        error = DeliveryError("DELIVERY_INTERNAL_ERROR", uncertain=True)
    row = db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id).with_for_update().execution_options(populate_existing=True))
    if row.lease != lease:
        db.rollback()
        return "LEASE_REPLACED"
    row.provider = used_provider.name
    if error is None:
        row.provider_message_id = message_id
        if row.challenge_id:
            challenge = db.get(EmailChallenge, row.challenge_id)
            challenge.delivered_at = datetime.now(UTC)
        _finish(db, row, "ACCEPTED")
        return "ACCEPTED"
    retry_safe = error.retryable and (not error.uncertain or used_provider.supports_idempotency)
    delay = max(error.retry_after, min(120, 5 * 2 ** (row.attempts - 1)) + secrets.randbelow(4))
    retry_at = datetime.now(UTC) + timedelta(seconds=delay)
    if retry_safe and row.attempts < settings.email_max_attempts and retry_at + timedelta(seconds=SEND_MARGIN_SECONDS) < row.expires_at:
        row.next_attempt_at = retry_at
        _finish(db, row, "RETRYING", error=error.code)
        return "RETRYING"
    terminal = "UNCERTAIN" if error.uncertain else "FAILED"
    if error.code == "MESSAGE_EXPIRED":
        terminal = "EXPIRED"
    if row.expires_at <= retry_at + timedelta(seconds=SEND_MARGIN_SECONDS) and retry_safe:
        terminal = "EXPIRED"
    if row.challenge_id:
        db.get(EmailChallenge, row.challenge_id).delivery_failed = True
    _finish(db, row, terminal, error=error.code)
    return terminal
