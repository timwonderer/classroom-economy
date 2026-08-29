"""
FEAT-STOR-007: Publish Insurance Product.

Publishes a POL-owned insurance definition (``InsurancePolicy.policy_uuid``)
as a purchasable ``StoreProduct`` in the same class boundary. This is the
"publish" step in the insurance arc (define → publish → purchase → freeze →
claim); it is deliberately separate from definition creation. Creating an
insurance definition (FEAT-CLASS-003 → FEAT-POL-001) does NOT make it
purchasable — a teacher must explicitly publish it here.

Authority:
- DOM-STORE-001 — a StoreProduct's product reference SHALL refer to a
  Policy-owned product definition lawful for the same class boundary;
  entitlement_type INSURANCE is a first-class product type.
- SPEC-STORE-001 — StoreProduct.payload is the single source of product
  configuration; the parser fails-fast on unknown fields and now enforces
  ``insurance_policy_uuid`` presence iff entitlement_type == INSURANCE.
- DOM-POL-001 §VI — the insurance definition is retrieved through its lawful
  class-scoped POL contract; publication proves same-class scope and IN_USE
  availability before creating the StoreProduct.

Invariants enforced here:
- Mandatory canonical teacher context (fail-closed; never assume the route
  pre-validated). The acting seat must be a teacher seat in the target class,
  owned by the context user.
- The referenced insurance definition must resolve in the SAME class and be
  IN_USE. HIDDEN/RETIRED/foreign/nonexistent definitions fail closed.
- No insurance economic terms are duplicated into StoreProduct — only the
  ``insurance_policy_uuid`` locator plus product-catalog fields are stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import Seat, StoreProduct
from app.services import insurance_definition_service as defs
from app.services.context_resolver import CanonicalContext
from app.services.store_policy_resolver import (
    StorePolicyConfigParser,
    PolicyParseError,
    PolicyValidationError,
)


class InsurancePublicationError(Exception):
    """Raised when insurance-product publication is unlawful or malformed."""


@dataclass(frozen=True)
class PublishedInsuranceProduct:
    """Result of a lawful insurance publication."""

    store_product_id: int
    store_policy_uuid: str
    insurance_policy_uuid: str
    class_id: str


def _require_teacher_scope(canonical_context: Optional[CanonicalContext], class_id: str) -> None:
    """Fail-closed teacher-scope gate for publication.

    Independently establishes (never assuming the route did): the context
    carries the canonical anchors, its class_id matches the target class, and
    its seat is a teacher seat in that class owned by the context user.
    """
    if canonical_context is None:
        raise InsurancePublicationError("Canonical context is required")

    user_id = getattr(canonical_context, "user_id", None)
    ctx_class_id = getattr(canonical_context, "class_id", None)
    seat_id = getattr(canonical_context, "seat_id", None)
    actor_role = getattr(canonical_context, "actor_role", None)

    if not user_id:
        raise InsurancePublicationError("Missing canonical user_id")
    if not ctx_class_id:
        raise InsurancePublicationError("Missing canonical class_id")
    if not seat_id:
        raise InsurancePublicationError("Missing canonical seat_id")
    if not actor_role:
        raise InsurancePublicationError("Missing canonical actor_role")
    if ctx_class_id != class_id:
        raise InsurancePublicationError(
            f"Class scope mismatch: context {ctx_class_id} != target {class_id}"
        )
    if actor_role != "teacher":
        raise InsurancePublicationError("Only teachers may publish insurance products")

    teacher_seat = db.session.get(Seat, seat_id)
    if teacher_seat is None:
        raise InsurancePublicationError("Canonical seat not found")
    if teacher_seat.class_id != class_id:
        raise InsurancePublicationError("Teacher seat is not in the requested class")
    if getattr(teacher_seat, "role", None) != "teacher":
        raise InsurancePublicationError("Canonical seat is not a teacher seat")
    if teacher_seat.user_id != user_id:
        raise InsurancePublicationError("Canonical seat is not owned by the context user")


@requires_feat_context("FEAT-STOR-007")
def publish_insurance_product(
    *,
    class_id: str,
    insurance_policy_uuid: str,
    product_definition: Dict[str, Any],
    canonical_context: CanonicalContext,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> PublishedInsuranceProduct:
    """Publish an IN_USE insurance definition as a purchasable StoreProduct.

    Args:
        class_id: Target class boundary (canonical).
        insurance_policy_uuid: The POL insurance definition to publish.
        product_definition: Catalog-level StoreProduct payload fields
            (price, is_purchasable, limits, name, etc.). MUST NOT carry any
            insurance economic terms — those live in the POL definition. The
            entitlement_type and insurance_policy_uuid locator are stamped by
            this FEAT; callers need not (and must not) override them with a
            conflicting value.
        canonical_context: Mandatory teacher context (fail-closed).

    Returns:
        PublishedInsuranceProduct describing the created StoreProduct.

    Raises:
        InsurancePublicationError: unlawful context, cross-class/unavailable
            definition, or a payload that duplicates economic terms.
        PolicyParseError / PolicyValidationError: malformed catalog payload.
    """
    _require_teacher_scope(canonical_context, class_id)

    if not insurance_policy_uuid:
        raise InsurancePublicationError("insurance_policy_uuid is required to publish")

    # Resolve the referenced definition through its lawful POL contract.
    # get_insurance_definition fails closed on class mismatch (returns None),
    # proving same-class scope.
    definition = defs.get_insurance_definition(insurance_policy_uuid, class_id=class_id)
    if definition is None:
        raise InsurancePublicationError(
            "Referenced insurance definition does not exist in this class"
        )
    if definition.availability_state != defs.IN_USE:
        raise InsurancePublicationError(
            f"Insurance definition is not IN_USE (state={definition.availability_state}); "
            "only IN_USE definitions may be published"
        )

    # Build the StoreProduct payload. The entitlement_type and locator are
    # authoritative here; reject any caller attempt to smuggle a conflicting
    # value so the linkage stays trustworthy.
    payload: Dict[str, Any] = dict(product_definition)

    supplied_type = payload.get("entitlement_type")
    if supplied_type is not None and supplied_type != "INSURANCE":
        raise InsurancePublicationError(
            "entitlement_type must be INSURANCE for an insurance publication"
        )
    payload["entitlement_type"] = "INSURANCE"

    supplied_locator = payload.get("insurance_policy_uuid")
    if supplied_locator is not None and supplied_locator != insurance_policy_uuid:
        raise InsurancePublicationError(
            "insurance_policy_uuid in payload conflicts with the definition being published"
        )
    payload["insurance_policy_uuid"] = insurance_policy_uuid

    # Validate the catalog payload (fail-fast on unknown fields, enforces the
    # locator-presence rule for INSURANCE). This will also reject any duplicated
    # insurance economic term because those are unknown StoreProduct fields.
    try:
        StorePolicyConfigParser.parse(payload=payload, class_id=class_id)
    except (PolicyParseError, PolicyValidationError) as exc:
        raise InsurancePublicationError(f"Invalid insurance product payload: {exc}") from exc

    store_product = StoreProduct(
        class_id=class_id,
        payload=payload,
        created_by_seat_id=canonical_context.seat_id,
    )
    db.session.add(store_product)
    db.session.flush()

    return PublishedInsuranceProduct(
        store_product_id=store_product.id,
        store_policy_uuid=store_product.policy_uuid,
        insurance_policy_uuid=insurance_policy_uuid,
        class_id=class_id,
    )
