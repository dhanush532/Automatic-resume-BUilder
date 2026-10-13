from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert

from app.auth.tokens import hash_token
from app.models.account_security import AuthRateBucket


def allow(db, key: str, *, limit: int, seconds: int) -> bool:
    now = datetime.now(UTC)
    statement = insert(AuthRateBucket).values(key=hash_token("rate:" + key), count=1, expires_at=now + timedelta(seconds=seconds))
    old = AuthRateBucket
    statement = statement.on_conflict_do_update(index_elements=[old.key], set_={
        "count": case((old.expires_at <= now, 1), else_=old.count + 1),
        "expires_at": case((old.expires_at <= now, now + timedelta(seconds=seconds)), else_=old.expires_at),
    }, where=(old.expires_at <= now) | (old.count < limit)).returning(old.key)
    return db.scalar(statement) is not None


def enforce(db, *keys: str, limit: int = 10, seconds: int = 3600):
    accepted = all(allow(db, key, limit=limit, seconds=seconds) for key in keys)
    db.commit()
    if not accepted:
        raise HTTPException(429, "Too many requests. Please wait before trying again.", headers={"Retry-After": str(seconds)})
