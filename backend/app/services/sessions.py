from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.auth.context import RequestContext
from app.auth.tokens import generate_raw_token, hash_token
from app.core.config import get_settings
from app.models.user import SessionStatus, User, UserSession


class SessionService:
    def create(self, db: Session, *, user: User, context: RequestContext) -> tuple[UserSession, str]:
        settings = get_settings()
        now = datetime.now(UTC)
        raw_token = generate_raw_token()
        session = UserSession(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            status=SessionStatus.ACTIVE,
            device_type=context.device_type,
            browser=context.browser,
            operating_system=context.operating_system,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            created_at=now,
            last_active_at=now,
            expires_at=now + timedelta(hours=settings.session_duration_hours),
            recent_auth_at=now,
        )
        db.add(session)
        db.flush()
        return session, raw_token

    def validate(self, db: Session, *, raw_token: str) -> UserSession | None:
        session = db.scalar(
            select(UserSession)
            .options(joinedload(UserSession.user))
            .join(UserSession.user)
            .where(UserSession.token_hash == hash_token(raw_token))
        )
        if not session or session.status != SessionStatus.ACTIVE or not session.user.is_active or not session.user.email_verified_at or session.user.deleted_at:
            return None
        if session.expires_at <= datetime.now(UTC):
            session.status = SessionStatus.EXPIRED
            db.commit()
            return None
        return session

    def touch(self, db: Session, *, session: UserSession) -> None:
        settings = get_settings()
        now = datetime.now(UTC)
        if session.last_active_at + timedelta(minutes=settings.session_activity_update_minutes) <= now:
            session.last_active_at = now
            db.commit()

    def revoke(self, db: Session, *, session: UserSession, reason: str) -> None:
        if session.status != SessionStatus.ACTIVE:
            return
        session.status = SessionStatus.REVOKED
        session.revoked_at = datetime.now(UTC)
        session.revoked_reason = reason

    def revoke_for_user(self, db: Session, *, user_id: UUID, reason: str, except_id: UUID | None = None) -> int:
        now = datetime.now(UTC)
        conditions = [UserSession.user_id == user_id, UserSession.status == SessionStatus.ACTIVE]
        if except_id:
            conditions.append(UserSession.id != except_id)
        result = db.execute(
            update(UserSession)
            .where(*conditions)
            .values(status=SessionStatus.REVOKED, revoked_at=now, revoked_reason=reason)
        )
        return result.rowcount or 0


session_service = SessionService()
