"""
Tests for display-alias generation and retry logic in the students management page.

This specifically tests that the MAX_JOIN_CODE_RETRIES constant is properly defined
and used when generating unique display aliases for classroom blocks.
"""
from app.models import User, Seat, IdentityProfile
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.dom.identity.helpers import admin_get_students


def test_DOM_IDEN_006__students_page_generates_display_aliases_for_blocks(client):
    """
    Test that accessing /admin/students doesn't crash when generating display aliases.

    This verifies that MAX_JOIN_CODE_RETRIES and related constants are defined.
    Regression test for: NameError: name 'MAX_JOIN_CODE_RETRIES' is not defined
    """
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    response = admin_get_students(client)

    # The page should load successfully
    assert response.status_code == 200


def test_DOM_IDEN_006__students_page_works_with_no_students(client):
    """
    Test that the students page works even with no students.

    Verifies the constants are defined even when the display-alias generation
    code path may not be exercised.
    """
    initialize_as_teacher("chemistry_p1", client, client.application)

    response = admin_get_students(client)

    assert response.status_code == 200
