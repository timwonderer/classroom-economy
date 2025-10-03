import hmac
import os
import secrets
from hashlib import sha256


_PEPPER = os.environ.get("PEPPER", "pepper").encode()


def hash_hmac(value: bytes, salt: bytes) -> str:
    """Return HMAC-SHA256 hex digest of ``salt + value`` using a pepper."""
    return hmac.new(_PEPPER, salt + value, sha256).hexdigest()


def hash_username(username: str, salt: bytes) -> str:
    return hash_hmac(username.encode(), salt)


def get_random_salt() -> bytes:
    """Return 16 random bytes."""
    try:
        import requests

        payload = {
            "jsonrpc": "2.0",
            "method": "generateBlobs",
            "params": {
                "apiKey": os.environ.get("RANDOM_ORG_API_KEY", ""),
                "n": 1,
                "size": 16,
            },
            "id": 1,
        }
        resp = requests.post("https://api.random.org/json-rpc/4/invoke", json=payload, timeout=5)
        resp.raise_for_status()
        blob = resp.json()["result"]["random"]["data"][0]
        return bytes.fromhex(blob)
    except Exception:
        return secrets.token_bytes(16)

