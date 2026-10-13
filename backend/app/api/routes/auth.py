from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthenticatedRequest,
    require_authenticated_request,
    require_same_site_mutation,
)
from app.auth.context import get_request_context
from app.auth.normalization import normalize_email
from app.auth.shared_limits import enforce
from app.auth.tokens import AuthenticationConfigurationError, hash_token
from app.core.config import get_settings
from app.core.database import get_db_session
from app.integrations.email import OutboundEmail, get_email_provider
from app.models.account_security import EmailChallenge, EmailDelivery
from app.models.user import LoginEvent, OAuthIdentity, SecurityEventType, User, UserSession
from app.schemas.auth import (
    AccountDeletionRequest,
    ChangePasswordRequest,
    EmailVerificationRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PublicUser,
    RegistrationRequest,
    SecurityEventSummary,
    SessionSummary,
)
from app.services.account_security import require_recent_auth
from app.services.authentication import (
    DuplicateIdentityError,
    EmailVerificationRequiredError,
    InvalidCredentialsError,
    authentication_service,
)
from app.services.email_challenges import issue_challenge, verify_challenge
from app.services.email_delivery import publish_email, queue_email
from app.services.security_events import record_security_event
from app.services.sessions import session_service

router = APIRouter(prefix="/auth")


def public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        phone=user.phone_e164,
        email_verified=bool(user.email_verified_at),
    )


def session_summary(session: UserSession, *, current_session_id: UUID) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        device_type=session.device_type,
        browser=session.browser,
        operating_system=session.operating_system,
        ip_address=session.ip_address,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
        expires_at=session.expires_at,
        status=session.status.value,
        current=session.id == current_session_id,
    )


def set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_duration_hours * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie_name, httponly=True, secure=settings.session_cookie_secure, path="/")


