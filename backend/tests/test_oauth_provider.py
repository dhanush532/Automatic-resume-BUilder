import asyncio
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest

from app.integrations.oauth import OAuthError, OAuthProvider


def github_client(monkeypatch, handler):
    monkeypatch.setattr("app.integrations.oauth.get_settings", lambda: SimpleNamespace(github_client_id="test-client", github_client_secret="test-secret"))
    client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr("app.integrations.oauth.httpx.AsyncClient", lambda **kwargs: client(transport=transport, **kwargs))


def test_github_exchange_uses_pkce_and_private_verified_email(monkeypatch):
    def provider(request):
        if request.url.path == "/login/oauth/access_token":
            values = parse_qs(request.content.decode())
            assert values["code_verifier"] == ["test-verifier"]
            assert values["client_id"] == ["test-client"]
            return httpx.Response(200, json={"access_token": "test-access"})
        assert request.headers["Authorization"] == "Bearer test-access"
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 12345, "name": None, "login": "test-user"})
        assert request.url.path == "/user/emails"
        return httpx.Response(200, json=[{"email": "unverified@example.com", "verified": False, "primary": True}, {"email": "private@example.com", "verified": True, "primary": False}])

    github_client(monkeypatch, provider)
    profile = asyncio.run(OAuthProvider("github").exchange_code(code="test-code", redirect_uri="https://web.example/api/v1/auth/oauth/github/callback", verifier="test-verifier", nonce="test-nonce"))
    assert profile.provider_user_id == "12345" and profile.display_name == "test-user"
    assert profile.verified_email == "private@example.com" and profile.email_verified


@pytest.mark.parametrize("error", ["incorrect_client_credentials", "redirect_uri_mismatch", "invalid_client"])
def test_github_configuration_rejection_is_classified_without_exposing_body(monkeypatch, error):
    github_client(monkeypatch, lambda request: httpx.Response(200, json={"error": error, "error_description": "private-provider-detail"}))
    with pytest.raises(OAuthError) as caught:
        asyncio.run(OAuthProvider("github").exchange_code(code="test-code", redirect_uri="https://web.example/callback", verifier="verifier", nonce="nonce"))
    assert caught.value.code == "provider_configuration"
    assert "private-provider-detail" not in str(caught.value)
