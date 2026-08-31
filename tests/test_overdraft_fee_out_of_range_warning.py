"""The teacher sets the overdraft/NSF fee; the CWI helper only recommends a range.

Per SPEC-ECON-003 §4.6.1 / §4.6.1.1 the Economic Engine does not set the fee — it
surfaces a CWI-normed recommended range for reference and warns (non-blocking)
when the teacher's chosen amount falls outside that range. This exercises the
warning path on the banking-settings save.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.economic_engine import resolve_overdraft_fine
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.helpers.class_domain import update_expected_weekly_hours


def test_resolve_overdraft_fine_surfaces_a_recommended_range():
    """The helper recommends a CWI-normed range (not a single price)."""
    reco = resolve_overdraft_fine(cwi=Decimal("100.00"), mode="default")
    assert reco.flat_fee_lower is not None and reco.flat_fee_upper is not None
    assert reco.flat_fee_lower < reco.flat_fee_upper
    assert reco.flat_fee_lower == (Decimal("100.00") * reco.fine_rate_lower).quantize(Decimal("0.01"))
    assert reco.flat_fee_upper == (Decimal("100.00") * reco.fine_rate_upper).quantize(Decimal("0.01"))


def test_out_of_range_overdraft_fee_saves_with_warning(client, app):
    initialize_as_teacher("chemistry_p1", client, app)
    # Give the class a resolvable CWI so a recommended band exists.
    update_expected_weekly_hours(client, "40")

    # A fee far above any reasonable band (CWI here is large; band is a small %).
    resp = client.post(
        "/admin/banking/settings",
        data={"interest_apy": "0", "flat_overdraft_fee": "999.00"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    # Saved (success), AND warned about being outside the recommended range.
    assert b"recommended range" in resp.data


def test_in_range_overdraft_fee_saves_without_warning(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    update_expected_weekly_hours(client, "40")

    # Choose a value INSIDE the class's own recommended band.
    with app.app_context():
        reco = resolve_overdraft_fine(class_id=classroom.class_id)
        mid = ((reco.flat_fee_lower + reco.flat_fee_upper) / 2).quantize(Decimal("0.01"))

    resp = client.post(
        "/admin/banking/settings",
        data={"interest_apy": "0", "flat_overdraft_fee": str(mid)},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    assert b"recommended range" not in resp.data
