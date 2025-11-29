"""Tests for attendance log filter dropdowns."""
import pytest
import pyotp
from app import app, db
from app.models import Admin, Student, TapEvent, StudentTeacher


@pytest.fixture
def client():
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
    )
    ctx = app.app_context()
    ctx.push()
    db.create_all()
    client = app.test_client()
    yield client
    db.drop_all()
    ctx.pop()


def test_attendance_log_includes_period_and_block_filters(client):
    """Test that the attendance log page includes periods and blocks for filters."""
    # Create test admin
    totp_secret = pyotp.random_base32()
    admin = Admin(username='testadmin', totp_secret=totp_secret)
    db.session.add(admin)
    db.session.commit()
    admin_id = admin.id

    # Create test students with different blocks
    s1 = Student(
        first_name='John', last_initial='D', teacher_id=admin_id, block='A', 
        salt=b'salt1234567890ab', has_completed_setup=True
    )
    s2 = Student(
        first_name='Jane', last_initial='S', teacher_id=admin_id, block='B', 
        salt=b'salt1234567890cd', has_completed_setup=True
    )
    s3 = Student(
        first_name='Bob', last_initial='W', teacher_id=admin_id, block='A,C', 
        salt=b'salt1234567890ef', has_completed_setup=True
    )
    db.session.add_all([s1, s2, s3])
    db.session.commit()

    # Link students to admin via StudentTeacher
    for s in [s1, s2, s3]:
        link = StudentTeacher(student_id=s.id, admin_id=admin_id)
        db.session.add(link)
    db.session.commit()

    # Create test TapEvents with different periods
    tap1 = TapEvent(student_id=s1.id, period='Period 1', status='active')
    tap2 = TapEvent(student_id=s1.id, period='Period 2', status='inactive')
    tap3 = TapEvent(student_id=s2.id, period='Period 1', status='active')
    tap4 = TapEvent(student_id=s3.id, period='Period 3', status='inactive')
    db.session.add_all([tap1, tap2, tap3, tap4])
    db.session.commit()

    # Log in as admin
    with client.session_transaction() as session:
        session['admin_id'] = admin_id
        session['is_admin'] = True
        session['is_system_admin'] = False

    # Request the attendance log page
    response = client.get('/admin/attendance-log')
    assert response.status_code == 200

    html = response.data.decode('utf-8')

    # Verify periods appear in the filter dropdown options
    assert 'Period 1' in html, "Period 1 should appear in filter options"
    assert 'Period 2' in html, "Period 2 should appear in filter options"
    assert 'Period 3' in html, "Period 3 should appear in filter options"

    # Verify blocks appear in the filter dropdown options
    assert '>A</option>' in html or 'value="A"' in html, "Block A should appear in filter options"
    assert '>B</option>' in html or 'value="B"' in html, "Block B should appear in filter options"
    assert '>C</option>' in html or 'value="C"' in html, "Block C should appear in filter options"


def test_attendance_log_empty_periods_and_blocks(client):
    """Test that the attendance log page works when there are no periods or blocks."""
    # Create test admin
    totp_secret = pyotp.random_base32()
    admin = Admin(username='emptytest', totp_secret=totp_secret)
    db.session.add(admin)
    db.session.commit()
    admin_id = admin.id

    # Log in as admin
    with client.session_transaction() as session:
        session['admin_id'] = admin_id
        session['is_admin'] = True
        session['is_system_admin'] = False

    # Request the attendance log page
    response = client.get('/admin/attendance-log')
    assert response.status_code == 200

    html = response.data.decode('utf-8')

    # Verify the page renders without errors
    assert 'Attendance History' in html
    assert 'All Periods' in html  # Default option should be present
    assert 'All Blocks' in html   # Default option should be present