@router.post("/register", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
def register(payload: RegistrationRequest, request: Request, response: Response, tasks: BackgroundTasks,
             db: Session = Depends(get_db_session), provider=Depends(get_email_provider)) -> PublicUser:
    if not provider.is_configured:
        raise HTTPException(503, "Email delivery is not configured. Registration is temporarily unavailable.")
    context = get_request_context(request)
    enforce(db, f"register-ip:{context.ip_address}", limit=30, seconds=3600)
    enforce(db, f"register-email:{payload.email}", limit=10, seconds=3600)
    try:
        existing = db.scalar(select(User).where(User.email == payload.email).with_for_update())
        pending = None
        if existing and existing.account_status == "PENDING" and not existing.email_verified_at:
            latest = db.scalar(select(EmailChallenge).where(EmailChallenge.user_id == existing.id).order_by(EmailChallenge.created_at.desc()).limit(1))
            if latest and latest.created_at + timedelta(seconds=60) > datetime.now(UTC):
                raise DuplicateIdentityError("account information")
            from app.auth.passwords import hash_password
            pending = {"password_hash": hash_password(payload.password), "full_name": payload.full_name,
                       "phone_e164": payload.phone, "username": payload.username}
            user = existing
        else:
            user, _ = authentication_service.register(db, payload=payload, context=context, verification_ttl=timedelta(minutes=5))
        challenge, delivery = issue_challenge(db, user=user, email=user.email, pending_values=pending)
        db.commit()
    except (DuplicateIdentityError, IntegrityError):
        db.rollback()
        raise HTTPException(409, "Unable to register with those details. Try signing in or account recovery.") from None
    except AuthenticationConfigurationError as error:
        db.rollback()
        raise HTTPException(503, str(error)) from None
    tasks.add_task(publish_email, delivery.id)
    response.set_cookie("careerpilot_delivery_receipt", hash_token("delivery-receipt:" + str(delivery.id)),
                        httponly=True, secure=get_settings().session_cookie_secure, samesite="lax", max_age=600)
    result = public_user(user)
    result.delivery_id, result.verification_expires_at = delivery.id, challenge.expires_at
    result.delivery_status = "QUEUED"
    return result

@router.post("/login", response_model=PublicUser)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> PublicUser:
    settings = get_settings()
    context = get_request_context(request)
    limiter_key = f"{context.ip_address}:{payload.identifier.strip().casefold()}"
    enforce(db, f"login-ip:{context.ip_address}", limit=100, seconds=settings.auth_rate_limit_window_seconds)
    enforce(db, "login:" + limiter_key, limit=settings.auth_login_rate_limit, seconds=settings.auth_rate_limit_window_seconds)
    try:
        user, raw_token, _ = authentication_service.authenticate(db, payload=payload, context=context)
        db.commit()
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email/username or password.") from error
    except EmailVerificationRequiredError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verify your email before signing in.") from error
    except AuthenticationConfigurationError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    set_session_cookie(response, raw_token)
    return public_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    session_service.revoke(db, session=authenticated.session, reason="logout")
    record_security_event(
        db,
        SecurityEventType.LOGOUT,
        user_id=authenticated.user.id,
        context=get_request_context(request),
    )
    db.commit()
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=PublicUser)
def get_me(authenticated: AuthenticatedRequest = Depends(require_authenticated_request)) -> PublicUser:
    return public_user(authenticated.user)


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> list[SessionSummary]:
    sessions = list(
        db.scalars(
            select(UserSession).where(UserSession.user_id == authenticated.user.id).order_by(UserSession.created_at.desc())
        )
    )
    return [session_summary(session, current_session_id=authenticated.session.id) for session in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: UUID,
    request: Request,
    response: Response,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    session = db.scalar(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == authenticated.user.id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    session_service.revoke(db, session=session, reason="user_revoked")
    record_security_event(
        db,
        SecurityEventType.SESSION_REVOKED,
        user_id=authenticated.user.id,
        context=get_request_context(request),
        metadata={"session_id": str(session.id)},
    )
    db.commit()
    if session.id == authenticated.session.id:
        clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/sessions/logout-others", status_code=status.HTTP_204_NO_CONTENT)
def logout_other_sessions(
    request: Request,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    count = session_service.revoke_for_user(
        db, user_id=authenticated.user.id, reason="logout_other_sessions", except_id=authenticated.session.id
    )
    if count:
        record_security_event(
            db,
            SecurityEventType.SESSION_REVOKED,
            user_id=authenticated.user.id,
            context=get_request_context(request),
            metadata={"count": str(count), "scope": "other_sessions"},
        )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all_sessions(
    request: Request,
    response: Response,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    count = session_service.revoke_for_user(db, user_id=authenticated.user.id, reason="logout_all_sessions")
    if count:
        record_security_event(
            db,
            SecurityEventType.SESSION_REVOKED,
            user_id=authenticated.user.id,
            context=get_request_context(request),
            metadata={"count": str(count), "scope": "all_sessions"},
        )
    db.commit()
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/security-events", response_model=list[SecurityEventSummary])
def list_security_events(
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
) -> list[SecurityEventSummary]:
    events = list(
        db.scalars(
            select(LoginEvent)
            .where(LoginEvent.user_id == authenticated.user.id)
            .order_by(LoginEvent.created_at.desc())
            .limit(50)
        )
    )
    return [
        SecurityEventSummary(
            id=event.id,
            event_type=event.event_type.value,
            ip_address=event.ip_address,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.post("/verify-email", response_model=PublicUser)
def verify_email(payload: EmailVerificationRequest, request: Request, db: Session = Depends(get_db_session)) -> PublicUser:
    context = get_request_context(request)
    enforce(db, f"verify-ip:{context.ip_address}", limit=60, seconds=300)
    try:
        if payload.token:
            user = authentication_service.verify_email(db, raw_token=payload.token, context=context)
            if not user:
                raise HTTPException(400, "Verification link is invalid or expired.")
        else:
            user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
            if not user:
                raise HTTPException(400, "Code is invalid or expired.")
            latest = db.scalar(select(EmailChallenge).where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == "REGISTRATION").order_by(EmailChallenge.created_at.desc()).limit(1))
            delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.challenge_id == latest.id)) if latest else None
            import hmac
            if not delivery or not hmac.compare_digest(request.cookies.get("careerpilot_delivery_receipt", ""), hash_token("delivery-receipt:" + str(delivery.id))):
                raise HTTPException(400, "Restart registration in this browser before verifying the code.")
            user = verify_challenge(db, user=user, code=payload.code, context=context)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "These account details are unavailable. Restart registration with another username.") from None
    return public_user(user)


@router.post("/forgot-password", status_code=202)
def forgot_password(payload: PasswordResetRequest, request: Request, tasks: BackgroundTasks,
                    db: Session = Depends(get_db_session), provider=Depends(get_email_provider)):
    if not provider.is_configured:
        raise HTTPException(503, "Email delivery is temporarily unavailable.")
    context = get_request_context(request)
    enforce(db, f"reset-ip:{context.ip_address}", limit=20, seconds=3600)
    enforce(db, f"reset-email:{payload.email}", limit=5, seconds=3600)
    user = db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True), User.deleted_at.is_(None)))
    if user and user.email_verified_at:
        ttl = timedelta(minutes=get_settings().password_reset_ttl_minutes)
        token = authentication_service.issue_password_reset(db, user=user, context=context, ttl=ttl)
        delivery = queue_email(db, user_id=user.id, purpose="PASSWORD_RESET", expires_at=datetime.now(UTC) + ttl,
            email=OutboundEmail(user.email, "Reset your CareerPilot password",
                f"Open this link to reset your password:\\n{get_settings().frontend_origin}/reset-password#token={token}\\n\\nThis link expires shortly and works once. Ignore it if you did not request it."))
        db.commit()
        tasks.add_task(publish_email, delivery.id)
    return {"message": "If this email belongs to an eligible account, a recovery message has been queued."}

