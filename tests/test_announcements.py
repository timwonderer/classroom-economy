"""
Tests for teacher announcement feature.

Tests the Announcement model, admin routes, and student display.
Ensures proper multi-tenancy scoping by class_id, with join_code retained as display metadata.
"""
from tests.helpers.v2_fixtures import seed_canonical_admin
from tests.helpers.admin_context import login_teacher
from tests.helpers.v2_fixtures import seed_class_with_seat
import pytest
import pyotp
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete as sa_delete
from app import db
from app.feats.base import FEATContext
from app.models import User, Announcement, ClassEconomy, Seat, IdentityProfile


@pytest.fixture
def test_teacher():
    """Create a test teacher with TOTP."""
    teacher = seed_canonical_admin('test_teacher_announcements').user
    db.session.flush()
    return teacher


@pytest.fixture
def teacher_block(test_teacher):
    """Create a teacher block with a display alias."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="announcements:teacher_block"):
        economy = ClassEconomy(
            join_code='TEST123',
            user_id=test_teacher.id,
            display_name='Test Announcements Class',
            status='active',
        )
        db.session.add(economy)
        db.session.flush()

        block = Seat(class_id=economy.class_id, user_id=test_teacher.id, role="teacher")
        db.session.add(block)
        db.session.flush()

        db.session.add(IdentityProfile(seat_id=block.id, profile_type='teacher_primary', first_name='encrypted_test_name', last_name='T'))
        db.session.flush()
    return block


class TestAnnouncementModel:
    """Tests for the Announcement model."""

    def test_announcement_creation(self, client, test_teacher, teacher_block):
        """Test creating an announcement."""
        announcement = Announcement(
            user_id=test_teacher.id,
            class_id=teacher_block.class_id,
            join_code=teacher_block.class_economy.join_code,
            audience_type='class',
            title='Test Announcement',
            message='This is a test message',
            priority='normal',
            is_active=True
        )
        with FEATContext("FEAT-ADMN-001", idempotency_key="announcements:create"):
            db.session.add(announcement)
            db.session.flush()

        assert announcement.id is not None
        assert announcement.title == 'Test Announcement'
        assert announcement.message == 'This is a test message'
        assert announcement.priority == 'normal'
        assert announcement.is_active is True

    def test_announcement_defaults(self, client, test_teacher, teacher_block):
        """Test announcement model defaults."""
        announcement = Announcement(
            user_id=test_teacher.id,
            class_id=teacher_block.class_id,
            join_code=teacher_block.class_economy.join_code,
            title='Test',
            message='Test message'
        )
        with FEATContext("FEAT-ADMN-001", idempotency_key="announcements:defaults"):
            db.session.add(announcement)
            db.session.flush()

        assert announcement.is_active is True
        assert announcement.priority == 'normal'
        assert announcement.expires_at is None
        assert announcement.created_at is not None

    def test_announcement_expiration(self, client, test_teacher, teacher_block):
        """Test announcement expiration logic."""
        with FEATContext("FEAT-ADMN-001", idempotency_key="announcements:expiration"):
            expired_announcement = Announcement(
                user_id=test_teacher.id,
                class_id=teacher_block.class_id,
                join_code=teacher_block.class_economy.join_code,
                title='Expired',
                message='This is expired',
                expires_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
            db.session.add(expired_announcement)

            active_announcement = Announcement(
                user_id=test_teacher.id,
                class_id=teacher_block.class_id,
                join_code=teacher_block.class_economy.join_code,
                title='Active',
                message='This is active',
                expires_at=datetime.now(timezone.utc) + timedelta(days=1)
            )
            db.session.add(active_announcement)

            no_expiry = Announcement(
                user_id=test_teacher.id,
                class_id=teacher_block.class_id,
                join_code=teacher_block.class_economy.join_code,
                title='No Expiry',
                message='Never expires'
            )
            db.session.add(no_expiry)
            db.session.flush()

        assert expired_announcement.is_expired() is True
        assert active_announcement.is_expired() is False
        assert no_expiry.is_expired() is False

    def test_announcement_should_display(self, client, test_teacher, teacher_block):
        """Test should_display method."""
        with FEATContext("FEAT-ADMN-001", idempotency_key="announcements:should_display"):
            visible = Announcement(
                user_id=test_teacher.id,
                class_id=teacher_block.class_id,
                join_code='TEST123',
                title='Visible',
                message='Should be visible',
                is_active=True
            )
            db.session.add(visible)

            inactive = Announcement(
                user_id=test_teacher.id,
                class_id=teacher_block.class_id,
                join_code='TEST123',
                title='Inactive',
                message='Should not be visible',
                is_active=False
            )
            db.session.add(inactive)

            expired = Announcement(
                user_id=test_teacher.id,
                class_id=teacher_block.class_id,
                join_code='TEST123',
                title='Expired',
                message='Should not be visible',
                is_active=True,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
            db.session.add(expired)
            db.session.flush()

        assert visible.should_display() is True
        assert inactive.should_display() is False
        assert expired.should_display() is False

    def test_announcement_priority_classes(self, client, test_teacher, teacher_block):
        """Test priority CSS classes and icons."""
        priorities = ['low', 'normal', 'high', 'urgent']
        expected_classes = ['alert-secondary', 'alert-info', 'alert-warning', 'alert-danger']
        expected_icons = ['push_pin', 'campaign', 'warning', 'error']

        for priority, expected_class, expected_icon in zip(priorities, expected_classes, expected_icons):
            announcement = Announcement(
                user_id=test_teacher.id,
                class_id=teacher_block.class_id,
                join_code='TEST123',
                title=f'{priority} priority',
                message='Test',
                priority=priority
            )
            with FEATContext("FEAT-ADMN-001", idempotency_key=f"announcements:priority:{priority}"):
                db.session.add(announcement)
                db.session.flush()

            assert announcement.get_priority_class() == expected_class
            assert announcement.get_priority_icon() == expected_icon


class TestAnnouncementMultiTenancy:
    """Tests for announcement multi-tenancy scoping."""

    def test_announcements_scoped_by_class_id(self, client, test_teacher):
        """Test that announcements are properly scoped by class_id."""
        economy_a = ClassEconomy(
            join_code='TESTA',
            user_id=test_teacher.id,
            display_name='Class A',
            status='active',
        )
        economy_b = ClassEconomy(
            join_code='TESTB',
            user_id=test_teacher.id,
            display_name='Class B',
            status='active',
        )
        with FEATContext("FEAT-IDEN-001", idempotency_key="announcements:multi_tenancy"):
            db.session.add(economy_a)
            db.session.add(economy_b)
            db.session.flush()

        announcement_a = Announcement(
            user_id=test_teacher.id,
            class_id=economy_a.class_id,
            join_code='TESTA',
            title='Announcement for Block A',
            message='Only Block A should see this',
            is_active=True
        )
        announcement_b = Announcement(
            user_id=test_teacher.id,
            class_id=economy_b.class_id,
            join_code='TESTB',
            title='Announcement for Block B',
            message='Only Block B should see this',
            is_active=True
        )
        with FEATContext("FEAT-ADMN-001", idempotency_key="announcements:multi_tenancy_create"):
            db.session.add(announcement_a)
            db.session.add(announcement_b)
            db.session.flush()

        announcements_a = Announcement.query.filter_by(is_active=True, class_id=economy_a.class_id).all()
        announcements_b = Announcement.query.filter_by(is_active=True, class_id=economy_b.class_id).all()

        assert len(announcements_a) == 1
        assert announcements_a[0].title == 'Announcement for Block A'

        assert len(announcements_b) == 1
        assert announcements_b[0].title == 'Announcement for Block B'

    def test_announcement_cascade_delete(self, client_with_fk, test_teacher, teacher_block):
        """Test that announcements are deleted when teacher is deleted."""
        announcement = Announcement(
            user_id=test_teacher.id,
            class_id=teacher_block.class_id,
            join_code='TEST123',
            title='Test Announcement',
            message='This should be deleted with teacher',
            is_active=True
        )
        with FEATContext("FEAT-ADMN-001", idempotency_key="announcements:cascade"):
            db.session.add(announcement)
            db.session.flush()

        announcement_id = announcement.id

        with FEATContext("FEAT-IDEN-001", idempotency_key="announcements:delete_teacher"):
            db.session.execute(sa_delete(User).where(User.id == test_teacher.id))
            db.session.flush()

        remaining = Announcement.query.filter_by(id=announcement_id).count()
        assert remaining == 0


def test_announcement_create_uses_class_id_scope(client):
    teacher = seed_canonical_admin("announcements_create_route").user
    db.session.flush()
    class_row = seed_class_with_seat(
        teacher=teacher,
        join_code="ANN123",
        display_name="Announcements",
        section="A",
    ).class_row
    login_teacher(client, teacher, class_id=class_row.class_id)

    response = client.get("/admin/announcements/create")

    assert response.status_code == 200
    assert b'name="class_id"' in response.data
    assert b'name="periods"' not in response.data
