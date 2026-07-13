import pytest
from decimal import Decimal
from app.extensions import db
from app.feats.base import FEATContext
from app.models import PayrollSettings
from app.payroll import get_daily_limit_seconds, get_pay_rate_for_block
from tests.helpers.v2_fixtures import seed_canonical_admin, seed_class_with_seat


def test_pay_rate_isolation_by_class_id(client):
    """Same teacher + same block across classes must not bleed settings."""
    teacher = seed_canonical_admin("teacher_scope_rates", "secret").user
    class_a = seed_class_with_seat(teacher=teacher, join_code="CLASS-A").class_row
    class_b = seed_class_with_seat(teacher=teacher, join_code="CLASS-B").class_row

    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll_join_code_scoping:rate"):
        db.session.add(
            PayrollSettings(
                class_id=class_a.class_id,
                block="Period 1",
                pay_rate=Decimal("0.50"),
                is_active=True,
            )
        )
        db.session.flush()

    rate_a = get_pay_rate_for_block("Period 1", class_id=class_a.class_id)
    rate_b = get_pay_rate_for_block("Period 1", class_id=class_b.class_id)

    assert round(rate_a * 60, 2) == Decimal("0.50")
    assert round(rate_b * 60, 2) == Decimal("0.25")


def test_daily_limit_isolation_by_class_id(client):
    """Daily limits must resolve by class_id, not teacher-level ownership."""
    teacher = seed_canonical_admin("teacher_scope_limits", "secret").user
    class_x = seed_class_with_seat(teacher=teacher, join_code="CLASS-X").class_row
    class_y = seed_class_with_seat(teacher=teacher, join_code="CLASS-Y").class_row

    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll_join_code_scoping:limit"):
        db.session.add(
            PayrollSettings(
                class_id=class_x.class_id,
                block="Period 1",
                settings_mode="simple",
                daily_limit_hours=2.0,
                is_active=True,
            )
        )
        db.session.flush()

    assert get_daily_limit_seconds("Period 1", class_id=class_x.class_id) == 7200
    assert get_daily_limit_seconds("Period 1", class_id=class_y.class_id) is None


def test_payroll_settings_lookup_requires_class_id(client):
    with pytest.raises(ValueError, match="class_id"):
        get_pay_rate_for_block("Period 1", class_id=None)

    with pytest.raises(ValueError, match="class_id"):
        get_daily_limit_seconds("Period 1", class_id=None)


def test_duplicate_active_settings_fail_closed(client):
    """Ambiguous active rows for same class/block must fail closed."""
    teacher = seed_canonical_admin("teacher_scope_dup", "secret").user
    class_a = seed_class_with_seat(teacher=teacher, join_code="CLASS-DUP").class_row

    with FEATContext("FEAT-ADMN-001", idempotency_key="payroll_join_code_scoping:duplicate"):
        db.session.add_all(
            [
                PayrollSettings(
                    class_id=class_a.class_id,
                    block="Period 1",
                    pay_rate=Decimal("0.50"),
                    is_active=True,
                ),
                PayrollSettings(
                    class_id=class_a.class_id,
                    block="Period 1",
                    pay_rate=Decimal("0.65"),
                    is_active=True,
                ),
            ]
        )
        db.session.flush()

    with pytest.raises(ValueError, match="Ambiguous PayrollSettings scope"):
        get_pay_rate_for_block("Period 1", class_id=class_a.class_id)
