from tests.helpers.classroom_initializer import initialize_as_student
from tests.dom.identity.helpers import student_help_support


def test_DOM_IDEN_006__student_help_support_page_renders(client):
    initialize_as_student("chemistry_p1", client, client.application)

    resp = student_help_support(client)

    assert resp.status_code == 200
    assert b"Student" in resp.data or b"student" in resp.data or b"Login" in resp.data
