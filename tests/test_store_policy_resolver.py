"""
Test StorePolicyResolver: exact UUID resolution and ambiguity prevention.

Proves that multiple policies with same product_id cannot cause ambiguity
because FEAT execution always supplies exact policy_uuid.
"""

import pytest
from decimal import Decimal
from datetime import timedelta
from app.extensions import db
from app.feats.base import FEATContext
from app.models import StoreProduct
from app.services.store_policy_resolver import (
    StorePolicyResolver,
    StorePolicyConfigParser,
    StorePolicyError,
    PolicyNotFound,
    PolicyParseError,
    PolicyValidationError,
)
from app.utils.time import utc_now
from tests.helpers.canonical_classroom import provision_classroom


@pytest.fixture
def canonical_classroom(app):
    """Create a canonical classroom through production code."""
    with app.app_context():
        return provision_classroom("chemistry_p1")


@pytest.fixture
def test_class(canonical_classroom):
    return {"class_id": canonical_classroom.class_id}


@pytest.fixture
def test_user(canonical_classroom):
    return {"user_id": canonical_classroom.teacher_user_id}


@pytest.fixture
def teacher_seat(canonical_classroom):
    return {"seat_id": canonical_classroom.teacher_seat_id}


class TestStorePolicyConfigParser:
    """Test StorePolicyConfigParser validation per SPEC-STORE-001."""

    def test_parse_valid_payload_all_fields(self, app):
        """Test parsing valid payload with all fields."""
        with app.app_context():
            payload = {
                # Required
                "product_id": 101,
                "is_purchasable": True,
                "supports_direct_grants": True,
                "price": "50.00",
                "entitlement_type": "DELAYED_USE",
                # Optional
                "limit_per_student": 5,
                "auto_expiry_days": 30,
                "name": "Test Product",
                "description": "Test Description",
                "tier": "standard",
                "bypass_cwi_warnings": False,
                "is_long_term_goal": False,
                "bundle_quantity": None,
                "bulk_discount_quantity": None,
                "bulk_discount_percentage": None,
                "collective_goal_type": None,
                "collective_goal_target": None,
                "collective_goal_expires_at": None,
            }

            config = StorePolicyConfigParser.parse(payload)

            assert config.product_id == 101
            assert config.is_purchasable is True
            assert config.supports_direct_grants is True
            assert config.price == Decimal("50.00")
            assert config.entitlement_type == "DELAYED_USE"
            assert config.limit_per_student == 5
            assert config.auto_expiry_days == 30

    def test_parse_rejects_unknown_fields(self, app):
        """Test fail-fast on unknown fields (SPEC-STORE-001 §III.A)."""
        with app.app_context():
            payload = {
                "product_id": 101,
                "is_purchasable": True,
                "supports_direct_grants": True,
                "price": "50.00",
                "entitlement_type": "DELAYED_USE",
                "unknown_field": "should_fail",  # Unknown field
            }

            with pytest.raises(PolicyParseError, match="Unknown fields"):
                StorePolicyConfigParser.parse(payload)

    def test_parse_rejects_missing_required_field(self, app):
        """Test validation fails with missing required field."""
        with app.app_context():
            payload = {
                "product_id": 101,
                "is_purchasable": True,
                "supports_direct_grants": True,
                # Missing: price
                "entitlement_type": "DELAYED_USE",
            }

            with pytest.raises(PolicyParseError, match="Required field missing"):
                StorePolicyConfigParser.parse(payload)

    def test_parse_rejects_type_mismatch(self, app):
        """Test validation fails on type mismatch."""
        with app.app_context():
            payload = {
                "product_id": "not_an_int",  # Should be integer
                "is_purchasable": True,
                "supports_direct_grants": True,
                "price": "50.00",
                "entitlement_type": "DELAYED_USE",
            }

            with pytest.raises(PolicyParseError):
                StorePolicyConfigParser.parse(payload)

    def test_parse_rejects_negative_price(self, app):
        """Test validation fails on negative price (SPEC-STORE-001 §V.C)."""
        with app.app_context():
            payload = {
                "product_id": 101,
                "is_purchasable": True,
                "supports_direct_grants": True,
                "price": "-10.00",  # Negative not allowed
                "entitlement_type": "DELAYED_USE",
            }

            with pytest.raises(PolicyValidationError, match="Price cannot be negative"):
                StorePolicyConfigParser.parse(payload)

    def test_parse_rejects_immediate_use_with_expiry(self, app):
        """Test IMMEDIATE_USE cannot have auto_expiry_days (SPEC-STORE-001 §V.A)."""
        with app.app_context():
            payload = {
                "product_id": 101,
                "is_purchasable": True,
                "supports_direct_grants": True,
                "price": "50.00",
                "entitlement_type": "IMMEDIATE_USE",
                "auto_expiry_days": 30,  # Not allowed for IMMEDIATE_USE
            }

            with pytest.raises(PolicyValidationError, match="IMMEDIATE_USE cannot have auto_expiry_days"):
                StorePolicyConfigParser.parse(payload)

    def test_parse_rejects_hall_pass_without_direct_grants(self, app):
        """Test HALL_PASS must support direct grants (SPEC-STORE-001 §V.A)."""
        with app.app_context():
            payload = {
                "product_id": 101,
                "is_purchasable": True,
                "supports_direct_grants": False,  # Required to be True
                "price": "50.00",
                "entitlement_type": "HALL_PASS",
            }

            with pytest.raises(PolicyValidationError, match="HALL_PASS must have supports_direct_grants=true"):
                StorePolicyConfigParser.parse(payload)

    def test_parse_rejects_bundle_xor_collective_goal(self, app):
        """Test bundle and collective_goal are mutually exclusive (SPEC-STORE-001 §V.B)."""
        with app.app_context():
            payload = {
                "product_id": 101,
                "is_purchasable": True,
                "supports_direct_grants": True,
                "price": "50.00",
                "entitlement_type": "COLLECTIVE_GOAL",
                "bundle_quantity": 5,  # Cannot have bundle with collective_goal
                "collective_goal_type": "fixed",
                "collective_goal_target": 100,
                "collective_goal_expires_at": (utc_now() + timedelta(days=30)).isoformat(),
            }

            with pytest.raises(PolicyValidationError, match="COLLECTIVE_GOAL cannot have bundle/bulk discount fields"):
                StorePolicyConfigParser.parse(payload)


