import hmac
import os
import secrets
from hashlib import sha256


def _get_pepper() -> bytes:
    """Return the primary pepper as bytes."""

    value = os.environ.get("PEPPER_KEY")
    if not value:
        raise KeyError("PEPPER_KEY")
    return value.encode()


def hash_hmac(value: bytes, salt: bytes) -> str:
    """Return HMAC-SHA256 hex digest of ``salt + value`` using the primary pepper."""

    pepper = _get_pepper()
    return hmac.new(pepper, salt + value, sha256).hexdigest()


def hash_username(username: str, salt: bytes) -> str:
    return hash_hmac(username.encode(), salt)


def hash_username_lookup(username: str) -> str:
    """Return a deterministic HMAC hash for username lookups.

    This intentionally omits the per-user salt so we can query by username
    without scanning all stored salts. It still relies on the global pepper
    for secrecy.
    """

    pepper = _get_pepper()
    return hmac.new(pepper, username.encode(), sha256).hexdigest()


def get_random_salt() -> bytes:
    """Return 16 cryptographically secure random bytes."""

    return secrets.token_bytes(16)
