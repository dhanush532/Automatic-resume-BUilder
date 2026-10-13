import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models.account_security import EmailChallenge, EmailDelivery
from app.models.user import User, UserSession
from app.schemas.auth import RegistrationRequest
from app.services.email_delivery import process_delivery
from tests.test_auth import PASSWORD, login, registration_payload, verify_user


def signup(client, **changes):
    data = {**registration_payload(), **changes}
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 201, response.text
    return data, response.json()


def accepted_code(db, response, provider):
    assert process_delivery(db, UUID(response["delivery_id"]), provider=provider, rate_check=lambda _: True) == "ACCEPTED"
    return re.search(r"\b[0-9]{6}\b", provider.messages[-1].text_body)[0]


def test_optional_phone_and_shared_phone_and_permanent_uuid(client, db_session):
    data = registration_payload()
    data.pop("phone")
    data.pop("username")
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 201 and response.json()["phone"] is None
    first = signup(client, phone="9000000001", phone_region="IN")[1]
    second = signup(client, phone="9000000001", phone_region="IN")[1]
    assert first["phone"] == second["phone"] == "+919000000001"
    assert first["id"] != second["id"]
    assert UUID(first["id"]).version == 4


def test_email_aliases_are_preserved_and_password_whitespace_is_preserved():
    data = {**registration_payload(), "email": "  A.B+tag@EXAMPLE.COM  ", "password": " StrongPassword!123 ", "confirm_password": " StrongPassword!123 "}
    value = RegistrationRequest(**data)
    assert value.email == "a.b+tag@example.com"
    assert value.password.startswith(" ") and value.password.endswith(" ")


def test_db_constraints_block_case_duplicate_and_uuid_duplicate(db_session, client):
    data, response = signup(client)
    user = db_session.get(User, response["id"])
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(text("INSERT INTO users (id,email,username,full_name,role,is_active) VALUES (:id,:email,:name,'Test account','USER',false)"),
                {"id": str(__import__('uuid').uuid4()), "email": user.email.upper(), "name": "collision_" + __import__('uuid').uuid4().hex[:10]})
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.execute(text("INSERT INTO users (id,email,username,full_name,role,is_active) VALUES (:id,'other@example.com',:name,'Test account','USER',false)"),
                {"id": str(user.id), "name": "collision_" + __import__('uuid').uuid4().hex[:10]})


def test_real_otp_flow_one_use_and_no_plaintext_api_or_database(client, db_session, test_email_provider):
    data, response = signup(client)
    assert client.post("/api/v1/auth/login", json={"identifier": data["email"], "password": PASSWORD}).status_code == 403
    code = accepted_code(db_session, response, test_email_provider)
    challenge = db_session.scalar(select(EmailChallenge).where(EmailChallenge.user_id == response["id"]))
    assert challenge.otp_hash != code and len(challenge.otp_hash) == 64
    assert code not in str(response)
    verified = client.post("/api/v1/auth/verify-email", json={"email": data["email"], "code": code})
    assert verified.status_code == 200
    assert verified.json()["id"] == response["id"]
    assert client.post("/api/v1/auth/verify-email", json={"email": data["email"], "code": code}).status_code == 400
    assert client.post("/api/v1/auth/login", json={"identifier": data["email"], "password": PASSWORD}).status_code == 200


def test_otp_expiry_attempt_limit_and_safe_resend(client, db_session, test_email_provider):
    data, response = signup(client)
    code = accepted_code(db_session, response, test_email_provider)
    challenge = db_session.scalar(select(EmailChallenge).where(EmailChallenge.user_id == response["id"]))
    wrong = "000001" if code != "000001" else "000002"
    for _ in range(5):
        assert client.post("/api/v1/auth/verify-email", json={"email": data["email"], "code": wrong}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"email": data["email"], "code": code}).status_code == 400
    assert client.post("/api/v1/auth/resend-verification", json={"email": data["email"]}).status_code == 429
    db_session.refresh(challenge)
    challenge.created_at = datetime.now(UTC) - timedelta(seconds=61)
    db_session.commit()
    resent = client.post("/api/v1/auth/resend-verification", json={"email": data["email"]})
    assert resent.status_code == 202
    new_code = accepted_code(db_session, resent.json(), test_email_provider)
    newest = db_session.scalar(select(EmailChallenge).where(EmailChallenge.user_id == response["id"]).order_by(EmailChallenge.created_at.desc()))
    newest.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert client.post("/api/v1/auth/verify-email", json={"email": data["email"], "code": new_code}).status_code == 400


def test_browser_binding_prevents_unrequested_pending_account_activation(client, db_session, test_email_provider):
    data, response = signup(client)
    code = accepted_code(db_session, response, test_email_provider)
    with TestClient(app) as unrelated:
        assert unrelated.post("/api/v1/auth/verify-email", json={"email": data["email"], "code": code}).status_code == 400
        assert unrelated.post("/api/v1/auth/resend-verification", json={"email": data["email"]}).status_code == 400


