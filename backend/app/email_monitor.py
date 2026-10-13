"""Operator monitoring; aggregate delivery state only, never message bodies."""
import json
from datetime import UTC, datetime

from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.models.account_security import EmailDelivery


def main():
    settings = get_settings()
    with Session(get_engine()) as db:
        states = dict(db.execute(select(EmailDelivery.status, func.count()).group_by(EmailDelivery.status)).all())
        oldest = db.scalar(select(func.min(EmailDelivery.created_at)).where(EmailDelivery.status.in_(["QUEUED", "RETRYING"])))
    broker = "unreachable"
    try:
        with Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1) as client:
            if client.ping():
                broker = "reachable"
    except Exception:
        pass
    print(json.dumps({"states": states, "oldest_pending_seconds": int((datetime.now(UTC) - oldest).total_seconds()) if oldest else 0,
                      "broker": broker, "provider": settings.email_provider or "unconfigured"}))


if __name__ == "__main__":
    main()
