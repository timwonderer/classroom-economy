import hmac
import os
import secrets
from hashlib import sha256
from typing import Iterator, Tuple


def _load_peppers() -> Tuple[bytes, Tuple[bytes, ...]]:
    """Return the primary pepper and any legacy peppers as byte strings."""

    primary = os.environ.get("PEPPER_KEY")
    if not primary:
        raise KeyError("PEPPER_KEY")

    primary_bytes = primary.encode()

    legacy_values = []
    legacy_csv = os.environ.get("PEPPER_LEGACY_KEYS")
    if legacy_csv:
        legacy_values.extend(value.strip() for value in legacy_csv.split(",") if value.strip())

    # Support the historical environment variable name automatically.
    legacy_env = os.environ.get("PEPPER")
    if legacy_env:
        legacy_values.append(legacy_env)

    legacy_bytes = []
    for value in legacy_values:
        encoded = value.encode()
        if encoded != primary_bytes and encoded not in legacy_bytes:
            legacy_bytes.append(encoded)

    return primary_bytes, tuple(legacy_bytes)


_PEPPER, _LEGACY_PEPPERS = _load_peppers()


def get_primary_pepper() -> bytes:
    """Return the configured primary pepper."""

    return _PEPPER


def get_legacy_peppers() -> Tuple[bytes, ...]:
    """Return any configured legacy peppers."""

    return _LEGACY_PEPPERS


def get_all_peppers() -> Tuple[bytes, ...]:
    """Return a tuple containing the primary pepper followed by any legacy peppers."""

    return (_PEPPER, *_LEGACY_PEPPERS)


def hash_hmac(value: bytes, salt: bytes, pepper: bytes | None = None) -> str:
    """Return HMAC-SHA256 hex digest of ``salt + value`` using the provided pepper."""

    pepper_bytes = pepper or _PEPPER
    return hmac.new(pepper_bytes, salt + value, sha256).hexdigest()


def hash_username(username: str, salt: bytes, pepper: bytes | None = None) -> str:
    return hash_hmac(username.encode(), salt, pepper)


def iter_username_hashes(username: str, salt: bytes) -> Iterator[tuple[str, bytes]]:
    """Yield ``(hash, pepper)`` pairs for the username using all configured peppers."""

    for pepper in get_all_peppers():
        yield hash_username(username, salt, pepper=pepper), pepper


def get_random_salt() -> bytes:
    """Return 16 cryptographically secure random bytes."""

    return secrets.token_bytes(16)
