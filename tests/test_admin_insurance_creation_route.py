"""Regression: creating an insurance policy through the real admin route must work.

This path previously crashed with FEATContextError (FEAT-CLASS-003 executing
FEAT-POL-001 — illegal FEAT-to-FEAT nesting). The fix makes CLASS-003 invoke the
POL domain command directly. Route-level so the exact ingress is exercised.
"""
from __future__ import annotations

from uuid import uuid4

from app.models import InsurancePolicy
from tests.helpers.canonical_classroom import provision_classroom, login_teacher
from tests.helpers.class_domain import enable_class_feature


def test_admin_creates_insurance_policy_via_route(app, client):
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        class_id = classroom.class_id
        login_teacher(client, classroom)

    resp = client.post("/admin/insurance/new", data={
        "insurance_type": "TRANSACTION", "premium": "5.00", "charge_frequency": "WEEKLY",
        "reimbursement_percentage": "80", "payout_multiple": "3",
        "claims_per_week_equivalent": "1", "claim_window_days": "7",
        "title": "Attendance Insurance", "description": "Covers lost tokens",
    }, follow_redirects=False)
    # No 500 (the FEATContextError is gone); success redirects to the manager.
    assert resp.status_code == 302

    with app.app_context():
        rows = InsurancePolicy.query.filter_by(class_id=class_id).all()
        assert len(rows) == 1
        assert rows[0].insurance_type == "TRANSACTION"
        assert rows[0].availability_state == "IN_USE"
