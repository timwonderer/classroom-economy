"""Wave 8 — Store Domain (DOM-STORE-001) tests.

Tests verify:
1. Canonical schema: Entitlement, EntitlementConsumption, InsuranceClaim,
   RedemptionEvent, StoreItemVisibility have the right columns, FKs, and
   constraints per DOM-STORE-001 v3.0.
2. Behavioral contracts: purchase creates store_purchases, redemption creates
   redemption_events, visibility is seat-scoped, insufficient balance blocks
   purchase, idempotency prevents duplicate purchase.
"""
from decimal import Decimal
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import UniqueConstraint

from app.feats.base import FEATContext
from app.feats.insurance_claim_feat import execute_claim_submission, execute_claim_approval
from app.feats.store_purchase_feat import execute_store_purchase
from app.models import (
    Entitlement,
    EntitlementConsumption,
    GrantType,
    Disposition,
    InsuranceClaim,
    InsuranceClaimStatus,
    RedemptionEvent,
    RedemptionEventAction,
    RedemptionEventSource,
    StorePurchase,
    StoreItemVisibility,
)
from tests.dom.entitlement.helpers import create_entitlement_store_item
from tests.dom.entitlement.helpers import set_entitlement_item_visibility
from tests.helpers.classroom_initializer import initialize


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
# Schema tests — Entitlement
# ===========================================================================

class TestEntitlementSchema:
    def test_DOM_STORE_001__entitlement_has_required_columns(self):
        """DOM-STORE-001 §VII.A: entitlements must have the canonical grant columns."""
        cols = _column_names(Entitlement)
        assert {
            "id", "entitlement_id", "entitlement_item_id",
            "target_seat_id", "actor_seat_id", "class_id",
            "grant_type", "correlation_id", "granted_at",
        } <= cols

    def test_DOM_STORE_001__entitlement_target_seat_fk_targets_seats(self):
        assert _fk_targets(Entitlement, "target_seat_id") == {"seats.id"}

    def test_DOM_STORE_001__entitlement_actor_seat_fk_targets_seats(self):
        assert _fk_targets(Entitlement, "actor_seat_id") == {"seats.id"}

    def test_DOM_STORE_001__entitlement_class_fk_targets_classes(self):
        assert _fk_targets(Entitlement, "class_id") == {"classes.class_id"}

    def test_DOM_STORE_001__entitlement_item_fk_targets_store_items(self):
        assert _fk_targets(Entitlement, "entitlement_item_id") == {"store_items.id"}

    def test_DOM_STORE_001__entitlement_tablename(self):
        assert Entitlement.__tablename__ == "entitlements"

    def test_DOM_STORE_001__entitlement_no_purchase_id_column(self):
        """entitlements must not persist purchase_id authority."""
        assert "purchase_id" not in _column_names(Entitlement)

    def test_DOM_STORE_001__entitlement_no_join_code_column(self):
        """entitlements must not have join_code; class_id is the canonical boundary."""
        assert "join_code" not in _column_names(Entitlement)

    def test_DOM_STORE_001__entitlement_no_teacher_id_column(self):
        """entitlements must not have teacher_id; actor_seat_id is the authority anchor."""
        assert "teacher_id" not in _column_names(Entitlement)


class TestEntitlementConsumptionSchema:
    def test_DOM_STORE_001__entitlement_consumption_has_required_columns(self):
        cols = _column_names(EntitlementConsumption)
        assert {
            "id", "consumption_id", "entitlement_id", "class_id",
            "target_seat_id", "actor_seat_id", "disposition",
            "correlation_id", "timestamp",
        } <= cols

    def test_DOM_STORE_001__entitlement_consumption_entitlement_fk_targets_entitlements(self):
        assert _fk_targets(EntitlementConsumption, "entitlement_id") == {"entitlements.entitlement_id"}

    def test_DOM_STORE_001__entitlement_consumption_target_fk_targets_seats(self):
        assert _fk_targets(EntitlementConsumption, "target_seat_id") == {"seats.id"}

    def test_DOM_STORE_001__entitlement_consumption_actor_fk_targets_seats(self):
        assert _fk_targets(EntitlementConsumption, "actor_seat_id") == {"seats.id"}

    def test_DOM_STORE_001__entitlement_consumption_class_fk_targets_classes(self):
        assert _fk_targets(EntitlementConsumption, "class_id") == {"classes.class_id"}

    def test_DOM_STORE_001__entitlement_consumption_tablename(self):
        assert EntitlementConsumption.__tablename__ == "entitlement_consumptions"

    def test_DOM_STORE_001__entitlement_consumption_unique_terminal_constraint(self):
        assert "uq_entitlement_terminal_event" in _unique_constraints(EntitlementConsumption)


