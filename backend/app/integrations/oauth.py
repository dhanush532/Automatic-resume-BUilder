"""Official authorization-code providers. Stable subjects, never email-only identity."""
import base64
import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException

from app.auth.normalization import normalize_email
from app.core.config import get_settings

PROVIDERS = {
    "google": {"authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
               "jwks": "https://www.googleapis.com/oauth2/v3/certs", "issuer": ["https://accounts.google.com", "accounts.google.com"],
               "scope": "openid email profile", "pkce": True},
    "github": {"authorize": "https://github.com/login/oauth/authorize", "token": "https://github.com/login/oauth/access_token",
               "scope": "read:user user:email", "pkce": True},
    "linkedin": {"authorize": "https://www.linkedin.com/oauth/v2/authorization", "token": "https://www.linkedin.com/oauth/v2/accessToken",
                 "jwks": "https://www.linkedin.com/oauth/openid/jwks", "issuer": "https://www.linkedin.com",
                 "scope": "openid profile email", "pkce": False},
}


class OAuthError(ValueError):
    def __init__(self, message: str, *, code: str = "provider_unavailable"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class OAuthProfile:
    provider: str
    provider_user_id: str
    verified_email: str | None
    display_name: str | None
    email_verified: bool = True


def validate_id_token(token, *, jwks, audience, issuer, nonce):
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise OAuthError("Invalid identity token.")
        keys = jwt.PyJWKSet.from_dict(jwks)
        key = next(item.key for item in keys.keys if item.key_id == header["kid"])
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=audience, issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]})
        if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OAuthError("Invalid identity token.")
        if claims.get("azp", audience) != audience or (isinstance(claims["aud"], list) and len(claims["aud"]) > 1 and claims.get("azp") != audience):
            raise OAuthError("Invalid authorized party.")
        if not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 255:
            raise OAuthError("Invalid provider subject.")
        return claims
    except Exception:
        raise OAuthError("Invalid identity token.") from None


class OAuthProvider:
    def __init__(self, name):
        if name not in PROVIDERS:
            raise OAuthError("Unsupported authentication provider.")
        self.name, self.configuration = name, PROVIDERS[name]

    @property
    def is_configured(self):
        settings = get_settings()
        return bool(getattr(settings, self.name + "_client_id") and getattr(settings, self.name + "_client_secret"))

    def authorization_url(self, *, state, redirect_uri, verifier, nonce):
        settings = get_settings()
        params = {"client_id": getattr(settings, self.name + "_client_id"), "redirect_uri": redirect_uri,
                  "response_type": "code", "scope": self.configuration["scope"], "state": state}
        if self.configuration.get("jwks"):
            params["nonce"] = nonce
            params["prompt"] = "select_account" if self.name == "google" else "login"
        if self.configuration["pkce"]:
            params["code_challenge"] = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            params["code_challenge_method"] = "S256"
        return self.configuration["authorize"] + "?" + urlencode(params)

    async def exchange_code(self, *, code, redirect_uri, verifier, nonce):
        settings = get_settings()
        values = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
                  "client_id": getattr(settings, self.name + "_client_id"), "client_secret": getattr(settings, self.name + "_client_secret")}
        if self.configuration["pkce"]:
            values["code_verifier"] = verifier
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
                response = await client.post(self.configuration["token"], data=values, headers={"Accept": "application/json"})
                if not response.is_success or len(response.content) > 500_000:
                    raise OAuthError("Provider exchange failed.", code="provider_configuration" if response.status_code in {400, 401, 403} else "provider_unavailable")
                token = response.json()
                access = token.get("access_token")
                if not isinstance(access, str) or not access or token.get("error"):
                    raise OAuthError("Provider exchange failed.", code="provider_configuration" if token.get("error") in {"incorrect_client_credentials", "redirect_uri_mismatch", "invalid_client"} else "provider_unavailable")
                if self.name == "github":
                    headers = {"Authorization": "Bearer " + access, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
                    profile_reply = await client.get("https://api.github.com/user", headers=headers)
                    email_reply = await client.get("https://api.github.com/user/emails", headers=headers)
                    if not profile_reply.is_success or not email_reply.is_success:
                        raise OAuthError("Provider profile unavailable.")
                    profile, emails = profile_reply.json(), email_reply.json()
                    identifier = profile.get("id")
                    if not isinstance(identifier, int) or isinstance(identifier, bool) or identifier <= 0:
                        raise OAuthError("Invalid provider subject.")
                    verified = [item for item in emails if item.get("verified") is True and isinstance(item.get("email"), str)]
                    verified.sort(key=lambda item: not item.get("primary", False))
                    email = normalize_email(verified[0]["email"]) if verified else None
                    return OAuthProfile(self.name, str(identifier), email, profile.get("name") or profile.get("login"), bool(email))
                key_reply = await client.get(self.configuration["jwks"], headers={"Accept": "application/json"})
                if not key_reply.is_success or len(key_reply.content) > 500_000:
                    raise OAuthError("Identity verification unavailable.")
                claims = validate_id_token(token.get("id_token", ""), jwks=key_reply.json(),
                    audience=getattr(settings, self.name + "_client_id"), issuer=self.configuration["issuer"], nonce=nonce)
                if self.name == "linkedin":
                    info = await client.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": "Bearer " + access})
                    if info.is_success:
                        details = info.json()
                        if details.get("sub") != claims["sub"]:
                            raise OAuthError("Provider subject mismatch.")
                        claims.update({key: details[key] for key in ("email", "email_verified", "name") if key in details})
                email = normalize_email(claims["email"]) if isinstance(claims.get("email"), str) else None
                return OAuthProfile(self.name, claims["sub"], email, claims.get("name"), claims.get("email_verified") is True)
        except OAuthError:
            raise
        except Exception:
            raise OAuthError("Provider authentication failed. Please try again.") from None


def get_oauth_provider(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unsupported authentication provider.")
    return OAuthProvider(provider)


google_oauth_provider = OAuthProvider("google")
