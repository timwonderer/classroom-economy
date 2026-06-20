from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.models import RentItem, RentPolicyVersion, Seat, Student, StudentItem
from app.utils.time import utc_now


def get_rent_hall_pass_grant_total_from_version(version: RentPolicyVersion) -> int:
    """Sum hall_pass_count from the frozen manifest on a policy version."""
    total = 0
    for item in (version.frozen_items or []):
        if item.get('rent_item_type') == 'hall_pass' and item.get('hall_pass_count'):
            total += item['hall_pass_count']
    return total


def get_frozen_privilege_items(version: RentPolicyVersion) -> list[dict]:
    """Return privilege-type items from the frozen manifest that are store-linked.

    These are the per-period entitlements a student gets when rent is paid.
    Privileges end at the cycle boundary (next payment required).
    """
    return [
        item for item in (version.frozen_items or [])
        if item.get('rent_item_type') == 'privilege'
        and item.get('is_available_in_store')
        and item.get('purchase_duration') != 'per_use'  # exclude legacy compat rows
    ]


def get_frozen_store_linked_items(version: RentPolicyVersion) -> list[dict]:
    """Return all store-linked items from the frozen manifest (excludes hall passes).

    Used by the student store display to mark items as rent-included or rent-per-use.
    """
    return [
        item for item in (version.frozen_items or [])
        if item.get('is_available_in_store')
        and item.get('store_item_id')
        and item.get('rent_item_type') != 'hall_pass'
    ]


def grant_rent_per_use_items_from_version(
    *, seat, version: RentPolicyVersion, calculate_due_dates_fn, settings=None,
) -> int:
    """Store-owned mutation for rent-derived per-use entitlements.

    Reads from the immutable frozen_items on the policy version, not from
    live RentItem rows.  ``settings`` is only used for ``first_rent_due_date``
    when computing expiry; if omitted the expiry is left open.
    """
    per_use_items = [
        item for item in (version.frozen_items or [])
        if item.get('rent_item_type') == 'per_use' and item.get('store_item_id')
    ]

    granted = 0
    now = utc_now()

    for pu_item in per_use_items:
        store_item_id = pu_item['store_item_id']
        use_limit = pu_item.get('use_limit')

        existing = StudentItem.query.filter(
            StudentItem.seat_id == seat.id,
            StudentItem.store_item_id == store_item_id,
            db.or_(StudentItem.uses_remaining > 0, StudentItem.uses_remaining == -1),
            db.or_(StudentItem.expiry_date.is_(None), StudentItem.expiry_date > now),
        ).first()

        if existing:
            existing.uses_remaining = use_limit if use_limit else -1
            continue

        expiry_date = None
        if settings and getattr(settings, 'first_rent_due_date', None):
            _, next_due = calculate_due_dates_fn(settings, now)
            if next_due:
                expiry_date = next_due

        db.session.add(StudentItem(
            seat_id=seat.id,
            class_id=seat.class_id,
            store_item_id=store_item_id,
            purchase_date=now,
            expiry_date=expiry_date,
            status='purchased',
            is_from_bundle=False,
            quantity_purchased=1,
            uses_remaining=use_limit if use_limit else -1,
        ))
        granted += 1

    return granted


# --- Legacy functions (to be removed once all callers migrate to version-based) ---


def get_rent_hall_pass_grant_total(rent_setting_id: int) -> int:
    total = db.session.query(
        db.func.coalesce(db.func.sum(RentItem.hall_pass_count), 0)
    ).filter(
        RentItem.rent_setting_id == rent_setting_id,
        RentItem.rent_item_type == 'hall_pass',
    ).scalar() or 0
    return int(total)


def grant_rent_per_use_items(*, seat, settings, calculate_due_dates_fn) -> int:
    """Store-owned mutation for rent-derived per-use entitlements."""
    per_use_items = RentItem.query.filter_by(
        rent_setting_id=settings.id,
        rent_item_type='per_use',
    ).all()

    granted = 0
    now = utc_now()

    for pu_item in per_use_items:
        if not pu_item.store_item_id:
            continue

        existing = StudentItem.query.filter(
            StudentItem.seat_id == seat.id,
            StudentItem.store_item_id == pu_item.store_item_id,
            db.or_(StudentItem.uses_remaining > 0, StudentItem.uses_remaining == -1),
            db.or_(StudentItem.expiry_date.is_(None), StudentItem.expiry_date > now),
        ).first()

        if existing:
            existing.uses_remaining = pu_item.use_limit if pu_item.use_limit else -1
            continue

        expiry_date = None
        if settings.first_rent_due_date:
            _, next_due = calculate_due_dates_fn(settings, now)
            if next_due:
                expiry_date = next_due

        db.session.add(StudentItem(
            seat_id=seat.id,
            class_id=seat.class_id,
            store_item_id=pu_item.store_item_id,
            purchase_date=now,
            expiry_date=expiry_date,
            status='purchased',
            is_from_bundle=False,
            quantity_purchased=1,
            uses_remaining=pu_item.use_limit if pu_item.use_limit else -1,
        ))
        granted += 1

    return granted


