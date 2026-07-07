import hmac
import secrets
from hashlib import sha256

from app.core.config import get_settings


ACCESS_KEY_PREFIX = "lcg_ak_"


def generate_access_key() -> tuple[str, str, str]:
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    return prefix, secret, f"{ACCESS_KEY_PREFIX}{prefix}.{secret}"


def hash_access_key_secret(secret: str) -> str:
    salt = get_settings().access_key_hash_salt.encode()
    return hmac.new(salt, secret.encode(), sha256).hexdigest()


def parse_access_key(token: str) -> tuple[str, str] | None:
    if not token.startswith(ACCESS_KEY_PREFIX) or "." not in token:
        return None
    left, secret = token.split(".", 1)
    prefix = left.removeprefix(ACCESS_KEY_PREFIX)
    if not prefix or not secret:
        return None
    return prefix, secret

