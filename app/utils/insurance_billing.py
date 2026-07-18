"""Helpers for canonical seat-scoped insurance billing cadence."""

from __future__ import annotations

import json
from datetime import timedelta

from app.utils.time import ensure_utc


def _policy_payload(policy_version) -> dict:
    if policy_version is None:
        return {}
    payload = getattr(policy_version, "policy_payload_json", None)
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def get_insurance_billing_snapshot(policy_version) -> dict:
    """Return the canonical billing fields for an insurance policy version."""
    payload = _policy_payload(policy_version)
    return {
        "premium": payload.get("premium", payload.get("insurance_premium", 0)),
        "charge_frequency": payload.get("charge_frequency", "monthly"),
        "waiting_period_days": int(payload.get("waiting_period_days", 0) or 0),
        "cycle_length_days": int(payload.get("cycle_length_days", 30) or 30),
    }


def insurance_next_payment_due(now_utc, charge_frequency):
    """Return the next premium due date for the given billing frequency."""
    frequency = (charge_frequency or "monthly").lower()
    now_utc = ensure_utc(now_utc)
    if frequency == "weekly":
        return now_utc + timedelta(days=7)
    if frequency == "biweekly":
        return now_utc + timedelta(days=14)
    if frequency == "semester":
        return now_utc + timedelta(days=7 * 16)
    return now_utc + timedelta(days=28)
