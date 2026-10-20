import base64
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.integrations.oauth import OAuthError, OAuthProfile, get_oauth_provider, validate_id_token
from app.main import app
from app.models.account_security import OAuthAttempt
from app.models.user import OAuthIdentity, User, UserSession
from tests.test_auth import login, registration_payload, verify_user


class MockOAuth:
    is_configured = True
    def __init__(self, name, profile):
        self.name, self.profile = name, profile
    def authorization_url(self, **values):
        return "https://provider.example/authorize?" + urlencode({"state": values["state"]})
    async def exchange_code(self, **values):
        if values["code"] != "test-code":
            raise OAuthError("Test-only rejected code")
        return OAuthProfile(self.name, **self.profile)


@pytest.fixture
def provider_profile():
    profile = {"provider_user_id": "test-subject-" + uuid4().hex, "verified_email": "oauth-" + uuid4().hex[:10] + "@example.com", "display_name": "Provider Test User", "email_verified": True}
    app.dependency_overrides[get_oauth_provider] = lambda provider: MockOAuth(provider, profile)
    yield profile
    app.dependency_overrides.pop(get_oauth_provider, None)


def authorize(client, provider, *, mode="login", terms=True):
    reply = client.post(f"/api/v1/auth/oauth/{provider}/start", json={"mode": mode, "terms_accepted": terms})
    assert reply.status_code == 200, reply.text
    return parse_qs(urlparse(reply.json()["authorization_url"]).query)["state"][0]


def callback(client, provider, state, code="test-code"):
    return client.get(f"/api/v1/auth/oauth/{provider}/callback", params={"state": state, "code": code}, follow_redirects=False)


@pytest.mark.parametrize("provider", ["google", "github", "linkedin"])
def test_social_registration_and_login_keep_same_uuid(client, db_session, provider_profile, provider):
    state = authorize(client, provider)
    reply = callback(client, provider, state)
    assert reply.status_code == 303 and reply.headers["location"].endswith("/review")
    user = client.get("/api/v1/auth/me").json()
    assert user["email"] == provider_profile["verified_email"]
    assert db_session.get(User, user["id"]).password_hash is None
    client.post("/api/v1/auth/logout")
    state = authorize(client, provider)
    assert callback(client, provider, state).headers["location"].endswith("/review")
    assert client.get("/api/v1/auth/me").json()["id"] == user["id"]
    assert db_session.scalar(select(func.count()).select_from(OAuthIdentity).where(OAuthIdentity.user_id == user["id"])) == 1


@pytest.mark.parametrize("provider", ["google", "github", "linkedin"])
def test_matching_email_requires_explicit_linking_and_preserves_data(client, db_session, provider_profile, provider):
    data = registration_payload()
    response = client.post("/api/v1/auth/register", json=data)
    owner = response.json()
    verify_user(client, db_session, owner["id"])
    provider_profile["verified_email"] = owner["email"]
    state = authorize(client, provider)
    result = callback(client, provider, state)
    assert "link_existing_account" in result.headers["location"]
    assert client.get("/api/v1/auth/me").status_code == 401
    assert db_session.scalar(select(func.count()).select_from(User).where(User.email == owner["email"])) == 1
    login(client, identifier=owner["email"])
    client.put("/api/v1/passport/profile", json={"full_name": "Preserved OAuth Owner"})
    resumes = client.get("/api/v1/resumes").json()
    state = authorize(client, provider, mode="link")
    assert "oauth=success" in callback(client, provider, state).headers["location"]
    assert client.get("/api/v1/auth/me").json()["id"] == owner["id"]
    assert client.get("/api/v1/resumes").json() == resumes
    assert client.delete(f"/api/v1/auth/oauth-identities/{provider}").status_code == 204


def test_invalid_replayed_expired_state_and_browser_mismatch_fail(client, db_session, provider_profile):
    assert "authentication_failed" in callback(client, "google", "invalid").headers["location"]
    state = authorize(client, "google")
    with TestClient(app) as other_browser:
        assert "authentication_failed" in callback(other_browser, "google", state).headers["location"]
    assert callback(client, "google", state).headers["location"].endswith("/review")
    assert "authentication_failed" in callback(client, "google", state).headers["location"]
    state = authorize(client, "google")
    row = db_session.scalar(select(OAuthAttempt).where(OAuthAttempt.consumed_at.is_(None)).order_by(OAuthAttempt.expires_at.desc()))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert "authentication_failed" in callback(client, "google", state).headers["location"]


def test_invalid_provider_token_and_unverified_email_do_not_create_account(client, db_session, provider_profile):
    state = authorize(client, "google")
    assert "authentication_failed" in callback(client, "google", state, code="bad-code").headers["location"]
    provider_profile["email_verified"] = False
    state = authorize(client, "linkedin")
    assert "authentication_failed" in callback(client, "linkedin", state).headers["location"]
    assert db_session.scalar(select(User).where(User.email == provider_profile["verified_email"])) is None


