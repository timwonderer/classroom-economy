import pytest
from app.feats.base import InvariantViolation
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


def test_DOM_IDEN_006__payroll_scope_missing_class_id_raises_invariant(client):
    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        from flask import session
        session.clear()

        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request()

        assert "Missing canonical class_id context" in str(excinfo.value)


def test_DOM_IDEN_006__payroll_scope_missing_seat_id_raises_invariant(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request(classroom.class_id)

        assert "Missing canonical seat_id context" in str(excinfo.value)


def test_DOM_IDEN_006__payroll_scope_seat_not_found_raises_invariant(client):
    classroom = initialize("chemistry_p1", client.application)

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request(classroom.class_id, 999999)

        assert "Seat not found for seat_id=999999" in str(excinfo.value)


def test_DOM_IDEN_006__payroll_scope_seat_class_mismatch_raises_invariant(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    seat_a = class_a.teacher_seat
    assert seat_a is not None

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request(class_b.class_id, seat_a.id)

        assert "Seat class mismatch" in str(excinfo.value)


def test_DOM_IDEN_006__payroll_scope_student_seat_insufficient_authority(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    student_seat = classroom.students[0].seat

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment?block=1'):
        with pytest.raises(InvariantViolation) as excinfo:
            _require_payroll_feature_scope_from_request(classroom.class_id, student_seat.id)

        assert "Insufficient authority" in str(excinfo.value)


def test_DOM_IDEN_006__payroll_scope_resolves_active_teacher_seat(client):
    class_a = initialize_as_teacher("chemistry_p1", client, client.application)
    class_b = initialize("biology_block_a", client.application)

    from app.routes.admin import _require_payroll_feature_scope_from_request

    with client.application.test_request_context('/admin/payroll/manual-payment'):
        seat_a = class_a.teacher_seat
        scope = _require_payroll_feature_scope_from_request(class_a.class_id, seat_a.id)

        assert scope["teacher_seat"].id == seat_a.id
        assert scope["teacher_seat"].class_id == class_a.class_id