class TestStorePolicyResolver:
    """Test StorePolicyResolver exact UUID resolution."""

    def test_resolve_store_item_exact_match(self, app, test_class, teacher_seat):
        """Test resolving policy by exact UUID."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:exact-match"):
                payload = {
                    "product_id": 101,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "50.00",
                    "entitlement_type": "DELAYED_USE",
                }

                config = StorePolicyResolver.create_store_product(
                    class_id=test_class["class_id"],
                    payload=payload,
                    created_by_seat_id=teacher_seat["seat_id"],
                )

            # Exact resolution by UUID
            store_product_uuid = config.policy_uuid
            config = StorePolicyResolver.resolve_store_item(store_product_uuid)

            assert config.product_id == 101
            assert config.entitlement_type == "DELAYED_USE"
            assert config.policy_uuid == store_product_uuid
            assert config.class_id == test_class["class_id"]

    def test_resolve_store_item_not_found(self, app):
        """Test PolicyNotFound when UUID doesn't exist."""
        with app.app_context():
            with pytest.raises(PolicyNotFound):
                StorePolicyResolver.resolve_store_item("nonexistent-uuid-12345")

    def test_resolve_store_item_validation_failure(self, app, test_class, teacher_seat):
        """Test PolicyValidationError propagates from parser."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:validation-failure"):
                # Invalid payload (negative price)
                payload = {
                    "product_id": 101,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "-10.00",  # Invalid
                    "entitlement_type": "DELAYED_USE",
                }

                with pytest.raises(PolicyValidationError):
                    StorePolicyResolver.create_store_product(
                        class_id=test_class["class_id"],
                        payload=payload,
                        created_by_seat_id=teacher_seat["seat_id"],
                    )


class TestMultiplePoliciesSameProductId:
    """Test that multiple policies with same product_id don't cause ambiguity.

    FEAT execution always supplies exact policy_uuid, so inference is impossible.
    """

    def test_multiple_policies_same_product_id_different_uuids(self, app, test_class, teacher_seat):
        """Test multiple non-retired policies for same product_id coexist without ambiguity."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:multi-policy"):
                # Policy 1: product_id=101, supports_direct_grants=True
                payload1 = {
                    "product_id": 101,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "50.00",
                    "entitlement_type": "HALL_PASS",
                }
                config1 = StorePolicyResolver.create_store_product(
                    class_id=test_class["class_id"],
                    payload=payload1,
                    created_by_seat_id=teacher_seat["seat_id"],
                )

                # Policy 2: product_id=101, supports_direct_grants=False (different config)
                payload2 = {
                    "product_id": 101,
                    "is_purchasable": True,
                    "supports_direct_grants": False,  # Different
                    "price": "75.00",  # Different
                    "entitlement_type": "DELAYED_USE",
                }
                config2 = StorePolicyResolver.create_store_product(
                    class_id=test_class["class_id"],
                    payload=payload2,
                    created_by_seat_id=teacher_seat["seat_id"],
                )

                # Both policies exist
                assert config1.policy_uuid != config2.policy_uuid
                assert config1.product_id == config2.product_id

                # Exact resolution of policy1
                resolved1 = StorePolicyResolver.resolve_store_item(config1.policy_uuid)
                assert resolved1.supports_direct_grants is True
                assert resolved1.price == Decimal("50.00")
                assert resolved1.entitlement_type == "HALL_PASS"

                # Exact resolution of policy2
                resolved2 = StorePolicyResolver.resolve_store_item(config2.policy_uuid)
                assert resolved2.supports_direct_grants is False
                assert resolved2.price == Decimal("75.00")
                assert resolved2.entitlement_type == "DELAYED_USE"

                # No ambiguity: each UUID resolves to its exact policy
                assert resolved1.policy_uuid != resolved2.policy_uuid
                assert resolved1.supports_direct_grants != resolved2.supports_direct_grants

    def test_policy_deletion_with_multiple_policies(self, app, test_class, teacher_seat):
        """Test deleting one policy doesn't affect others with same product_id."""
        with app.app_context():
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:delete-one"):
                # Create two policies
                payload1 = {
                    "product_id": 102,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "50.00",
                    "entitlement_type": "DELAYED_USE",
                }
                config1 = StorePolicyResolver.create_store_product(
                    class_id=test_class["class_id"],
                    payload=payload1,
                    created_by_seat_id=teacher_seat["seat_id"],
                )

                payload2 = {
                    "product_id": 102,
                    "is_purchasable": True,
                    "supports_direct_grants": True,
                    "price": "60.00",
                    "entitlement_type": "DELAYED_USE",
                }
                config2 = StorePolicyResolver.create_store_product(
                    class_id=test_class["class_id"],
                    payload=payload2,
                    created_by_seat_id=teacher_seat["seat_id"],
                )

            uuid1 = config1.policy_uuid
            uuid2 = config2.policy_uuid

            # Both resolve
            resolved1 = StorePolicyResolver.resolve_store_item(uuid1)
            resolved2 = StorePolicyResolver.resolve_store_item(uuid2)
            assert resolved1.price == Decimal("50.00")
            assert resolved2.price == Decimal("60.00")

            # Delete policy1
            with FEATContext("FEAT-TEST-SETUP", idempotency_key="store-policy-resolver:delete-one-cleanup"):
                store_product1 = db.session.query(StoreProduct).filter_by(policy_uuid=uuid1).one()
                db.session.delete(store_product1)
                db.session.flush()

            # policy1 UUID no longer resolves (expected behavior)
            with pytest.raises(PolicyNotFound):
                StorePolicyResolver.resolve_store_item(uuid1)

            # policy2 UUID still resolves (unaffected)
            resolved2_after = StorePolicyResolver.resolve_store_item(uuid2)
            assert resolved2_after.price == Decimal("60.00")


class TestFeatExactResolution:
    """Test FEAT-STOR-004 contract: accept policy_uuid, resolve exactly."""

    def test_feat_stor_004_requires_policy_uuid_not_product_id(self, app):
        """Verify FEAT-STOR-004 signature requires policy_uuid, not product_id."""
        from app.feats.direct_entitlement_grant_feat import execute_direct_grant
        import inspect

        sig = inspect.signature(execute_direct_grant)
        params = list(sig.parameters.keys())

        # Must have policy_uuid
        assert "policy_uuid" in params, "FEAT-STOR-004 must accept policy_uuid"

        # Should NOT have product_id as parameter
        assert "product_id" not in params, "FEAT-STOR-004 must NOT accept product_id as parameter"
