"""
Cloudflare Turnstile verification utility.

This module provides server-side verification for Cloudflare Turnstile tokens.
"""

import urllib.request
import urllib.parse
import json
from flask import current_app


def verify_turnstile_token(token, remote_ip=None):
    """
    Verify a Cloudflare Turnstile token with the Siteverify API.

    Args:
        token (str): The Turnstile token from the client (cf-turnstile-response)
        remote_ip (str, optional): The user's IP address for additional verification

    Returns:
        bool: True if the token is valid, False otherwise

    Notes:
        - Tokens expire after 5 minutes (300 seconds)
        - Each token can only be validated once
        - Server-side validation is mandatory for security
    """
    if not token:
        current_app.logger.warning("Turnstile verification failed: No token provided")
        return False

    secret_key = current_app.config.get('TURNSTILE_SECRET_KEY')
    if not secret_key:
        current_app.logger.error("Turnstile verification failed: TURNSTILE_SECRET_KEY not configured")
        return False

    # Cloudflare Turnstile siteverify endpoint
    url = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

    # Prepare the request data
    data = {
        'secret': secret_key,
        'response': token,
    }

    # Add remote IP if provided (optional but recommended)
    if remote_ip:
        data['remoteip'] = remote_ip

    try:
        # Encode the data
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')

        # Make the request
        req = urllib.request.Request(url, data=encoded_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))

        # Check if verification was successful
        if result.get('success'):
            current_app.logger.info(f"Turnstile verification successful: {result}")
            return True
        else:
            error_codes = result.get('error-codes', [])
            current_app.logger.warning(f"Turnstile verification failed: {error_codes}")
            return False

    except urllib.error.URLError as e:
        current_app.logger.error(f"Turnstile verification network error: {e}")
        return False
    except json.JSONDecodeError as e:
        current_app.logger.error(f"Turnstile verification JSON decode error: {e}")
        return False
    except Exception as e:
        current_app.logger.error(f"Turnstile verification unexpected error: {e}")
        return False