class TestInsuranceClaimSchema:
    def test_DOM_STORE_001__insurance_claim_has_required_columns(self):
        cols = _column_names(InsuranceClaim)
        assert {
            "id", "claim_id", "class_id", "entitlement_id",
            "target_seat_id", "actor_seat_id", "transaction_id",
            "claimed_dates", "status", "submitted_at",
            "decided_at", "decided_by_seat_id", "correlation_id",
        } <= cols

    def test_DOM_STORE_001__insurance_claim_entitlement_fk_targets_entitlements(self):
        assert _fk_targets(InsuranceClaim, "entitlement_id") == {"entitlements.entitlement_id"}

    def test_DOM_STORE_001__insurance_claim_target_fk_targets_seats(self):
        assert _fk_targets(InsuranceClaim, "target_seat_id") == {"seats.id"}

    def test_DOM_STORE_001__insurance_claim_actor_fk_targets_seats(self):
        assert _fk_targets(InsuranceClaim, "actor_seat_id") == {"seats.id"}

    def test_DOM_STORE_001__insurance_claim_decided_by_fk_targets_seats(self):
        assert _fk_targets(InsuranceClaim, "decided_by_seat_id") == {"seats.id"}

    def test_DOM_STORE_001__insurance_claim_transaction_fk_targets_ledger(self):
        assert _fk_targets(InsuranceClaim, "transaction_id") == {"ledger_transaction.id"}

    def test_DOM_STORE_001__insurance_claim_tablename(self):
        assert InsuranceClaim.__tablename__ == "insurance_claims"


# ===========================================================================
# Schema tests — RedemptionEvent
# ===========================================================================

class TestRedemptionEventSchema:
    def test_DOM_STORE_001__redemption_event_has_required_columns(self):
        """DOM-STORE-001 §VII.4: redemption_events must have entitlement_id, action, source, timestamp."""
        cols = _column_names(RedemptionEvent)
        assert {
            "id", "entitlement_id", "seat_id", "class_id",
            "action", "source", "initiated_by_user_id",
            "seat_display_name", "class_display_label",
            "notes", "timestamp",
        } <= cols

    def test_DOM_STORE_001__redemption_event_entitlement_fk_targets_entitlements(self):
        assert _fk_targets(RedemptionEvent, "entitlement_id") == {"entitlements.entitlement_id"}

    def test_DOM_STORE_001__redemption_event_tablename(self):
        assert RedemptionEvent.__tablename__ == "redemption_events"

    def test_DOM_STORE_001__redemption_event_no_student_item_id_column(self):
        """redemption_events replaces redemption_audit_logs; no student_item_id FK."""
        assert "student_item_id" not in _column_names(RedemptionEvent)

    def test_DOM_STORE_001__redemption_event_action_enum_values(self):
        assert {e.value for e in RedemptionEventAction} == {"REQUEST", "APPROVED", "REJECTED"}

    def test_DOM_STORE_001__redemption_event_source_enum_values(self):
        assert {e.value for e in RedemptionEventSource} == {"live"}


# ===========================================================================
# Schema tests — StoreItemVisibility
# ===========================================================================

class TestStoreItemVisibilitySchema:
    def test_DOM_STORE_001__store_item_visibility_has_required_columns(self):
        """DOM-STORE-001 §VII.2: store_item_visibility must have store_item_id, seat_id."""
        cols = _column_names(StoreItemVisibility)
        assert {"id", "store_item_id", "seat_id"} <= cols

    def test_DOM_STORE_001__store_item_visibility_store_item_fk_targets_store_items(self):
        assert _fk_targets(StoreItemVisibility, "store_item_id") == {"store_items.id"}

    def test_DOM_STORE_001__store_item_visibility_seat_fk_targets_seats(self):
        assert _fk_targets(StoreItemVisibility, "seat_id") == {"seats.id"}

    def test_DOM_STORE_001__store_item_visibility_tablename(self):
        assert StoreItemVisibility.__tablename__ == "store_item_visibility"

    def test_DOM_STORE_001__store_item_visibility_unique_constraint_on_item_seat(self):
        assert "uq_store_item_visibility_item_seat" in _unique_constraints(StoreItemVisibility)

    def test_DOM_STORE_001__store_item_visibility_no_block_column(self):
        """INV-CORE-000 §6: no label-based scoping. No block column."""
        assert "block" not in _column_names(StoreItemVisibility)


# ===========================================================================
# Behavioral tests (require app context / DB)
# ===========================================================================