def test_last_method_recent_auth_and_duplicate_provider_identity(client, db_session, provider_profile):
    state = authorize(client, "github")
    callback(client, "github", state)
    owner = client.get("/api/v1/auth/me").json()
    assert client.delete("/api/v1/auth/oauth-identities/github").status_code == 409
    session = db_session.scalar(select(UserSession).where(UserSession.user_id == owner["id"]))
    session.recent_auth_at = datetime.now(UTC) - timedelta(minutes=11)
    db_session.commit()
    assert client.post("/api/v1/auth/oauth/google/start", json={"mode": "link"}).status_code == 403
    state = authorize(client, "github", mode="reauth")
    assert "oauth=success" in callback(client, "github", state).headers["location"]
    other_data = registration_payload()
    client.post("/api/v1/auth/logout")
    other = client.post("/api/v1/auth/register", json=other_data).json()
    verify_user(client, db_session, other["id"])
    login(client, identifier=other["email"])
    state = authorize(client, "github", mode="link")
    assert "authentication_failed" in callback(client, "github", state).headers["location"]
    identity = db_session.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == "github", OAuthIdentity.provider_user_id == provider_profile["provider_user_id"]))
    assert str(identity.user_id) == owner["id"]


def test_unauthorized_linking_is_rejected(client, provider_profile):
    assert client.post("/api/v1/auth/oauth/google/start", json={"mode": "link"}).status_code == 401


def test_new_social_account_without_consent_returns_to_signup(client, db_session, provider_profile):
    state = authorize(client, "github", terms=False)
    response = callback(client, "github", state)
    assert response.headers["location"].endswith("/signup?oauth_error=terms_required")
    assert db_session.scalar(select(User).where(User.email == provider_profile["verified_email"])) is None
    assert client.get("/api/v1/auth/me").status_code == 401
    state = authorize(client, "github", terms=True)
    assert callback(client, "github", state).headers["location"].endswith("/review")


def test_existing_social_account_can_sign_in_without_new_registration_consent(client, provider_profile):
    state = authorize(client, "github")
    callback(client, "github", state)
    owner = client.get("/api/v1/auth/me").json()["id"]
    client.post("/api/v1/auth/logout")
    state = authorize(client, "github", terms=False)
    assert callback(client, "github", state).headers["location"].endswith("/review")
    assert client.get("/api/v1/auth/me").json()["id"] == owner


def test_invalid_callback_does_not_destroy_another_pending_attempt(client, provider_profile):
    state = authorize(client, "github")
    assert "session_expired" in callback(client, "github", "unrelated-invalid-state").headers["location"]
    assert callback(client, "github", state).headers["location"].endswith("/review")


def test_cancelled_sign_in_and_provider_errors_have_safe_reasons(client, provider_profile, monkeypatch, caplog):
    cancelled = client.get("/api/v1/auth/oauth/github/callback?error=access_denied", follow_redirects=False)
    assert "reason=access_denied" in cancelled.headers["location"]

    async def failed_exchange(self, **kwargs):
        raise OAuthError("DO-NOT-LOG-provider-access-token", code="provider_configuration")

    monkeypatch.setattr(MockOAuth, "exchange_code", failed_exchange)
    state = authorize(client, "github")
    failed = callback(client, "github", state)
    assert "reason=provider_configuration" in failed.headers["location"]
    assert "DO-NOT-LOG" not in caplog.text and "reason=provider_configuration" in caplog.text


def test_unsupported_oauth_provider_is_not_a_server_error(client):
    assert client.post("/api/v1/auth/oauth/unknown/start", json={"mode": "login"}).status_code == 404
    assert client.get("/api/v1/auth/oauth/unknown/callback").status_code == 404


@pytest.fixture
def signed_identity():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_numbers()
    def encode(number):
        return base64.urlsafe_b64encode(number.to_bytes((number.bit_length()+7)//8, "big")).rstrip(b"=").decode()
    jwks = {"keys": [{"kty": "RSA", "kid": "test-key", "use": "sig", "alg": "RS256", "n": encode(public.n), "e": encode(public.e)}]}
    claims = {"iss": "https://accounts.google.com", "aud": "test-client", "sub": "test-subject", "iat": int(datetime.now(UTC).timestamp()), "exp": int((datetime.now(UTC)+timedelta(minutes=5)).timestamp()), "nonce": "test-nonce"}
    return private, jwks, claims


@pytest.mark.parametrize("change", [{"aud":"wrong"},{"iss":"https://evil.example"},{"nonce":"wrong"},{"exp":1},{"sub":""},{"azp":"wrong"}])
def test_oidc_claim_validation_is_strict(signed_identity, change):
    private, jwks, claims = signed_identity
    token = jwt.encode({**claims, **change}, private, algorithm="RS256", headers={"kid":"test-key"})
    with pytest.raises(OAuthError):
        validate_id_token(token, jwks=jwks, audience="test-client", issuer="https://accounts.google.com", nonce="test-nonce")


def test_oidc_valid_signature_and_forged_signature(signed_identity):
    private, jwks, claims = signed_identity
    token = jwt.encode(claims, private, algorithm="RS256", headers={"kid":"test-key"})
    assert validate_id_token(token, jwks=jwks, audience="test-client", issuer="https://accounts.google.com", nonce="test-nonce")["sub"] == "test-subject"
    fake = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(claims, fake, algorithm="RS256", headers={"kid":"test-key"})
    with pytest.raises(OAuthError):
        validate_id_token(token, jwks=jwks, audience="test-client", issuer="https://accounts.google.com", nonce="test-nonce")
