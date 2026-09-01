"""Slice 8.2b-1 — Q1a/Q1b compliant compute vertical.

Proves the vertical end-to-end against real source-domain facts:

    completed-cycle window
        → authoritative source-domain reads (PROD attendance, Identity
          enrollment, Ledger provenance, STORE purchases, OBL self-payments)
        → contract-valid Q1a-C1, Q1a-C2, Q1b-C1 entries
        → a *partial* observations_json payload

The intended end-state is that the 8.2a materialization gate rejects the
partial payload **solely** because 14 of the 17 required candidates are not yet
computed (SPEC-ITR-001 §15.8) — not because of any structural defect in the
three entries this slice produces.

These tests exercise the §6.3 provenance classifier for real: a system-FEAT
ledger row (payroll) must NOT count as student agency, while a STORE purchase
grant must count via the source-domain union (§6.2, §6.4, INV-ITR-016).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import AttendanceSession, EntitlementEvent
from app.services.ledger_service import create_pending_transaction
from app.services.interpretation.compute import (
    compute_partial_observations,
    compute_partial_payload,
)
from app.services.interpretation.observation_contract import (
    REQUIRED_SET_V1,
    validate_for_materialization,
    validate_payload_structure,
)
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize


# The candidates this file focuses on. Composition now emits the full set, so
# presence is asserted as a subset rather than exact equality.
Q1_CANDIDATES = frozenset({"Q1a-C1", "Q1a-C2", "Q1b-C1"})


def _seed_window(classroom):
    """Seed a completed-cycle window with a controlled mix of source-domain facts.

    Returns ``(class_id, window_start, window_end)``. Layout across the four
    enrolled seats:

    * seat[0]: attendance in window + student-originated ledger row  → Q1a & Q1b
    * seat[1]: attendance in window only                             → Q1a only
    * seat[2]: STORE purchase grant in window (no attendance)        → Q1b only
    * seat[3]: system-FEAT (payroll) ledger row only                 → neither
    * seat[2] also gets an out-of-window attendance to prove windowing
    """
    cid = classroom.class_id
    teacher_seat_id = classroom.teacher_seat_id
    sA, sB, sC, sD = classroom.students

    now = utc_now()
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)
    before_window = now - timedelta(hours=3)

    with FEATContext("FEAT-PROD-001", correlation_id="itr-test:att", idempotency_key="itr:att"):
        db.session.add_all([
            AttendanceSession(
                target_seat_id=sA.seat_id, class_id=cid, target_user_id=sA.user.id,
                actor_seat_id=teacher_seat_id, reason_code="start_work", timestamp=now,
            ),
            AttendanceSession(
                target_seat_id=sB.seat_id, class_id=cid, target_user_id=sB.user.id,
                actor_seat_id=teacher_seat_id, reason_code="start_work", timestamp=now,
            ),
            # Out-of-window: must NOT count toward Q1a for seat C.
            AttendanceSession(
                target_seat_id=sC.seat_id, class_id=cid, target_user_id=sC.user.id,
                actor_seat_id=teacher_seat_id, reason_code="start_work", timestamp=before_window,
            ),
        ])
        db.session.flush()

    # seat A: genuine student-originated ledger act (non-system FEAT).
    with FEATContext("FEAT-STOR-001", correlation_id="itr-test:A", idempotency_key="itr:A"):
        create_pending_transaction(
            seat_id=sA.seat_id, class_id=cid, target_seat_id=sA.seat_id, actor_seat_id=sA.seat_id,
            mechanism="self", amount=Decimal("5.00"), account_type="checking",
            type="purchase", description="student act",
        )

    # seat D: system-FEAT ledger row (payroll). mechanism=self, but feat_code is
    # in the system-originated set → must be excluded by the §6.3 classifier.
    with FEATContext("FEAT-LED-004", correlation_id="itr-test:D", idempotency_key="itr:D"):
        create_pending_transaction(
            seat_id=sD.seat_id, class_id=cid, target_seat_id=sD.seat_id, actor_seat_id=sD.seat_id,
            mechanism="self", amount=Decimal("10.00"), account_type="checking",
            type="payroll", description="system payroll",
        )

    # seat C: STORE purchase grant (source-domain fact, precedence per INV-ITR-016).
    with FEATContext("FEAT-STOR-001", correlation_id="itr-test:C", idempotency_key="itr:C"):
        db.session.add(EntitlementEvent(
            class_id=cid, entitlement_id=str(uuid.uuid4()),
            target_seat_id=sC.seat_id, actor_seat_id=sC.seat_id,
            entitlement_type="PRIVILEGE", acquisition_type="PURCHASE", event_type="GRANTED",
            timestamp=now,
        ))
        db.session.flush()

    return cid, window_start, window_end


def _by_id(entries):
    return {e["candidate_id"]: e for e in entries}


def test_q1a_q1b_entries_are_individually_contract_lawful(app):
    """The three computed entries carry no structural contract errors."""
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_window(classroom)

    entries = compute_partial_observations(cid, start, end)
    present = {e["candidate_id"] for e in entries}
    assert Q1_CANDIDATES <= present

    # Sorted ascending by candidate_id (§15.9).
    assert [e["candidate_id"] for e in entries] == sorted(present)

    payload = _wrap_with_all_17(entries)
    # With the other 14 supplied as lawful placeholders, the only thing that could
    # fail is a structural defect in OUR three entries — assert none exists.
    result = validate_payload_structure(payload)
    assert result.errors == (), result.errors
    assert result.complete is True


def test_q1a_values_reflect_source_domain_facts(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_window(classroom)

    entries = _by_id(compute_partial_observations(cid, start, end))

    q1a_c1 = entries["Q1a-C1"]["value"]
    # seats A and B attended in-window; C's attendance is out-of-window; D none.
    assert q1a_c1["numerator"] == 2
    assert q1a_c1["denominator"] == 4
    assert q1a_c1["value"] == "0.5000"

    q1a_c2 = entries["Q1a-C2"]["value"]
    assert q1a_c2["kind"] == "distribution"
    assert q1a_c2["count"] == 4          # population size, not a sum
    assert "n_at_or_below_zero" not in q1a_c2  # attendance counts: no balance tail
    assert q1a_c2["mean"] == "0.50"      # counts [1,1,0,0] → mean 0.5


def test_q1b_classifier_excludes_system_feat_and_unions_sources(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_window(classroom)

    entries = _by_id(compute_partial_observations(cid, start, end))
    q1b_c1 = entries["Q1b-C1"]["value"]

    # A (ledger, non-system) + C (store purchase) act; D's payroll row is a
    # system-FEAT and is excluded; B did not act economically.
    assert q1b_c1["numerator"] == 2
    assert q1b_c1["denominator"] == 4
    assert q1b_c1["value"] == "0.5000"


def test_full_payload_over_participation_window_is_materializable(app):
    """After slice 8.2b-5 the compute core is contract-complete: a lawful window
    yields all 17 candidates with no structural defect (SPEC-ITR-001 §15.8)."""
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_window(classroom)

    payload = compute_partial_payload(cid, start, end)

    assert payload["coverage"]["complete"] is True

    result = validate_payload_structure(payload)
    assert result.complete is True
    assert result.present_ids == REQUIRED_SET_V1
    assert result.missing_ids == frozenset()
    assert result.errors == ()

    # The fail-closed gate now ACCEPTS the complete payload.
    validate_for_materialization(payload)


# --- helper: complete the payload with lawful placeholders for the other 14 ---


def _wrap_with_all_17(computed_entries):
    """Wrap the 3 computed entries plus lawful placeholders for the other 14.

    This is a test-only scaffold to isolate structural validation of the three
    real entries from the (expected) incomplete-coverage failure. It is NOT part
    of the compute layer — production compute never fabricates candidates.
    """
    from app.services.interpretation.observation_contract import (
        REQUIRED_SET_VERSION, SCHEMA_VERSION, SPEC_REF, SPEC_VERSION,
        BALANCE_DISTRIBUTION_CANDIDATES,
    )

    def _placeholder(cid):
        base = {
            "candidate_id": cid,
            "semantic_kind": "descriptive_observation",
            "subject": "class_id",
            "observation_basis": "seat_id",
            "aggregation": "class_aggregate_from_seat_observations",
            "reference_dependency": "none",
            "normalization_dependency": None,
            "applicability": "computed",
            "not_applicable_reason": None,
            "qualifiers": None,
        }
        if cid in BALANCE_DISTRIBUTION_CANDIDATES:
            base["value"] = {
                "kind": "distribution", "count": 1,
                "p10": "0.00", "p25": "0.00", "p50": "0.00", "p75": "0.00",
                "p90": "0.00", "iqr": "0.00", "n_at_or_below_zero": 0,
            }
        elif cid == "Q9-C1":
            base["value"] = {
                "kind": "signal_set",
                "signals": [
                    {"signal_id": "s", "applicability": "computed",
                     "value": {"kind": "counts", "items": [{"label": "x", "count": 1}], "total": 1}},
                ],
            }
        else:
            base["value"] = {"kind": "fraction", "numerator": 0, "denominator": 1, "value": "0.0000"}
        return base

    computed_ids = {e["candidate_id"] for e in computed_entries}
    entries = list(computed_entries) + [
        _placeholder(cid) for cid in REQUIRED_SET_V1 if cid not in computed_ids
    ]
    entries.sort(key=lambda e: e["candidate_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "spec": {"ref": SPEC_REF, "version": SPEC_VERSION},
        "coverage": {"required_set_version": REQUIRED_SET_VERSION},
        "observations": entries,
    }
