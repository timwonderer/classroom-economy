"""Canonical helper wrappers for the Obligations domain tests.

Each helper here performs one production action only. The helpers do not
construct identity or scope; tests must provision canonical state through
`tests.helpers.classroom_initializer`.
"""

from __future__ import annotations


def manual_payroll(client, *, student_ids, description, amount, payment_type="deposit", account_type="checking", save_action="apply_only"):
    """Invoke the canonical manual payroll route for selected students."""
    return client.post(
        "/admin/payroll/manual-payment",
        data={
            "student_ids": student_ids,
            "description": description,
            "amount": amount,
            "payment_type": payment_type,
            "account_type": account_type,
            "save_action": save_action,
        },
        follow_redirects=False,
    )


def rent_pay(client, period: str):
    """Invoke the canonical student rent payment route for one period."""
    return client.post(f"/student/rent/pay/{period}", follow_redirects=False)


def tap_in_students(client, seat_ids):
    """Invoke the canonical admin tap-in route for one or more seats."""
    return client.post(
        "/admin/tap-in-students",
        json={"seat_ids": seat_ids},
        follow_redirects=False,
    )
