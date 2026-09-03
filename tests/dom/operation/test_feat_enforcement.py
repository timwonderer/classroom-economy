import pytest
from app.extensions import db
from app.models import User, UserRole
from app.feats.base import FEATContextError, requires_feat_context, is_feat_active
from tests.helpers.classroom_initializer import initialize

@pytest.mark.enforce_feat
def test_FEAT_CORE_000__commit_fails_outside_feat_context(app):
    """
    CONFIRM: No mutation until a FEAT context is established.
    This is the core architectural safeguard.
    """
    user = User(user_role=UserRole.STUDENT, username_hash="test_feat_commit_guard_unique")
    db.session.add(user)

    with pytest.raises(FEATContextError) as excinfo:
        db.session.commit()

    assert "MANDATORY FEAT CONSTITUTIONAL VIOLATION (COMMIT)" in str(excinfo.value)
    db.session.rollback()

@pytest.mark.enforce_feat
def test_FEAT_CORE_000__flush_fails_outside_feat_context(app):
    """
    CONFIRM: No SQL emission (flush) until a FEAT context is established.
    """
    user = User(user_role=UserRole.STUDENT, username_hash="test_feat_flush_guard_unique")
    db.session.add(user)

    with pytest.raises(FEATContextError) as excinfo:
        db.session.flush()

    assert "MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH)" in str(excinfo.value)
    db.session.rollback()

@pytest.mark.enforce_feat
def test_FEAT_CORE_000__commit_succeeds_inside_feat_context(app):
    """
    CONFIRM: Mutations are permitted in FEAT context without direct commit.
    """
    classroom = initialize("chemistry_p1", app)

    @requires_feat_context("FEAT-TEST-001")
    def legal_mutation():
        from app.services.classroom_setup import create_student

        stu, _seat, _profile = create_student(
            classroom.class_id,
            first_name="Legal",
            last_name="M",
        )
        db.session.flush()
        return stu

    stu = legal_mutation()
    assert stu.id is not None
    assert is_feat_active() is False # Should be cleared after exit

@pytest.mark.enforce_feat
def test_FEAT_CORE_000__nested_feat_context(app):
    """
    CONFIRM: Nested FEATs are tracked correctly without direct commit calls.
    """
    @requires_feat_context("OUTER")
    def outer():
        assert is_feat_active()
        
        @requires_feat_context("INNER")
        def inner():
            assert is_feat_active()
            db.session.flush()
        
        inner()
        assert is_feat_active()
        db.session.flush()
    
    outer()
    assert is_feat_active() is False


@pytest.mark.enforce_feat
def test_FEAT_CORE_000__direct_commit_inside_feat_context_is_blocked(app):
    """
    CONFIRM: Only FEAT orchestrator boundary can commit.
    """
    @requires_feat_context("FEAT-TEST-001")
    def illegal_commit():
        db.session.commit()

    with pytest.raises(FEATContextError) as excinfo:
        illegal_commit()
    assert "MANDATORY FEAT ATOMICITY VIOLATION (COMMIT)" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# FEAT execution-boundary guard: exactly one FEAT per request (INV-ARC-000 §VIII.2,
# INV-ARC-021 §V.2). Nesting a business FEAT inside another is forbidden regardless
# of feat_name or correlation-ID equality/formatting.
# --------------------------------------------------------------------------- #

from app.feats.base import FEATContext


def test_boundary__same_correlation_nested_different_feat_fails(app):
    with app.app_context():
        with FEATContext("FEAT-OBL-001", correlation_id="corr_x", idempotency_key="k:1"):
            with pytest.raises(FEATContextError, match="Nested FEAT context forbidden"):
                with FEATContext("FEAT-OBL-002", correlation_id="corr_x", idempotency_key="k:2"):
                    pass


def test_boundary__different_correlation_nested_different_feat_fails(app):
    with app.app_context():
        with FEATContext("FEAT-OBL-001", correlation_id="corr_a", idempotency_key="k:1"):
            with pytest.raises(FEATContextError, match="Nested FEAT context forbidden"):
                with FEATContext("FEAT-OBL-003", correlation_id="corr_b", idempotency_key="k:2"):
                    pass


def test_boundary__same_feat_nesting_fails(app):
    with app.app_context():
        with FEATContext("FEAT-OBL-001", correlation_id="corr_x", idempotency_key="k:1"):
            with pytest.raises(FEATContextError, match="Nested FEAT context forbidden"):
                with FEATContext("FEAT-OBL-001", correlation_id="corr_x", idempotency_key="k:1"):
                    pass


def test_boundary__correlation_prefix_normalization_cannot_permit_nesting(app):
    with app.app_context():
        with FEATContext("FEAT-OBL-001", correlation_id="feat:x", idempotency_key="k:1"):
            with pytest.raises(FEATContextError, match="Nested FEAT context forbidden"):
                with FEATContext("FEAT-OBL-002", correlation_id="corr_feat:x", idempotency_key="k:2"):
                    pass
        with FEATContext("FEAT-OBL-001", correlation_id="corr_feat:y", idempotency_key="k:1"):
            with pytest.raises(FEATContextError, match="Nested FEAT context forbidden"):
                with FEATContext("FEAT-OBL-003", idempotency_key="k:2"):
                    pass
