"""V2 canonical test fixture helpers.

Tests create identity through the production service layer.
No authority bridge patterns.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.services.classroom_setup import create_teacher as _svc_create_teacher
from app.feats.base import FEATContext
from app.extensions import db
from app.models import ClassEconomy, ClassFeature, Seat, StoreItem, StorePurchase, Transaction, User, UserRole
from app.services import ledger_service


def make_teacher(username: str, totp_secret: str | None = None) -> User:
    """Create a canonical V2 teacher (User with role=TEACHER).

    Delegates to app/services/classroom_setup.create_teacher().
    Flushes but does NOT commit — caller owns the transaction.
    """
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"make_teacher:{username}"):
        return _svc_create_teacher(username, totp_secret=totp_secret)


def make_sysadmin(username: str, totp_secret: str | None = None) -> User:
    """Create a canonical V2 sysadmin (User with role=SYSADMIN).

    Flushes but does NOT commit.
    """
    from app.utils.auth_username import build_hashed_username_fields
    from app.utils.encryption import normalize_totp_for_storage

    _salt, u_hash, u_lookup = build_hashed_username_fields(username)
    sysadmin = User(
        user_role=UserRole.SYSADMIN,
        username_hash=u_hash,
        username_lookup_hash=u_lookup,
        totp_secret_encrypted=normalize_totp_for_storage(totp_secret) if totp_secret else None,
    )
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"make_sysadmin:{username}"):
        db.session.add(sysadmin)
        db.session.flush()
    return sysadmin


@dataclass(frozen=True)
class CanonicalFixtureSeed:
    user: User
    class_row: ClassEconomy | None = None
    seat: Seat | None = None
    item: StoreItem | None = None
    transaction: Transaction | None = None
    purchase: StorePurchase | None = None
    class_feature: ClassFeature | None = None


def seed_canonical_admin(username: str, totp_secret: str | None = None) -> CanonicalFixtureSeed:
    """Create the canonical teacher user used by v2 tests."""
    return CanonicalFixtureSeed(user=make_teacher(username, totp_secret=totp_secret))


def seed_class_with_seat(
    *,
    teacher: User,
    join_code: str,
    display_name: str | None = None,
    section: str | None = None,
    student_first_name: str = "Student",
    student_last_name: str = "Test",
) -> CanonicalFixtureSeed:
    """Create a canonical class plus one claimed student seat."""
    from tests.helpers.class_scope import create_class_scope, make_student_identity
    class_row = create_class_scope(
        teacher_user=teacher,
        join_code=join_code,
        display_name=display_name,
        section=section,
    )
    seat = make_student_identity(
        class_id=class_row.class_id,
        first_name=student_first_name,
        last_name=student_last_name,
        claimed=True,
    )
    return CanonicalFixtureSeed(user=teacher, class_row=class_row, seat=seat)


def seed_student_identity(
    *,
    class_id: str,
    first_name: str,
    last_name: str = "Test",
    username: str | None = None,
) -> CanonicalFixtureSeed:
    """Create a canonical student identity row under FEAT ownership."""
    from tests.helpers.class_scope import make_student_identity

    seat = make_student_identity(
        class_id=class_id,
        first_name=first_name,
        last_name=last_name,
        username=username,
        claimed=True,
    )
    return CanonicalFixtureSeed(
        user=db.session.get(User, seat.user_id),
        seat=seat,
    )


def seed_student_membership(
    *,
    user: User,
    class_id: str,
    first_name: str,
    last_name: str = "Test",
    claimed: bool = True,
) -> CanonicalFixtureSeed:
    """Bind an existing user to an additional canonical student seat."""
    from app.models import IdentityProfile
    from app.utils.time import utc_now

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"seed_student_membership:{user.id}:{class_id}:{first_name}:{last_name}"):
        seat = Seat(
            user_id=user.id,
            class_id=class_id,
            role="student",
            claimed_at=utc_now() if claimed else None,
        )
        db.session.add(seat)
        db.session.flush()
        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=class_id,
            profile_type="student_claimed" if claimed else "student_unclaimed",
            first_name=first_name,
            last_name=last_name,
        )
        db.session.add(profile)
        db.session.flush()
    return CanonicalFixtureSeed(
        user=user,
        seat=seat,
    )


def seed_store_item(
    *,
    class_id: str,
    user_id: int,
    name: str = "Store Item",
    price: str | Decimal = "10.00",
    item_type: str = "standard",
    is_active: bool = True,
    **kwargs: Any,
) -> CanonicalFixtureSeed:
    """Create a canonical store item row under FEAT ownership."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"seed_store_item:{class_id}:{name}"):
        item = StoreItem(
            class_id=class_id,
            user_id=user_id,
            name=name,
            price=Decimal(str(price)),
            item_type=item_type,
            is_active=is_active,
            **kwargs,
        )
        db.session.add(item)
        db.session.flush()
    return CanonicalFixtureSeed(user=db.session.get(User, user_id), item=item)


def seed_purchase(
    *,
    seat_id: int,
    class_id: str,
    user_id: int,
    amount: str | Decimal,
    description: str,
    item: StoreItem | None = None,
    account_type: str = "checking",
    transaction_type: str = "purchase",
) -> CanonicalFixtureSeed:
    """Create a canonical pending purchase transaction and matching StorePurchase."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"seed_purchase:{seat_id}:{class_id}:{description}"):
        tx = ledger_service.create_pending_transaction(
            seat_id=seat_id,
            class_id=class_id,
            user_id=user_id,
            amount=Decimal(str(amount)),
            account_type=account_type,
            type=transaction_type,
            description=description,
        )
        purchase = None
        if item is not None:
            purchase = StorePurchase(
                seat_id=seat_id,
                class_id=class_id,
                store_item_id=item.id,
                quantity=1,
                price_at_purchase=Decimal("0.00"),
                total_price=Decimal("0.00"),
                status="purchased",
            )
            db.session.add(purchase)
        db.session.flush()
    return CanonicalFixtureSeed(user=db.session.get(User, user_id), transaction=tx, purchase=purchase)


def seed_class_feature(
    *,
    class_id: str,
    feature_name: str,
) -> CanonicalFixtureSeed:
    """Create a canonical class feature flag row under FEAT ownership."""
    with FEATContext("FEAT-ADMN-001", idempotency_key=f"seed_class_feature:{class_id}:{feature_name}"):
        existing = ClassFeature.query.filter_by(class_id=class_id, feature_name=feature_name).first()
        if existing:
            return CanonicalFixtureSeed(user=None, class_feature=existing)
        row = ClassFeature(class_id=class_id, feature_name=feature_name)
        db.session.add(row)
        db.session.flush()
    return CanonicalFixtureSeed(user=None, class_feature=row)


def clear_class_feature(
    *,
    class_id: str,
    feature_name: str,
) -> int:
    """Remove a canonical class feature row under FEAT ownership."""
    with FEATContext("FEAT-ADMN-001", idempotency_key=f"clear_class_feature:{class_id}:{feature_name}"):
        rows = ClassFeature.query.filter_by(class_id=class_id, feature_name=feature_name).all()
        for row in rows:
            db.session.delete(row)
        db.session.flush()
    return len(rows)
