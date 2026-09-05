"""Slice 8.2b-4 — Q4 (savings behavior) + Q6 (resource distribution).

The two candidates share a historically-correct resource surface but ask
different questions, so the tests guard four things hard:

* **Stock vs flow never blur (§9.2).** A seat can hold savings at window end
  without contributing this cycle (contributed earlier), and a system credit can
  create a holder who never contributed. Q4-C1 (holders) and Q4-C2/C3
  (contributions) are asserted to diverge on exactly those cases.
* **not_applicable is exact (§9.6, §11.5).** With savings disabled, all Q4
  candidates and Q6-C2 are ``not_applicable`` (no value, structured reason) — never
  zero; Q6-C3 falls back to a checking-only distribution with the required basis
  note; Q6-C1 stays computed.
* **Distribution vocabulary is fixed (§15.6.1).** Balance distributions carry the
  pinned core plus ``n_at_or_below_zero`` and nothing else.
* **End-of-cycle balance is historical (§11.4).** A transaction dated after the
  cycle boundary must not leak into the cycle's balances.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import LedgerMechanism, Transaction, TransactionStatus
from app.services.interpretation.resource_distribution import compute_q6
from app.services.interpretation.savings_behavior import compute_q4
from app.services.ledger_provenance_query_service import get_posted_balances_as_of
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.class_domain import disable_class_feature, enable_class_feature
from tests.helpers.classroom_initializer import initialize


def _by_id(entries):
    return {e["candidate_id"]: e for e in entries}


def _post(cid, seat, account_type, amount, ts, mechanism=LedgerMechanism.SELF):
    """Insert one POSTED ledger row directly (test scaffold)."""
    db.session.add(Transaction(
        seat_id=seat.seat_id, target_seat_id=seat.seat_id, actor_seat_id=seat.seat_id,
        class_id=cid, amount=Decimal(amount), account_type=account_type,
        mechanism=mechanism, status=TransactionStatus.POSTED, type="test", timestamp=ts,
    ))


def _seed_resources(classroom):
    """Seed a controlled end-of-cycle resource surface (savings enabled).

    Checking (cents): sA 10000, sB 5000, sC 0, sD -2000.
    Savings  (cents): sA 3000 (student contribution, in-window),
                      sB 2000 (student contribution BEFORE window — holder, not a
                               current-cycle contributor),
                      sC 0,
                      sD 1000 (SYSTEM credit — holder, never a contributor).
    Plus a post-window savings row for sC that must NOT leak into the cycle.
    """
    cid = classroom.class_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(hours=1)
    in_window = now - timedelta(minutes=30)
    before_window = now - timedelta(hours=3)
    after_window = now + timedelta(hours=2)

    enable_class_feature(class_id=cid, feature="banking")

    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"q4q6:{cid}"):
        # Checking balances.
        _post(cid, sA, "checking", "100.00", in_window)
        _post(cid, sB, "checking", "50.00", in_window)
        _post(cid, sD, "checking", "-20.00", in_window)
        # Savings: stock vs flow separation.
        _post(cid, sA, "savings", "30.00", in_window)                     # holds + contributes
        _post(cid, sB, "savings", "20.00", before_window)                 # holds, contributed earlier
        _post(cid, sD, "savings", "10.00", in_window, LedgerMechanism.SYSTEM)  # holds, not student
        # Historical guard: a later-cycle deposit that must be excluded.
        _post(cid, sC, "savings", "99.00", after_window)
        db.session.flush()

    return cid, window_start, window_end


# --------------------------------------------------------------------------- #
# Q4 — savings behavior (enabled): stock vs flow                              #
# --------------------------------------------------------------------------- #


def test_q4_stock_and_flow_are_separate_observations(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_resources(classroom)

    entries = _by_id(compute_q4(cid, start, end))

    # Q4-C1 stock: holders = sA, sB, sD (3 of 4). sB holds without an in-window
    # contribution; the post-window sC deposit is excluded → not a holder.
    q4_c1 = entries["Q4-C1"]
    assert q4_c1["applicability"] == "computed"
    assert q4_c1["value"]["kind"] == "fraction"
    assert q4_c1["value"]["numerator"] == 3
    assert q4_c1["value"]["denominator"] == 4
    assert q4_c1["value"]["value"] == "0.7500"

    # Q4-C2 flow: only sA contributed in-window (sB earlier, sD is a system credit).
    q4_c2 = entries["Q4-C2"]["value"]
    assert q4_c2["numerator"] == 1
    assert q4_c2["denominator"] == 4
    assert q4_c2["value"] == "0.2500"

    # Q4-C3 flow volume: sA's 30.00 only.
    q4_c3 = entries["Q4-C3"]
    assert q4_c3["value"]["kind"] == "amount"
    assert q4_c3["value"]["value"] == "30.00"
    assert q4_c3["value"]["unit"] == "tokens"
    assert q4_c3["normalization_dependency"] is None

    # Stock (3 holders) and flow (1 contributor) genuinely diverge.
    assert q4_c1["value"]["numerator"] != q4_c2["numerator"]


# --------------------------------------------------------------------------- #
# Q6 — resource distribution (enabled): fixed vocabulary, three surfaces       #
# --------------------------------------------------------------------------- #


def test_q6_checking_distribution_uses_pinned_vocabulary(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_resources(classroom)

    q6_c1 = _by_id(compute_q6(cid, start, end))["Q6-C1"]["value"]
    # cents [-2000, 0, 5000, 10000]
    assert set(q6_c1) == {"kind", "count", "p10", "p25", "p50", "p75", "p90",
                          "iqr", "n_at_or_below_zero", "mean"}
    assert q6_c1["count"] == 4
    assert q6_c1["n_at_or_below_zero"] == 2       # sD (-20.00) and sC (0)
    assert q6_c1["p50"] == "25.00"
    assert q6_c1["iqr"] == "67.50"
    assert q6_c1["mean"] == "32.50"


def test_q6_savings_and_total_distributions(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_resources(classroom)

    entries = _by_id(compute_q6(cid, start, end))

    # Q6-C2 savings: cents [0, 1000, 2000, 3000]
    q6_c2 = entries["Q6-C2"]
    assert q6_c2["applicability"] == "computed"
    assert q6_c2["value"]["count"] == 4
    assert q6_c2["value"]["n_at_or_below_zero"] == 1   # sC (0)
    assert q6_c2["value"]["p50"] == "15.00"

    # Q6-C3 total resources: cents [-1000, 0, 7000, 13000]
    q6_c3 = entries["Q6-C3"]["value"]
    assert q6_c3["count"] == 4
    assert q6_c3["n_at_or_below_zero"] == 2            # sD (-10.00) and sC (0)
    assert q6_c3["p50"] == "35.00"


def test_end_of_cycle_balance_excludes_later_transactions(app):
    """The post-window sC savings deposit must not leak into the cycle balance."""
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_resources(classroom)
    sC = classroom.students[2]

    as_of = get_posted_balances_as_of(cid, end, "savings")
    # sC only has a post-window deposit → absent (treated as 0) as of window end.
    assert sC.seat_id not in as_of
    # A read as of *now+3h* would include it — proving the window bound is real.
    later = get_posted_balances_as_of(cid, utc_now() + timedelta(hours=3), "savings")
    assert later.get(sC.seat_id) == Decimal("99.00")


# --------------------------------------------------------------------------- #
# Q4/Q6 — savings disabled: exact not_applicable + Q6-C3 checking-only         #
# --------------------------------------------------------------------------- #


def _seed_checking_only(classroom):
    cid = classroom.class_id
    sA, sB, sC, sD = classroom.students
    now = utc_now()
    # Provisioning enables 'banking' (which governs savings) by default; disable
    # it so this window observes the savings-disabled path.
    disable_class_feature(class_id=cid, feature="banking")
    with FEATContext("FEAT-TEST-SETUP", idempotency_key=f"q6:nosav:{cid}"):
        _post(cid, sA, "checking", "100.00", now - timedelta(minutes=30))
        _post(cid, sB, "checking", "50.00", now - timedelta(minutes=30))
        db.session.flush()
    return cid, now - timedelta(hours=1), now + timedelta(hours=1)


def test_q4_all_not_applicable_when_savings_disabled(app):
    # Banking is NOT enabled by the initializer, so savings is disabled.
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_checking_only(classroom)

    entries = _by_id(compute_q4(cid, start, end))
    for candidate in ("Q4-C1", "Q4-C2", "Q4-C3"):
        entry = entries[candidate]
        assert entry["applicability"] == "not_applicable", candidate
        assert entry["value"] is None
        assert entry["not_applicable_reason"] == {"feature": "savings", "state": "disabled"}


def test_q6_savings_disabled_c2_na_and_c3_checking_only_basis_note(app):
    classroom = initialize("chemistry_p1", app)
    cid, start, end = _seed_checking_only(classroom)

    entries = _by_id(compute_q6(cid, start, end))

    # Q6-C1 checking is always computed.
    assert entries["Q6-C1"]["applicability"] == "computed"

    # Q6-C2 savings is not_applicable — never a zero distribution.
    q6_c2 = entries["Q6-C2"]
    assert q6_c2["applicability"] == "not_applicable"
    assert q6_c2["value"] is None
    assert q6_c2["not_applicable_reason"] == {"feature": "savings", "state": "disabled"}

    # Q6-C3 falls back to a checking-only distribution WITH the required basis note.
    q6_c3 = entries["Q6-C3"]
    assert q6_c3["applicability"] == "computed"
    assert q6_c3["qualifiers"] == {
        "basis_note": {"code": "checking_only_savings_disabled", "excluded_component": "savings"}
    }
    # Checking-only total equals the Q6-C1 checking distribution exactly.
    assert q6_c3["value"] == entries["Q6-C1"]["value"]
