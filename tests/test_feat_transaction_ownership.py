"""Transaction-ownership guarantees for the FEATContext root fix.

Root defect (fixed in ``FEATContext.__enter__``): a *top-level* FEAT that opened
while an incidental read-only autobegin was live took a ``begin_nested()``
SAVEPOINT instead of a top-level ``begin()``. Releasing a savepoint is not a
commit, so the FEAT's mutations were silently discarded (FEAT-ENTRY logged, but
never FEAT-COMMIT-OWNERSHIP).

The fix adds ``is_discardable_read_autobegin()`` and rolls back *only* a clean
read autobegin before a top-level FEAT takes ``begin()``. Every other
transaction state (explicit BEGIN, active savepoint, pending ORM mutation,
nested FEAT) is preserved.

These tests pin both layers:

  * Predicate layer — ``is_discardable_read_autobegin()`` returns True ONLY for a
    clean read autobegin, and False for explicit BEGIN, pending mutation, and an
    active savepoint.
  * Behavioural layer — through ``FEATContext``: fresh session and read-autobegin
    both yield a durable top-level commit (FEAT-COMMIT-OWNERSHIP emitted, change
    persists); a nested FEAT keeps savepoint semantics; an explicit BEGIN is not
    discarded; a failed FEAT rolls back its owned mutation with no commit
    evidence.

Commit evidence: ``FEAT-COMMIT-OWNERSHIP`` is logged by ``increment_commit_count``
only on a real top-level commit (``before_commit`` fires it when the session is
NOT in a nested transaction). A savepoint release therefore leaves it absent —
which is exactly what the pre-fix defect produced.
"""

import logging

import pytest
from sqlalchemy import text

from app.extensions import db
from app.feats.base import FEATContext, is_discardable_read_autobegin, is_nested_feat
from app.models import RentSettings
from tests.helpers.classroom_initializer import initialize

BASE_LOGGER = "app.feats.base"


def _sess():
    """Underlying Session (scoped_session does not proxy transaction introspection)."""
    return db.session()


def _rent_settings(class_id):
    return RentSettings.query.filter_by(class_id=class_id).first()


