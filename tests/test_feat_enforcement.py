import pytest
from app.extensions import db
from app.models import User, UserRole, ClassEconomy
from app.feats.base import FEATContextError, requires_feat_context, is_feat_active
from tests.helpers.class_scope import make_student_identity

@pytest.mark.enforce_feat
def test_commit_fails_outside_feat_context(app):
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
def test_flush_fails_outside_feat_context(app):
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
def test_commit_succeeds_inside_feat_context(app):
    """
    CONFIRM: Mutations are permitted in FEAT context without direct commit.
    """
    teacher = User(user_role=UserRole.TEACHER, username_hash="feat_test_teacher_unique")
    db.session.add(teacher)
    # Need a FEAT context just to flush the teacher
    from app.feats.base import FEATContext
    with FEATContext("FEAT-TEST-001"):
        db.session.flush()
    class_row = ClassEconomy(user_id=teacher.id, join_code="FEAT-TEST-CLS")
    db.session.add(class_row)
    with FEATContext("FEAT-TEST-002"):
        db.session.flush()

    @requires_feat_context("FEAT-TEST-001")
    def legal_mutation():
        stu = make_student_identity(class_id=class_row.class_id, first_name="Legal", last_name="M")
        db.session.flush()
        return stu

    stu = legal_mutation()
    assert stu.id is not None
    assert is_feat_active() is False # Should be cleared after exit

@pytest.mark.enforce_feat
def test_nested_feat_context(app):
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
def test_direct_commit_inside_feat_context_is_blocked(app):
    """
    CONFIRM: Only FEAT orchestrator boundary can commit.
    """
    @requires_feat_context("FEAT-TEST-001")
    def illegal_commit():
        db.session.commit()

    with pytest.raises(FEATContextError) as excinfo:
        illegal_commit()
    assert "MANDATORY FEAT ATOMICITY VIOLATION (COMMIT)" in str(excinfo.value)
