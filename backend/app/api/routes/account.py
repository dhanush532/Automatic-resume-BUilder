import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated_request
from app.api.routes.auth import clear_session_cookie, public_user
from app.auth.context import get_request_context
from app.auth.normalization import normalize_email, normalize_phone
from app.auth.passwords import verify_password
from app.auth.shared_limits import enforce
from app.auth.tokens import hash_token
from app.core.config import get_settings
from app.core.database import get_db_session
from app.integrations.email import OutboundEmail, get_email_provider
from app.models.account_security import EmailChallenge, EmailDelivery
from app.models.user import OAuthIdentity, User
from app.schemas.auth import (
    AccountUpdateRequest,
    EmailChangeConfirmRequest,
    PasswordResetRequest,
    ReauthenticateRequest,
)
from app.services.account_security import require_recent_auth
from app.services.email_challenges import issue_challenge, verify_challenge
from app.services.email_delivery import publish_email, queue_email
from app.services.sessions import session_service

router = APIRouter(prefix="/auth")


@router.get("/capabilities")
def capabilities():
    settings = get_settings()
    return {"email_delivery_configured": get_email_provider().is_configured,
            "providers": [{"name": name, "configured": bool(getattr(settings, name + "_client_id") and getattr(settings, name + "_client_secret"))}
                          for name in ("google", "github", "linkedin")]}


@router.post("/resend-verification", status_code=202)
def resend(payload: PasswordResetRequest, request: Request, response: Response, tasks: BackgroundTasks,
           db: Session = Depends(get_db_session), provider=Depends(get_email_provider)):
    if not provider.is_configured:
        raise HTTPException(503, "Email delivery is temporarily unavailable. Try again once delivery is restored.")
    enforce(db, f"resend-ip:{get_request_context(request).ip_address}", limit=20, seconds=3600)
    enforce(db, f"resend-email:{payload.email}", limit=10, seconds=3600)
    user = db.scalar(select(User).where(User.email == normalize_email(payload.email), User.account_status == "PENDING"))
    if user and not user.email_verified_at:
        latest = db.scalar(select(EmailChallenge).where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == "REGISTRATION").order_by(EmailChallenge.created_at.desc()).limit(1))
        previous_delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.challenge_id == latest.id)) if latest else None
        if not previous_delivery or not hmac.compare_digest(request.cookies.get("careerpilot_delivery_receipt", ""), hash_token("delivery-receipt:" + str(previous_delivery.id))):
            raise HTTPException(400, "Restart registration in this browser to request another code safely.")
        pending = dict(latest.pending_values) if latest else {}
        challenge, delivery = issue_challenge(db, user=user, email=user.email, pending_values=pending)
        db.commit()
        tasks.add_task(publish_email, delivery.id)
        response.set_cookie("careerpilot_delivery_receipt", hash_token("delivery-receipt:" + str(delivery.id)),
                            httponly=True, secure=get_settings().session_cookie_secure, samesite="lax", max_age=600)
        return {"message": "A new verification message has been queued.", "delivery_id": delivery.id,
                "expires_at": challenge.expires_at, "retry_after": 60}
    return {"message": "If this email has a pending registration, a message will be queued.", "retry_after": 60}


@router.get("/email-delivery/{delivery_id}")
def delivery_status(delivery_id: UUID, request: Request, db: Session = Depends(get_db_session)):
    receipt = request.cookies.get("careerpilot_delivery_receipt", "")
    if not hmac.compare_digest(receipt, hash_token("delivery-receipt:" + str(delivery_id))):
        raise HTTPException(404, "Delivery status unavailable.")
    row = db.get(EmailDelivery, delivery_id)
    if not row:
        raise HTTPException(404, "Delivery status unavailable.")
    now = datetime.now(UTC)
    state = "EXPIRED" if row.status in {"QUEUED", "RETRYING"} and row.expires_at <= now else row.status
    return {"status": state, "expires_at": row.expires_at,
            "retry_after": max(0, 60 - int((now - row.created_at).total_seconds())),
            "message": {"ACCEPTED": "The provider accepted the message. Inbox delivery is not confirmed.",
                        "FAILED": "Delivery failed. Request a new code after the cooldown.",
                        "EXPIRED": "This code expired before it could be delivered. Request a new code.",
                        "UNCERTAIN": "Delivery could not be confirmed. Check your inbox or request a new code after the cooldown."}.get(state, "Delivery is pending. Please check again shortly.")}


