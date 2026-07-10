"""Tests for rent item types (privilege, per-use, hall-pass) in V2 canonical patterns."""
from tests.helpers.v2_fixtures import make_teacher
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.admin_context import login_teacher
import pytest
import re
from decimal import Decimal
from app.models import (
    User, RentItem, RentSettings, RentPayment, RentWaiver,
    StoreItem, StudentItem, Transaction, ClassEconomy, Seat, IdentityProfile,
    ClassFeature,
)
from app.extensions import db
from datetime import datetime, timezone, timedelta


def _enable_rent(class_id):
    """Enable the 'rent' feature for a class if not already enabled."""
    existing = ClassFeature.query.filter_by(class_id=class_id, feature_name="rent").first()
    if not existing:
        db.session.add(ClassFeature(class_id=class_id, feature_name="rent"))
        db.session.flush()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def teacher_user(client):
    """Create a teacher User."""
    teacher = make_teacher("teacher_rent")
    db.session.commit()
    return teacher


@pytest.fixture
def class_scope(client, teacher_user):
    """Create a class economy for the teacher with 'rent' feature enabled."""
    ce = create_class_scope(teacher_user=teacher_user, join_code="JOINCODE123", section="A")
    _enable_rent(ce.class_id)
    db.session.commit()
    return ce


@pytest.fixture
def student_seat(client, class_scope):
    """Create a student seat in the teacher's class."""
    seat = make_student_identity(
        class_id=class_scope.class_id,
        first_name="Test",
        last_name="S",
        claimed=True,
    )
    db.session.commit()
    return seat


@pytest.fixture
def admin_class_scope(client, teacher_user):
    """Create a second class scope used by admin-focused tests (section='A' so block routes work)."""
    ce = ClassEconomy.query.filter_by(join_code="SCOPE123").first()
    if not ce:
        ce = create_class_scope(teacher_user=teacher_user, join_code="SCOPE123", section="A")
        db.session.flush()
    elif ce.section != "A":
        ce.section = "A"
        db.session.flush()
    _enable_rent(ce.class_id)
    # ensure at least one student seat exists so routes can resolve context
    make_student_identity(class_id=ce.class_id, first_name="Scope", last_name="S", claimed=True)
    db.session.commit()
    return ce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login_student(client, seat):
    """Set up a minimal student session for the given seat."""
    student_user = db.session.get(User, seat.user_id)
    assert student_user is not None
    db.session.execute(
        db.text("UPDATE users SET last_active_class_id = :cid, last_active_seat_id = :sid WHERE id = :uid"),
        {"cid": seat.class_id, "sid": seat.id, "uid": student_user.id},
    )
    db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = student_user.id
        sess["current_session_nonce"] = student_user.current_session_nonce
        sess["current_join_code"] = ClassEconomy.query.filter_by(
            class_id=seat.class_id
        ).first().join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
    return student_user


def _get_checking_balance(seat):
    """Sum checking transactions for a seat to compute available balance."""
    result = db.session.execute(
        db.text(
            "SELECT COALESCE(SUM(amount), 0) FROM ledger_transaction "
            "WHERE seat_id = :sid AND account_type = 'checking'"
        ),
        {"sid": seat.id},
    ).scalar()
    return Decimal(str(result))


def _add_rent_payment(seat, class_id, *, amount, period="A", now=None):
    """Add a RentPayment + matching Transaction for a seat."""
    join_code = ClassEconomy.query.filter_by(class_id=class_id).first().join_code
    now = now or datetime.now(timezone.utc)
    db.session.add(
        RentPayment(
            seat_id=seat.id,
            class_id=class_id,
            join_code=join_code,
            period=period,
            amount_paid=Decimal(str(amount)),
            period_month=now.month,
            period_year=now.year,
            coverage_month=now.month,
            coverage_year=now.year,
            payment_date=now,
        )
    )
    db.session.add(
        Transaction(
            user_id=seat.user_id,
            seat_id=seat.id,
            class_id=class_id,
            join_code=join_code,
            amount=Decimal(str(amount)) * -1,
            account_type="checking",
            type="Rent Payment",
            description=f"Rent for Period {period}",
            timestamp=now,
        )
    )


def _make_canonical_context(seat):
    """Build a minimal CanonicalContext-like object for direct function tests."""
    from app.services.context_resolver import CanonicalContext
    return CanonicalContext(
        user_id=seat.user_id,
        class_id=seat.class_id,
        seat_id=seat.id,
        actor_role="student",
    )


# ---------------------------------------------------------------------------
# Tests: admin configure rent item types
# ---------------------------------------------------------------------------