@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: PasswordResetConfirmRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    try:
        user = authentication_service.reset_password(
            db, raw_token=payload.token, new_password=payload.password, context=get_request_context(request)
        )
    except AuthenticationConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or has expired.")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    from app.auth.passwords import hash_password, verify_password

    require_recent_auth(authenticated)
    enforce(db, f"password-change:{authenticated.user.id}", limit=10, seconds=300)
    if not verify_password(payload.current_password, authenticated.user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    authenticated.user.password_hash = hash_password(payload.password)
    session_service.revoke_for_user(db, user_id=authenticated.user.id, reason="password_changed")
    record_security_event(
        db,
        SecurityEventType.PASSWORD_CHANGED,
        user_id=authenticated.user.id,
        context=get_request_context(request),
    )
    db.commit()
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.delete("/oauth-identities/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_oauth_provider(
    provider: str,
    request: Request,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    require_recent_auth(authenticated)
    db.scalar(select(User).where(User.id == authenticated.user.id).with_for_update())
    identity = db.scalar(
        select(OAuthIdentity).where(
            OAuthIdentity.user_id == authenticated.user.id,
            OAuthIdentity.provider == provider.strip().casefold(),
        )
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OAuth connection not found.")
    others = list(db.scalars(select(OAuthIdentity).where(OAuthIdentity.user_id == authenticated.user.id, OAuthIdentity.id != identity.id)))
    if not authenticated.user.password_hash and not others:
        raise HTTPException(409, "Add another usable sign-in method before disconnecting the last provider.")
    db.delete(identity)
    record_security_event(
        db,
        SecurityEventType.OAUTH_DISCONNECTED,
        user_id=authenticated.user.id,
        context=get_request_context(request),
        metadata={"provider": provider.strip().casefold()},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/account/delete", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountDeletionRequest,
    request: Request,
    response: Response,
    authenticated: AuthenticatedRequest = Depends(require_authenticated_request),
    db: Session = Depends(get_db_session),
    _: None = Depends(require_same_site_mutation),
) -> Response:
    from datetime import UTC, datetime

    from app.auth.passwords import verify_password

    require_recent_auth(authenticated)
    enforce(db, f"account-delete:{authenticated.user.id}", limit=5, seconds=300)
    if payload.password:
        if not verify_password(payload.password, authenticated.user.password_hash):
            raise HTTPException(400, "Password is incorrect.")
    if payload.confirmation != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm account deactivation.")
    authenticated.user.is_active = False
    authenticated.user.account_status = "DELETED"
    authenticated.user.password_hash = None
    authenticated.user.deleted_at = datetime.now(UTC)
    session_service.revoke_for_user(db, user_id=authenticated.user.id, reason="account_deleted")
    from sqlalchemy import delete

    from app.models.base import Base
    # An explicit, recently authenticated deletion request erases only the caller's
    # owned rows. Shared templates, companies, skills and global jobs are retained.
    for table in reversed(Base.metadata.sorted_tables):
        if "user_id" in table.c and table.name != "login_events":
            db.execute(delete(table).where(table.c.user_id == authenticated.user.id))
    for event in db.scalars(select(LoginEvent).where(LoginEvent.user_id == authenticated.user.id)):
        event.identifier = event.ip_address = event.user_agent = None
        event.event_metadata = {}
    authenticated.user.email = f"deleted-{authenticated.user.id}@deleted.invalid"
    authenticated.user.username = "deleted_" + authenticated.user.id.hex[:22]
    authenticated.user.full_name = "Deleted account"
    authenticated.user.phone_e164 = None
    authenticated.user.email_verified_at = None
    record_security_event(
        db,
        SecurityEventType.ACCOUNT_DELETED,
        user_id=authenticated.user.id,
    )
    db.commit()
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/data-export", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def request_data_export(authenticated: AuthenticatedRequest = Depends(require_authenticated_request)) -> dict[str, str]:
    # The authorization gate is in place; scoped export assembly arrives with the Passport entities.
    del authenticated
    return {"detail": "Data export will be available when Career Passport records are implemented."}