def _commit_ownership_lines(caplog, feat_name):
    return [
        r.getMessage()
        for r in caplog.records
        if "FEAT-COMMIT-OWNERSHIP" in r.getMessage() and feat_name in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# Predicate layer — is_discardable_read_autobegin()
# ---------------------------------------------------------------------------

def test_predicate_true_for_clean_read_autobegin(app):
    """A read-only autobegin with no pending mutation is discardable."""
    initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()  # normalise to a clean session
        db.session.execute(text("SELECT 1"))  # implicit autobegin (origin AUTOBEGIN)
        assert _sess().in_transaction()
        assert is_discardable_read_autobegin(db.session) is True
        db.session.rollback()


def test_predicate_false_for_explicit_begin(app):
    """An explicit session.begin() (origin BEGIN) must never be discarded."""
    initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()
        db.session.begin()  # explicit boundary, origin == BEGIN
        try:
            assert _sess().in_transaction()
            assert is_discardable_read_autobegin(db.session) is False
        finally:
            db.session.rollback()


def test_predicate_false_for_autobegin_with_pending_dirty(app):
    """An autobegin carrying a dirty (pending UPDATE) row is not discardable."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()
        rs = _rent_settings(classroom.class_id)  # read → autobegin
        rs.grace_period_days = (rs.grace_period_days or 0) + 1  # dirty, unflushed
        try:
            assert db.session.dirty
            assert is_discardable_read_autobegin(db.session) is False
        finally:
            db.session.rollback()  # discard the pending change


def test_predicate_false_for_autobegin_with_pending_new(app):
    """An autobegin carrying a pending INSERT is not discardable."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()
        db.session.execute(text("SELECT 1"))  # autobegin
        db.session.add(RentSettings(class_id=classroom.class_id, grace_period_days=99))
        try:
            assert db.session.new
            assert is_discardable_read_autobegin(db.session) is False
        finally:
            db.session.rollback()


def test_predicate_false_for_active_savepoint(app):
    """An active SAVEPOINT is an intentional nested boundary, not a read autobegin."""
    initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()
        db.session.execute(text("SELECT 1"))  # outer autobegin
        db.session.begin_nested()  # savepoint
        try:
            assert _sess().in_nested_transaction()
            assert is_discardable_read_autobegin(db.session) is False
        finally:
            db.session.rollback()


# ---------------------------------------------------------------------------
# Behavioural layer — through FEATContext
# ---------------------------------------------------------------------------

def test_fresh_session_feat_owns_and_commits(app, caplog):
    """Fresh session (no active txn) → FEAT owns a top-level txn and commits durably."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()  # ensure no transaction is live
        assert not _sess().in_transaction()

        target = 41
        with caplog.at_level(logging.INFO, logger=BASE_LOGGER):
            with FEATContext("FEAT-TEST-FRESH", idempotency_key="feat:test:fresh:1"):
                rs = _rent_settings(classroom.class_id)
                rs.grace_period_days = target

        assert _commit_ownership_lines(caplog, "FEAT-TEST-FRESH"), (
            "Top-level FEAT on a fresh session must emit FEAT-COMMIT-OWNERSHIP"
        )
        assert not _sess().in_nested_transaction()

        db.session.expire_all()
        assert _rent_settings(classroom.class_id).grace_period_days == target


def test_read_autobegin_feat_discards_read_then_commits(app, caplog):
    """SELECT/autobegin → FEAT discards only the read txn, owns begin(), commits durably.

    This is the exact pre-fix defect: without the root correction the FEAT would
    take a savepoint on top of the before_request read and its write would be
    silently dropped (no FEAT-COMMIT-OWNERSHIP, no persistence).
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()
        db.session.execute(text("SELECT 1"))  # incidental read autobegin
        assert _sess().in_transaction()

        target = 42
        with caplog.at_level(logging.INFO, logger=BASE_LOGGER):
            with FEATContext("FEAT-TEST-AUTOBEGIN", idempotency_key="feat:test:autobegin:1"):
                # The FEAT owns a top-level begin(), not a savepoint.
                assert not _sess().in_nested_transaction()
                rs = _rent_settings(classroom.class_id)
                rs.grace_period_days = target

        assert _commit_ownership_lines(caplog, "FEAT-TEST-AUTOBEGIN"), (
            "FEAT after a read autobegin must own a real commit, not a savepoint release"
        )

        db.session.expire_all()
        assert _rent_settings(classroom.class_id).grace_period_days == target


def test_active_outer_feat_keeps_nested_semantics(app, caplog):
    """An inner FEAT under an active outer FEAT stays nested: it owns no separate
    transaction and produces no independent top-level commit — the outer FEAT is
    the single atomic boundary.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()

        target = 37
        with caplog.at_level(logging.INFO, logger=BASE_LOGGER):
            with FEATContext("FEAT-TEST-OUTER", idempotency_key="feat:test:outer:1"):
                assert not is_nested_feat()  # outer is the top-level boundary
                outer_txn = _sess().in_transaction()
                assert outer_txn
                with FEATContext("FEAT-TEST-INNER"):
                    # Inner is recognised as nested and shares the outer transaction;
                    # it must NOT open a competing top-level transaction.
                    assert is_nested_feat()
                    assert _sess().in_transaction()
                    _rent_settings(classroom.class_id).grace_period_days = target
                # Back in outer scope after inner exit.
                assert not is_nested_feat()

        # Exactly one atomic commit — owned by the outer FEAT, not the inner.
        assert _commit_ownership_lines(caplog, "FEAT-TEST-OUTER"), (
            "Outer FEAT must own the single top-level commit"
        )
        assert not _commit_ownership_lines(caplog, "FEAT-TEST-INNER"), (
            "Nested inner FEAT must not emit its own commit-ownership"
        )
        db.session.expire_all()
        assert _rent_settings(classroom.class_id).grace_period_days == target


def test_autobegin_with_pending_mutation_is_adopted_and_commits(app, caplog):
    """An autobegin carrying a pending write is ADOPTED (not discarded, not nested).

    When a top-level FEAT opens over an autobegin that already holds an unflushed
    mutation, discarding it would lose the write and burying it under a savepoint
    would never commit it (a savepoint release is not a commit of the underlying
    autobegin). The FEAT must instead adopt that autobegin as its own top-level
    transaction and fold the pre-existing write into its single durable commit.
    """
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()

        rs = _rent_settings(classroom.class_id)  # read → autobegin
        rs.rent_amount = rs.rent_amount + 7      # pending write on the autobegin
        assert _sess().in_transaction()
        assert db.session.dirty
        expected_rent = rs.rent_amount

        with caplog.at_level(logging.INFO, logger=BASE_LOGGER):
            with FEATContext("FEAT-TEST-ADOPT", idempotency_key="feat:test:adopt:1"):
                # Adopted the autobegin as the owned top-level transaction — NOT a savepoint.
                assert not _sess().in_nested_transaction()
                # A second mutation, this one owned by the FEAT itself.
                _rent_settings(classroom.class_id).grace_period_days = 44

        # The FEAT owns a real top-level commit that persists BOTH writes.
        assert _commit_ownership_lines(caplog, "FEAT-TEST-ADOPT"), (
            "A FEAT that adopts a pending autobegin must own a durable top-level commit"
        )
        db.session.expire_all()
        persisted = _rent_settings(classroom.class_id)
        assert persisted.grace_period_days == 44, "FEAT-owned write must persist"
        assert persisted.rent_amount == expected_rent, (
            "Pre-existing pending write on the adopted autobegin must persist, not be dropped"
        )


def test_explicit_begin_is_not_discarded(app):
    """A top-level FEAT under an explicit BEGIN nests via savepoint; the BEGIN survives."""
    initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()
        db.session.begin()  # explicit non-FEAT boundary
        try:
            feat = FEATContext("FEAT-TEST-EXPLICIT", idempotency_key="feat:test:explicit:1")
            feat.__enter__()
            try:
                # The explicit BEGIN was preserved, so the FEAT layered a savepoint
                # on top of it instead of rolling it back and taking a fresh begin().
                assert _sess().in_nested_transaction()
            finally:
                feat.__exit__(None, None, None)
            # Savepoint released; the explicit BEGIN is still the live transaction.
            assert _sess().in_transaction()
            assert not _sess().in_nested_transaction()
        finally:
            db.session.rollback()


def test_failed_feat_rolls_back_owned_mutation(app, caplog):
    """A FEAT that raises rolls back its owned write and emits no commit evidence."""
    classroom = initialize("chemistry_p1", app)
    with app.app_context():
        db.session.rollback()
        original = _rent_settings(classroom.class_id).grace_period_days

        with caplog.at_level(logging.INFO, logger=BASE_LOGGER):
            with pytest.raises(RuntimeError):
                with FEATContext("FEAT-TEST-FAIL", idempotency_key="feat:test:fail:1"):
                    rs = _rent_settings(classroom.class_id)
                    rs.grace_period_days = (original or 0) + 100
                    raise RuntimeError("boom inside FEAT")

        assert not _commit_ownership_lines(caplog, "FEAT-TEST-FAIL"), (
            "A failed FEAT must not emit FEAT-COMMIT-OWNERSHIP"
        )

        db.session.rollback()
        db.session.expire_all()
        assert _rent_settings(classroom.class_id).grace_period_days == original
