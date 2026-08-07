from tests.helpers.classroom_initializer import initialize
from tests.dom.identity.helpers import student_get_dashboard, student_login_next


def test_DOM_IDEN_006__student_login_next_redirect(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)
    classroom = initialize("chemistry_p1", client.application)
    student = classroom.students[0]

    # Access protected route while unauthenticated
    resp = student_get_dashboard(client)
    assert resp.status_code == 302
    assert '/student/login' in resp.headers['Location']
    assert '/student/dashboard' in resp.headers['Location']

    # Login with next parameter and expect redirect back
    login_resp = student_login_next(client, username=student.username, pin=student.pin, next_path="/student/dashboard")
    assert login_resp.status_code == 302
    assert login_resp.headers['Location'].endswith('/student/dashboard')
