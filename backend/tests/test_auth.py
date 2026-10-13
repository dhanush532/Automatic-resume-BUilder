from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.context import RequestContext
from app.models.user import LoginEvent, SecurityTokenPurpose, SessionStatus, User, UserSession
from app.services.authentication import authentication_service
from app.services.security_tokens import security_token_service

PASSWORD = "Trustworthy!234"
CONTEXT = RequestContext(
    ip_address="127.0.0.1",
    user_agent="CareerPilot test",
    device_type="desktop",
    browser="Test",
    operating_system="Test",
)


@pytest.fixture(autouse=True)
def clean_test_users(db_session: Session):
    created_ids: list[object] = []
    yield created_ids
    if created_ids:
        db_session.rollback()
        db_session.execute(delete(LoginEvent).where(LoginEvent.user_id.in_(created_ids)))
        db_session.execute(delete(User).where(User.id.in_(created_ids)))
        db_session.commit()


def registration_payload(suffix: str | None = None) -> dict[str, object]:
    suffix = suffix or uuid4().hex[:10]
    return {
        "full_name": "Taylor Careerpilot",
        "username": f"test_{suffix}",
        "email": f"test-{suffix}@example.com",
        "phone": "+14155552671" if suffix == "duplicate" else f"+1415{int(suffix[:7], 16) % 10_000_000:07d}",
        "password": PASSWORD,
        "confirm_password": PASSWORD,
        "terms_accepted": True,
    }


def register(client: TestClient, tracked_ids: list[object], suffix: str | None = None) -> dict[str, object]:
    response = client.post("/api/v1/auth/register", json=registration_payload(suffix))
    assert response.status_code == 201, response.text
    payload = response.json()
    tracked_ids.append(payload["id"])
    return payload


def verify_user(client: TestClient, db_session: Session, user_id: str) -> str:
    user = db_session.get(User, user_id)
    assert user
    _, raw_token = security_token_service.issue(
        db_session,
        user_id=user.id,
        purpose=SecurityTokenPurpose.EMAIL_VERIFICATION,
        ttl=timedelta(hours=1),
    )
    db_session.commit()
    response = client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 200, response.text
    return raw_token


