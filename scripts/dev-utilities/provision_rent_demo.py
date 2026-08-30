"""One-off DEV provisioner: a rent-enabled simulated classroom for browser demo.

Uses the canonical test helpers (production code paths) so identity encryption,
PIN hashing, roster fingerprints, and obligation/entitlement invariants all hold
— which is what makes the generated student able to actually log in.

Backdates first_rent_due_date so reconcile-as-of-now produces a real, past-dated
OUTSTANDING rent assessment for each seat, and funds each seat's checking so the
Pay Rent flow succeeds.

Run:  source venv/bin/activate && python scripts/dev-utilities/provision_rent_demo.py
"""

from datetime import datetime, timezone
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.feats.base import FEATContext
from app.feats.reconcile_rent_feat import execute_reconcile_rent
from tests.helpers.canonical_classroom import provision_classroom
from tests.helpers.class_domain import enable_class_feature, customize_rent_settings
from tests.helpers.ledger import create_ledger_idempotent_transaction

# Backdated schedule: first due Aug 1, reconcile as of now (late Aug) -> outstanding.
FIRST_DUE = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
REFERENCE_NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
HALL_PASS_GRANTS = [{"entitlement_type": "HALL_PASS", "quantity": 2}]

app = create_app()
with app.app_context():
    classroom = provision_classroom("chemistry_p1")

    enable_class_feature(class_id=classroom.class_id, feature="rent")
    customize_rent_settings(
        classroom.class_id,
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=FIRST_DUE,
        grace_period_days=3,
        rent_amount=Decimal("50.00"),
        satisfaction_benefits=HALL_PASS_GRANTS,
    )

    result = execute_reconcile_rent(
        classroom.class_id, reference_time_utc=REFERENCE_NOW
    )

    # Fund every seat's checking so Pay Rent won't hit INSUFFICIENT_FUNDS.
    for student in classroom.students:
        seat_id = student.seat.id
        with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"demo-fund:{seat_id}"):
            create_ledger_idempotent_transaction(
                idempotency_key=f"demo-fund-seat:{seat_id}",
                seat_id=seat_id,
                class_id=classroom.class_id,
                user_id=student.user.id,
                amount=Decimal("100.00"),
                account_type="checking",
                type="payroll",
                description="Demo funding",
            )
    db.session.commit()

    print("=" * 60)
    print("DEMO RENT CLASSROOM PROVISIONED")
    print("=" * 60)
    print(f"class_id   : {classroom.class_id}")
    print(f"join_code  : {classroom.join_code}")
    print(f"assessments created: {getattr(result, 'assessments_created', '?')}")
    print(f"cycles created     : {getattr(result, 'cycles_created', '?')}")
    print("-" * 60)
    print("STUDENT LOGINS (PIN 1234):")
    for s in classroom.students:
        print(f"  username={s.username!r}  pin={s.pin!r}  seat_id={s.seat.id}")
    print("=" * 60)