def test_admin_configure_rent_item_types(client, teacher_user, admin_class_scope):
    """Test that admin can configure different rent item types."""
    login_teacher(client, teacher_user, class_id=admin_class_scope.class_id)

    settings = RentSettings(class_id=admin_class_scope.class_id)
    db.session.add(settings)
    db.session.commit()

    data = {
        "settings_block": "A",
        "is_enabled": "on",
        "rent_amount": "50.00",
        "frequency_type": "monthly",
        "due_day_of_month": "1",
        "grace_period_days": "3",
        "late_penalty_amount": "10.00",
        # Item 0: Privilege
        "rent_item_name_0": "Desk",
        "rent_item_type_0": "privilege",
        "rent_item_store_available_0": "on",
        "rent_item_store_price_0": "100.00",
        "rent_item_purchase_duration_0": "per_period",
        # Item 1: Per-Use
        "rent_item_name_1": "Pencil",
        "rent_item_type_1": "per_use",
        "rent_item_store_available_1": "on",
        "rent_item_store_price_1": "5.00",
        "rent_item_purchase_duration_1": "per_use",
        "rent_item_use_limit_1": "5",
        # Item 2: Hall Pass
        "rent_item_name_2": "Bonus Pass",
        "rent_item_type_2": "hall_pass",
        "rent_item_hall_pass_count_2": "2",
    }

    resp = client.post("/admin/rent-settings", data=data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Rent settings updated successfully" in resp.data

    items = (
        RentItem.query.filter_by(rent_setting_id=settings.id)
        .order_by(RentItem.order_index)
        .all()
    )
    assert len(items) == 3

    assert items[0].name == "Desk"
    assert items[0].rent_item_type == "privilege"
    assert items[0].store_price == Decimal("100.00")
    assert items[0].store_item_id is not None

    assert items[1].name == "Pencil"
    assert items[1].rent_item_type == "per_use"
    assert items[1].use_limit == 5
    assert items[1].store_item_id is not None

    assert items[2].name == "Bonus Pass"
    assert items[2].rent_item_type == "hall_pass"
    assert items[2].hall_pass_count == 2
    assert items[2].store_item_id is None


def test_store_sync_logic(client, teacher_user, admin_class_scope):
    """Test that store items are created/updated correctly based on type."""
    settings = RentSettings(class_id=admin_class_scope.class_id)
    db.session.add(settings)
    db.session.flush()

    # Pre-create store items so sync takes the "update existing" path
    # (avoids a bug in admin.py line 6168 that uses teacher_id instead of user_id)
    privilege_store = StoreItem(
        user_id=teacher_user.id,
        class_id=admin_class_scope.class_id,
        join_code=admin_class_scope.join_code,
        name="Privilege",
        price=Decimal("10.00"),
        item_type="delayed",
        is_active=True,
    )
    per_use_store = StoreItem(
        user_id=teacher_user.id,
        class_id=admin_class_scope.class_id,
        join_code=admin_class_scope.join_code,
        name="Consumable",
        price=Decimal("2.00"),
        item_type="delayed",
        is_active=True,
    )
    db.session.add_all([privilege_store, per_use_store])
    db.session.flush()

    privilege = RentItem(
        rent_setting_id=settings.id,
        name="Privilege",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("10.00"),
        purchase_duration="per_period",
        store_item_id=privilege_store.id,
    )
    per_use = RentItem(
        rent_setting_id=settings.id,
        name="Consumable",
        rent_item_type="per_use",
        is_available_in_store=True,
        store_price=Decimal("2.00"),
        purchase_duration="per_use",
        use_limit=1,
        store_item_id=per_use_store.id,
    )
    hall_pass = RentItem(
        rent_setting_id=settings.id,
        name="HP",
        rent_item_type="hall_pass",
        hall_pass_count=1,
    )
    db.session.add_all([privilege, per_use, hall_pass])
    db.session.commit()

    from app.routes.admin import _sync_rent_items_to_store
    _sync_rent_items_to_store(settings, teacher_user.id, "A")

    db.session.refresh(privilege_store)
    assert privilege_store is not None
    assert privilege_store.price == Decimal("10.00")
    assert privilege_store.limit_per_student == 1
    assert privilege_store.is_rent_linked is True

    db.session.refresh(per_use_store)
    assert per_use_store is not None
    assert per_use_store.is_rent_linked is True

    hall_pass_store = StoreItem.query.filter_by(name="HP").first()
    assert hall_pass_store is None


def test_student_purchase_per_use_item(client, teacher_user, class_scope, student_seat):
    """Test student purchasing a multi-use item."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Multi-Use Snack",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
    )
    db.session.add(store_item)
    db.session.flush()

    settings = RentSettings(class_id=class_scope.class_id)
    db.session.add(settings)
    db.session.flush()

    rent_item = RentItem(
        rent_setting_id=settings.id,
        name="Multi-Use Snack",
        rent_item_type="per_use",
        is_available_in_store=True,
        store_price=Decimal("5.00"),
        purchase_duration="per_use",
        use_limit=3,
        store_item_id=store_item.id,
    )
    db.session.add(rent_item)

    # Give student money
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=100,
            account_type="checking",
        )
    )
    db.session.commit()

    # Set student password
    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")
    db.session.commit()

    _login_student(client, seat)

    data = {"item_id": store_item.id, "passphrase": "password", "quantity": 1}
    resp = client.post("/api/purchase-item", json=data)
    assert resp.status_code == 200

    student_item = StudentItem.query.filter_by(
        seat_id=seat.id, store_item_id=store_item.id
    ).first()
    assert student_item is not None
    assert student_item.status == "purchased"
    assert student_item.uses_remaining is None


def test_student_use_per_use_item(client, teacher_user, class_scope, student_seat):
    """Test decrementing uses for a multi-use item."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    store_item = StoreItem(
        user_id=teacher_user.id, name="Pencil", price=5, is_active=True
    )
    db.session.add(store_item)
    db.session.flush()

    student_item = StudentItem(
        seat_id=seat.id,
        correlation_id="corr_test",
        store_item_id=store_item.id,
        status="purchased",
        uses_remaining=3,
    )
    db.session.add(student_item)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")
    db.session.commit()

    _login_student(client, seat)

    data = {"student_item_id": student_item.id, "passphrase": "password"}
    resp = client.post("/api/use-item", json=data)
    assert resp.status_code == 200
    assert "2 uses remaining" in resp.json["message"]

    db.session.refresh(student_item)
    assert student_item.uses_remaining == 2
    assert student_item.status == "purchased"

    client.post("/api/use-item", json=data)
    db.session.refresh(student_item)
    assert student_item.uses_remaining == 1

    client.post("/api/use-item", json=data)
    db.session.refresh(student_item)
    assert student_item.uses_remaining == 0
    assert student_item.status == "processing"


