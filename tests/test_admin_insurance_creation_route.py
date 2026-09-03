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


def _tier_post(client, group, level, *, group_new=None, title="Tier"):
    data = {
        "insurance_type": "TRANSACTION", "premium": "5.00", "charge_frequency": "WEEKLY",
        "reimbursement_percentage": "80", "payout_multiple": "3",
        "claims_per_week_equivalent": "1", "claim_window_days": "7",
        "title": title, "tier_group": group, "tier_level": str(level),
    }
    if group_new is not None:
        data["tier_group_new"] = group_new
    return client.post("/admin/insurance/new", data=data, follow_redirects=False)


def test_admin_creates_grouped_tier_via_route(app, client):
    """A new-group submission (tier_group=__new__ + tier_group_new) creates a grouped tier."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        class_id = classroom.class_id
        login_teacher(client, classroom)

    resp = _tier_post(client, "__new__", 1, group_new="Paycheck Protection", title="Basic")
    assert resp.status_code == 302

    with app.app_context():
        row = InsurancePolicy.query.filter_by(class_id=class_id).one()
        assert row.tier_group == "Paycheck Protection"
        assert row.tier_level == 1


def test_admin_duplicate_rank_in_group_rejected_via_route(app, client):
    """A second Basic in the same group is rejected by the guard (form re-renders, no 2nd row)."""
    with app.app_context():
        classroom = provision_classroom("chemistry_p1")
        enable_class_feature(class_id=classroom.class_id, feature="insurance")
        class_id = classroom.class_id
        login_teacher(client, classroom)

    assert _tier_post(client, "__new__", 1, group_new="Paycheck Protection").status_code == 302
    # Now the group exists; join it and try Basic again.
    resp = _tier_post(client, "Paycheck Protection", 1)
    assert resp.status_code == 200  # re-rendered form with error, not a redirect

    with app.app_context():
        rows = InsurancePolicy.query.filter_by(class_id=class_id).all()
        assert len(rows) == 1  # the duplicate was not created
