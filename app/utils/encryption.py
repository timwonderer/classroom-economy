"""
Custom encryption types for securing PII (Personally Identifiable Information).

This module provides SQLAlchemy custom type decorators for encrypting sensitive data
at rest using Fernet (AES encryption).
"""

import os
from sqlalchemy.types import TypeDecorator, LargeBinary
from cryptography.fernet import Fernet


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
