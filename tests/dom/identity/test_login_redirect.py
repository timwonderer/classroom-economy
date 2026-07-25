from tests.helpers.classroom_initializer import initialize_as_student
from tests.dom.identity.helpers import student_get_dashboard, student_login_next

def test_DOM_IDEN_006__student_login_next_redirect(client):
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)

    # Access protected route
    resp = student_get_dashboard(client)
    assert resp.status_code == 302
    assert resp.headers['Location'].startswith('/student/login')
    assert '/student/dashboard' in resp.headers['Location']

    # Login and expect redirect back
    login_resp = student_login_next(client, username=student.username, pin=student.pin, next_path="/student/dashboard")
    assert login_resp.status_code == 302
    assert login_resp.headers['Location'].endswith('/student/dashboard')
