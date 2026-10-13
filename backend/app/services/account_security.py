from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from app.core.config import get_settings


def require_recent_auth(authenticated):
    stamp = authenticated.session.recent_auth_at
    if not stamp or stamp + timedelta(minutes=get_settings().recent_auth_minutes) <= datetime.now(UTC):
        raise HTTPException(403, "Please reauthenticate before changing account security settings.")
