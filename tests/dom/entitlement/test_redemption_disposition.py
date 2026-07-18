"""
FEAT-STOR-006: Redemption Disposition — enforcement-active tests.

These tests are marked `enforce_feat` so the conftest does NOT wrap them in
the global FEATBypass. That means the FEAT constitutional enforcement
(before_flush listener in app/feats/base.py) is fully live during the route
calls. If the routes' @feat_shell decorator is removed, these tests will
fail loudly with FEATContextError instead of silently passing.

FEATBypass is used only inside fixture-setup blocks where we're seeding rows,
not exercising business logic.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import (
    RedemptionEvent,
    RedemptionEventAction,
    StoreItem,
    StorePurchase,
    Transaction,
    TransactionStatus,
)
from tests.helpers.v2_fixtures import make_teacher
from tests.helpers.admin_context import login_teacher
from app.services.classroom_setup import create_class, create_student


def _seed_redemption_scenario(*, username: str, join_code: str, item_price: Decimal):
    """
    Seed a realistic redemption scenario: one teacher (with canonical User),
    one student, one seat, one store item, and one StorePurchase in 'processing'
    state with a matching purchase transaction.

    All seeding occurs inside FEATContext so the same production mutation
    path is used as the routes under test.

    Returns a dict of primary-key IDs (not detached ORM objects) so callers
    can rehydrate after a route call.
    """
    with FEATContext("FEAT-STOR-006", idempotency_key=f"redemption-seed:{username}"):
        teacher = make_teacher(username)
        economy = create_class(
            teacher.id,
            join_code=join_code,
            display_name=f"Redemption {username}",
            section="A",
        )
        student_user, student_seat, _profile = create_student(
            economy.class_id,
            first_name="X",
            last_name="S",
            claimed=True,
        )

        item = StoreItem(
            name="Prize",
            price=item_price,
            user_id=teacher.id,
            class_id=economy.class_id,
            is_active=True,
        )
        db.session.add(item)
        db.session.flush()

        # Original purchase transaction (the money that left the student's account)
        purchase_tx = Transaction(
            seat_id=student_seat.id,
            target_seat_id=student_seat.id,
            actor_seat_id=student_seat.id,
            mechanism="self",
            class_id=economy.class_id,
            amount=-item_price,
            account_type="checking",
            type="purchase",
            status=TransactionStatus.PENDING,
            description=f"Purchase: {item.name}",
            join_code=join_code,
        )
        db.session.add(purchase_tx)
        db.session.flush()

        # Redemption transaction (the held-pending entry created by /use-item)
        redemption_tx = Transaction(
            seat_id=student_seat.id,
            target_seat_id=student_seat.id,
            actor_seat_id=student_seat.id,
            mechanism="self",
            class_id=economy.class_id,
            amount=Decimal("0.00"),
            account_type="checking",
            type="redemption",
            status=TransactionStatus.PENDING,
            description=f"Used: {item.name}",
            join_code=join_code,
        )
        db.session.add(redemption_tx)
        db.session.flush()

        purchase = StorePurchase(
            seat_id=student_seat.id,
            class_id=economy.class_id,
            store_item_id=item.id,
            quantity=1,
            price_at_purchase=item_price,
            total_price=item_price,
            status="processing",
        )
        db.session.add(purchase)
        db.session.flush()

        # Snapshot all IDs BEFORE commit; SQLAlchemy expires attributes on commit
        # and we don't want to re-read them through a closed transaction.
        snapshot = {
            "owner_user_id": teacher.id,
            "user_id": teacher.id,
            "student_id": student_user.id,
            "class_id": economy.class_id,
            "seat_id": student_seat.id,
            "student_seat_id": student_seat.id,
            "item_id": item.id,
            "student_item_id": purchase.id,
            "purchase_tx_id": purchase_tx.id,
            "redemption_tx_id": redemption_tx.id,
        }
        assert db.session.get(StorePurchase, purchase.id).status == "processing"
        return snapshot


def _login_canonical_admin(client, *, user_id: int):
    from app.models import User

    user = db.session.get(User, user_id)
    nonce = f"nonce-{user_id}"
    if user is not None:
        with FEATContext("FEAT-STOR-006", idempotency_key=f"redemption:login:{user_id}"):
            user.current_session_nonce = nonce
            db.session.flush()
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["is_admin"] = True
        sess["current_session_nonce"] = nonce
        if user is not None:
            sess["current_class_id"] = user.last_active_class_id
            sess["current_seat_id"] = user.last_active_seat_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


@pytest.mark.enforce_feat
def test_DOM_STORE_001__approve_redemption_succeeds_under_feat_enforcement(client):
    """
    With FEAT enforcement ACTIVE (no global FEATBypass), POST /api/approve-redemption
    must succeed end-to-end: 200 response, audit row written, item status flipped.

    Before FEAT-STOR-006 was added, this exact path raised FEATContextError → 500.
    """
    ids = _seed_redemption_scenario(
        username="approver_enforced",
        join_code="ENF001",
        item_price=Decimal("10.00"),
    )
    _login_canonical_admin(client, user_id=ids["owner_user_id"])

    resp = client.post(
        "/api/approve-redemption",
        json={"student_item_id": ids["student_item_id"]},
    )

    assert resp.status_code == 200, f"expected 200 under enforcement, got {resp.status_code}: {resp.data!r}"
    assert resp.json["status"] == "success"

    # Canonical redemption event persisted
    event_rows = RedemptionEvent.query.filter_by(
        purchase_id=ids["student_item_id"],
        action=RedemptionEventAction.APPROVED,
    ).all()
    assert len(event_rows) == 1
    assert event_rows[0].initiated_by_user_id == ids["owner_user_id"]
    assert event_rows[0].class_id == ids["class_id"]

    # Item state advanced
    refetched_item = db.session.get(StorePurchase, ids["student_item_id"])
    assert refetched_item.status == "completed"

    # Redemption transaction description rewritten
    refetched_tx = db.session.get(Transaction, ids["redemption_tx_id"])
    assert refetched_tx.description.startswith("Redeemed:")


@pytest.mark.enforce_feat
def test_DOM_STORE_001__reject_redemption_succeeds_and_creates_refund_under_enforcement(client):
    """
    POST /api/reject-redemption under live enforcement: 200, audit row, refund Tx,
    item status set to 'rejected'.
    """
    ids = _seed_redemption_scenario(
        username="rejecter_enforced",
        join_code="ENF002",
        item_price=Decimal("15.00"),
    )
    _login_canonical_admin(client, user_id=ids["owner_user_id"])

    resp = client.post(
        "/api/reject-redemption",
        json={"student_item_id": ids["student_item_id"]},
    )

    assert resp.status_code == 200, f"expected 200 under enforcement, got {resp.status_code}: {resp.data!r}"
    assert resp.json["status"] == "success"

    # Audit row persisted
    event_rows = RedemptionEvent.query.filter_by(
        purchase_id=ids["student_item_id"],
        action=RedemptionEventAction.REJECTED,
    ).all()
    assert len(event_rows) == 1

    # Item is in terminal rejected state
    refetched_item = db.session.get(StorePurchase, ids["student_item_id"])
    assert refetched_item.status == "rejected"

    # Refund transaction created with positive amount equal to item price
    refund_txs = Transaction.query.filter_by(
        seat_id=ids["seat_id"],
        class_id=ids["class_id"],
        type="refund",
    ).all()
    assert len(refund_txs) == 1
    assert refund_txs[0].amount == Decimal("15.00")

    # Original purchase tx now points at the refund as its reversal
    purchase_tx = db.session.get(Transaction, ids["purchase_tx_id"])
    assert purchase_tx.reversal_transaction_id == refund_txs[0].id


@pytest.mark.enforce_feat
def test_DOM_STORE_001__approve_rejects_non_processing_item_with_409(client):
    """
    Business-rule failure (item not in 'processing' state) should be caught
    by the route as RedemptionDispositionError and converted to a 409, NOT
    leak as a 500 or a FEATContextError.
    """
    ids = _seed_redemption_scenario(
        username="approver_stale",
        join_code="ENF003",
        item_price=Decimal("5.00"),
    )

    # Advance item to a terminal state before the route call
    with FEATContext("FEAT-STOR-006", idempotency_key="redemption:advance_item"):
        purchase = db.session.get(StorePurchase, ids["student_item_id"])
        purchase.status = "completed"

    _login_canonical_admin(client, user_id=ids["owner_user_id"])
    resp = client.post(
        "/api/approve-redemption",
        json={"student_item_id": ids["student_item_id"]},
    )

    # The route's pre-FEAT validation also catches this (returns 404 "already processed").
    # The point of this test is: under enforcement, the route does not 500.
    assert resp.status_code in (404, 409), f"got {resp.status_code}: {resp.data!r}"
    assert resp.status_code != 500


@pytest.mark.enforce_feat
def test_DOM_STORE_001__approve_redemption_missing_student_item_id_returns_400(client):
    """Pure validation path — must not reach FEAT, must not 500."""
    ids = _seed_redemption_scenario(
        username="approver_validate",
        join_code="ENF004",
        item_price=Decimal("1.00"),
    )
    _login_canonical_admin(client, user_id=ids["owner_user_id"])

    resp = client.post("/api/approve-redemption", json={})
    assert resp.status_code == 400
    assert resp.json["status"] == "error"


@pytest.mark.enforce_feat
def test_DOM_STORE_001__approve_redemption_rejects_intruder_admin_with_403(client):
    """Authorization gate must fire before the FEAT body runs."""
    owner = _seed_redemption_scenario(
        username="owner_admin_isolation",
        join_code="ENF005A",
        item_price=Decimal("10.00"),
    )

    # Build a separate canonical admin who has NO membership in owner's class
    with FEATContext("FEAT-STOR-006", idempotency_key="redemption:intruder"):
        intruder_user = make_teacher("intruder_isolation")
        intruder_class = create_class(
            intruder_user.id,
            join_code="INTRUDER1",
            display_name="Intruder Class",
            section="A",
        )

    login_teacher(client, intruder_user, class_id=intruder_class.class_id)

    resp = client.post(
        "/api/approve-redemption",
        json={"student_item_id": owner["student_item_id"]},
    )
    assert resp.status_code == 403 or resp.status_code == 404

    # And state was NOT mutated
    refetched = db.session.get(StorePurchase, owner["student_item_id"])
    assert refetched.status == "processing"
    assert RedemptionEvent.query.filter_by(purchase_id=owner["student_item_id"]).count() == 0
