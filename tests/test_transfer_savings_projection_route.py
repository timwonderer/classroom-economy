"""The /student/transfer savings projection must be honest and crash-free.

Regression for SPEC-ECON-001 §10/§11 at the route boundary: the projection was
previously computed with a hardcoded 4.5% APY fallback and bespoke math that
diverged from the runtime payout engine. The route now sources rate/cadence from
the Economic Engine and, when interest is unconfigured (the default provisioned
state, interest_rate IS NULL), must render a flat, honestly-labeled projection —
never a fabricated rate and never a 500.
"""

from __future__ import annotations

from tests.helpers.classroom_initializer import initialize_as_student


def test_transfer_page_renders_flat_when_interest_unconfigured(client, app):
    """Default classroom has no interest_rate -> honest 'not configured' copy, 200."""
    classroom, student = initialize_as_student("chemistry_p1", client, app)

    resp = client.get("/student/transfer", follow_redirects=False)
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    # Honest disclosure that interest is not configured...
    assert "not currently configured" in body
    # ...and NOT a fabricated default rate advertised as real.
    assert "4.5% annual simple interest" not in body