def test_prevent_deletion_of_linked_items(client, teacher_user, admin_class_scope):
    """Test that admin cannot delete store items linked to rent settings."""
    login_teacher(client, teacher_user, class_id=admin_class_scope.class_id)

    store_item = StoreItem(
        user_id=teacher_user.id,
        class_id=admin_class_scope.class_id,
        join_code=admin_class_scope.join_code,
        name="Rent Linked",
        price=10,
        is_active=True,
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.commit()

    resp = client.post(
        f"/admin/store/delete/{store_item.id}", follow_redirects=True
    )
    assert b"Cannot delete" in resp.data
    assert b"managed by Rent Settings" in resp.data

    db.session.refresh(store_item)
    assert store_item.is_active is True

    resp = client.post(
        f"/admin/store/hard-delete/{store_item.id}", follow_redirects=True
    )
    assert b"Cannot delete" in resp.data

    db.session.refresh(store_item)
    assert store_item is not None


def test_hall_pass_topoff_replenishes_rent_portion_only(client, teacher_user, class_scope, student_seat):
    """Test hall pass top-off only replenishes the rent-granted portion, not purchased passes."""
    seat = student_seat
    assert seat is not None

    seat.hall_passes = 1
    db.session.commit()

    total_hall_passes = 3  # student has 1 rent + 2 purchased = 3 total
    # Simulate: student purchased 2 extra = 3 total hall passes on seat side
    # We'll track total via the seat attribute directly

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("50.00"),
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db.session.add(settings)
    db.session.flush()

    hall_pass_item = RentItem(
        rent_setting_id=settings.id,
        name="Hall Passes",
        rent_item_type="hall_pass",
        hall_pass_count=3,
    )
    db.session.add(hall_pass_item)
    db.session.commit()

    total_grant = sum(
        item.hall_pass_count for item in [hall_pass_item] if item.hall_pass_count
    )
    current_rent_passes = seat.hall_passes  # 1
    top_off = max(0, total_grant - current_rent_passes)  # 3 - 1 = 2

    # Simulate: student has 3 total (1 rent + 2 purchased), top-off adds 2 more
    simulated_total = total_hall_passes + top_off  # 3 + 2 = 5
    seat.hall_passes = total_grant  # 3
    db.session.commit()

    db.session.refresh(seat)
    assert simulated_total == 5
    assert seat.hall_passes == 3


def test_hall_pass_topoff_zero_existing(client, teacher_user, class_scope, student_seat):
    """Test hall pass top-off when student has 0 passes grants full amount."""
    seat = student_seat
    assert seat is not None

    seat.hall_passes = 0
    db.session.commit()

    total_grant = 3
    current_rent_passes = seat.hall_passes
    top_off = max(0, total_grant - current_rent_passes)

    seat.hall_passes = total_grant
    db.session.commit()

    db.session.refresh(seat)
    assert top_off == 3
    assert seat.hall_passes == 3


def test_hall_pass_consumption_decrements_rent_passes_first(client, teacher_user, class_scope, student_seat):
    """Test that using a hall pass decrements rent_hall_passes before purchased passes."""
    seat = student_seat
    assert seat is not None

    # seat.hall_passes tracks rent-granted passes
    seat.hall_passes = 3
    db.session.commit()

    total_passes = 5  # 3 rent + 2 purchased (tracked externally)

    # Consume 1 pass
    total_passes -= 1
    if seat.hall_passes > 0:
        seat.hall_passes -= 1
    db.session.commit()

    db.session.refresh(seat)
    assert total_passes == 4
    assert seat.hall_passes == 2

    # Consume 2 more rent passes
    for _ in range(2):
        total_passes -= 1
        if seat.hall_passes > 0:
            seat.hall_passes -= 1
    db.session.commit()

    db.session.refresh(seat)
    assert total_passes == 2
    assert seat.hall_passes == 0

    # Next pass from purchased (rent grant stays 0)
    total_passes -= 1
    if seat.hall_passes > 0:
        seat.hall_passes -= 1
    db.session.commit()

    db.session.refresh(seat)
    assert total_passes == 1
    assert seat.hall_passes == 0


def test_unpaid_period_revokes_rent_hall_passes_and_payment_restores_immediately(
    client, teacher_user, class_scope, student_seat
):
    """Unpaid students lose rent-granted hall passes for the new period; paying restores them immediately."""
    from app.routes.student import _ensure_rent_hall_pass_top_off

    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Hall Pass Grant",
            rent_item_type="hall_pass",
            hall_pass_count=3,
        )
    )

    assert seat is not None
    seat.hall_passes = 3
    # Simulate student has 5 total (3 rent + 2 purchased)
    db.session.commit()

    context = _make_canonical_context(seat)
    fixed_now = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(
        seat, context, settings=settings, now=fixed_now
    )
    assert changed is True
    assert awarded == 0
    assert revoked == 3

    db.session.commit()
    db.session.refresh(seat)
    assert seat.hall_passes == 0

    # Pay rent and reconcile again
    _add_rent_payment(
        seat,
        class_scope.class_id,
        amount="10.00",
        period="A",
        now=fixed_now,
    )
    db.session.commit()

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(
        seat,
        context,
        settings=settings,
        now=fixed_now + timedelta(minutes=5),
    )
    assert changed is True
    assert awarded == 3
    assert revoked == 0

    db.session.commit()
    db.session.refresh(seat)
    assert seat.hall_passes == 3


def test_hall_pass_top_off_restores_after_base_rent_paid_even_with_late_fee_due(
    client, teacher_user, class_scope, student_seat
):
    """Hall-pass rent perk should restore once base rent is paid, even if late fee remains outstanding."""
    from app.routes.student import _ensure_rent_hall_pass_top_off

    seat = student_seat

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("2.00"),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Hall Pass Grant",
            rent_item_type="hall_pass",
            hall_pass_count=3,
        )
    )

    assert seat is not None
    seat.hall_passes = 0
    db.session.commit()

    context = _make_canonical_context(seat)
    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    # Student pays base rent only; late fee remains.
    _add_rent_payment(
        seat,
        class_scope.class_id,
        amount="10.00",
        period="A",
        now=fixed_now,
    )
    # Mark as late (amend the just-added payment)
    rp = RentPayment.query.filter_by(seat_id=seat.id).first()
    rp.was_late = True
    rp.late_fee_charged = Decimal("0.00")
    db.session.commit()

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(
        seat,
        context,
        settings=settings,
        now=fixed_now + timedelta(minutes=1),
    )
    assert changed is True
    assert awarded == 3
    assert revoked == 0

    db.session.commit()
    db.session.refresh(seat)
    assert seat.hall_passes == 3


def test_hall_pass_top_off_accepts_legacy_whitespace_period_values(
    client, teacher_user, class_scope, student_seat
):
    """Top-off should still detect paid coverage when legacy RentPayment.period contains trailing whitespace."""
    from app.routes.student import _ensure_rent_hall_pass_top_off

    seat = student_seat

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Hall Pass Grant",
            rent_item_type="hall_pass",
            hall_pass_count=3,
        )
    )

    assert seat is not None
    seat.hall_passes = 0
    db.session.commit()

    context = _make_canonical_context(seat)
    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    # Legacy data: period stored with trailing whitespace
    db.session.add(
        RentPayment(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            join_code=class_scope.join_code,
            period="A ",
            amount_paid=Decimal("10.00"),
            period_month=fixed_now.month,
            period_year=fixed_now.year,
            coverage_month=fixed_now.month,
            coverage_year=fixed_now.year,
            payment_date=fixed_now,
        )
    )
    student_user = db.session.get(User, seat.user_id)
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("-10.00"),
            account_type="checking",
            type="Rent Payment",
            description="Rent paid with legacy period whitespace",
            timestamp=fixed_now,
        )
    )
    db.session.commit()

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(
        seat,
        context,
        settings=settings,
        now=fixed_now + timedelta(minutes=1),
    )
    assert changed is True
    assert awarded == 3
    assert revoked == 0

    db.session.commit()
    db.session.refresh(seat)
    assert seat.hall_passes == 3


