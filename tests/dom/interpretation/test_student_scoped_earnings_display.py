from tests.helpers.class_domain import enable_class_feature
from tests.dom.interpretation.helpers import payroll_visibility_state


def _build_multi_class_student(client, app):
    class_a, class_g = payroll_visibility_state(client, app)
    enable_class_feature(class_id=class_a.class_id, feature_name="banking")
    student = class_a.students[0]
    return class_a, student


def test_DOM_LED_001__student_payroll_displays_class_scoped_lifetime_earnings(client, app):
    classroom, student = _build_multi_class_student(client, app)

    response = client.get("/student/payroll")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Total Lifetime Earnings" in body
    assert "$10.00" in body
    assert "$210.00" not in body


def test_DOM_LED_001__student_transfer_displays_class_scoped_total_earnings(client, app):
    classroom, student = _build_multi_class_student(client, app)

    response = client.get("/student/transfer")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Total Earnings" in body
    assert "$10.00" in body
    assert "$210.00" not in body
