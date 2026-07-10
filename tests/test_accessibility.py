"""
Automated accessibility tests for Classroom Token Hub.
Uses BeautifulSoup to audit rendered HTML against core WCAG 2.1 Level AA principles.
"""

import pytest
from bs4 import BeautifulSoup


def audit_html_accessibility(html_content):
    """
    Core accessibility auditor running static checks on rendered HTML.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Page Title (WCAG 2.4.2)
    title_tag = soup.find('title')
    assert title_tag is not None, "Page is missing a <title> element."
    title_text = title_tag.get_text(strip=True)
    assert len(title_text) > 0, "<title> element is empty."
    assert "placeholder" not in title_text.lower(), "Page title contains placeholder text."

    # 2. Image Alt Text (WCAG 1.1.1)
    for img in soup.find_all('img'):
        assert img.has_attr('alt'), f"Image missing 'alt' attribute: {img}"

    # 3. Accessible Links and Buttons (WCAG 2.4.4)
    # Check that interactive controls have accessible names/text
    for a in soup.find_all('a'):
        # Ignore links that are empty anchors or purely used for javascript hooks
        if not a.has_attr('href') and not a.has_attr('role'):
            continue
        
        # Check text content or aria-label or title
        text = a.get_text(strip=True)
        has_accessible_name = (
            len(text) > 0 or 
            a.has_attr('aria-label') or 
            a.has_attr('aria-labelledby') or 
            a.has_attr('title') or
            # Or if it contains a child with alternative text
            bool(a.find('img', alt=lambda x: x and len(x.strip()) > 0))
        )
        assert has_accessible_name, f"Link missing accessible name: {a}"

    for button in soup.find_all('button'):
        # Strip Material Symbols icon ligature text (e.g. 'more_vert', 'close') which
        # render as icon glyphs — they are NOT meaningful accessible names for screen readers.
        import re as _re
        raw_text = button.get_text(strip=True)
        # Remove spans that are purely material icon ligatures (single snake_case word)
        visible_text = raw_text
        for icon_span in button.find_all('span', class_=lambda c: c and 'material-symbols' in ' '.join(c)):
            visible_text = visible_text.replace(icon_span.get_text(strip=True), '')
        visible_text = visible_text.strip()
        has_accessible_name = (
            len(visible_text) > 0 or
            button.has_attr('aria-label') or
            button.has_attr('aria-labelledby') or
            button.has_attr('title') or
            # Or if it contains an image with alt text
            bool(button.find('img', alt=lambda x: x and len(x.strip()) > 0))
        )
        assert has_accessible_name, f"Button missing accessible name: {button}"

    # 4. Form Labels (WCAG 1.3.1)
    # Every input, select, and textarea should have an associated label or aria description
    for control_type in ['input', 'select', 'textarea']:
        for control in soup.find_all(control_type):
            # Ignore hidden inputs, submit buttons, checkboxes/radios handled otherwise
            if control.get('type') in ['hidden', 'submit', 'button', 'image']:
                continue

            control_id = control.get('id')
            has_label = False

            # Check if there is a <label> targeting this control's ID
            if control_id:
                label = soup.find('label', attrs={'for': control_id})
                if label:
                    has_label = True

            # Check if nested inside a <label>
            if not has_label:
                parent = control.parent
                while parent:
                    if parent.name == 'label':
                        has_label = True
                        break
                    parent = parent.parent

            # Check if there's aria-label or aria-labelledby
            if not has_label:
                if control.has_attr('aria-label') or control.has_attr('aria-labelledby'):
                    has_label = True

            # NOTE: placeholder is intentionally NOT accepted as a label substitute.
            # WCAG 1.3.1 requires an explicit <label>, aria-label, or aria-labelledby.
            # Placeholder text disappears when the user types and is insufficient for
            # screen readers as a persistent accessible name.

            assert has_label, f"Form control <{control_type}> missing associated label or ARIA identifier: {control}"

    # 5. Unique ID Attributes (WCAG 4.1.1)
    ids = [el.get('id') for el in soup.find_all(id=True)]
    duplicates = set([x for x in ids if ids.count(x) > 1])
    assert not duplicates, f"Duplicate ID attributes found on page: {duplicates}"

    # 6. Logical Heading Structure (WCAG 1.3.1)
    # (a) Every page must have exactly one h1.
    # (b) Headings must not skip levels downwards (e.g. h1 to h3).
    headings = []
    for el in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        headings.append(int(el.name[1]))

    h1_count = headings.count(1)
    assert h1_count >= 1, "Page has no <h1> element. Every page must have a top-level heading."
    assert h1_count == 1, f"Page has {h1_count} <h1> elements. There must be exactly one <h1> per page."

    for i in range(1, len(headings)):
        prev_level = headings[i-1]
        curr_level = headings[i]
        # Skipping level downwards is a violation (e.g. h1 -> h3). Going back up (e.g. h3 -> h1 or h2) is fine.
        assert curr_level <= prev_level + 1, (
            f"Heading levels skip from h{prev_level} directly to h{curr_level}."
        )


def test_privacy_page_accessibility(client):
    """Test accessibility of the Privacy Policy page."""
    response = client.get('/privacy')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_district_page_accessibility(client):
    """Test accessibility of the District Information page."""
    response = client.get('/district')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_offline_page_accessibility(client):
    """Test accessibility of the Offline fallback page."""
    response = client.get('/offline')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_docs_page_accessibility(client):
    """Test accessibility of the documentation landing page."""
    response = client.get('/docs/')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


# ==============================================================================
# Authenticated Accessibility Tests
# ==============================================================================
from datetime import datetime, timezone
from tests.helpers.canonical_session import set_canonical_context
from app.extensions import db
from app.models import ClassEconomy, Seat, IdentityProfile, RentSettings, User, TeacherOnboarding
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.v2_fixtures import make_admin
from app.hash_utils import hash_username
from app.utils.auth_username import build_hashed_username_fields
from werkzeug.security import generate_password_hash


@pytest.fixture
def auth_student_context(app, client):
    """Sets up a V2 student and class context, and logs them in."""
    with app.app_context():
        teacher = make_admin("access_teacher_s")
        db.session.flush()

        join_code = "ACCESST1"
        class_row = create_class_scope(
            teacher=teacher,
            join_code=join_code,
            block="A",
            display_name="A Period",
        )
        student_user = User(
            username_hash="access_student_hash",
            username_lookup_hash="access_student_lookup",
            password_hash=generate_password_hash("secret"),
            pin_hash=generate_password_hash("1234"),
            user_role="student",
            has_completed_setup=True,
            last_active_class_id=class_row.class_id,
        )
        db.session.add(student_user)
        db.session.flush()

        seat = make_student_identity(
            class_id=class_row.class_id,
            user_id=student_user.id,
            block="A",
            claimed=True,
            first_name="Accessibility",
            last_name="S",
        )
        student_user.last_active_seat_id = seat.id
        student_user.current_session_nonce = "accessibility-nonce"
        db.session.flush()
        
        rent_settings = RentSettings(
            class_id=class_row.class_id,
            block="A",
            is_enabled=True,
        )
        db.session.add(rent_settings)
        from app.models import ClassFeature
        for feat in ClassFeature.feature_names():
            exists = ClassFeature.query.filter_by(class_id=class_row.class_id, feature_name=feat).first()
            if not exists:
                db.session.add(ClassFeature(class_id=class_row.class_id, feature_name=feat))
        db.session.commit()

        student_id = student_user.id
        class_id = class_row.class_id
        user_id = student_user.id
        seat_id = seat.id

    # Log in student
    with client.session_transaction() as sess:
        sess["current_session_nonce"] = "accessibility-nonce"
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
        set_canonical_context(
            sess,
            user_id=user_id,
            class_id=class_id,
            seat_id=seat_id,
            role="student",
            join_code=join_code,
        )
        
    return {
        "student_id": student_id,
        "class_id": class_id,
        "join_code": join_code,
    }


@pytest.fixture
def auth_teacher_context(app, client):
    """Sets up a V2 teacher and logs them in."""
    with app.app_context():
        teacher = make_admin("access_teacher_t")
        db.session.flush()

        join_code = "ACCESST2"
        class_row = create_class_scope(
            teacher=teacher,
            join_code=join_code,
            block="A",
            display_name="A Period",
        )

        # Mark onboarding as completed for this teacher
        onboarding = TeacherOnboarding(
            user_id=teacher.id,
            is_completed=True,
            completed_at=datetime.now(timezone.utc)
        )
        db.session.add(onboarding)
        db.session.flush()

        teacher.has_completed_setup = True
        teacher.last_active_class_id = class_row.class_id
        from app.models import ClassFeature
        for feat in ClassFeature.feature_names():
            exists = ClassFeature.query.filter_by(class_id=class_row.class_id, feature_name=feat).first()
            if not exists:
                db.session.add(ClassFeature(class_id=class_row.class_id, feature_name=feat))
        db.session.commit()

        teacher_id = teacher.id
        class_id = class_row.class_id
        user_id = teacher.id

    # Log in teacher
    teacher_seat = Seat.query.filter_by(user_id=user_id, class_id=class_id, role="teacher").first()
    assert teacher_seat is not None

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user_id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
            join_code=join_code,
        )
        sess['admin_id'] = teacher_id
        sess['is_system_admin'] = False

    return {
        "teacher_id": teacher_id,
        "class_id": class_id,
        "join_code": join_code,
    }


def test_student_dashboard_accessibility(client, auth_student_context):
    response = client.get('/student/dashboard')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_student_transfer_accessibility(client, auth_student_context):
    response = client.get('/student/transfer')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_student_rent_accessibility(client, auth_student_context):
    response = client.get('/student/rent')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_student_shop_accessibility(client, auth_student_context):
    response = client.get('/student/shop')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_student_insurance_accessibility(client, auth_student_context):
    response = client.get('/student/insurance')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_student_help_support_accessibility(client, auth_student_context):
    response = client.get('/student/help-support')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_teacher_dashboard_accessibility(client, auth_teacher_context):
    response = client.get('/admin/')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_teacher_students_accessibility(client, auth_teacher_context):
    response = client.get('/admin/students')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_teacher_rent_settings_accessibility(client, auth_teacher_context):
    response = client.get('/admin/rent-settings')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_teacher_store_accessibility(client, auth_teacher_context):
    response = client.get('/admin/store')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))


def test_teacher_insurance_accessibility(client, auth_teacher_context):
    response = client.get('/admin/insurance')
    assert response.status_code == 200
    audit_html_accessibility(response.data.decode('utf-8'))
