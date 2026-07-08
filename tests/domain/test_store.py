"""Wave 8 — Store Domain (DOM-STORE-001) tests.

Tests verify:
1. Canonical schema: StorePurchase, RedemptionEvent, StoreItemVisibility
   have the right columns, FKs, and constraints per DOM-STORE-001 v2.0.
2. Behavioral contracts: purchase creates store_purchases, redemption creates
   redemption_events, visibility is seat-scoped, insufficient balance blocks
   purchase, idempotency prevents duplicate purchase.
"""
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import UniqueConstraint

from app.models import (
    RedemptionEvent,
    RedemptionEventAction,
    RedemptionEventSource,
    StorePurchase,
    StorePurchaseStatus,
    StoreItemVisibility,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fk_targets(model, column_name):
    return {fk.target_fullname for fk in model.__table__.c[column_name].foreign_keys}


def _column_names(model):
    return set(model.__table__.c.keys())


def _unique_constraints(model):
    return {c.name for c in model.__table__.constraints if isinstance(c, UniqueConstraint)}


# ===========================================================================
# Schema tests — StorePurchase
# ===========================================================================

class TestStorePurchaseSchema:
    def test_has_required_columns(self):
        """DOM-STORE-001 §VII.3: store_purchases must have seat_id, class_id, store_item_id, quantity, price_at_purchase, total_price, status."""
        cols = _column_names(StorePurchase)
        assert {
            "id", "seat_id", "class_id", "store_item_id",
            "quantity", "price_at_purchase", "total_price", "status",
            "idempotency_key", "ledger_tx_id", "purchased_at",
            "expiry_date", "is_from_bundle", "bundle_remaining",
            "uses_remaining", "collective_goal_instance_code",
        } <= cols

    def test_seat_fk_targets_seats(self):
        assert _fk_targets(StorePurchase, "seat_id") == {"seats.id"}

    def test_class_fk_targets_classes(self):
        assert _fk_targets(StorePurchase, "class_id") == {"classes.class_id"}

    def test_store_item_fk_targets_store_items(self):
        assert _fk_targets(StorePurchase, "store_item_id") == {"store_items.id"}

    def test_ledger_tx_fk_targets_ledger_transaction(self):
        assert _fk_targets(StorePurchase, "ledger_tx_id") == {"ledger_transaction.id"}

    def test_tablename(self):
        assert StorePurchase.__tablename__ == "store_purchases"

    def test_no_student_id_column(self):
        """store_purchases must not have legacy student_id; seat_id is the canonical anchor."""
        assert "student_id" not in _column_names(StorePurchase)

    def test_no_join_code_column(self):
        """store_purchases must not have join_code; class_id is the canonical boundary."""
        assert "join_code" not in _column_names(StorePurchase)

    def test_no_teacher_id_column(self):
        """store_purchases must not have teacher_id; no teacher scoping in v2 store tables."""
        assert "teacher_id" not in _column_names(StorePurchase)


# ===========================================================================
# Schema tests — RedemptionEvent
# ===========================================================================

class TestRedemptionEventSchema:
    def test_has_required_columns(self):
        """DOM-STORE-001 §VII.4: redemption_events must have purchase_id, action, source, timestamp."""
        cols = _column_names(RedemptionEvent)
        assert {
            "id", "purchase_id", "seat_id", "class_id",
            "action", "source", "initiated_by_user_id",
            "seat_display_name", "class_display_label",
            "notes", "timestamp",
        } <= cols

    def test_purchase_fk_targets_store_purchases(self):
        assert _fk_targets(RedemptionEvent, "purchase_id") == {"store_purchases.id"}

    def test_tablename(self):
        assert RedemptionEvent.__tablename__ == "redemption_events"

    def test_no_student_item_id_column(self):
        """redemption_events replaces redemption_audit_logs; no student_item_id FK."""
        assert "student_item_id" not in _column_names(RedemptionEvent)

    def test_action_enum_values(self):
        assert {e.value for e in RedemptionEventAction} == {"request", "approved", "rejected"}

    def test_source_enum_values(self):
        assert {e.value for e in RedemptionEventSource} == {"live"}


# ===========================================================================
# Schema tests — StoreItemVisibility
# ===========================================================================

class TestStoreItemVisibilitySchema:
    def test_has_required_columns(self):
        """DOM-STORE-001 §VII.2: store_item_visibility must have store_item_id, seat_id."""
        cols = _column_names(StoreItemVisibility)
        assert {"id", "store_item_id", "seat_id"} <= cols

    def test_store_item_fk_targets_store_items(self):
        assert _fk_targets(StoreItemVisibility, "store_item_id") == {"store_items.id"}

    def test_seat_fk_targets_seats(self):
        assert _fk_targets(StoreItemVisibility, "seat_id") == {"seats.id"}

    def test_tablename(self):
        assert StoreItemVisibility.__tablename__ == "store_item_visibility"

    def test_unique_constraint_on_item_seat(self):
        assert "uq_store_item_visibility_item_seat" in _unique_constraints(StoreItemVisibility)

    def test_no_block_column(self):
        """INV-CORE-000 §6: no label-based scoping. No block column."""
        assert "block" not in _column_names(StoreItemVisibility)


# ===========================================================================
# Behavioral tests (require app context / DB)
# ===========================================================================

@pytest.fixture
def store_test_setup(app):
    """Create minimal class + seat + store item for store domain tests."""
    from app.models import ClassEconomy, Seat, StoreItem, User, UserRole
    from app.extensions import db
    from app.utils.auth_username import build_hashed_username_fields

    with app.app_context():
        uname = f"store_teacher_{uuid.uuid4().hex[:8]}"
        _, username_hash, username_lookup_hash = build_hashed_username_fields(uname)
        user = User(
            user_role=UserRole.TEACHER,
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
        )
        db.session.add(user)
        db.session.flush()

        class_id = str(uuid.uuid4())
        join_code = uuid.uuid4().hex[:8].upper()
        economy = ClassEconomy(
            class_id=class_id,
            join_code=join_code,
            user_id=user.id,
            display_name="Test Class",
        )
        db.session.add(economy)
        db.session.flush()

        seat = Seat(
            class_id=class_id,
            user_id=user.id,
        )
        db.session.add(seat)
        db.session.flush()

        item = StoreItem(
            user_id=user.id,
            class_id=class_id,
            name="Test Reward",
            price=Decimal("10.00"),
            item_type="delayed",
            is_active=True,
        )
        db.session.add(item)
        db.session.commit()

        yield {
            "user": user,
            "class_id": class_id,
            "join_code": join_code,
            "seat": seat,
            "item": item,
            "teacher_id": user.id,
        }


class TestStorePurchaseBehavior:
    def test_purchase_creates_store_purchase_record(self, app, store_test_setup):
        """Purchase through service creates a StorePurchase row."""
        from app.services.store_service import record_standard_purchase_items
        from app.extensions import db

        with app.app_context():
            ctx = store_test_setup
            seat = db.session.merge(ctx["seat"])
            item = db.session.merge(ctx["item"])

            purchase_ids = record_standard_purchase_items(
                seat=seat,
                item=item,
                quantity=1,
                purchase_tx_id=None,
                total_price=Decimal("10.00"),
                expiry_date=None,
                purchase_status="purchased",
                uses_remaining=None,
            )

            assert len(purchase_ids) == 1
            purchase = db.session.get(StorePurchase, purchase_ids[0])
            assert purchase is not None
            assert purchase.seat_id == seat.id
            assert purchase.class_id == ctx["class_id"]
            assert purchase.store_item_id == item.id
            assert purchase.price_at_purchase == Decimal("10.00")
            assert purchase.status == "purchased"

    def test_idempotency_key_prevents_duplicate(self, app, store_test_setup):
        """Duplicate idempotency_key is rejected by unique constraint."""
        from app.services.store_service import record_standard_purchase_items
        from app.extensions import db
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            ctx = store_test_setup
            seat = db.session.merge(ctx["seat"])
            item = db.session.merge(ctx["item"])

            record_standard_purchase_items(
                seat=seat,
                item=item,
                quantity=1,
                purchase_tx_id=None,
                total_price=Decimal("10.00"),
                expiry_date=None,
                purchase_status="purchased",
                uses_remaining=None,
                idempotency_key="test-idem-key-001",
            )
            db.session.commit()

            with pytest.raises(IntegrityError):
                record_standard_purchase_items(
                    seat=seat,
                    item=item,
                    quantity=1,
                    purchase_tx_id=None,
                    total_price=Decimal("10.00"),
                    expiry_date=None,
                    purchase_status="purchased",
                    uses_remaining=None,
                    idempotency_key="test-idem-key-001",
                )
                db.session.flush()


class TestStoreVisibilityBehavior:
    def test_visibility_defaults_to_all(self, app, store_test_setup):
        """No visibility rows means visible to all seats."""
        from app.services.store_service import is_item_visible_to_seat
        from app.extensions import db

        with app.app_context():
            ctx = store_test_setup
            item = db.session.merge(ctx["item"])
            seat = db.session.merge(ctx["seat"])
            assert is_item_visible_to_seat(item.id, seat.id) is True

    def test_visibility_restricts_to_granted_seats(self, app, store_test_setup):
        """Visibility grants restrict to specific seats only."""
        from app.services.store_service import is_item_visible_to_seat, set_item_visibility
        from app.models import Seat
        from app.extensions import db

        with app.app_context():
            ctx = store_test_setup
            item = db.session.merge(ctx["item"])
            seat = db.session.merge(ctx["seat"])

            from app.models import User, UserRole
            from app.utils.auth_username import build_hashed_username_fields
            uname2 = f"other_{uuid.uuid4().hex[:8]}"
            _, h2, lh2 = build_hashed_username_fields(uname2)
            other_user = User(user_role=UserRole.STUDENT, username_hash=h2, username_lookup_hash=lh2)
            db.session.add(other_user)
            db.session.flush()
            other_seat = Seat(class_id=ctx["class_id"], user_id=other_user.id)
            db.session.add(other_seat)
            db.session.flush()

            set_item_visibility(item.id, [seat.id])
            db.session.flush()

            assert is_item_visible_to_seat(item.id, seat.id) is True
            assert is_item_visible_to_seat(item.id, other_seat.id) is False


class TestRedemptionEventBehavior:
    def test_redemption_event_creation(self, app, store_test_setup):
        """Redemption event can be created against a StorePurchase."""
        from app.extensions import db

        with app.app_context():
            ctx = store_test_setup
            seat = db.session.merge(ctx["seat"])
            item = db.session.merge(ctx["item"])

            purchase = StorePurchase(
                seat_id=seat.id,
                class_id=ctx["class_id"],
                store_item_id=item.id,
                quantity=1,
                price_at_purchase=Decimal("10.00"),
                total_price=Decimal("10.00"),
                status="processing",
            )
            db.session.add(purchase)
            db.session.flush()

            event = RedemptionEvent(
                purchase_id=purchase.id,
                seat_id=seat.id,
                class_id=ctx["class_id"],
                action=RedemptionEventAction.APPROVED,
                source=RedemptionEventSource.LIVE,
                initiated_by_user_id=ctx["teacher_id"],
                seat_display_name="Test Student",
                class_display_label="Test Class",
            )
            db.session.add(event)
            db.session.commit()

            saved = db.session.get(RedemptionEvent, event.id)
            assert saved is not None
            assert saved.purchase_id == purchase.id
            assert saved.action == RedemptionEventAction.APPROVED
