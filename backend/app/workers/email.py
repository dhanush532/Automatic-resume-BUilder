from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import Celery
from kombu import Queue
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.models.account_security import EmailChallenge, EmailDelivery
from app.services.email_delivery import process_delivery, publish_email

celery_app = Celery("careerpilot-email", broker=get_settings().redis_url)
celery_app.conf.update(
    task_serializer="json", accept_content=["json"], task_ignore_result=True,
    task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
    broker_connection_timeout=2, broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 120, "priority_steps": [0, 3, 6, 9], "queue_order_strategy": "priority", "socket_connect_timeout": 2, "socket_timeout": 2},
    task_publish_retry=False, task_soft_time_limit=60, task_time_limit=75,
    task_queues=(Queue("emails_auth"), Queue("emails_default")), task_default_queue="emails_default",
    beat_schedule={"email-outbox-dispatch": {"task": "email.dispatch", "schedule": 5.0, "options": {"queue": "emails_auth", "priority": 0}}},
)


@celery_app.task(name="email.deliver")
def deliver_email(delivery_id: str):
    # Task arguments contain only an opaque database UUID.
    with Session(get_engine(), autoflush=False) as db:
        try:
            return process_delivery(db, UUID(delivery_id))
        except Exception:
            db.rollback()
            return "WORKER_ERROR"  # lease recovery handles interrupted processing


@celery_app.task(name="email.dispatch")
def dispatch_pending():
    now = datetime.now(UTC)
    with Session(get_engine(), autoflush=False) as db:
        # Clear secret transient material on expired/superseded requests.
        db.execute(update(EmailDelivery).where(EmailDelivery.status.in_(["QUEUED", "RETRYING"]), EmailDelivery.expires_at <= now)
                   .values(status="EXPIRED", encrypted_payload=None, updated_at=now))
        # Preserve the intended password hash across a short OTP expiry/resend.
        # After 24 hours the browser receipt has expired: a new registration is required.
        db.execute(update(EmailChallenge).where(EmailChallenge.created_at < now - timedelta(hours=24)).values(pending_values={}))
        rows = db.scalars(select(EmailDelivery).where(
            EmailDelivery.status.in_(["QUEUED", "RETRYING", "SENDING"]), EmailDelivery.next_attempt_at <= now,
            EmailDelivery.updated_at <= now - timedelta(seconds=5),
            or_(EmailDelivery.locked_until.is_(None), EmailDelivery.locked_until <= now))
            .order_by(EmailDelivery.priority, EmailDelivery.created_at).limit(100).with_for_update(skip_locked=True)).all()
        identities = [(row.id, row.priority) for row in rows]
        # Avoid flooding Redis if multiple dispatchers run. This is not a send lease.
        for row in rows:
            row.updated_at = now
        db.commit()
        for identifier, priority in identities:
            # Do not move next_attempt_at into the future: a fast worker must be
            # able to claim immediately, before publish_email returns.
            publish_email(identifier, priority=priority)
        return len(identities)
