from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.tokens import generate_raw_token, hash_token
from app.models.user import SecurityToken, SecurityTokenPurpose


class SecurityTokenService:
    def issue(
        self,
        db: Session,
        *,
        user_id: UUID,
        purpose: SecurityTokenPurpose,
        ttl: timedelta,
        requested_ip: str | None = None,
    ) -> tuple[SecurityToken, str]:
        now = datetime.now(UTC)
        db.execute(
            update(SecurityToken)
            .where(
                SecurityToken.user_id == user_id,
                SecurityToken.purpose == purpose,
                SecurityToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        raw_token = generate_raw_token()
        token = SecurityToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(raw_token),
            created_at=now,
            expires_at=now + ttl,
            requested_ip=requested_ip,
        )
        db.add(token)
        db.flush()
        return token, raw_token

    def consume(self, db: Session, *, raw_token: str, purpose: SecurityTokenPurpose) -> SecurityToken | None:
        now = datetime.now(UTC)
        statement = (
            select(SecurityToken)
            .where(
                SecurityToken.token_hash == hash_token(raw_token),
                SecurityToken.purpose == purpose,
                SecurityToken.used_at.is_(None),
            )
            .with_for_update()
        )
        token = db.scalar(statement)
        if not token or token.expires_at <= now:
            return None
        token.used_at = now
        return token


security_token_service = SecurityTokenService()