@pytest.fixture
def store_test_setup(app):
    """Create canonical classroom + store item for store domain tests."""
    from app.models import StoreItem
    from app.extensions import db

    with app.app_context():
        classroom = initialize("chemistry_p1", app)
        item = create_entitlement_store_item(
            teacher_id=classroom.teacher_user.id,
            class_id=classroom.class_id,
            name="Test Reward",
            price=Decimal("10.00"),
            item_type="delayed",
        )

        yield {
            "classroom": classroom,
            "seat": classroom.teacher_seat,
            "item": item,
        }


class TestStorePurchaseBehavior:
    def test_DOM_STORE_001__purchase_creates_entitlement_record(self, app, store_test_setup):
        """Purchase through FEAT-STOR-001 creates an entitlement row."""
        from app.extensions import db
        from tests.dom.entitlement.helpers import create_entitlement_store_item

        with app.app_context():
            ctx = store_test_setup
            seat = db.session.merge(ctx["seat"])
            item = create_entitlement_store_item(
                teacher_id=ctx["classroom"].teacher_user.id,
                class_id=ctx["classroom"].class_id,
                name="Zero Price Reward",
                price=Decimal("0.00"),
                item_type="delayed",
            )

            with FEATContext("FEAT-STOR-001", idempotency_key="store_test:purchase_record"):
                result = execute_store_purchase(
                    ctx=SimpleNamespace(class_id=ctx["classroom"].class_id),
                    seat=seat,
                    item=item,
                    quantity=1,
                    total_price=Decimal("0.00"),
                    purchase_description=f"Purchase: {item.name}",
                    banking_settings=None,
                    idempotency_key="store_test:purchase_record",
                    is_instant_use=False,
                )

                assert len(result.entitlement_ids) == 1
                entitlement = db.session.query(Entitlement).filter_by(entitlement_id=result.entitlement_ids[0]).one()
                assert entitlement.target_seat_id == seat.id
                assert entitlement.class_id == ctx["classroom"].class_id
                assert entitlement.entitlement_item_id == item.id
                assert entitlement.grant_type == GrantType.PURCHASE
                assert entitlement.correlation_id == "store_test:purchase_record"

    def test_DOM_STORE_001__idempotency_key_prevents_duplicate(self, app, store_test_setup):
        """Duplicate idempotency key replays the canonical entitlement grant."""
        from app.extensions import db
        from tests.dom.entitlement.helpers import create_entitlement_store_item

        with app.app_context():
            ctx = store_test_setup
            seat = db.session.merge(ctx["seat"])
            item = create_entitlement_store_item(
                teacher_id=ctx["classroom"].teacher_user.id,
                class_id=ctx["classroom"].class_id,
                name="Replay Safe Reward",
                price=Decimal("0.00"),
                item_type="delayed",
            )

            with FEATContext("FEAT-STOR-001", idempotency_key="store_test:idempotency_first"):
                first = execute_store_purchase(
                    ctx=SimpleNamespace(class_id=ctx["classroom"].class_id),
                    seat=seat,
                    item=item,
                    quantity=1,
                    total_price=Decimal("0.00"),
                    purchase_description=f"Purchase: {item.name}",
                    banking_settings=None,
                    idempotency_key="test-idem-key-001",
                    is_instant_use=False,
                )

            with FEATContext("FEAT-STOR-001", idempotency_key="store_test:idempotency_second"):
                second = execute_store_purchase(
                    ctx=SimpleNamespace(class_id=ctx["classroom"].class_id),
                    seat=seat,
                    item=item,
                    quantity=1,
                    idempotency_key="test-idem-key-001",
                    total_price=Decimal("0.00"),
                    purchase_description=f"Purchase: {item.name}",
                    banking_settings=None,
                    is_instant_use=False,
                )

            assert first.entitlement_ids == second.entitlement_ids
            assert db.session.query(Entitlement).filter_by(
                correlation_id="test-idem-key-001",
                target_seat_id=seat.id,
                class_id=ctx["classroom"].class_id,
                entitlement_item_id=item.id,
            ).count() == 1


class TestStoreVisibilityBehavior:
    def test_DOM_STORE_001__visibility_defaults_to_all(self, app, store_test_setup):
        """No visibility rows means visible to all seats."""
        from app.services.store_service import is_item_visible_to_seat
        from app.extensions import db

        with app.app_context():
            ctx = store_test_setup
            item = db.session.merge(ctx["item"])
            seat = db.session.merge(ctx["seat"])
            with FEATContext("FEAT-STOR-001", idempotency_key="store_test:visibility_default"):
                assert is_item_visible_to_seat(item.id, seat.id) is True

    def test_DOM_STORE_001__visibility_restricts_to_granted_seats(self, app, store_test_setup):
        """Visibility grants restrict to specific seats only."""
        from app.services.store_service import is_item_visible_to_seat
        from app.models import Seat
        from app.extensions import db

        with app.app_context():
            ctx = store_test_setup
            item = db.session.merge(ctx["item"])
            seat = db.session.merge(ctx["seat"])

            with FEATContext("FEAT-STOR-001", idempotency_key="store_test:visibility_grant"):
                from app.models import User, UserRole
                from app.utils.auth_username import build_hashed_username_fields
                uname2 = f"other_{uuid.uuid4().hex[:8]}"
                _, h2, lh2 = build_hashed_username_fields(uname2)
                other_user = User(user_role=UserRole.STUDENT, username_hash=h2, username_lookup_hash=lh2)
                db.session.add(other_user)
                db.session.flush()
                other_seat = Seat(class_id=ctx["classroom"].class_id, user_id=other_user.id)
                db.session.add(other_seat)
                db.session.flush()

                set_entitlement_item_visibility(item.id, [seat.id])

                assert is_item_visible_to_seat(item.id, seat.id) is True
                assert is_item_visible_to_seat(item.id, other_seat.id) is False