@router.get("/email-deliveries")
def own_deliveries(auth=Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    rows = db.scalars(select(EmailDelivery).where(EmailDelivery.user_id == auth.user.id).order_by(EmailDelivery.created_at.desc()).limit(20))
    return [{"id": row.id, "purpose": row.purpose, "status": row.status, "attempts": row.attempts,
             "error_code": row.error_code, "created_at": row.created_at} for row in rows]


@router.post("/reauthenticate", status_code=204)
def reauthenticate(payload: ReauthenticateRequest, request: Request, auth=Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    enforce(db, f"reauth-user:{auth.user.id}", f"reauth-ip:{get_request_context(request).ip_address}", limit=10, seconds=300)
    if not verify_password(payload.password, auth.user.password_hash):
        raise HTTPException(401, "Unable to reauthenticate.")
    auth.session.recent_auth_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


@router.patch("/account")
def update_account(payload: AccountUpdateRequest, auth=Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    auth.user.full_name = payload.full_name.strip()
    auth.user.phone_e164 = normalize_phone(payload.phone, payload.phone_region)
    db.commit()
    return public_user(auth.user)


@router.get("/oauth-identities")
def connected(auth=Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    return {"password_available": bool(auth.user.password_hash), "providers": [
        {"provider": row.provider, "linked_at": row.linked_at} for row in db.scalars(select(OAuthIdentity).where(OAuthIdentity.user_id == auth.user.id))]}


@router.post("/email-change", status_code=202)
def request_email_change(payload: PasswordResetRequest, request: Request, tasks: BackgroundTasks,
                         auth=Depends(require_authenticated_request), db: Session = Depends(get_db_session), provider=Depends(get_email_provider)):
    require_recent_auth(auth)
    if not provider.is_configured:
        raise HTTPException(503, "Email delivery is temporarily unavailable.")
    enforce(db, f"email-change:{auth.user.id}", limit=5, seconds=3600)
    email = normalize_email(payload.email)
    if db.scalar(select(User.id).where(func.lower(func.btrim(User.email)) == email)):
        raise HTTPException(409, "That email address cannot be used. Your current email is unchanged.")
    challenge, delivery = issue_challenge(db, user=auth.user, email=email, purpose="EMAIL_CHANGE")
    db.commit()
    tasks.add_task(publish_email, delivery.id)
    return {"message": "Verification queued for the new email. Your current email remains active.", "expires_at": challenge.expires_at}


@router.post("/email-change/confirm")
def confirm_email_change(payload: EmailChangeConfirmRequest, request: Request, response: Response, tasks: BackgroundTasks,
                         auth=Depends(require_authenticated_request), db: Session = Depends(get_db_session)):
    require_recent_auth(auth)
    old_email = auth.user.email
    try:
        user = verify_challenge(db, user=auth.user, code=payload.code, purpose="EMAIL_CHANGE", context=get_request_context(request))
        session_service.revoke_for_user(db, user_id=user.id, reason="email_changed")
        notification = queue_email(db, user_id=user.id, purpose="SECURITY_NOTICE", priority=6, expires_at=datetime.now(UTC) + timedelta(hours=24),
            email=OutboundEmail(old_email, "CareerPilot email changed", "Your CareerPilot email was changed after verification. If this was not you, contact support promptly."))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "The new email is unavailable. Your original email was retained.") from None
    tasks.add_task(publish_email, notification.id, priority=6)
    clear_session_cookie(response)
    return public_user(user)
