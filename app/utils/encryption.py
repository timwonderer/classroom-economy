"""
Custom encryption types for securing PII (Personally Identifiable Information).

This module provides SQLAlchemy custom type decorators and helper functions for
encrypting sensitive data at rest using Fernet (AES encryption).
"""

import os
import base64
from sqlalchemy.types import TypeDecorator, LargeBinary
from cryptography.fernet import Fernet, InvalidToken


class PIIEncryptedType(TypeDecorator):
    """Custom AES encryption for PII fields using Fernet."""
    impl = LargeBinary

    def __init__(self, key_env_var, *args, **kwargs):
        key = os.getenv(key_env_var)
        if not key:
            raise RuntimeError(f"Missing required environment variable: {key_env_var}")
        self.fernet = Fernet(key)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.encode('utf-8')
        return self.fernet.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = self.fernet.decrypt(value)
        return decrypted.decode('utf-8')


# Helper functions for encrypting TOTP secrets (and other sensitive strings)
def _get_fernet():
    """Get Fernet cipher instance using ENCRYPTION_KEY environment variable."""
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise RuntimeError("Missing required environment variable: ENCRYPTION_KEY")
    return Fernet(key)


def encrypt_totp(plaintext_secret):
    """
    Encrypt a TOTP secret and return base64-encoded string suitable for database storage.

    Args:
        plaintext_secret (str): The plaintext TOTP secret (e.g., "JBSWY3DPEHPK3PXP")

    Returns:
        str: Base64-encoded encrypted secret
    """
    if not plaintext_secret:
        return None

    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(plaintext_secret.encode('utf-8'))
    # Return as base64 string for storage in VARCHAR column
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def decrypt_totp(encrypted_secret):
    """
    Decrypt a TOTP secret from base64-encoded encrypted string.

    Handles both encrypted (new) and plaintext (legacy) secrets for backward compatibility.
    If decryption fails, assumes it's a legacy plaintext secret and returns as-is.

    Args:
        encrypted_secret (str): Base64-encoded encrypted secret or legacy plaintext

    Returns:
        str: Plaintext TOTP secret
    """
    if not encrypted_secret:
        return None

    # Heuristic: Encrypted secrets are base64 (longer), plaintext TOTP secrets are exactly 32 chars
    # and only contain A-Z2-7 (base32 alphabet)
    if len(encrypted_secret) == 32 and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567' for c in encrypted_secret.upper()):
        # Legacy plaintext secret - return as-is
        return encrypted_secret

    # Try to decrypt
    try:
        fernet = _get_fernet()
        encrypted_bytes = base64.b64decode(encrypted_secret.encode('utf-8'))
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode('utf-8')
    except (InvalidToken, ValueError, TypeError, base64.binascii.Error):
        # If decryption fails, assume it's a legacy plaintext secret
        return encrypted_secret
