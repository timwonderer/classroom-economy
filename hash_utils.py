import hmac
import os
import secrets
from hashlib import sha256

# PEPPER_KEY is now a required environment variable, checked in app.py.
# No default is provided here to ensure it fails fast if not set.
_PEPPER = os.environ["PEPPER_KEY"].encode()


def hash_hmac(value: bytes, salt: bytes) -> str:
    """Return HMAC-SHA256 hex digest of ``salt + value`` using a pepper."""
    return hmac.new(_PEPPER, salt + value, sha256).hexdigest()


def hash_username(username: str, salt: bytes) -> str:
    return hash_hmac(username.encode(), salt)


def get_random_salt() -> bytes:
    """Return 16 cryptographically secure random bytes."""
    return secrets.token_bytes(16)