def login(client: TestClient, *, identifier: str) -> dict[str, object]:
    response = client.post("/api/v1/auth/login", json={"identifier": identifier, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def test_successful_signup_normalizes_and_never_returns_password_data(
    client: TestClient, clean_test_users: list[object]
):
    data = registration_payload()
    data["email"] = str(data["email"]).upper()
    data["username"] = str(data["username"]).upper()
    response = client.post("/api/v1/auth/register", json=data)

    assert response.status_code == 201
    response_data = response.json()
    clean_test_users.append(response_data["id"])
    assert response_data["email"] == str(data["email"]).casefold()
    assert response_data["username"] == str(data["username"]).casefold()
    assert "password" not in response.text.casefold()
    assert "password_hash" not in response.text


def test_duplicate_email_and_username_are_rejected(client: TestClient, clean_test_users: list[object]):
    first = register(client, clean_test_users)
    duplicate_email = registration_payload()
    duplicate_email["email"] = first["email"]
    response = client.post("/api/v1/auth/register", json=duplicate_email)
    assert response.status_code == 409
    duplicate_username = registration_payload()
    duplicate_username["username"] = first["username"]
    response = client.post("/api/v1/auth/register", json=duplicate_username)
    assert response.status_code == 409


def test_invalid_signup_data_is_rejected(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Taylor",
            "username": "?",
            "email": "not-an-email",
            "phone": "123",
            "password": "weak",
            "confirm_password": "different",
            "terms_accepted": False,
        },
    )
    assert response.status_code == 422


def test_verified_user_can_login_and_receives_http_only_session(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user = register(client, clean_test_users)
    verify_user(client, db_session, user["id"])
    response = client.post("/api/v1/auth/login", json={"identifier": user["email"], "password": PASSWORD})

    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].casefold()
    assert "password_hash" not in response.text
    session = db_session.scalar(select(UserSession).where(UserSession.user_id == user["id"]))
    assert session and session.status == SessionStatus.ACTIVE
    assert len(session.token_hash) == 64


def test_invalid_password_is_generic_and_records_failure(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user = register(client, clean_test_users)
    response = client.post("/api/v1/auth/login", json={"identifier": user["email"], "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email/username or password."
    assert db_session.scalar(select(LoginEvent).where(LoginEvent.user_id == user["id"]))


def test_protected_endpoint_requires_authentication(client: TestClient):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_session_expiration_invalidates_the_session(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user = register(client, clean_test_users)
    verify_user(client, db_session, user["id"])
    login(client, identifier=user["username"])
    session = db_session.scalar(select(UserSession).where(UserSession.user_id == user["id"]))
    assert session
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    assert client.get("/api/v1/auth/me").status_code == 401
    db_session.refresh(session)
    assert session.status == SessionStatus.EXPIRED


def test_session_validation_refreshes_stale_activity(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user = register(client, clean_test_users)
    verify_user(client, db_session, user["id"])
    login(client, identifier=user["email"])
    session = db_session.scalar(select(UserSession).where(UserSession.user_id == user["id"]))
    assert session
    session.last_active_at = datetime.now(UTC) - timedelta(minutes=10)
    db_session.commit()

    assert client.get("/api/v1/auth/me").status_code == 200
    db_session.refresh(session)
    assert session.last_active_at > datetime.now(UTC) - timedelta(minutes=1)


def test_logout_revokes_current_session(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user = register(client, clean_test_users)
    verify_user(client, db_session, user["id"])
    login(client, identifier=user["email"])
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    session = db_session.scalar(select(UserSession).where(UserSession.user_id == user["id"]))
    assert session and session.status == SessionStatus.REVOKED
    assert client.get("/api/v1/auth/me").status_code == 401


def test_user_cannot_revoke_another_users_session(
    db_session: Session, clean_test_users: list[object]
):
    with TestClient(__import__("app.main", fromlist=["app"]).app) as user_a_client, TestClient(
        __import__("app.main", fromlist=["app"]).app
    ) as user_b_client:
        user_a = register(user_a_client, clean_test_users)
        user_b = register(user_b_client, clean_test_users)
        verify_user(user_a_client, db_session, user_a["id"])
        verify_user(user_b_client, db_session, user_b["id"])
        login(user_a_client, identifier=user_a["email"])
        login(user_b_client, identifier=user_b["email"])
        session_b = db_session.scalar(select(UserSession).where(UserSession.user_id == user_b["id"]))
        assert session_b
        response = user_a_client.delete(f"/api/v1/auth/sessions/{session_b.id}")
        assert response.status_code == 404
        db_session.refresh(session_b)
        assert session_b.status == SessionStatus.ACTIVE


def test_logout_all_other_sessions_preserves_current_session(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user = register(client, clean_test_users)
    verify_user(client, db_session, user["id"])
    login(client, identifier=user["email"])
    second_client = TestClient(__import__("app.main", fromlist=["app"]).app)
    login(second_client, identifier=user["username"])

    response = client.post("/api/v1/auth/sessions/logout-others")
    assert response.status_code == 204
    sessions = list(db_session.scalars(select(UserSession).where(UserSession.user_id == user["id"])))
    assert len([session for session in sessions if session.status == SessionStatus.ACTIVE]) == 1
    assert second_client.get("/api/v1/auth/me").status_code == 401
    second_client.close()


def test_email_verification_token_is_one_time_and_expires(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user = register(client, clean_test_users)
    raw_token = verify_user(client, db_session, user["id"])
    assert client.post("/api/v1/auth/verify-email", json={"token": raw_token}).status_code == 400
    _, expired_token = security_token_service.issue(
        db_session,
        user_id=user["id"],
        purpose=SecurityTokenPurpose.EMAIL_VERIFICATION,
        ttl=timedelta(seconds=-1),
    )
    db_session.commit()
    assert client.post("/api/v1/auth/verify-email", json={"token": expired_token}).status_code == 400


def test_password_reset_token_is_one_time_and_expires(
    client: TestClient, db_session: Session, clean_test_users: list[object]
):
    user_data = register(client, clean_test_users)
    verify_user(client, db_session, user_data["id"])
    user = db_session.get(User, user_data["id"])
    assert user
    raw_token = authentication_service.issue_password_reset(
        db_session, user=user, context=CONTEXT, ttl=timedelta(minutes=5)
    )
    db_session.commit()
    reset_body = {"token": raw_token, "password": "NewTrustworthy!234", "confirm_password": "NewTrustworthy!234"}
    assert client.post("/api/v1/auth/reset-password", json=reset_body).status_code == 204
    assert client.post("/api/v1/auth/reset-password", json=reset_body).status_code == 400
    _, expired_token = security_token_service.issue(
        db_session,
        user_id=user.id,
        purpose=SecurityTokenPurpose.PASSWORD_RESET,
        ttl=timedelta(seconds=-1),
    )
    db_session.commit()
    expired_body = {"token": expired_token, "password": PASSWORD, "confirm_password": PASSWORD}
    assert client.post("/api/v1/auth/reset-password", json=expired_body).status_code == 400
