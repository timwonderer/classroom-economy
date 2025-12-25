"""
Passwordless.dev API Client (Official SDK Wrapper)

This module provides a wrapper around the official Bitwarden Passwordless.dev
Python SDK for WebAuthn/FIDO2 passkey authentication.

Official SDK: https://github.com/bitwarden/passwordless-python
Documentation: https://docs.passwordless.dev/guide/api

Environment Variables Required:
- PASSWORDLESS_API_KEY: Private API secret for backend operations
- PASSWORDLESS_API_PUBLIC: Public API key for frontend operations

Note: This implementation uses passwordless.dev as the initial provider, but
the database schema and models are designed to be compatible with self-hosted
WebAuthn using the py-webauthn library for future migration if needed.
"""

import os
import base64
from typing import Dict, Any

from passwordless import (
    PasswordlessClient as _PasswordlessClient,
    PasswordlessClientBuilder,
    PasswordlessOptions,
    RegisterToken,
    RegisteredToken,
    VerifySignIn,
    VerifiedUser,
)


class PasswordlessClient:
    """
    Wrapper around the official Passwordless.dev SDK.

    Provides a simplified interface for passkey operations while using
    the official Bitwarden SDK under the hood.
    """

    def __init__(self):
        """
        Initialize the Passwordless.dev client using the official SDK.

        Raises:
            ValueError: If required API keys are not configured
        """
        self.api_key = os.environ.get("PASSWORDLESS_API_KEY")
        self.api_public = os.environ.get("PASSWORDLESS_API_PUBLIC")

        if not self.api_key:
            raise ValueError(
                "PASSWORDLESS_API_KEY environment variable is required. "
                "Get your API keys from https://admin.passwordless.dev"
            )

        if not self.api_public:
            raise ValueError(
                "PASSWORDLESS_API_PUBLIC environment variable is required. "
                "Get your API keys from https://admin.passwordless.dev"
            )

        # Initialize the official SDK client
        # PasswordlessOptions(secret, url) - url defaults to https://v4.passwordless.dev
        api_url = os.environ.get("PASSWORDLESS_API_URL", "https://v4.passwordless.dev")
        options = PasswordlessOptions(self.api_key, api_url)
        self._client: _PasswordlessClient = PasswordlessClientBuilder(options).build()

    def register_token(self, user_id: str, username: str, displayname: str) -> str:
        """
        Generate a registration token for creating a new passkey.

        This token is used by the frontend to initiate the WebAuthn credential
        creation ceremony.

        Args:
            user_id: Unique identifier for the system admin (e.g., "sysadmin_123")
            username: System admin username
            displayname: Display name for the credential (used as username in SDK)

        Returns:
            Registration token to be used in the frontend

        Raises:
            Exception: If the SDK request fails
        """
        # Note: RegisterToken only accepts user_id, username, and aliases
        # The username parameter is what shows in the browser UI
        register_token = RegisterToken(
            user_id=user_id,
            username=displayname,  # This is shown in browser UI
            aliases=[username]      # Allow login by username
        )

        response: RegisteredToken = self._client.register_token(register_token)
        return response.token

    def verify_signin(self, token: str) -> Dict[str, Any]:
        """
        Verify a sign-in token after WebAuthn authentication.

        After the user completes the WebAuthn ceremony in the browser,
        the frontend sends a token back. This method verifies the token
        and returns user information.

        Args:
            token: The sign-in token from the frontend

        Returns:
            Dictionary containing:
                - success (bool): Whether verification succeeded (always True if no exception)
                - userId (str): The user ID if successful
                - timestamp (str): When the token was verified
                - origin (str): Origin of the request
                - device (str): Device information
                - country (str): Country code
                - credentialId (str): The credential ID used
                - type (str): Credential type
                - expiresAt (str): When the token expires

        Raises:
            Exception: If verification fails
        """
        verify_signin = VerifySignIn(token)
        user: VerifiedUser = self._client.sign_in(verify_signin)

        # Convert VerifiedUser to dictionary format expected by our code
        return {
            "success": True,
            "userId": user.user_id,
            "timestamp": user.timestamp,
            "origin": user.origin,
            "device": user.device,
            "country": user.country,
            "credentialId": user.credential_id,
            "type": user.type,
            "expiresAt": user.expires_at
        }

    def get_public_key(self) -> str:
        """
        Get the public API key for frontend use.

        Returns:
            The public API key
        """
        return self.api_public


def decode_credential_id(credential_id_b64: str) -> bytes:
    """
    Decode a base64url-encoded credential ID from passwordless.dev.

    Handles padding automatically as credential IDs may not be padded.

    Args:
        credential_id_b64: Base64url-encoded credential ID string

    Returns:
        Decoded credential ID as bytes

    Raises:
        ValueError: If the credential ID cannot be decoded
    """
    # Add padding if needed (base64url strings must be multiples of 4)
    credential_id_b64 += '=' * (4 - len(credential_id_b64) % 4)
    return base64.urlsafe_b64decode(credential_id_b64)


# Singleton instance
_client = None


def get_passwordless_client() -> PasswordlessClient:
    """
    Get or create the Passwordless.dev client singleton.

    Returns:
        PasswordlessClient instance

    Raises:
        ValueError: If API keys are not configured
    """
    global _client
    if _client is None:
        _client = PasswordlessClient()
    return _client
