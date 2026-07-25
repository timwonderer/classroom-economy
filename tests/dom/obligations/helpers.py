"""Canonical helper wrappers for the Obligations domain tests.

Each helper here performs one production action only. The helpers do not
construct identity or scope; tests must provision canonical state through
`tests.helpers.classroom_initializer`.
"""

from __future__ import annotations


def rent_pay(client, period: str):
    """Invoke the canonical student rent payment route for one period."""
    return client.post(f"/student/rent/pay/{period}", follow_redirects=False)


def add_rent_waiver(
    client,
    *,
    student_ids,
    waiver_scope,
    reason="",
    past_due_dates=None,
    future_periods_count=None,
):
    """Invoke the canonical rent-waiver creation route."""
    data = {
        "student_ids": student_ids,
        "waiver_scope": waiver_scope,
        "reason": reason,
    }
    if past_due_dates:
        data["past_due_dates"] = past_due_dates
    if future_periods_count is not None:
        data["future_periods_count"] = future_periods_count
    return client.post("/admin/rent-waiver/add", data=data, follow_redirects=False)


def remove_rent_waiver(client, waiver_id: int):
    """Invoke the canonical rent-waiver removal route."""
    return client.post(f"/admin/rent-waiver/{waiver_id}/remove", follow_redirects=False)


def purchase_insurance(client, policy_id: int):
    """Invoke the canonical student insurance purchase route."""
    return client.post(f"/student/insurance/purchase/{policy_id}", follow_redirects=False)
