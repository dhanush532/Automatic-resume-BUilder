import hashlib
import hmac
import secrets

from app.core.config import get_settings


class AuthenticationConfigurationError(RuntimeError):
    pass


def generate_raw_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    settings = get_settings()
    if not settings.auth_secret:
        raise AuthenticationConfigurationError("AUTH_SECRET must be configured before authentication can be enabled.")
    if settings.is_production and settings.auth_secret == "replace-with-a-long-random-secret":
        raise AuthenticationConfigurationError("AUTH_SECRET must be replaced before production authentication is enabled.")
    return hmac.new(settings.auth_secret.encode("utf-8"), raw_token.encode("utf-8"), hashlib.sha256).hexdigest()
