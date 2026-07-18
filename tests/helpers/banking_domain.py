"""Canonical banking-domain FEAT route wrappers for test setup."""

from __future__ import annotations

from typing import Any


def update_banking_settings(client, **form_data: Any):
    """POST /admin/banking/settings."""
    return client.post(
        "/admin/banking/settings",
        data=form_data,
        follow_redirects=False,
    )
