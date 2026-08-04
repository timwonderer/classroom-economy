"""
Store Policy Resolver — STORE-owned policy consumption service.

Implements DOM-STORE-001 and SPEC-STORE-001:
- Resolves store product policies by UUID (exact immutable retrieval)
- Parses and validates policy payloads (fail-fast per SPEC-STORE-001)
- Supports discovery of canonical policy definitions for a class

Key principle: UUID resolution is exact, not inferential.
- resolve_store_item(policy_uuid) returns that exact immutable policy
- list_store_policies(class_id) returns canonical policy definitions for the class
- No cross-domain FK; no version inference from product_id + time
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.extensions import db
from app.models import StoreProduct, ClassEconomy


class StorePolicyError(Exception):
    """Base exception for store policy resolution errors."""
    pass


class PolicyNotFound(StorePolicyError):
    """Raised when policy UUID does not resolve."""
    pass


class PolicyParseError(StorePolicyError):
    """Raised when policy payload fails SPEC-STORE-001 schema validation."""
    pass


class PolicyValidationError(StorePolicyError):
    """Raised when policy payload violates SPEC-STORE-001 constraints."""
    pass


@dataclass(frozen=True)
class StorePolicyConfig:
    """Immutable resolved store product policy.

    Represents a resolved, validated policy per SPEC-STORE-001.
    All fields present and type-checked; no unknown fields.
    Snapshottable into entitlement_events.payload for historical reference.
    """

    # Required fields per SPEC-STORE-001 §IV.A
    product_id: int
    is_purchasable: bool
    supports_direct_grants: bool
    price: Decimal
    entitlement_type: str  # IMMEDIATE_USE | DELAYED_USE | HALL_PASS | PRIVILEGE | INSURANCE | COLLECTIVE_GOAL

    # Optional fields per SPEC-STORE-001 §IV.C
    limit_per_student: Optional[int] = None
    auto_expiry_days: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tier: Optional[str] = None
    bypass_cwi_warnings: bool = False
    is_long_term_goal: bool = False
    bundle_quantity: Optional[int] = None
    bulk_discount_quantity: Optional[int] = None
    bulk_discount_percentage: Optional[float] = None
    collective_goal_type: Optional[str] = None
    collective_goal_target: Optional[int] = None
    collective_goal_expires_at: Optional[datetime] = None

    # Metadata for historical reference
    policy_uuid: str = field(default="")
    class_id: str = field(default="")
    created_at: Optional[datetime] = None


class StorePolicyConfigParser:
    """Parses and validates store product policy payloads per SPEC-STORE-001.

    Enforces:
    - Fail-fast on unknown fields (SPEC-STORE-001 §III.A)
    - Type checking per schema
    - Value range validation (SPEC-STORE-001 §V.C)
    - Type-specific rules (SPEC-STORE-001 §V.A)
    - Mutual exclusion rules (SPEC-STORE-001 §V.B)
    """

    # Known field names per SPEC-STORE-001
    REQUIRED_FIELDS = {
        'product_id',
        'is_purchasable',
        'supports_direct_grants',
        'price',
        'entitlement_type',
    }

    OPTIONAL_FIELDS = {
        'limit_per_student',
        'auto_expiry_days',
        'name',
        'description',
        'tier',
        'bypass_cwi_warnings',
        'is_long_term_goal',
        'bundle_quantity',
        'bulk_discount_quantity',
        'bulk_discount_percentage',
        'collective_goal_type',
        'collective_goal_target',
        'collective_goal_expires_at',
    }

    ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS

    VALID_ENTITLEMENT_TYPES = {
        'IMMEDIATE_USE',
        'DELAYED_USE',
        'HALL_PASS',
        'PRIVILEGE',
        'INSURANCE',
        'COLLECTIVE_GOAL',
    }

    VALID_TIERS = {'basic', 'standard', 'premium', 'luxury'}
    VALID_COLLECTIVE_GOAL_TYPES = {'fixed', 'whole_class'}

    @classmethod
    def parse(cls, payload: Dict[str, Any],
              policy_uuid: str = "",
              class_id: str = "",
              created_at: Optional[datetime] = None) -> StorePolicyConfig:
        """Parse and validate policy payload per SPEC-STORE-001.

        Args:
            payload: Raw JSON payload from store_products.payload
            policy_uuid: UUID for historical reference
            class_id: Class scope for policy
            created_at: When policy was created

        Returns:
            StorePolicyConfig: Immutable validated policy

        Raises:
            PolicyParseError: Unknown field in payload (fail-fast per SPEC-STORE-001 §VII.2)
            PolicyValidationError: Type mismatch, missing required field, or invalid value
        """
        if not isinstance(payload, dict):
            raise PolicyParseError(f"Payload must be dict, got {type(payload).__name__}")

        # SPEC-STORE-001 §VII.2: Reject unknown fields (fail-fast)
        unknown_fields = set(payload.keys()) - cls.ALLOWED_FIELDS
        if unknown_fields:
            raise PolicyParseError(f"Unknown fields in payload: {', '.join(sorted(unknown_fields))}")

        # Validate required fields present and non-null
        for field_name in cls.REQUIRED_FIELDS:
            if field_name not in payload:
                raise PolicyParseError(f"Required field missing: {field_name}")
            if payload[field_name] is None:
                raise PolicyParseError(f"Required field cannot be null: {field_name}")

        try:
            # Parse required fields
            product_id = cls._parse_int(payload['product_id'], 'product_id')
            is_purchasable = cls._parse_bool(payload['is_purchasable'], 'is_purchasable')
            supports_direct_grants = cls._parse_bool(payload['supports_direct_grants'], 'supports_direct_grants')
            price = cls._parse_decimal(payload['price'], 'price')
            entitlement_type = cls._parse_entitlement_type(payload['entitlement_type'])

            # Parse optional fields
            limit_per_student = cls._parse_int_or_null(payload.get('limit_per_student'), 'limit_per_student')
            auto_expiry_days = cls._parse_int_or_null(payload.get('auto_expiry_days'), 'auto_expiry_days')
            name = cls._parse_string_or_null(payload.get('name'), 'name', max_length=100)
            description = cls._parse_string_or_null(payload.get('description'), 'description')
            tier = cls._parse_tier(payload.get('tier'))
            bypass_cwi_warnings = cls._parse_bool_with_default(payload.get('bypass_cwi_warnings'), False)
            is_long_term_goal = cls._parse_bool_with_default(payload.get('is_long_term_goal'), False)
            bundle_quantity = cls._parse_int_or_null(payload.get('bundle_quantity'), 'bundle_quantity')
            bulk_discount_quantity = cls._parse_int_or_null(payload.get('bulk_discount_quantity'), 'bulk_discount_quantity')
            bulk_discount_percentage = cls._parse_float_or_null(payload.get('bulk_discount_percentage'), 'bulk_discount_percentage')
            collective_goal_type = cls._parse_collective_goal_type(payload.get('collective_goal_type'))
            collective_goal_target = cls._parse_int_or_null(payload.get('collective_goal_target'), 'collective_goal_target')
            collective_goal_expires_at = cls._parse_datetime_or_null(payload.get('collective_goal_expires_at'), 'collective_goal_expires_at')

            # Validate value ranges and constraints
            cls._validate_ranges(
                price=price,
                limit_per_student=limit_per_student,
                auto_expiry_days=auto_expiry_days,
                bundle_quantity=bundle_quantity,
                bulk_discount_quantity=bulk_discount_quantity,
                bulk_discount_percentage=bulk_discount_percentage,
                collective_goal_target=collective_goal_target,
            )

            # Validate type-specific rules
            cls._validate_type_specific_rules(
                entitlement_type=entitlement_type,
                auto_expiry_days=auto_expiry_days,
                supports_direct_grants=supports_direct_grants,
                bundle_quantity=bundle_quantity,
                bulk_discount_quantity=bulk_discount_quantity,
                bulk_discount_percentage=bulk_discount_percentage,
                collective_goal_type=collective_goal_type,
                collective_goal_target=collective_goal_target,
                collective_goal_expires_at=collective_goal_expires_at,
            )

            # Validate mutual exclusion rules
            cls._validate_mutual_exclusion_rules(
                bundle_quantity=bundle_quantity,
                bulk_discount_quantity=bulk_discount_quantity,
                bulk_discount_percentage=bulk_discount_percentage,
                collective_goal_type=collective_goal_type,
                collective_goal_target=collective_goal_target,
                collective_goal_expires_at=collective_goal_expires_at,
            )

            return StorePolicyConfig(
                product_id=product_id,
                is_purchasable=is_purchasable,
                supports_direct_grants=supports_direct_grants,
                price=price,
                entitlement_type=entitlement_type,
                limit_per_student=limit_per_student,
                auto_expiry_days=auto_expiry_days,
                name=name,
                description=description,
                tier=tier,
                bypass_cwi_warnings=bypass_cwi_warnings,
                is_long_term_goal=is_long_term_goal,
                bundle_quantity=bundle_quantity,
                bulk_discount_quantity=bulk_discount_quantity,
                bulk_discount_percentage=bulk_discount_percentage,
                collective_goal_type=collective_goal_type,
                collective_goal_target=collective_goal_target,
                collective_goal_expires_at=collective_goal_expires_at,
                policy_uuid=policy_uuid,
                class_id=class_id,
                created_at=created_at,
            )

        except PolicyParseError:
            raise
        except PolicyValidationError:
            raise
        except Exception as e:
            raise PolicyParseError(f"Unexpected error parsing payload: {str(e)}")

    # ============================================================================
    # Type parsers (SPEC-STORE-001 §V type checking)
    # ============================================================================

    @staticmethod
    def _parse_int(value: Any, field_name: str) -> int:
        """Parse integer field."""
        if not isinstance(value, int) or isinstance(value, bool):
            raise PolicyParseError(f"Field {field_name} must be integer, got {type(value).__name__}")
        return value

    @staticmethod
    def _parse_bool(value: Any, field_name: str) -> bool:
        """Parse boolean field."""
        if not isinstance(value, bool):
            raise PolicyParseError(f"Field {field_name} must be boolean, got {type(value).__name__}")
        return value

    @staticmethod
    def _parse_bool_with_default(value: Any, default: bool) -> bool:
        """Parse optional boolean field with default."""
        if value is None:
            return default
        if not isinstance(value, bool):
            raise PolicyParseError(f"Boolean field must be boolean, got {type(value).__name__}")
        return value

    @staticmethod
    def _parse_decimal(value: Any, field_name: str) -> Decimal:
        """Parse decimal (price) field per SPEC-STORE-001."""
        if isinstance(value, str):
            try:
                return Decimal(value)
            except Exception:
                raise PolicyParseError(f"Field {field_name} must be decimal string, got invalid value")
        elif isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        else:
            raise PolicyParseError(f"Field {field_name} must be decimal string or number, got {type(value).__name__}")

    @staticmethod
    def _parse_int_or_null(value: Any, field_name: str) -> Optional[int]:
        """Parse optional integer field."""
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise PolicyParseError(f"Field {field_name} must be integer or null, got {type(value).__name__}")
        return value

    @staticmethod
    def _parse_float_or_null(value: Any, field_name: str) -> Optional[float]:
        """Parse optional float field."""
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PolicyParseError(f"Field {field_name} must be float or null, got {type(value).__name__}")
        return float(value)

    @staticmethod
    def _parse_string_or_null(value: Any, field_name: str, max_length: Optional[int] = None) -> Optional[str]:
        """Parse optional string field."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise PolicyParseError(f"Field {field_name} must be string or null, got {type(value).__name__}")
        if max_length and len(value) > max_length:
            raise PolicyParseError(f"Field {field_name} exceeds max length {max_length}")
        return value

    @staticmethod
    def _parse_datetime_or_null(value: Any, field_name: str) -> Optional[datetime]:
        """Parse optional ISO8601 datetime field."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except Exception:
                raise PolicyParseError(f"Field {field_name} must be ISO8601 datetime, got invalid value")
        raise PolicyParseError(f"Field {field_name} must be ISO8601 datetime or null, got {type(value).__name__}")

    @classmethod
    def _parse_entitlement_type(cls, value: Any) -> str:
        """Parse and validate entitlement_type enum."""
        if not isinstance(value, str):
            raise PolicyParseError(f"Field entitlement_type must be string, got {type(value).__name__}")
        if value not in cls.VALID_ENTITLEMENT_TYPES:
            raise PolicyValidationError(f"Invalid entitlement_type: {value}. Must be one of: {', '.join(cls.VALID_ENTITLEMENT_TYPES)}")
        return value

    @classmethod
    def _parse_tier(cls, value: Any) -> Optional[str]:
        """Parse and validate tier enum."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise PolicyParseError(f"Field tier must be string or null, got {type(value).__name__}")
        if value not in cls.VALID_TIERS:
            raise PolicyValidationError(f"Invalid tier: {value}. Must be one of: {', '.join(cls.VALID_TIERS)}")
        return value

    @classmethod
    def _parse_collective_goal_type(cls, value: Any) -> Optional[str]:
        """Parse and validate collective_goal_type enum."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise PolicyParseError(f"Field collective_goal_type must be string or null, got {type(value).__name__}")
        if value not in cls.VALID_COLLECTIVE_GOAL_TYPES:
            raise PolicyValidationError(f"Invalid collective_goal_type: {value}. Must be one of: {', '.join(cls.VALID_COLLECTIVE_GOAL_TYPES)}")
        return value

    # ============================================================================
    # Validation (SPEC-STORE-001 §V)
    # ============================================================================

    @staticmethod
    def _validate_ranges(price: Decimal,
                         limit_per_student: Optional[int],
                         auto_expiry_days: Optional[int],
                         bundle_quantity: Optional[int],
                         bulk_discount_quantity: Optional[int],
                         bulk_discount_percentage: Optional[float],
                         collective_goal_target: Optional[int]) -> None:
        """Validate value ranges per SPEC-STORE-001 §V.C."""
        # Price must be ≥ 0
        if price < Decimal('0'):
            raise PolicyValidationError("Price cannot be negative")

        # limit_per_student: if set, must be > 0
        if limit_per_student is not None and limit_per_student <= 0:
            raise PolicyValidationError("limit_per_student must be > 0 if set")

        # auto_expiry_days: if set, must be > 0
        if auto_expiry_days is not None and auto_expiry_days <= 0:
            raise PolicyValidationError("auto_expiry_days must be > 0 if set")

        # bundle_quantity: if set, must be > 1
        if bundle_quantity is not None and bundle_quantity <= 1:
            raise PolicyValidationError("bundle_quantity must be > 1 if set")

        # bulk_discount_quantity: if set, must be > 1
        if bulk_discount_quantity is not None and bulk_discount_quantity <= 1:
            raise PolicyValidationError("bulk_discount_quantity must be > 1 if set")

        # bulk_discount_percentage: if set, must be in [0, 100]
        if bulk_discount_percentage is not None and not (0 <= bulk_discount_percentage <= 100):
            raise PolicyValidationError("bulk_discount_percentage must be in range [0, 100] if set")

        # collective_goal_target: if set, must be > 0
        if collective_goal_target is not None and collective_goal_target <= 0:
            raise PolicyValidationError("collective_goal_target must be > 0 if set")

    @staticmethod
    def _validate_type_specific_rules(entitlement_type: str,
                                      auto_expiry_days: Optional[int],
                                      supports_direct_grants: bool,
                                      bundle_quantity: Optional[int],
                                      bulk_discount_quantity: Optional[int],
                                      bulk_discount_percentage: Optional[float],
                                      collective_goal_type: Optional[str],
                                      collective_goal_target: Optional[int],
                                      collective_goal_expires_at: Optional[datetime]) -> None:
        """Validate type-specific rules per SPEC-STORE-001 §V.A."""

        if entitlement_type == 'IMMEDIATE_USE':
            # auto_expiry_days MUST be null
            if auto_expiry_days is not None:
                raise PolicyValidationError("IMMEDIATE_USE cannot have auto_expiry_days")
            # Cannot be bundled or part of collective goal
            if bundle_quantity is not None or bulk_discount_quantity is not None or collective_goal_type is not None:
                raise PolicyValidationError("IMMEDIATE_USE cannot be bundled or part of collective goal")

        elif entitlement_type == 'DELAYED_USE':
            # auto_expiry_days optional
            # Cannot be bundled or part of collective goal
            if bundle_quantity is not None or bulk_discount_quantity is not None or collective_goal_type is not None:
                raise PolicyValidationError("DELAYED_USE cannot be bundled or part of collective goal")

        elif entitlement_type == 'HALL_PASS':
            # supports_direct_grants MUST be true
            if not supports_direct_grants:
                raise PolicyValidationError("HALL_PASS must have supports_direct_grants=true")
            # Cannot be bundled or part of collective goal
            if bundle_quantity is not None or bulk_discount_quantity is not None or collective_goal_type is not None:
                raise PolicyValidationError("HALL_PASS cannot be bundled or part of collective goal")

        elif entitlement_type == 'PRIVILEGE':
            # auto_expiry_days MUST be null
            if auto_expiry_days is not None:
                raise PolicyValidationError("PRIVILEGE cannot have auto_expiry_days")
            # supports_direct_grants MUST be true
            if not supports_direct_grants:
                raise PolicyValidationError("PRIVILEGE must have supports_direct_grants=true")
            # Cannot be bundled or part of collective goal
            if bundle_quantity is not None or bulk_discount_quantity is not None or collective_goal_type is not None:
                raise PolicyValidationError("PRIVILEGE cannot be bundled or part of collective goal")

        elif entitlement_type == 'COLLECTIVE_GOAL':
            # collective_goal_type MUST be set
            if collective_goal_type is None:
                raise PolicyValidationError("COLLECTIVE_GOAL must have collective_goal_type set")
            # collective_goal_target MUST be set
            if collective_goal_target is None:
                raise PolicyValidationError("COLLECTIVE_GOAL must have collective_goal_target set")
            # collective_goal_expires_at MUST be set
            if collective_goal_expires_at is None:
                raise PolicyValidationError("COLLECTIVE_GOAL must have collective_goal_expires_at set")
            # Bundle fields MUST all be null
            if bundle_quantity is not None or bulk_discount_quantity is not None or bulk_discount_percentage is not None:
                raise PolicyValidationError("COLLECTIVE_GOAL cannot have bundle/bulk discount fields")

    @staticmethod
    def _validate_mutual_exclusion_rules(bundle_quantity: Optional[int],
                                         bulk_discount_quantity: Optional[int],
                                         bulk_discount_percentage: Optional[float],
                                         collective_goal_type: Optional[str],
                                         collective_goal_target: Optional[int],
                                         collective_goal_expires_at: Optional[datetime]) -> None:
        """Validate mutual exclusion rules per SPEC-STORE-001 §V.B."""

        # Bundle XOR Collective Goal
        has_bundle_fields = bundle_quantity is not None or bulk_discount_quantity is not None or bulk_discount_percentage is not None
        has_collective_goal_fields = collective_goal_type is not None or collective_goal_target is not None or collective_goal_expires_at is not None

        if has_bundle_fields and has_collective_goal_fields:
            raise PolicyValidationError("Cannot have both bundle/bulk discount and collective goal fields")

        # Collective Goal Completeness: if any field is set, all must be set
        collective_goal_fields = [collective_goal_type, collective_goal_target, collective_goal_expires_at]
        num_set = sum(1 for f in collective_goal_fields if f is not None)
        if num_set > 0 and num_set < 3:
            raise PolicyValidationError("Collective goal fields must all be set together or all null")


class StorePolicyResolver:
    """Resolves store product policies by UUID.

    Implements:
    - Exact resolution: resolve_store_item(policy_uuid) → StorePolicyConfig
    - Discovery: list_store_policies(class_id) → List[StorePolicyConfig]

    Key principles:
    - UUID resolution is exact, not inferential
    - If policy is deleted, UUID no longer resolves (expected behavior)
    - Historical entitlements remain valid from their own snapshots
    """

    @staticmethod
    def resolve_store_item(policy_uuid: str) -> StorePolicyConfig:
        """Resolve exact immutable policy by UUID per SPEC-STORE-001 §VII.

        Args:
            policy_uuid: UUID locator for the policy

        Returns:
            StorePolicyConfig: Immutable validated policy

        Raises:
            PolicyNotFound: If UUID does not resolve (expected after cleanup)
            PolicyParseError: If payload fails schema validation
            PolicyValidationError: If payload violates constraints
        """
        store_product = db.session.query(StoreProduct).filter_by(policy_uuid=policy_uuid).first()

        if not store_product:
            raise PolicyNotFound(f"Policy UUID {policy_uuid} not found (may have been deleted)")

        # Parse and validate payload per SPEC-STORE-001
        try:
            return StorePolicyConfigParser.parse(
                payload=store_product.payload,
                policy_uuid=store_product.policy_uuid,
                class_id=store_product.class_id,
                created_at=store_product.created_at,
            )
        except (PolicyParseError, PolicyValidationError) as e:
            raise StorePolicyError(f"Policy {policy_uuid} validation failed: {str(e)}")

    @staticmethod
    def list_store_policies(class_id: str) -> List[StorePolicyConfig]:
        """List canonical store policy definitions for a class.

        This is a pure configuration discovery primitive. It does not evaluate
        student eligibility, affordability, entitlement ownership, class feature
        state, ordering, or presentation. Those concerns belong in Phase 5
        view models.
        Args:
            class_id: Class scope for policies

        Returns:
            List[StorePolicyConfig]: Canonical policy definitions for the class

        Raises:
            StorePolicyError: If any policy fails validation (stop on first error)
        """
        # Verify class exists
        class_economy = db.session.query(ClassEconomy).filter_by(class_id=class_id).first()
        if not class_economy:
            return []

        # Query non-retired policies for this class
        store_products = db.session.query(StoreProduct).filter_by(
            class_id=class_id,
            is_retired=False,
        ).all()

        # Parse and validate each policy; fail-fast on first error
        policies = []
        for store_product in store_products:
            try:
                policy = StorePolicyConfigParser.parse(
                    payload=store_product.payload,
                    policy_uuid=store_product.policy_uuid,
                    class_id=store_product.class_id,
                    created_at=store_product.created_at,
                )
                policies.append(policy)
            except (PolicyParseError, PolicyValidationError) as e:
                # Fail-fast: stop on first validation error
                raise StorePolicyError(f"Policy {store_product.policy_uuid} in class {class_id} validation failed: {str(e)}")

        return policies

    @staticmethod
    def create_store_product(class_id: str,
                            payload: Dict[str, Any],
                            created_by_seat_id: Optional[int] = None) -> StorePolicyConfig:
        """Create a new store product policy and return resolved config.

        Note: This is a convenience method for testing and policy creation.
        Production code should use StorePolicyConfig validation directly.

        Args:
            class_id: Class scope for policy
            payload: Policy payload (will be validated)
            created_by_seat_id: Optional seat ID of creator

        Returns:
            StorePolicyConfig: Resolved policy

        Raises:
            PolicyParseError: If payload fails schema validation
            PolicyValidationError: If payload violates constraints
        """
        # Parse and validate before persisting
        config = StorePolicyConfigParser.parse(payload=payload, class_id=class_id)

        # Create and persist
        store_product = StoreProduct(
            class_id=class_id,
            payload=payload,
            created_by_seat_id=created_by_seat_id,
        )
        db.session.add(store_product)
        db.session.flush()

        # Return config with populated UUID and timestamps
        return StorePolicyConfig(
            product_id=config.product_id,
            is_purchasable=config.is_purchasable,
            supports_direct_grants=config.supports_direct_grants,
            price=config.price,
            entitlement_type=config.entitlement_type,
            limit_per_student=config.limit_per_student,
            auto_expiry_days=config.auto_expiry_days,
            name=config.name,
            description=config.description,
            tier=config.tier,
            bypass_cwi_warnings=config.bypass_cwi_warnings,
            is_long_term_goal=config.is_long_term_goal,
            bundle_quantity=config.bundle_quantity,
            bulk_discount_quantity=config.bulk_discount_quantity,
            bulk_discount_percentage=config.bulk_discount_percentage,
            collective_goal_type=config.collective_goal_type,
            collective_goal_target=config.collective_goal_target,
            collective_goal_expires_at=config.collective_goal_expires_at,
            policy_uuid=store_product.policy_uuid,
            class_id=store_product.class_id,
            created_at=store_product.created_at,
        )
