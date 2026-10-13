import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update

from app.auth.tokens import hash_token
from app.integrations.email import OutboundEmail
from app.models.account_security import EmailChallenge, EmailDelivery
from app.models.user import SecurityEventType, User
from app.services.email_delivery import queue_email
from app.services.security_events import record_security_event


def issue_challenge(db, *, user: User, email: str, purpose="REGISTRATION", pending_values=None):
    now = datetime.now(UTC)
    # Serialize generation/resends for this account.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    previous = db.scalar(select(EmailChallenge).where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == purpose)
                         .order_by(EmailChallenge.created_at.desc()).limit(1))
    if previous and previous.created_at + timedelta(seconds=60) > now:
        raise HTTPException(429, "Please wait 60 seconds before requesting another code.", headers={"Retry-After": "60"})
    old_ids = select(EmailChallenge.id).where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == purpose)
    db.execute(update(EmailDelivery).where(EmailDelivery.challenge_id.in_(old_ids), EmailDelivery.status.in_(["QUEUED", "RETRYING"]))
               .values(status="CANCELLED", encrypted_payload=None, updated_at=now))
    db.execute(update(EmailChallenge).where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == purpose,
               EmailChallenge.consumed_at.is_(None)).values(consumed_at=now, pending_values={}))
    identifier = uuid4()
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = EmailChallenge(id=identifier, user_id=user.id, email=email, purpose=purpose,
        otp_hash=hash_token(f"email-otp:{identifier}:{code}"), expires_at=now + timedelta(minutes=5), attempts=0,
        created_at=now, pending_values=pending_values or {}, delivery_failed=False)
    db.add(challenge)
    db.flush()
    delivery = queue_email(db, user_id=user.id, challenge_id=identifier, purpose=purpose,
        expires_at=challenge.expires_at, email=OutboundEmail(email, "CareerPilot verification code",
        f"Your CareerPilot verification code is {code}.\n\nIt expires in 5 minutes and can be used once.\nIf you did not request this code, you can ignore this email.\nCareerPilot will never ask you to share this code."))
    return challenge, delivery


def verify_challenge(db, *, user: User, code: str, purpose="REGISTRATION", context=None):
    # User first, then challenge: same lock order as issue/email/account updates.
    user = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    now = datetime.now(UTC)
    challenge = db.scalar(select(EmailChallenge).where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == purpose)
                          .order_by(EmailChallenge.created_at.desc()).limit(1).with_for_update())
    if (not challenge or challenge.consumed_at or challenge.expires_at <= now or challenge.attempts >= 5
            or not challenge.delivered_at or user.deleted_at or user.account_status in {"DISABLED", "DELETED"}):
        raise HTTPException(400, "Code is invalid, expired, or not delivered. Request a new code if needed.")
    challenge.attempts += 1
    if not hmac.compare_digest(challenge.otp_hash, hash_token(f"email-otp:{challenge.id}:{code}")):
        db.commit()  # failed attempts must survive the HTTP error
        raise HTTPException(400, "Code is invalid or expired. Request a new code after five unsuccessful attempts.")
    challenge.consumed_at = now
    if purpose == "REGISTRATION":
        for name, value in challenge.pending_values.items():
            if name in {"password_hash", "username", "full_name", "phone_e164"}:
                setattr(user, name, value)
        user.email_verified_at, user.is_active, user.account_status = now, True, "ACTIVE"
        record_security_event(db, SecurityEventType.EMAIL_VERIFIED, user_id=user.id, context=context)
    else:
        user.email = challenge.email
        user.email_verified_at = now
        record_security_event(db, SecurityEventType.EMAIL_CHANGED, user_id=user.id, context=context)
    challenge.pending_values = {}
    db.execute(update(EmailDelivery).where(EmailDelivery.challenge_id == challenge.id, EmailDelivery.status.in_(["QUEUED", "RETRYING"]))
               .values(status="CANCELLED", encrypted_payload=None, updated_at=now))
    return user
