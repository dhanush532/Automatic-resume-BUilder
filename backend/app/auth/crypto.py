import base64
import hmac

from cryptography.fernet import Fernet

from app.auth.tokens import hash_token
from app.core.config import get_settings


def cipher() -> Fernet:
    hash_token("configuration-check")
    key = hmac.digest(get_settings().auth_secret.encode(), b"CareerPilot encrypted transient auth material v1", "sha256")
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return cipher().decrypt(value.encode()).decode()
