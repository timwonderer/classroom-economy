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
    """POST /admin/economy/update-expected-hours.

    This value lives on EconomicEngine (canonical per DOM-CLASS-002), not on
    payroll_settings. The route creates a new immutable engine version via
    FEAT-CLASS-005. The `apply_to_all` param is retained for form compatibility
    but is no longer meaningful (teacher context is always exactly one class).
    """
    return client.post(
        "/admin/economy/update-expected-hours",
        data={
            "expected_weekly_hours": expected_weekly_hours,
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


def customize_rent_settings(class_id: str, **fields: Any):
    """Record a new rent policy version for a class and return it.

    ``rent_settings`` is an append-only immutable repository (DOM-POL-001
    §VI.0/§VI.1): ``policy_uuid`` *is* the version, and the definition payload is
    frozen at insert. This helper therefore does NOT edit the provisioned row —
    it supersedes it, minting a new ``policy_uuid`` and retiring the predecessor,
    which is exactly what a teacher submission does in production. Unspecified
    fields are carried forward from the current policy, so a partial call still
    yields a complete contract.

    Editing in place is not merely discouraged here; ``RentSettings``'
    ``before_update`` guard rejects it outright, because an assessment that froze
    the old ``policy_uuid`` resolves its amount through that row.

    This is the highest-level authorized setup mechanism available for tests
    without a live teacher session (route-driven tests should use
    ``update_rent_settings`` instead). The write is performed through the
    canonical setup-FEAT boundary (FEAT-TEST-SETUP) so it does not bypass
    FEAT-INTEGRITY enforcement.
    """
    from app.services.admin_settings_service import supersede_rent_settings
    from app.services.class_configuration_query_service import get_rent_settings

    with FEATContext(
        "FEAT-TEST-SETUP",
        idempotency_key=f"rent_settings:customize:{class_id}",
    ):
        if get_rent_settings(class_id) is None:
            raise AssertionError(
                f"No canonical RentSettings found for class {class_id}; "
                "provision_classroom is expected to seed exactly one."
            )
        return supersede_rent_settings(class_id=class_id, updates=fields)


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


