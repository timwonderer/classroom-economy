"""
Passwordless.dev API Client

This module provides a client for interacting with the Passwordless.dev (Bitwarden)
API for WebAuthn/FIDO2 passkey authentication.

Documentation: https://docs.passwordless.dev/guide/api

Environment Variables Required:
- PASSWORDLESS_API_KEY: Private API secret for backend operations
- PASSWORDLESS_API_PUBLIC: Public API key for frontend operations

Note: This implementation uses passwordless.dev as the initial provider, but
the database schema and models are designed to be compatible with self-hosted
WebAuthn using the py-webauthn library for future migration if needed.
"""

import os
import requests
from typing import Dict, Any, Optional


class PasswordlessClient:
    """Client for Passwordless.dev API operations."""

    API_BASE_URL = "https://v4.passwordless.dev"

    def __init__(self):
        """
        Initialize the Passwordless.dev client.

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

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Passwordless.dev API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path (e.g., "/register/token")
            data: Request payload (for POST requests)

        Returns:
            JSON response from the API

        Raises:
            requests.HTTPError: If the API request fails
        """
        url = f"{self.API_BASE_URL}{endpoint}"
        headers = {
            "ApiSecret": self.api_key,
            "Content-Type": "application/json"
        }

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            timeout=10
        )

        response.raise_for_status()
        return response.json()

    def register_token(self, user_id: str, username: str, displayname: str) -> str:
        """
        Generate a registration token for creating a new passkey.

        This token is used by the frontend to initiate the WebAuthn credential
        creation ceremony.

        Args:
            user_id: Unique identifier for the system admin (e.g., "sysadmin_123")
            username: System admin username
            displayname: Display name for the credential

        Returns:
            Registration token to be used in the frontend

        Raises:
            requests.HTTPError: If the API request fails
        """
        payload = {
            "userId": user_id,
            "username": username,
            "displayname": displayname,
            "aliases": [username]  # Allow login by username
        }

        response = self._make_request("POST", "/register/token", payload)
        return response.get("token")

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
                - success (bool): Whether verification succeeded
                - userId (str): The user ID if successful
                - timestamp (str): When the token was verified
                - origin (str): Origin of the request
                - device (str): Device information
                - country (str): Country code
                - nickname (str): Credential nickname if set
                - credentialId (str): The credential ID used
                - expiresAt (str): When the token expires

        Raises:
            requests.HTTPError: If verification fails
        """
        payload = {"token": token}
        return self._make_request("POST", "/signin/verify", payload)

    def list_credentials(self, user_id: str) -> list:
        """
        List all credentials for a user.

        Args:
            user_id: The user ID to query credentials for

        Returns:
            List of credential dictionaries

        Raises:
            requests.HTTPError: If the API request fails
        """
        endpoint = f"/credentials/list?userId={user_id}"
        response = self._make_request("GET", endpoint)
        return response.get("values", [])

    def delete_credential(self, credential_id: str) -> bool:
        """
        Delete a specific credential.

        Args:
            credential_id: The credential ID to delete

        Returns:
            True if deletion succeeded

        Raises:
            requests.HTTPError: If the API request fails
        """
        endpoint = f"/credentials/{credential_id}"
        self._make_request("DELETE", endpoint)
        return True

    def get_public_key(self) -> str:
        """
        Get the public API key for frontend use.

        Returns:
            The public API key
        """
        return self.api_public


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