class TestRedemptionEventBehavior:
    def test_DOM_STORE_001__redemption_event_creation(self, app, store_test_setup):
        """Redemption event can be created against a StorePurchase."""
        from app.extensions import db

        with app.app_context():
            ctx = store_test_setup
            seat = db.session.merge(ctx["seat"])
            item = db.session.merge(ctx["item"])

            with FEATContext("FEAT-STOR-006", idempotency_key="store_test:redemption_event"):
                purchase = StorePurchase(
                    seat_id=seat.id,
                    class_id=ctx["classroom"].class_id,
                    store_item_id=item.id,
                    quantity=1,
                    price_at_purchase=Decimal("10.00"),
                    total_price=Decimal("10.00"),
                    status="processing",
                )
                db.session.add(purchase)
                db.session.flush()

                from app.models import GrantType
                from app.services.store_entitlement_service import grant_entitlement
                entitlement = grant_entitlement(
                    entitlement_item_id=item.id,
                    target_seat_id=seat.id,
                    actor_seat_id=seat.id,
                    class_id=ctx["classroom"].class_id,
                    grant_type=GrantType.PURCHASE,
                )

                event = RedemptionEvent(
                    entitlement_id=entitlement.entitlement_id,
                    seat_id=seat.id,
                    class_id=ctx["classroom"].class_id,
                    action=RedemptionEventAction.APPROVED,
                    source=RedemptionEventSource.LIVE,
                    initiated_by_user_id=ctx["classroom"].teacher_user.id,
                    seat_display_name="Test Student",
                    class_display_label="Test Class",
                )
                db.session.add(event)
                db.session.flush()

            saved = db.session.get(RedemptionEvent, event.id)
            assert saved is not None
            assert saved.entitlement_id == entitlement.entitlement_id
            assert saved.action == RedemptionEventAction.APPROVED


class TestInsuranceClaimBehavior:
    def test_DOM_STORE_001__insurance_claim_submission_and_approval(self, app, store_test_setup):
        """Insurance FEAT writes canonical claim state without touching entitlement authority."""
        from app.extensions import db
        from app.models import Entitlement, InsuranceClaim, InsuranceClaimStatus
        from app.services.store_entitlement_service import grant_entitlement

        with app.app_context():
            ctx = store_test_setup
            seat = db.session.merge(ctx["seat"])
            item = db.session.merge(ctx["item"])
            with FEATContext("FEAT-STOR-001", idempotency_key="store_test:insurance_grant"):
                entitlement = grant_entitlement(
                    entitlement_item_id=item.id,
                    target_seat_id=seat.id,
                    actor_seat_id=seat.id,
                    class_id=ctx["classroom"].class_id,
                    grant_type=GrantType.PURCHASE,
                    correlation_id="store_test:insurance_claim",
                )

            result = execute_claim_submission(
                entitlement_id=entitlement.entitlement_id,
                target_seat_id=seat.id,
                actor_seat_id=seat.id,
                class_id=ctx["classroom"].class_id,
                transaction_id=None,
                claimed_dates={"note": "test"},
                correlation_id="store_test:insurance_claim",
                policy_claim_type="NON_MONETARY",
            )

            claim = db.session.query(InsuranceClaim).filter_by(claim_id=result.claim_id).one()
            assert claim is not None
            assert claim.status == InsuranceClaimStatus.SUBMITTED
            assert claim.entitlement_id == entitlement.entitlement_id
            assert claim.transaction_id is None
            assert db.session.get(Entitlement, entitlement.id).entitlement_id == entitlement.entitlement_id

            approved = execute_claim_approval(
                claim_id=claim.claim_id,
                decided_by_seat_id=seat.id,
            )

            db.session.refresh(claim)
            assert approved.status == InsuranceClaimStatus.APPROVED.value
            assert claim.status == InsuranceClaimStatus.APPROVED
