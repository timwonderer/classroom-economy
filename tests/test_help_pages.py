from app import db
from app.models import Admin
from datetime import datetime, timezone

def test_admin_help_page(client):
    # Create admin
    admin = Admin(username='admin', totp_secret='base32secret3232')
    db.session.add(admin)
    db.session.commit()

    # Login as admin
    with client.session_transaction() as sess:
        sess["admin_id"] = admin.id
        sess["is_admin"] = True

    resp = client.get("/admin/help-support")
    if resp.status_code != 200:
        print(resp.data) # Debug info
    assert resp.status_code == 200
    assert b"Knowledge Base" in resp.data
    assert b"Report an Issue" in resp.data

def test_student_help_page(client, test_student):
    # Login as student
    with client.session_transaction() as sess:
        sess["student_id"] = test_student.id
        # Use current time in UTC
        now = datetime.now(timezone.utc).isoformat()
        sess['login_time'] = now
        sess['last_activity'] = now

    resp = client.get("/student/help-support")
    if resp.status_code != 200:
        print(resp.data)
    assert resp.status_code == 200
    assert b"Knowledge Base" in resp.data
    assert b"Report an Issue" in resp.data
