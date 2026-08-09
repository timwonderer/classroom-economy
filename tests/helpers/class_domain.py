"""Canonical class-domain FEAT route wrappers for test setup.

Every helper in this module performs exactly one production action by calling a
real FEAT route. No helper mutates DB state directly.

Tests should pair these wrappers with the canonical classroom initializer from
tests.helpers.classroom_initializer.
"""

from __future__ import annotations

from typing import Any

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassFeature


def enable_class_feature(*, class_id: str, feature_name: str = None, feature: str = None):
    """Seed a single class feature row via the production FEAT path.

    Args:
        class_id: The class to enable feature for
        feature_name: DEPRECATED - use 'feature' instead
        feature: Feature name (e.g., 'payroll', 'rent', 'banking')
    """
    # Support both old and new parameter names for backward compatibility during migration
    feature_value = feature or feature_name
    if not feature_value:
        raise ValueError("Either 'feature' or 'feature_name' parameter must be provided")

    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"class_feature:enable:{class_id}:{feature_value}"):
        # Phase 2 semantic: Feature is enabled by linking to current EconomicEngine version
        from app.models import EconomicEngine
        from sqlalchemy import desc

        # Get the most recent EconomicEngine version for this class
        latest_engine = EconomicEngine.query.filter_by(
            class_id=class_id
        ).order_by(desc(EconomicEngine.created_at)).first()

        # If no engine exists, create a default one for this class
        if not latest_engine:
            latest_engine = EconomicEngine(
                class_id=class_id,
                economic_version_id="v1",  # Default initial version
                economy_policy_mode="default",
            )
            db.session.add(latest_engine)
            db.session.flush()

        economic_version_id = latest_engine.economic_version_id

        cf = ClassFeature(
            class_id=class_id,
            feature=feature_value,
            economic_version_id=economic_version_id  # Link to current version for enablement
        )
        db.session.add(cf)
        db.session.flush()
        db.session.info["feat_orchestrator_commit"] = True
        try:
            db.session.commit()
        finally:
            db.session.info.pop("feat_orchestrator_commit", None)
        return cf


def disable_class_feature(*, class_id: str, feature_name: str = None, feature: str = None):
    """Disable a class feature by appending a disablement row (append-only).

    Phase 2 semantics: Rather than deleting the feature row, we append a new row
    with economic_version_id=None to represent disablement. This preserves the
    append-only timeline contract.

    Args:
        class_id: The class
        feature_name: DEPRECATED - use 'feature' instead
        feature: Feature name (e.g., 'payroll', 'rent', 'banking')
    """
    # Support both old and new parameter names for backward compatibility during migration
    feature_value = feature or feature_name
    if not feature_value:
        raise ValueError("Either 'feature' or 'feature_name' parameter must be provided")

    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"class_feature:disable:{class_id}:{feature_value}"):
        # Check if feature currently exists as enabled
        existing = ClassFeature.query.filter_by(
            class_id=class_id,
            feature=feature_value
        ).order_by(ClassFeature.effective_at.desc()).first()

        if existing and existing.economic_version_id is not None:
            # Feature is currently enabled; append a disablement row
            cf = ClassFeature(
                class_id=class_id,
                feature=feature_value,
                economic_version_id=None  # Signals "disabled"
            )
            db.session.add(cf)
            db.session.flush()
            db.session.info["feat_orchestrator_commit"] = True
            try:
                db.session.commit()
            finally:
                db.session.info.pop("feat_orchestrator_commit", None)
            return cf
        else:
            # Feature already disabled or doesn't exist; no-op
            return existing


def update_payroll_settings(client, **form_data: Any):
    """POST /admin/payroll/settings."""
    return client.post(
        "/admin/payroll/settings",
        data=form_data,
        follow_redirects=False,
    )


def update_expected_weekly_hours(client, expected_weekly_hours: str, *, apply_to_all: bool = False):
    """POST /admin/payroll/update-expected-hours."""
    return client.post(
        "/admin/payroll/update-expected-hours",
        data={
            "expected_weekly_hours": expected_weekly_hours,
            "apply_to_all": "true" if apply_to_all else "false",
        },
        follow_redirects=False,
    )


def update_rent_settings(client, **form_data: Any):
    """POST /admin/rent-settings."""
    return client.post(
        "/admin/rent-settings",
        data=form_data,
        follow_redirects=False,
    )


def manual_payroll(
    client,
    *,
    student_ids: list[int | str],
    description: str,
    amount: str,
    account_type: str = "checking",
    save_action: str = "apply_only",
    payment_type: str = "deposit",
):
    """POST /admin/payroll/manual-payment."""
    payload: dict[str, Any] = {
        "student_ids": [str(student_id) for student_id in student_ids],
        "description": description,
        "amount": amount,
        "account_type": account_type,
        "save_action": save_action,
        "payment_type": payment_type,
    }
    return client.post(
        "/admin/payroll/manual-payment",
        data=payload,
        follow_redirects=False,
    )


def tap_in_student(client, seat_id: int):
    """POST /admin/tap-in-students for one seat."""
    return client.post(
        "/admin/tap-in-students",
        json={"seat_ids": [seat_id]},
        follow_redirects=False,
    )


def tap_in_students(client, seat_ids: list[int]):
    """POST /admin/tap-in-students for many seats."""
    return client.post(
        "/admin/tap-in-students",
        json={"seat_ids": seat_ids},
        follow_redirects=False,
    )


def tap_out_student(client, seat_id: int, *, reason: str = "Teacher tap-out"):
    """POST /admin/tap-out-students for one seat."""
    return client.post(
        "/admin/tap-out-students",
        json={"seat_ids": [seat_id], "reason": reason},
        follow_redirects=False,
    )


def tap_out_students(client, seat_ids: list[int] | None = None, *, tap_out_all: bool = False, reason: str = "Teacher tap-out"):
    """POST /admin/tap-out-students for many seats or all seats."""
    payload: dict[str, Any] = {"reason": reason, "tap_out_all": tap_out_all}
    if seat_ids is not None:
        payload["seat_ids"] = seat_ids
    return client.post(
        "/admin/tap-out-students",
        json=payload,
        follow_redirects=False,
    )


def update_feature_settings_for_period(client, period: str, **features: Any):
    """POST /admin/feature-settings/period/<period>."""
    return client.post(
        f"/admin/feature-settings/period/{period}",
        json=features,
        follow_redirects=False,
    )


def copy_feature_settings(client, *, source_period: str, target_periods: list[str]):
    """POST /admin/feature-settings/copy."""
    return client.post(
        "/admin/feature-settings/copy",
        json={
            "source_period": source_period,
            "target_periods": target_periods,
        },
        follow_redirects=False,
    )