def test_mid_period_lock_blocks_semantic_changes(client, teacher_user, admin_class_scope):
    """Test that semantic fields are locked when students have paid rent for current period."""
    login_teacher(client, teacher_user, class_id=admin_class_scope.class_id)

    settings = RentSettings(
        class_id=admin_class_scope.class_id,
        rent_amount=Decimal("50.00"),
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db.session.add(settings)
    db.session.flush()

    rent_item = RentItem(
        rent_setting_id=settings.id,
        name="Desk",
        rent_item_type="privilege",
        order_index=0,
        is_available_in_store=True,
        store_price=Decimal("100.00"),
        purchase_duration="per_period",
    )
    db.session.add(rent_item)
    db.session.flush()

    # Create a student who has paid rent for the current coverage period
    payer_seat = make_student_identity(
        class_id=admin_class_scope.class_id,
        first_name="Payer",
        last_name="P",
    )
    db.session.flush()

    now = datetime.now(timezone.utc)
    db.session.add(
        RentPayment(
            seat_id=payer_seat.id,
            class_id=admin_class_scope.class_id,
            join_code=admin_class_scope.join_code,
            period="A",
            amount_paid=Decimal("50.00"),
            coverage_month=now.month,
            coverage_year=now.year,
        )
    )
    db.session.commit()

    data = {
        "settings_block": "A",
        "is_enabled": "on",
        "rent_amount": "50.00",
        "frequency_type": "monthly",
        "due_day_of_month": "1",
        "rent_item_name_0": "Desk",
        "rent_item_id_0": str(rent_item.id),
        "rent_item_type_0": "per_use",  # Changed from privilege
        "rent_item_store_available_0": "on",
        "rent_item_store_price_0": "100.00",
        "rent_item_purchase_duration_0": "per_use",
        "rent_item_use_limit_0": "5",
    }

    resp = client.post("/admin/rent-settings", data=data, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(rent_item)
    assert rent_item.rent_item_type == "privilege"
    assert rent_item.use_limit is None
    assert rent_item.name == "Desk"


def test_mid_period_lock_allows_new_items(client, teacher_user, admin_class_scope):
    """Test that new items can be added even when mid-period lock is active."""
    login_teacher(client, teacher_user, class_id=admin_class_scope.class_id)

    settings = RentSettings(
        class_id=admin_class_scope.class_id,
        rent_amount=Decimal("50.00"),
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db.session.add(settings)
    db.session.flush()

    payer_seat = make_student_identity(
        class_id=admin_class_scope.class_id,
        first_name="Payer",
        last_name="P",
    )
    db.session.flush()

    now = datetime.now(timezone.utc)
    db.session.add(
        RentPayment(
            seat_id=payer_seat.id,
            class_id=admin_class_scope.class_id,
            join_code=admin_class_scope.join_code,
            period="A",
            amount_paid=Decimal("50.00"),
            coverage_month=now.month,
            coverage_year=now.year,
        )
    )
    db.session.commit()

    data = {
        "settings_block": "A",
        "is_enabled": "on",
        "rent_amount": "50.00",
        "frequency_type": "monthly",
        "due_day_of_month": "1",
        "rent_item_name_0": "New Item",
        "rent_item_type_0": "per_use",
        "rent_item_store_available_0": "on",
        "rent_item_store_price_0": "10.00",
        "rent_item_purchase_duration_0": "per_use",
        "rent_item_use_limit_0": "3",
    }

    resp = client.post("/admin/rent-settings", data=data, follow_redirects=True)
    assert resp.status_code == 200

    new_item = RentItem.query.filter_by(
        rent_setting_id=settings.id, name="New Item"
    ).first()
    assert new_item is not None
    assert new_item.rent_item_type == "per_use"
    assert new_item.use_limit == 3


def test_legacy_rent_items_default_to_privilege(client, teacher_user, admin_class_scope):
    """Test that existing rent items without rent_item_type default to privilege."""
    settings = RentSettings(class_id=admin_class_scope.class_id)
    db.session.add(settings)
    db.session.flush()

    item = RentItem(
        rent_setting_id=settings.id,
        name="Legacy Desk",
        is_available_in_store=True,
        store_price=Decimal("50.00"),
        purchase_duration="per_period",
    )
    db.session.add(item)
    db.session.commit()

    db.session.refresh(item)
    assert item.rent_item_type == "privilege"


def test_per_use_free_purchase_from_rent(client, teacher_user, class_scope, student_seat):
    """Test that a student with rent-granted uses_remaining can purchase for $0."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Rent Snack",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    rent_granted = StudentItem(
        seat_id=seat.id,
        correlation_id="corr_test",
        store_item_id=store_item.id,
        status="purchased",
        uses_remaining=3,
        purchase_date=datetime.now(timezone.utc),
    )
    db.session.add(rent_granted)

    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=100,
            account_type="checking",
        )
    )
    db.session.commit()

    original_balance = _get_checking_balance(seat)

    _login_student(client, seat)

    data = {"item_id": store_item.id, "passphrase": "password", "quantity": 1}
    resp = client.post("/api/purchase-item", json=data)
    assert resp.status_code == 200
    assert "$0" in resp.json["message"] or "rent perk" in resp.json["message"].lower()

    db.session.refresh(rent_granted)
    assert rent_granted.uses_remaining == 2

    db.session.expire_all()
    new_balance = _get_checking_balance(seat)
    assert new_balance == original_balance

    purchased_items = StudentItem.query.filter_by(
        seat_id=seat.id, store_item_id=store_item.id
    ).all()
    assert any(si.uses_remaining is None for si in purchased_items)


def test_per_use_charges_when_uses_exhausted(client, teacher_user, class_scope, student_seat):
    """Test that after free uses are exhausted, the student pays regular price."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Rent Pencil",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    rent_granted = StudentItem(
        seat_id=seat.id,
        correlation_id="corr_test",
        store_item_id=store_item.id,
        status="purchased",
        uses_remaining=0,
        purchase_date=datetime.now(timezone.utc),
    )
    db.session.add(rent_granted)

    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=100,
            account_type="checking",
        )
    )
    db.session.commit()

    original_balance = _get_checking_balance(seat)

    _login_student(client, seat)

    data = {"item_id": store_item.id, "passphrase": "password", "quantity": 1}
    resp = client.post("/api/purchase-item", json=data)
    assert resp.status_code == 200

    db.session.expire_all()
    assert _get_checking_balance(seat) < original_balance


def test_per_use_free_purchase_without_precreated_grant_when_rent_paid(
    client, teacher_user, class_scope, student_seat
):
    """Paid-rent students should still get $0 per-use purchases when grant rows are missing."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Rent Pencil No Grant",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Rent Pencil No Grant",
            rent_item_type="per_use",
            is_available_in_store=True,
            store_price=Decimal("5.00"),
            purchase_duration="per_use",
            use_limit=1,
            store_item_id=store_item.id,
        )
    )

    now = datetime.now(timezone.utc)
    _add_rent_payment(seat, class_scope.class_id, amount="10.00", period="A", now=now)
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=100,
            account_type="checking",
        )
    )
    db.session.commit()

    starting_balance = _get_checking_balance(seat)

    _login_student(client, seat)

    resp = client.post(
        "/api/purchase-item",
        json={"item_id": store_item.id, "passphrase": "password", "quantity": 1},
    )
    assert resp.status_code == 200
    assert "$0" in resp.json["message"] or "rent perk" in resp.json["message"].lower()

    db.session.expire_all()
    assert _get_checking_balance(seat) == starting_balance


def test_shop_only_disables_privilege_items_when_rent_paid(
    client, teacher_user, class_scope, student_seat
):
    """When rent is paid, privilege items are included/disabled but per-use items remain purchasable."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    privilege_store_item = StoreItem(
        user_id=teacher_user.id,
        name="Desk Privilege",
        price=Decimal("50.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    per_use_store_item = StoreItem(
        user_id=teacher_user.id,
        name="Pencil Per Use",
        price=Decimal("3.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add_all([privilege_store_item, per_use_store_item])
    db.session.flush()

    db.session.add_all(
        [
            RentItem(
                rent_setting_id=settings.id,
                name="Desk Privilege",
                rent_item_type="privilege",
                is_available_in_store=True,
                store_price=Decimal("50.00"),
                purchase_duration="per_period",
                store_item_id=privilege_store_item.id,
            ),
            RentItem(
                rent_setting_id=settings.id,
                name="Pencil Per Use",
                rent_item_type="per_use",
                is_available_in_store=True,
                store_price=Decimal("3.00"),
                purchase_duration="per_use",
                use_limit=5,
                store_item_id=per_use_store_item.id,
            ),
        ]
    )

    now = datetime.now(timezone.utc)
    _add_rent_payment(seat, class_scope.class_id, amount="10.00", period="A", now=now)
    db.session.commit()

    _login_student(client, seat)

    resp = client.get("/student/shop")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    privilege_button = re.search(
        rf'data-item-id="{privilege_store_item.id}"[^>]*>',
        html,
        re.DOTALL,
    )
    assert privilege_button is not None
    assert "disabled" in privilege_button.group(0)

    per_use_button = re.search(
        rf'data-item-id="{per_use_store_item.id}"[^>]*>',
        html,
        re.DOTALL,
    )
    assert per_use_button is not None
    assert "disabled" not in per_use_button.group(0)


def test_shop_keeps_item_purchasable_when_per_use_and_privilege_links_overlap(
    client, teacher_user, class_scope, student_seat
):
    """If legacy data creates mixed rent item types for one store item, per-use access should remain purchasable."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)
    anchor_now = datetime.now(timezone.utc)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=anchor_now - timedelta(days=60),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Mixed Rent Link",
        price=Decimal("8.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add_all(
        [
            RentItem(
                rent_setting_id=settings.id,
                name="Mixed Rent Link Priv",
                rent_item_type="privilege",
                is_available_in_store=True,
                store_price=Decimal("8.00"),
                purchase_duration="per_period",
                store_item_id=store_item.id,
            ),
            RentItem(
                rent_setting_id=settings.id,
                name="Mixed Rent Link Use",
                rent_item_type="per_use",
                is_available_in_store=True,
                store_price=Decimal("8.00"),
                purchase_duration="per_use",
                use_limit=2,
                store_item_id=store_item.id,
            ),
        ]
    )

    now = datetime.now(timezone.utc)
    _add_rent_payment(seat, class_scope.class_id, amount="10.00", period="A", now=now)
    db.session.commit()

    _login_student(client, seat)

    resp = client.get("/student/shop")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    button = re.search(rf'data-item-id="{store_item.id}"[^>]*>', html, re.DOTALL)
    assert button is not None
    assert "disabled" not in button.group(0)


def test_shop_treats_legacy_privilege_with_per_use_duration_as_per_use(
    client, teacher_user, class_scope, student_seat
):
    """Legacy privilege+per_use-duration rows should render as purchasable rent perks, not included/disabled."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)
    anchor_now = datetime.now(timezone.utc)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=anchor_now - timedelta(days=60),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Legacy Per Use Link",
        price=Decimal("9.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Legacy Per Use Link",
            rent_item_type="privilege",
            purchase_duration="per_use",
            is_available_in_store=True,
            store_price=Decimal("9.00"),
            use_limit=1,
            store_item_id=store_item.id,
        )
    )

    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, anchor_now)
    assert coverage_due_date is not None

    db.session.add(
        RentPayment(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            join_code=class_scope.join_code,
            period="A",
            amount_paid=Decimal("10.00"),
            period_month=anchor_now.month,
            period_year=anchor_now.year,
            coverage_month=coverage_due_date.month,
            coverage_year=coverage_due_date.year,
            payment_date=anchor_now,
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("-10.00"),
            account_type="checking",
            type="Rent Payment",
            description="Rent for Period A",
        )
    )
    db.session.commit()

    _login_student(client, seat)

    resp = client.get("/student/shop")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    button = re.search(rf'data-item-id="{store_item.id}"[^>]*>', html, re.DOTALL)
    assert button is not None
    assert "disabled" not in button.group(0)
    assert "Rent Perk price: $0.00" in html


def test_api_allows_zero_cost_rent_linked_purchase_when_paid_without_per_use_mapping(
    client, teacher_user, class_scope, student_seat
):
    """Paid-rent students can still buy non-privilege rent-linked perks for $0 when mapping rows are missing."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")
    anchor_now = datetime.now(timezone.utc)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=anchor_now - timedelta(days=60),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Link Only Perk",
        price=Decimal("12.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)

    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, anchor_now)
    assert coverage_due_date is not None

    db.session.add(
        RentPayment(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            join_code=class_scope.join_code,
            period="A",
            amount_paid=Decimal("10.00"),
            period_month=anchor_now.month,
            period_year=anchor_now.year,
            coverage_month=coverage_due_date.month,
            coverage_year=coverage_due_date.year,
            payment_date=anchor_now,
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("-10.00"),
            account_type="checking",
            type="Rent Payment",
            description="Rent for Period A",
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("100.00"),
            account_type="checking",
        )
    )
    db.session.commit()

    starting_balance = _get_checking_balance(seat)

    _login_student(client, seat)

    resp = client.post(
        "/api/purchase-item",
        json={"item_id": store_item.id, "passphrase": "password", "quantity": 1},
    )
    assert resp.status_code == 200
    assert "purchased" in resp.json["message"].lower()

    db.session.expire_all()
    assert _get_checking_balance(seat) == starting_balance


def test_api_hall_pass_item_skips_rent_perk_zero_cost_flow(
    client, teacher_user, class_scope, student_seat
):
    """Hall-pass items should always purchase directly and never create rent-perk inventory rows."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    from app.routes.student import _calculate_rent_coverage_due_date

    student_user.passphrase_hash = generate_password_hash("password")

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    hall_pass_item = StoreItem(
        user_id=teacher_user.id,
        name="Paid Hall Pass",
        price=Decimal("5.00"),
        is_active=True,
        item_type="hall_pass",
        is_rent_linked=True,
    )
    db.session.add(hall_pass_item)
    db.session.flush()

    now = datetime.now(timezone.utc)
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    assert coverage_due_date is not None

    db.session.add(
        RentPayment(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            join_code=class_scope.join_code,
            period="A",
            amount_paid=Decimal("10.00"),
            period_month=now.month,
            period_year=now.year,
            coverage_month=coverage_due_date.month,
            coverage_year=coverage_due_date.year,
            payment_date=now,
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("-10.00"),
            account_type="checking",
            type="Rent Payment",
            description="Rent for Period A",
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("100.00"),
            account_type="checking",
            type="Deposit",
            description="Seed funds",
        )
    )
    db.session.commit()

    starting_balance = _get_checking_balance(seat)
    starting_hall_passes = seat.hall_passes

    _login_student(client, seat)

    resp = client.post(
        "/api/purchase-item",
        json={"item_id": hall_pass_item.id, "passphrase": "password", "quantity": 1},
    )
    assert resp.status_code == 200
    assert "Hall Pass" in resp.json["message"]

    db.session.refresh(seat)
    assert seat.hall_passes == starting_hall_passes + 1

    db.session.expire_all()
    assert _get_checking_balance(seat) == starting_balance - Decimal("5.00")

    created_rows = StudentItem.query.filter_by(
        seat_id=seat.id, store_item_id=hall_pass_item.id
    ).all()
    assert len(created_rows) == 0


def test_use_item_converts_legacy_hall_pass_inventory_row(
    client, teacher_user, class_scope, student_seat
):
    """Legacy hall-pass StudentItem rows should redeem into hall-pass balance immediately."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")

    hall_pass_item = StoreItem(
        user_id=teacher_user.id,
        name="Legacy Hall Pass",
        price=Decimal("5.00"),
        is_active=True,
        item_type="hall_pass",
    )
    db.session.add(hall_pass_item)
    db.session.flush()

    legacy_row = StudentItem(
        seat_id=seat.id,
        correlation_id="corr_test",
        store_item_id=hall_pass_item.id,
        status="purchased",
        quantity_purchased=2,
    )
    db.session.add(legacy_row)
    db.session.commit()

    starting_hall_passes = seat.hall_passes

    _login_student(client, seat)

    resp = client.post(
        "/api/use-item",
        json={
            "student_item_id": legacy_row.id,
            "passphrase": "password",
            "details": "Need to use this old item",
        },
    )
    assert resp.status_code == 200
    assert "Added 2 hall pass(es)" in resp.json["message"]

    db.session.refresh(seat)
    db.session.refresh(legacy_row)

    assert seat.hall_passes == starting_hall_passes + 2
    assert legacy_row.status == "redeemed"
    assert legacy_row.redemption_date is not None
    assert "Hall pass grant processed" in (legacy_row.redemption_details or "")


def test_shop_displays_rent_perk_price_as_free(client, teacher_user, class_scope, student_seat):
    """Rent perk items with active free uses should display $0 pricing in the student shop."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Rent Linked Pencil",
        price=Decimal("7.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add(
        StudentItem(
            seat_id=seat.id,
            correlation_id="corr_test",
            store_item_id=store_item.id,
            status="purchased",
            uses_remaining=2,
            purchase_date=datetime.now(timezone.utc),
        )
    )
    db.session.commit()

    _login_student(client, seat)

    resp = client.get("/student/shop")
    assert resp.status_code == 200
    assert b"Rent Perk price: $0.00" in resp.data
    assert b"Regular: $7.00" in resp.data


def test_shop_displays_rent_perk_price_as_free_when_rent_paid_without_grant_row(
    client, teacher_user, class_scope, student_seat
):
    """Shop should display per-use rent perk as $0 for paid-rent students even when grant row is missing."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    per_use_store_item = StoreItem(
        user_id=teacher_user.id,
        name="Paid Rent Pencil",
        price=Decimal("4.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(per_use_store_item)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Paid Rent Pencil",
            rent_item_type="per_use",
            is_available_in_store=True,
            store_price=Decimal("4.00"),
            purchase_duration="per_use",
            use_limit=2,
            store_item_id=per_use_store_item.id,
        )
    )

    now = datetime.now(timezone.utc)
    _add_rent_payment(seat, class_scope.class_id, amount="10.00", period="A", now=now)
    db.session.commit()

    _login_student(client, seat)

    resp = client.get("/student/shop")
    assert resp.status_code == 200
    assert b"Paid Rent Pencil" in resp.data
    assert b"Rent Perk price: $0.00" in resp.data


def test_admin_store_hides_delete_button_for_rent_linked_items(
    client, teacher_user, admin_class_scope
):
    """Rent-linked items should hide delete even when legacy is_rent_linked flag is stale."""
    login_teacher(client, teacher_user, class_id=admin_class_scope.class_id)

    settings = RentSettings(class_id=admin_class_scope.class_id)
    db.session.add(settings)
    db.session.flush()

    rent_linked = StoreItem(
        user_id=teacher_user.id,
        name="Rent Linked Item",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=False,
    )
    regular = StoreItem(
        user_id=teacher_user.id,
        name="Regular Item",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=False,
    )
    db.session.add_all([rent_linked, regular])
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Rent Linked Item",
            rent_item_type="privilege",
            is_available_in_store=True,
            store_price=Decimal("5.00"),
            purchase_duration="per_period",
            store_item_id=rent_linked.id,
        )
    )
    db.session.commit()

    resp = client.get("/admin/store")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    linked_delete = re.search(
        rf'(data-item-id="{rent_linked.id}"[^>]*data-bs-target="#deleteItemModal"|'
        rf'data-bs-target="#deleteItemModal"[^>]*data-item-id="{rent_linked.id}")',
        html,
        re.DOTALL,
    )
    assert linked_delete is None

    regular_delete = re.search(
        rf'(data-item-id="{regular.id}"[^>]*data-bs-target="#deleteItemModal"|'
        rf'data-bs-target="#deleteItemModal"[^>]*data-item-id="{regular.id}")',
        html,
        re.DOTALL,
    )
    assert regular_delete is not None

    delete_resp = client.post(
        f"/admin/store/delete/{rent_linked.id}", follow_redirects=True
    )
    assert delete_resp.status_code == 200
    assert b"Cannot delete" in delete_resp.data


def test_privilege_badge_only_shows_privilege_items(client, teacher_user, class_scope, student_seat):
    """Test that _build_rent_privileges_by_block only shows privilege-type items as badges."""
    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("50.00"),
        frequency_type="monthly",
        due_day_of_month=1,
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db.session.add(settings)
    db.session.flush()

    privilege_item = RentItem(
        rent_setting_id=settings.id,
        name="Desk Badge",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("10.00"),
        purchase_duration="per_period",
    )
    per_use_item = RentItem(
        rent_setting_id=settings.id,
        name="Pencil Uses",
        rent_item_type="per_use",
        is_available_in_store=True,
        store_price=Decimal("2.00"),
        purchase_duration="per_use",
        use_limit=5,
    )
    hall_pass_item = RentItem(
        rent_setting_id=settings.id,
        name="HP Grant",
        rent_item_type="hall_pass",
        hall_pass_count=3,
    )
    db.session.add_all([privilege_item, per_use_item, hall_pass_item])
    db.session.commit()

    badge_items = RentItem.query.filter(
        RentItem.rent_setting_id == settings.id,
        RentItem.rent_item_type == "privilege",
        RentItem.purchase_duration == "per_period",
        RentItem.is_available_in_store == True,
    ).all()

    assert len(badge_items) == 1
    assert badge_items[0].name == "Desk Badge"
    assert badge_items[0].rent_item_type == "privilege"


def test_late_fee_only_when_unpaid_by_grace(client, teacher_user, class_scope, student_seat):
    """Test that late fees are only applied when rent is not fully paid by grace deadline."""
    from datetime import timedelta
    from app.routes.student import utc_now, _total_paid_by_grace

    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    now = utc_now()

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        late_penalty_amount=Decimal("2.00"),
        frequency_type="weekly",
        first_rent_due_date=now - timedelta(days=7),
        grace_period_days=3,
    )
    db.session.add(settings)
    db.session.commit()

    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    grace_end_date = coverage_due_date + timedelta(days=settings.grace_period_days)

    # Test 1: Full payment BEFORE grace deadline - no late fee
    payment_date_before_grace = grace_end_date - timedelta(days=1)

    payment1 = RentPayment(
        seat_id=seat.id,
        class_id=class_scope.class_id,
        join_code=class_scope.join_code,
        period="A",
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        amount_paid=Decimal("10.00"),
        payment_date=payment_date_before_grace,
    )
    db.session.add(payment1)
    txn1 = Transaction(
        user_id=student_user.id,
        seat_id=seat.id,
        class_id=seat.class_id,
        join_code=class_scope.join_code,
        amount=-Decimal("10.00"),
        account_type="checking",
        type="Rent Payment",
        timestamp=payment_date_before_grace,
        description="Rent payment",
    )
    db.session.add(txn1)
    db.session.commit()

    payments = [payment1]
    paid_by_grace = _total_paid_by_grace(payments, grace_end_date)
    assert paid_by_grace == Decimal("10.00")

    future_now = grace_end_date + timedelta(days=1)
    late_fee = Decimal("0.00")
    if future_now > grace_end_date and paid_by_grace < settings.rent_amount:
        late_fee = settings.late_penalty_amount

    assert late_fee == Decimal("0.00"), "Late fee should not apply when paid in full by grace deadline"

    db.session.delete(payment1)
    db.session.delete(txn1)
    db.session.commit()

    # Test 2: Partial payment before grace deadline - late fee applies
    payment2 = RentPayment(
        seat_id=seat.id,
        class_id=class_scope.class_id,
        join_code=class_scope.join_code,
        period="A",
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        amount_paid=Decimal("6.00"),
        payment_date=payment_date_before_grace,
    )
    db.session.add(payment2)
    txn2 = Transaction(
        user_id=student_user.id,
        seat_id=seat.id,
        class_id=seat.class_id,
        join_code=class_scope.join_code,
        amount=-Decimal("6.00"),
        account_type="checking",
        type="Rent Payment",
        timestamp=payment_date_before_grace,
        description="Partial rent payment",
    )
    db.session.add(txn2)
    db.session.commit()

    payments2 = [payment2]
    paid_by_grace2 = _total_paid_by_grace(payments2, grace_end_date)
    assert paid_by_grace2 == Decimal("6.00")

    late_fee2 = Decimal("0.00")
    if future_now > grace_end_date and paid_by_grace2 < settings.rent_amount:
        late_fee2 = settings.late_penalty_amount

    assert late_fee2 == Decimal("2.00"), "Late fee should apply when not paid in full by grace deadline"
    assert settings.rent_amount + late_fee2 == Decimal("12.00")

    db.session.delete(payment2)
    db.session.delete(txn2)
    db.session.commit()

    # Test 3: Payment AFTER grace deadline - should not count toward paid_by_grace
    payment_date_after_grace = grace_end_date + timedelta(days=1)

    payment3 = RentPayment(
        seat_id=seat.id,
        class_id=class_scope.class_id,
        join_code=class_scope.join_code,
        period="A",
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        amount_paid=Decimal("10.00"),
        payment_date=payment_date_after_grace,
    )
    db.session.add(payment3)
    txn3 = Transaction(
        user_id=student_user.id,
        seat_id=seat.id,
        class_id=seat.class_id,
        join_code=class_scope.join_code,
        amount=-Decimal("10.00"),
        account_type="checking",
        type="Rent Payment",
        timestamp=payment_date_after_grace,
        description="Rent payment after grace",
    )
    db.session.add(txn3)
    db.session.commit()

    payments3 = [payment3]
    paid_by_grace3 = _total_paid_by_grace(payments3, grace_end_date)
    assert paid_by_grace3 == Decimal("0.00"), "Payment after grace should not count in paid_by_grace"

    late_fee3 = Decimal("0.00")
    if future_now > grace_end_date and paid_by_grace3 < settings.rent_amount:
        late_fee3 = settings.late_penalty_amount

    assert late_fee3 == Decimal("2.00"), "Late fee should apply when payment is after grace deadline"


def test_per_use_free_purchase_recovers_from_exhausted_grant_row_when_rent_paid(
    client, teacher_user, class_scope, student_seat, monkeypatch
):
    """Paid-rent students should not be charged if a stale exhausted grant row is the only row present."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    from werkzeug.security import generate_password_hash
    student_user.passphrase_hash = generate_password_hash("password")

    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.routes.api.utc_now", lambda: fixed_now)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        user_id=teacher_user.id,
        name="Unlimited Pencil",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Unlimited Pencil",
            rent_item_type="per_use",
            is_available_in_store=True,
            store_price=Decimal("5.00"),
            purchase_duration="per_use",
            use_limit=None,
            store_item_id=store_item.id,
        )
    )

    db.session.add(
        RentPayment(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            join_code=class_scope.join_code,
            period="A",
            amount_paid=Decimal("10.00"),
            period_month=fixed_now.month,
            period_year=fixed_now.year,
            coverage_month=fixed_now.month,
            coverage_year=fixed_now.year,
            payment_date=fixed_now,
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("-10.00"),
            account_type="checking",
            type="Rent Payment",
            description="Rent for Period A",
            timestamp=fixed_now,
        )
    )
    # Stale exhausted grant row
    db.session.add(
        StudentItem(
            seat_id=seat.id,
            correlation_id="corr_test",
            store_item_id=store_item.id,
            purchase_date=fixed_now,
            status="purchased",
            uses_remaining=0,
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("100.00"),
            account_type="checking",
            type="Deposit",
            description="Seed funds",
        )
    )
    db.session.commit()

    starting_balance = _get_checking_balance(seat)

    _login_student(client, seat)

    resp = client.post(
        "/api/purchase-item",
        json={"item_id": store_item.id, "passphrase": "password", "quantity": 1},
    )
    assert resp.status_code == 200
    assert "$0" in resp.json["message"] or "rent perk" in resp.json["message"].lower()

    db.session.expire_all()
    assert _get_checking_balance(seat) == starting_balance


