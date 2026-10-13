from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.context import RequestContext
from app.auth.normalization import normalize_email, normalize_username
from app.auth.passwords import hash_password, password_needs_rehash, verify_password
from app.models.user import SecurityEventType, SecurityTokenPurpose, User
from app.schemas.auth import LoginRequest, RegistrationRequest
from app.services.security_events import record_security_event
from app.services.security_tokens import security_token_service
from app.services.sessions import session_service


class DuplicateIdentityError(ValueError):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"A user with this {field} already exists.")


class InvalidCredentialsError(ValueError):
    pass


class EmailVerificationRequiredError(ValueError):
    pass


class AuthenticationService:
    def register(
        self,
        db: Session,
        *,
        payload: RegistrationRequest,
        context: RequestContext,
        verification_ttl: timedelta,
    ) -> tuple[User, str]:
        email = normalize_email(payload.email)
        username = normalize_username(payload.username)
        existing = db.scalar(select(User).where(or_(User.email == email, User.username == username)))
        if existing:
            if existing.email == email:
                raise DuplicateIdentityError("email")
            if existing.username == username:
                raise DuplicateIdentityError("username")

        user = User(
            email=email,
            username=username,
            full_name=payload.full_name,
            phone_e164=payload.phone,
            password_hash=hash_password(payload.password),
            terms_accepted_at=datetime.now(UTC),
            is_active=False,
            account_status="PENDING",
        )
        db.add(user)
        db.flush()
        return user, ""

    def authenticate(self, db: Session, *, payload: LoginRequest, context: RequestContext) -> tuple[User, str, object]:
        identifier = payload.identifier.strip().lower()
        user = db.scalar(select(User).where(or_(User.email == identifier, User.username == identifier)))
        if not user or user.deleted_at or user.account_status in {"DISABLED", "DELETED"} or not verify_password(payload.password, user.password_hash):
            record_security_event(
                db,
                SecurityEventType.LOGIN_FAILURE,
                user_id=user.id if user else None,
                identifier=identifier,
                context=context,
            )
            db.commit()
            raise InvalidCredentialsError
        if not user.email_verified_at:
            raise EmailVerificationRequiredError
        if not user.is_active:
            raise InvalidCredentialsError
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(payload.password)
        session, raw_token = session_service.create(db, user=user, context=context)
        record_security_event(db, SecurityEventType.LOGIN_SUCCESS, user_id=user.id, identifier=identifier, context=context)
        return user, raw_token, session

    def verify_email(self, db: Session, *, raw_token: str, context: RequestContext) -> User | None:
        token = security_token_service.consume(
            db, raw_token=raw_token, purpose=SecurityTokenPurpose.EMAIL_VERIFICATION
        )
        if not token:
            return None
        user = token.user
        if user.deleted_at or user.account_status in {"DISABLED", "DELETED"}:
            return None
        if not user.email_verified_at:
            user.email_verified_at = datetime.now(UTC)
            user.is_active = True
            user.account_status = "ACTIVE"
            record_security_event(db, SecurityEventType.EMAIL_VERIFIED, user_id=user.id, context=context)
        return user

    def reset_password(self, db: Session, *, raw_token: str, new_password: str, context: RequestContext) -> User | None:
        token = security_token_service.consume(db, raw_token=raw_token, purpose=SecurityTokenPurpose.PASSWORD_RESET)
        if not token:
            return None
        user = token.user
        user.password_hash = hash_password(new_password)
        session_service.revoke_for_user(db, user_id=user.id, reason="password_reset")
        record_security_event(db, SecurityEventType.PASSWORD_RESET, user_id=user.id, context=context)
        return user

    def issue_password_reset(self, db: Session, *, user: User, context: RequestContext, ttl: timedelta) -> str:
        _, raw_token = security_token_service.issue(
            db,
            user_id=user.id,
            purpose=SecurityTokenPurpose.PASSWORD_RESET,
            ttl=ttl,
            requested_ip=context.ip_address,
        )
        return raw_token


authentication_service = AuthenticationService()