def test_abandoned_registration_recovery_updates_password_only_after_proof(client, db_session, test_email_provider):
    data, response = signup(client)
    challenge = db_session.scalar(select(EmailChallenge).where(EmailChallenge.user_id == response["id"]))
    challenge.created_at = datetime.now(UTC) - timedelta(minutes=6)
    challenge.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    replacement = {**data, "password": "Replacement!234", "confirm_password": "Replacement!234"}
    recovered = client.post("/api/v1/auth/register", json=replacement)
    assert recovered.status_code == 201 and recovered.json()["id"] == response["id"]
    code = accepted_code(db_session, recovered.json(), test_email_provider)
    assert client.post("/api/v1/auth/verify-email", json={"email": data["email"], "code": code}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"identifier": data["email"], "password": PASSWORD}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"identifier": data["email"], "password": "Replacement!234"}).status_code == 200


def test_contact_update_email_change_and_session_revocation_preserve_data(client, db_session, test_email_provider):
    data, response = signup(client)
    verify_user(client, db_session, response["id"])
    login(client, identifier=data["email"])
    assert client.put("/api/v1/passport/profile", json={"full_name": "Preserved Owner"}).status_code == 200
    resumes = client.get("/api/v1/resumes").json()
    result = client.patch("/api/v1/auth/account", json={"full_name": "New Name", "phone": None})
    assert result.status_code == 200 and result.json()["id"] == response["id"]
    new_email = "changed-" + __import__('uuid').uuid4().hex[:10] + "@example.com"
    assert client.post("/api/v1/auth/email-change", json={"email": new_email}).status_code == 202
    challenge = db_session.scalar(select(EmailChallenge).where(EmailChallenge.user_id == response["id"], EmailChallenge.purpose == "EMAIL_CHANGE"))
    delivery = db_session.scalar(select(EmailDelivery).where(EmailDelivery.challenge_id == challenge.id))
    assert db_session.get(User, response["id"]).email == data["email"]
    process_delivery(db_session, delivery.id, provider=test_email_provider, rate_check=lambda _: True)
    code = re.search(r"\b[0-9]{6}\b", test_email_provider.messages[-1].text_body)[0]
    confirmed = client.post("/api/v1/auth/email-change/confirm", json={"code": code})
    assert confirmed.status_code == 200 and confirmed.json()["id"] == response["id"]
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", json={"identifier": new_email, "password": PASSWORD}).status_code == 200
    assert client.get("/api/v1/resumes").json() == resumes


def test_recent_authentication_and_structured_error_redaction(client, db_session):
    data, response = signup(client)
    verify_user(client, db_session, response["id"])
    login(client, identifier=data["email"])
    session = db_session.scalar(select(UserSession).where(UserSession.user_id == response["id"]))
    session.recent_auth_at = datetime.now(UTC) - timedelta(minutes=11)
    db_session.commit()
    assert client.post("/api/v1/auth/email-change", json={"email": "other@example.com"}).status_code == 403
    assert client.post("/api/v1/auth/reauthenticate", json={"password": PASSWORD}).status_code == 204
    assert client.post("/api/v1/auth/email-change", json={"email": "other@example.com"}).status_code == 202
    weak = client.post("/api/v1/auth/register", json={**registration_payload(), "password": "SecretBAD", "confirm_password": "SecretBAD"})
    assert weak.status_code == 422 and "SecretBAD" not in weak.text


def test_account_deletion_is_owner_scoped_and_uuid_tombstone_remains(client, db_session):
    data, response = signup(client)
    verify_user(client, db_session, response["id"])
    login(client, identifier=data["email"])
    assert client.put("/api/v1/passport/profile", json={"full_name": "Delete Test Owner"}).status_code == 200
    assert client.post("/api/v1/auth/account/delete", json={"password": PASSWORD, "confirmation": "DELETE"}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    user = db_session.get(User, response["id"])
    db_session.refresh(user)
    assert user.id == UUID(response["id"]) and user.account_status == "DELETED"
    assert user.email != data["email"] and user.password_hash is None
    from app.models.resume import Resume, ResumeTemplate
    assert db_session.scalar(select(func.count()).select_from(Resume).where(Resume.user_id == user.id)) == 0
    assert db_session.scalar(select(func.count()).select_from(ResumeTemplate)) >= 7


def test_unconfigured_delivery_refuses_registration_without_creating_account(client, db_session):
    from app.integrations.email import UnconfiguredEmailProvider, get_email_provider
    app.dependency_overrides[get_email_provider] = lambda: UnconfiguredEmailProvider()
    data = registration_payload()
    assert client.post("/api/v1/auth/register", json=data).status_code == 503
    assert db_session.scalar(select(User).where(User.email == data["email"])) is None


def test_login_rate_limit_is_shared_database_state(client, db_session, monkeypatch):
    from app.core.config import get_settings
    from app.models.account_security import AuthRateBucket
    monkeypatch.setattr(get_settings(), "auth_login_rate_limit", 2)
    data, response = signup(client)
    verify_user(client, db_session, response["id"])
    for _ in range(2):
        assert client.post("/api/v1/auth/login", json={"identifier": data["email"], "password": "Incorrect!234"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"identifier": data["email"], "password": "Incorrect!234"}).status_code == 429
    assert db_session.scalar(select(func.count()).select_from(AuthRateBucket)) > 0
