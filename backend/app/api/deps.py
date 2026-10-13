from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db_session
from app.models.user import User, UserSession
from app.services.sessions import session_service


@dataclass(frozen=True)
class AuthenticatedRequest:
    user: User
    session: UserSession


def require_authenticated_request(
    request: Request, db: Session = Depends(get_db_session)
) -> AuthenticatedRequest:
    raw_token = request.cookies.get(get_settings().session_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    session = session_service.validate(db, raw_token=raw_token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or has expired.")
    session_service.touch(db, session=session)
    return AuthenticatedRequest(user=session.user, session=session)


def require_same_site_mutation(request: Request) -> None:
    """Reject explicit cross-site browser mutations before cookie-backed handlers run."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != get_settings().frontend_origin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-site request rejected.")


def require_current_user(authenticated: AuthenticatedRequest = Depends(require_authenticated_request)) -> User:
    return authenticated.user