def ensure_active_rent_per_use_grant(
    *,
    seat,
    store_item_id: int,
    use_limit: int | None,
    now=None,
    expiry_date=None,
):
    """Store-owned mutation for ensuring a current rent grant row exists."""
    now = now or utc_now()
    existing = StudentItem.query.filter(
        StudentItem.seat_id == seat.id,
        StudentItem.store_item_id == store_item_id,
        db.or_(StudentItem.uses_remaining > 0, StudentItem.uses_remaining == -1),
        db.or_(StudentItem.expiry_date.is_(None), StudentItem.expiry_date > now),
    ).first()
    if existing:
        return existing

    granted_item = StudentItem(
        seat_id=seat.id,
        class_id=seat.class_id,
        store_item_id=store_item_id,
        purchase_date=now,
        expiry_date=expiry_date,
        status='purchased',
        is_from_bundle=False,
        quantity_purchased=1,
        uses_remaining=use_limit if use_limit else -1,
    )
    db.session.add(granted_item)
    return granted_item


def record_rent_perk_purchase(
    *,
    seat,
    item,
    purchase_tx_id: int,
    active_rent_item,
    now,
):
    """Store-owned mutation for a zero-cost rent-perk purchase."""
    if active_rent_item and active_rent_item.uses_remaining != -1:
        active_rent_item.uses_remaining -= 1

    expiry_date = None
    if item.item_type == 'delayed' and item.auto_expiry_days:
        expiry_date = now + timedelta(days=item.auto_expiry_days)

    student_item = StudentItem(
        seat_id=seat.id,
        class_id=seat.class_id,
        store_item_id=item.id,
        purchase_date=now,
        expiry_date=expiry_date,
        status='purchased',
        purchase_transaction_id=purchase_tx_id,
        is_from_bundle=False,
        quantity_purchased=1,
        uses_remaining=None,
    )
    db.session.add(student_item)
    return student_item


def record_standard_purchase_items(
    *,
    seat,
    student_id: int | None,
    item,
    quantity: int,
    purchase_tx_id: int,
    expiry_date,
    student_item_status: str,
    uses_remaining,
):
    """Store-owned mutation for standard StudentItem issuance."""
    created_item_ids = []

    from app.feats.base import get_correlation_id
    corr_id = get_correlation_id()
    if item.is_bundle and item.bundle_quantity is not None:
        new_student_item = StudentItem(
            seat_id=seat.id,
            student_id=student_id,
            class_id=seat.class_id,
            store_item_id=item.id,
            correlation_id=corr_id,
            purchase_date=utc_now(),
            expiry_date=expiry_date,
            status=student_item_status,
            purchase_transaction_id=purchase_tx_id,
            is_from_bundle=True,
            bundle_remaining=item.bundle_quantity * quantity,
            quantity_purchased=quantity,
            uses_remaining=uses_remaining,
            collective_goal_instance_code=item.collective_goal_instance_code if item.item_type == 'collective' else None,
        )
        db.session.add(new_student_item)
        db.session.flush()
        created_item_ids.append(new_student_item.id)
        return created_item_ids

    for _ in range(quantity):
        new_student_item = StudentItem(
            seat_id=seat.id,
            student_id=student_id,
            class_id=seat.class_id,
            store_item_id=item.id,
            correlation_id=corr_id,
            purchase_date=utc_now(),
            expiry_date=expiry_date,
            status=student_item_status,
            purchase_transaction_id=purchase_tx_id,
            is_from_bundle=False,
            quantity_purchased=1,
            uses_remaining=uses_remaining,
            collective_goal_instance_code=item.collective_goal_instance_code if item.item_type == 'collective' else None,
        )
        db.session.add(new_student_item)
        db.session.flush()
        created_item_ids.append(new_student_item.id)

    return created_item_ids


def decrement_inventory(item, quantity: int) -> None:
    if item.inventory is not None:
        item.inventory -= quantity


def unlock_collective_goal_if_ready(*, item, class_id: str, join_code: str | None = None) -> None:
    """Store-owned mutation for collective-goal unlock state."""
    if not class_id:
        raise ValueError("class_id is required for collective goal unlock")
    class_size = db.session.query(db.func.count(db.func.distinct(Student.id))).join(
        IdentityProfile, IdentityProfile.id == Student.identity_id
    ).join(
        Seat, Seat.id == IdentityProfile.seat_id,
    ).filter(
        Seat.class_id == class_id,
        Seat.claimed_at.isnot(None),
    ).scalar() or 0

    purchased_query = db.session.query(db.func.count(db.func.distinct(StudentItem.student_id))).filter(
        StudentItem.store_item_id == item.id,
        StudentItem.class_id == class_id,
        StudentItem.status.in_(['pending', 'processing', 'purchased', 'redeemed', 'completed']),
        StudentItem.collective_goal_instance_code == item.collective_goal_instance_code,
    )
    if join_code:
        purchased_query = purchased_query.filter(StudentItem.join_code == join_code)
    purchased_students_count = purchased_query.scalar() or 0

    target = int(item.collective_goal_target or 0) if item.collective_goal_type == 'fixed' else class_size
    if target > 0 and purchased_students_count >= target:
        pending_items_query = StudentItem.query.filter(
            StudentItem.store_item_id == item.id,
            StudentItem.class_id == class_id,
            StudentItem.status == 'pending',
            StudentItem.collective_goal_instance_code == item.collective_goal_instance_code,
        )
        if join_code:
            pending_items_query = pending_items_query.filter(StudentItem.join_code == join_code)
        pending_items = pending_items_query.all()
        for pending_item in pending_items:
            pending_item.status = "processing"
