import hmac
import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_authenticated_request
from app.api.routes.auth import set_session_cookie
from app.auth.context import get_request_context
from app.auth.crypto import decrypt, encrypt
from app.auth.shared_limits import enforce
from app.auth.tokens import generate_raw_token, hash_token
from app.core.config import get_settings
from app.core.database import get_db_session
from app.integrations.oauth import OAuthError, get_oauth_provider
from app.models.account_security import OAuthAttempt
from app.models.user import OAuthIdentity, SecurityEventType, User
from app.schemas.auth import OAuthStartRequest
from app.services.account_security import require_recent_auth
from app.services.security_events import record_security_event
from app.services.sessions import session_service

router = APIRouter(prefix="/auth/oauth")
COOKIE = "careerpilot_oauth_browser"


def callback_uri(provider):
    settings = get_settings()
    return settings.backend_origin.rstrip("/") + settings.api_prefix + f"/auth/oauth/{provider}/callback"


@router.post("/{provider}/start")
def start(provider: str, payload: OAuthStartRequest, request: Request, db: Session = Depends(get_db_session), adapter=Depends(get_oauth_provider)):
    if not adapter.is_configured:
        raise HTTPException(503, "This sign-in provider is not configured yet.")
    enforce(db, f"oauth-ip:{get_request_context(request).ip_address}", limit=30, seconds=300)
    auth = require_authenticated_request(request, db) if payload.mode in {"link", "reauth"} else None
    if auth and payload.mode == "link":
        require_recent_auth(auth)
    state, browser, verifier, nonce = (generate_raw_token() for _ in range(4))
    attempt = OAuthAttempt(provider=provider, mode=payload.mode, state_hash=hash_token("oauth-state:" + state),
        browser_hash=hash_token("oauth-browser:" + browser), encrypted_verifier=encrypt(verifier), nonce=nonce,
        user_id=auth.user.id if auth else None, session_id=auth.session.id if auth else None,
        terms_accepted=payload.terms_accepted, expires_at=datetime.now(UTC) + timedelta(minutes=10))
    db.add(attempt)
    db.commit()
    response = JSONResponse({"authorization_url": adapter.authorization_url(state=state, redirect_uri=callback_uri(provider), verifier=verifier, nonce=nonce)})
    response.set_cookie(COOKIE, browser, httponly=True, secure=get_settings().session_cookie_secure, samesite="lax", max_age=600)
    return response


@router.get("/{provider}/callback")
async def callback(provider: str, request: Request, db: Session = Depends(get_db_session), adapter=Depends(get_oauth_provider)):
    settings = get_settings()
    failure_url = settings.frontend_origin + "/login?oauth_error=authentication_failed"
    response = RedirectResponse(failure_url, status_code=303)
    response.delete_cookie(COOKIE, httponly=True, secure=settings.session_cookie_secure)
    if not adapter.is_configured:
        return response
    state, browser, code = request.query_params.get("state", ""), request.cookies.get(COOKIE, ""), request.query_params.get("code", "")
    if not state or not browser or len(state) > 256 or not code or len(code) > 4096 or request.query_params.get("error"):
        return response
    attempt = db.scalar(select(OAuthAttempt).where(OAuthAttempt.provider == provider, OAuthAttempt.state_hash == hash_token("oauth-state:" + state))
                        .with_for_update())
    if (not attempt or attempt.consumed_at or attempt.expires_at <= datetime.now(UTC)
            or not hmac.compare_digest(attempt.browser_hash, hash_token("oauth-browser:" + browser))):
        db.rollback()
        return response
    attempt.consumed_at = datetime.now(UTC)
    try:
        verifier, nonce = decrypt(attempt.encrypted_verifier), attempt.nonce
    except Exception:
        attempt.consumed_at = datetime.now(UTC)
        db.commit()
        return response
    attempt.encrypted_verifier = "consumed"
    target_id, session_id, mode, terms = attempt.user_id, attempt.session_id, attempt.mode, attempt.terms_accepted
    db.commit()  # one-use state before network calls; no row locks held at the provider
    try:
        profile = await adapter.exchange_code(code=code, redirect_uri=callback_uri(provider), verifier=verifier, nonce=nonce)
        if profile.provider != provider or not profile.provider_user_id or len(profile.provider_user_id) > 255:
            raise OAuthError("Invalid provider identity.")
        identity = db.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == provider, OAuthIdentity.provider_user_id == profile.provider_user_id))
        if mode in {"link", "reauth"}:
            auth = require_authenticated_request(request, db)
            if auth.user.id != target_id or auth.session.id != session_id:
                raise OAuthError("Account context changed.")
            db.scalar(select(User).where(User.id == target_id).with_for_update())
            if mode == "reauth":
                if not identity or identity.user_id != target_id:
                    raise OAuthError("Authenticate with a connected provider.")
                auth.session.recent_auth_at = datetime.now(UTC)
            else:
                require_recent_auth(auth)
                if identity and identity.user_id != target_id:
                    raise OAuthError("Provider is linked to another account.")
                if not identity:
                    identity = OAuthIdentity(user_id=target_id, provider=provider, provider_user_id=profile.provider_user_id,
                        provider_email=profile.verified_email, created_at=datetime.now(UTC), linked_at=datetime.now(UTC))
                    db.add(identity)
                    record_security_event(db, SecurityEventType.OAUTH_LINKED, user_id=target_id, context=get_request_context(request), metadata={"provider": provider})
            db.commit()
            response.headers["location"] = settings.frontend_origin + "/settings/account?oauth=success"
            return response
        if identity:
            user = db.scalar(select(User).where(User.id == identity.user_id).with_for_update())
        else:
            if not profile.verified_email or not profile.email_verified or not terms:
                raise OAuthError("Registration requires a verified provider email and terms acceptance.")
            email = str(TypeAdapter(EmailStr).validate_python(profile.verified_email)).strip().lower()
            if db.scalar(select(User.id).where(User.email == email)):
                response.headers["location"] = settings.frontend_origin + "/login?oauth_error=link_existing_account"
                db.rollback()
                return response
            user = User(email=email, username="u_" + uuid4().hex[:20], full_name=(profile.display_name or "CareerPilot user")[:120],
                password_hash=None, email_verified_at=datetime.now(UTC), terms_accepted_at=datetime.now(UTC), is_active=True, account_status="ACTIVE")
            db.add(user)
            db.flush()
            db.add(OAuthIdentity(user_id=user.id, provider=provider, provider_user_id=profile.provider_user_id,
                provider_email=email, created_at=datetime.now(UTC), linked_at=datetime.now(UTC)))
        if not user or not user.is_active or not user.email_verified_at or user.deleted_at:
            raise OAuthError("Account is not active.")
        _, raw = session_service.create(db, user=user, context=get_request_context(request))
        record_security_event(db, SecurityEventType.LOGIN_SUCCESS, user_id=user.id, context=get_request_context(request), metadata={"provider": provider})
        db.commit()
        set_session_cookie(response, raw)
        response.headers["location"] = settings.frontend_origin + "/passport"
    except Exception:
        db.rollback()
        logging.getLogger(__name__).warning("oauth_authentication_failed provider=%s", provider)
    return response
