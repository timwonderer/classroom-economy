from tests.helpers.support_domain import initialize_support_teacher


def test_DOM_SUP_001__announcement_create_uses_class_id_scope(client):
    initialize_support_teacher("chemistry_p1", client, client.application)

    response = client.get("/admin/announcements/create")

    assert response.status_code == 200
    assert b'name="class_id"' in response.data
    assert b'name="periods"' not in response.data
