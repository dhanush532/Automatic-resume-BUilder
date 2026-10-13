from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.context import RequestContext
from app.models.user import LoginEvent, SecurityEventType


def record_security_event(
    db: Session,
    event_type: SecurityEventType,
    *,
    user_id: UUID | None = None,
    identifier: str | None = None,
    context: RequestContext | None = None,
    metadata: dict[str, str] | None = None,
) -> LoginEvent:
    event = LoginEvent(
        user_id=user_id,
        event_type=event_type,
        identifier=identifier,
        ip_address=context.ip_address if context else None,
        user_agent=context.user_agent if context else None,
        event_metadata=metadata,
        created_at=datetime.now(UTC),
    )
    db.add(event)
    return event
