import pytest
from app.feats.base import InvariantViolation
from app.extensions import db
from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import create_class_scope
from app.models import ClassFeature, Seat
from tests.helpers.canonical_session import set_canonical_context


def test_payroll_scope_missing_class_id_raises_invariant(client):
    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        from flask import session
        session.clear()

        # Invoking the helper directly proves class_id is required
        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request()

        assert "Missing canonical class_id context" in str(excinfo.value)


def test_payroll_scope_missing_seat_id_raises_invariant(client):
    teacher = make_admin("teacher_no_seat", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_scope = create_class_scope(
        teacher=teacher,
        display_name="No Seat Class",
        create_teacher_membership=False,
    )
    db.session.commit()

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        from flask import session
        teacher_seat = Seat.query.filter_by(class_id=class_scope.class_id, role="teacher").first()
        assert teacher_seat is not None
        set_canonical_context(
            session,
            user_id=teacher_seat.user_id,
            class_id=class_scope.class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )

        # Invoking the helper directly proves seat_id is required
        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request()

        assert "Missing canonical seat_id context" in str(excinfo.value)


def test_payroll_scope_seat_not_found_raises_invariant(client):
    teacher = make_admin("teacher_invalid_seat", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_scope = create_class_scope(
        teacher=teacher,
        display_name="Invalid Seat Class",
        create_teacher_membership=False,
    )
    db.session.commit()

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        from flask import session
        set_canonical_context(
            session,
            user_id=teacher.id,
            class_id=class_scope.class_id,
            seat_id=999999,
            role="teacher",
        )

        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request()

        assert "Seat not found for seat_id=999999" in str(excinfo.value)


def test_payroll_scope_seat_class_mismatch_raises_invariant(client):
    teacher = make_admin("teacher_mismatch", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_a = create_class_scope(teacher=teacher, display_name="Class A")
    class_b = create_class_scope(teacher=teacher, display_name="Class B")
    db.session.commit()

    seat_a = Seat.query.filter_by(role='teacher', class_id=class_a.class_id).first()
    assert seat_a is not None

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        from flask import session
        set_canonical_context(
            session,
            user_id=teacher.id,
            class_id=class_b.class_id,
            seat_id=seat_a.id,
            role="teacher",
        )

        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request()

        assert "Seat class mismatch" in str(excinfo.value)


def test_payroll_scope_student_seat_insufficient_authority(client):
    teacher = make_admin("teacher_student_seat", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_scope = create_class_scope(teacher=teacher, display_name="Class A")

    # Create a student seat in this class
    student_seat = Seat(
        class_id=class_scope.class_id,
        role='student',
    )
    db.session.add(student_seat)
    db.session.commit()

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        from flask import session
        set_canonical_context(
            session,
            user_id=teacher.user_id,
            class_id=class_scope.class_id,
            seat_id=student_seat.id,
            role="student",
        )

        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request()

        assert "Insufficient authority" in str(excinfo.value)


def test_payroll_scope_resolves_active_teacher_seat(client):
    teacher = make_admin("teacher_two_seats", "secret")
    db.session.add(teacher)
    db.session.flush()

    class_a = create_class_scope(teacher=teacher, display_name="Class A")
    class_b = create_class_scope(teacher=teacher, display_name="Class B")

    db.session.commit()

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        from flask import session
        session['admin_id'] = teacher.id
        session['is_admin'] = True
        # Retrieve the seat_a for class_a to pass/mock in the session
        seat_a = Seat.query.filter_by(role='teacher', class_id=class_a.class_id).first()
        assert seat_a is not None
        set_canonical_context(
            session,
            user_id=teacher.user_id,
            class_id=class_a.class_id,
            seat_id=seat_a.id,
            role="teacher",
        )

        # Call the helper
        scope = _require_payroll_feature_scope_from_request()

        assert scope["teacher_seat"].id == seat_a.id
        assert scope["teacher_seat"].class_id == class_a.class_id
