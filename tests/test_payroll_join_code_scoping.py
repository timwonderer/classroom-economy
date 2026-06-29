import pytest
from decimal import Decimal

from app.extensions import db
from app.models import ClassEconomy, PayrollSettings
from app.payroll import get_daily_limit_seconds, get_pay_rate_for_block
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import create_class_scope


def _create_class(admin, join_code: str) -> ClassEconomy:
    return create_class_scope(
        teacher=admin,
        join_code=join_code,
        block="A",
        display_name=join_code,
    )


def test_pay_rate_isolation_by_class_id(client):
    """Same teacher + same block across classes must not bleed settings."""
    teacher = make_admin("teacher_scope_rates", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_a = _create_class(teacher, "CLASS-A")
    class_b = _create_class(teacher, "CLASS-B")

    db.session.add(
        PayrollSettings(
            class_id=class_a.class_id,
            block="Period 1",
            pay_rate=Decimal("0.50"),
            is_active=True,
        )
    )
    db.session.commit()

    rate_a = get_pay_rate_for_block("Period 1", class_id=class_a.class_id)
    rate_b = get_pay_rate_for_block("Period 1", class_id=class_b.class_id)

    assert round(rate_a * 60, 2) == Decimal("0.50")
    assert round(rate_b * 60, 2) == Decimal("0.25")


def test_daily_limit_isolation_by_class_id(client):
    """Daily limits must resolve by class_id, not teacher-level ownership."""
    teacher = make_admin("teacher_scope_limits", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_x = _create_class(teacher, "CLASS-X")
    class_y = _create_class(teacher, "CLASS-Y")

    db.session.add(
        PayrollSettings(
            class_id=class_x.class_id,
            block="Period 1",
            settings_mode="simple",
            daily_limit_hours=2.0,
            is_active=True,
        )
    )
    db.session.commit()

    assert get_daily_limit_seconds("Period 1", class_id=class_x.class_id) == 7200
    assert get_daily_limit_seconds("Period 1", class_id=class_y.class_id) is None


def test_payroll_settings_lookup_requires_class_id(client):
    with pytest.raises(ValueError, match="class_id"):
        get_pay_rate_for_block("Period 1", class_id=None)

    with pytest.raises(ValueError, match="class_id"):
        get_daily_limit_seconds("Period 1", class_id=None)


def test_duplicate_active_settings_fail_closed(client):
    """Ambiguous active rows for same class/block must fail closed."""
    teacher = make_admin("teacher_scope_dup", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_a = _create_class(teacher, "CLASS-DUP")

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
    db.session.commit()

    with pytest.raises(ValueError, match="Ambiguous PayrollSettings scope"):
        get_pay_rate_for_block("Period 1", class_id=class_a.class_id)
