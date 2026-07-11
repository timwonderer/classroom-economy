from datetime import datetime, timezone


def test_admin_required_blocks_missing_identity(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    response = client.get("/admin/students", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/login" in response.headers.get("Location", "")
