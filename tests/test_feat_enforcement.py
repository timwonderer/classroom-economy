import pytest
from app.extensions import db
from app.models import User, UserRole
from app.feats.base import FEATContextError, requires_feat_context, is_feat_active
from tests.helpers.class_scope import make_student_identity

def test_commit_fails_outside_feat_context(app):
    """
    CONFIRM: No mutation until a FEAT context is established.
    This is the core architectural safeguard.
    """
    stu = make_student_identity(block="A", first_name="Illegal", last_name="M")
    db.session.add(stu)
    
    with pytest.raises(FEATContextError) as excinfo:
        db.session.commit()
    
    assert "MANDATORY FEAT CONSTITUTIONAL VIOLATION (COMMIT)" in str(excinfo.value)
    db.session.rollback()

def test_flush_fails_outside_feat_context(app):
    """
    CONFIRM: No SQL emission (flush) until a FEAT context is established.
    """
    stu = make_student_identity(block="A", first_name="IllegalFlush", last_name="M")
    db.session.add(stu)
    
    with pytest.raises(FEATContextError) as excinfo:
        db.session.flush()
    
    assert "MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH)" in str(excinfo.value)
    db.session.rollback()

def test_commit_succeeds_inside_feat_context(app):
    """
    CONFIRM: Mutations are permitted in FEAT context without direct commit.
    """
    @requires_feat_context("FEAT-TEST-001")
    def legal_mutation():
        stu = make_student_identity(block="A", first_name="Legal", last_name="M")
        db.session.add(stu)
        db.session.flush()
        return stu

    stu = legal_mutation()
    assert stu.id is not None
    assert is_feat_active() is False # Should be cleared after exit

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

def test_feat_bypass_fails_in_production(app, monkeypatch):
    """
    CONFIRM: FEATBypass is strictly prohibited in production.
    """
    from app.feats.base import FEATBypass
    monkeypatch.setenv("FLASK_ENV", "production")
    
    with pytest.raises(FEATContextError) as excinfo:
        with FEATBypass():
            pass
    
    assert "strictly prohibited in PRODUCTION" in str(excinfo.value)

def test_feat_bypass_logs_warning(app, caplog):
    """
    CONFIRM: FEATBypass emits a warning log.
    """
    from app.feats.base import FEATBypass
    import logging
    
    with caplog.at_level(logging.WARNING):
        with FEATBypass():
            pass
    
    assert "FEAT-INTEGRITY-WARNING" in caplog.text