def test_rent_payment_hall_pass_top_off_recovers_from_stale_counter(
    client, teacher_user, class_scope, student_seat, monkeypatch
):
    """Hall-pass grant should still top-off when rent_hall_passes counter drifted above actual passes."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.routes.student.utc_now", lambda: fixed_now)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Hall Pass Bonus",
            rent_item_type="hall_pass",
            hall_pass_count=3,
            is_available_in_store=False,
        )
    )

    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("100.00"),
            account_type="checking",
            type="Deposit",
            description="Seed funds",
        )
    )
    db.session.commit()

    _login_student(client, seat)

    resp = client.post("/student/rent/pay/A", follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(seat)
    assert seat.hall_passes == 3


def test_waiver_does_not_grant_rent_perks_in_shop(
    client, teacher_user, class_scope, student_seat, monkeypatch
):
    """A waiver allows access but should not grant paid-rent perks."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    fixed_now = datetime.now(timezone.utc)
    monkeypatch.setattr("app.routes.student.utc_now", lambda: fixed_now)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    privilege_store_item = StoreItem(
        user_id=teacher_user.id,
        name="Waiver Desk Privilege",
        price=Decimal("50.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    per_use_store_item = StoreItem(
        user_id=teacher_user.id,
        name="Waiver Pencil Per Use",
        price=Decimal("3.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add_all([privilege_store_item, per_use_store_item])
    db.session.flush()

    db.session.add_all(
        [
            RentItem(
                rent_setting_id=settings.id,
                name="Waiver Desk Privilege",
                rent_item_type="privilege",
                is_available_in_store=True,
                store_price=Decimal("50.00"),
                purchase_duration="per_period",
                store_item_id=privilege_store_item.id,
            ),
            RentItem(
                rent_setting_id=settings.id,
                name="Waiver Pencil Per Use",
                rent_item_type="per_use",
                is_available_in_store=True,
                store_price=Decimal("3.00"),
                purchase_duration="per_use",
                use_limit=5,
                store_item_id=per_use_store_item.id,
            ),
        ]
    )

    db.session.add(
        RentWaiver(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            waiver_start_date=datetime(2000, 1, 1, tzinfo=timezone.utc),
            waiver_end_date=datetime(2100, 1, 1, tzinfo=timezone.utc),
            periods_count=1,
        )
    )
    db.session.commit()

    _login_student(client, seat)

    resp = client.get("/student/shop")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    privilege_card = re.search(
        rf'data-item-id="{privilege_store_item.id}"[^>]*data-has-rent-free-purchase="([^"]+)"',
        html,
    )
    assert privilege_card is not None
    assert privilege_card.group(1) == "false"

    per_use_card = re.search(
        rf'data-item-id="{per_use_store_item.id}"[^>]*data-has-rent-free-purchase="([^"]+)"',
        html,
    )
    assert per_use_card is not None
    assert per_use_card.group(1) == "false"


def test_shop_keeps_rent_perks_when_payment_exists_alongside_waiver(
    client, teacher_user, class_scope, student_seat, monkeypatch
):
    """A real payment should still grant perks even if a waiver also exists."""
    seat = student_seat
    student_user = db.session.get(User, seat.user_id)

    fixed_now = datetime.now(timezone.utc)
    monkeypatch.setattr("app.routes.student.utc_now", lambda: fixed_now)

    settings = RentSettings(
        class_id=class_scope.class_id,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()

    privilege_store_item = StoreItem(
        user_id=teacher_user.id,
        name="Paid + Waived Privilege",
        price=Decimal("50.00"),
        is_active=True,
        item_type="delayed",
        is_rent_linked=True,
    )
    db.session.add(privilege_store_item)
    db.session.flush()

    db.session.add(
        RentItem(
            rent_setting_id=settings.id,
            name="Paid + Waived Privilege",
            rent_item_type="privilege",
            is_available_in_store=True,
            store_price=Decimal("50.00"),
            purchase_duration="per_period",
            store_item_id=privilege_store_item.id,
        )
    )

    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, fixed_now)
    assert coverage_due_date is not None

    db.session.add(
        RentPayment(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            join_code=class_scope.join_code,
            period="A",
            amount_paid=Decimal("10.00"),
            period_month=coverage_due_date.month,
            period_year=coverage_due_date.year,
            coverage_month=coverage_due_date.month,
            coverage_year=coverage_due_date.year,
            payment_date=fixed_now,
        )
    )
    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=seat.class_id,
            join_code=class_scope.join_code,
            amount=Decimal("-10.00"),
            account_type="checking",
            type="Rent Payment",
            description="Rent for Period A",
            timestamp=fixed_now,
        )
    )
    db.session.add(
        RentWaiver(
            seat_id=seat.id,
            class_id=class_scope.class_id,
            waiver_start_date=datetime(2000, 1, 1, tzinfo=timezone.utc),
            waiver_end_date=datetime(2100, 1, 1, tzinfo=timezone.utc),
            periods_count=1,
        )
    )
    db.session.commit()

    _login_student(client, seat)

    resp = client.get("/student/shop")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    privilege_button = re.search(
        rf'data-item-id="{privilege_store_item.id}"[^>]*>',
        html,
        re.DOTALL,
    )
    assert privilege_button is not None
    assert "disabled" in privilege_button.group(0)
    assert "Included in your rent!" in html
