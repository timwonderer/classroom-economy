"""
Tests for feature settings and teacher onboarding functionality.
"""
import pytest
from app import app, db
from app.models import Admin, FeatureSettings, TeacherOnboarding


@pytest.fixture
def test_admin():
    """Create a test admin for feature settings tests."""
    import pyotp
    admin = Admin(
        username='test_teacher',
        totp_secret=pyotp.random_base32(),
    )
    db.session.add(admin)
    db.session.commit()
    return admin


class TestFeatureSettings:
    """Tests for the FeatureSettings model and routes."""

    def test_feature_settings_model_defaults(self, client, test_admin):
        """Test that FeatureSettings has correct defaults."""
        settings = FeatureSettings(teacher_id=test_admin.id, block=None)
        db.session.add(settings)
        db.session.commit()

        assert settings.payroll_enabled is True
        assert settings.insurance_enabled is True
        assert settings.banking_enabled is True
        assert settings.rent_enabled is True
        assert settings.hall_pass_enabled is True
        assert settings.store_enabled is True
        assert settings.bug_reports_enabled is True
        assert settings.bug_rewards_enabled is True

    def test_feature_settings_to_dict(self, client, test_admin):
        """Test the to_dict method returns all features."""
        settings = FeatureSettings(
            teacher_id=test_admin.id,
            block='A',
            payroll_enabled=True,
            insurance_enabled=False,
            banking_enabled=True,
            rent_enabled=False,
            hall_pass_enabled=True,
            store_enabled=True,
            bug_reports_enabled=False,
            bug_rewards_enabled=True,
        )
        db.session.add(settings)
        db.session.commit()

        settings_dict = settings.to_dict()
        assert settings_dict['payroll_enabled'] is True
        assert settings_dict['insurance_enabled'] is False
        assert settings_dict['rent_enabled'] is False
        assert settings_dict['bug_reports_enabled'] is False

    def test_feature_settings_per_period(self, client, test_admin):
        """Test that different periods can have different settings."""
        # Create global settings
        global_settings = FeatureSettings(
            teacher_id=test_admin.id,
            block=None,
            payroll_enabled=True,
            rent_enabled=True,
        )
        db.session.add(global_settings)

        # Create period A settings with different values
        period_a_settings = FeatureSettings(
            teacher_id=test_admin.id,
            block='A',
            payroll_enabled=True,
            rent_enabled=False,  # Different from global
        )
        db.session.add(period_a_settings)

        # Create period B settings with different values
        period_b_settings = FeatureSettings(
            teacher_id=test_admin.id,
            block='B',
            payroll_enabled=False,  # Different from global
            rent_enabled=True,
        )
        db.session.add(period_b_settings)

        db.session.commit()

        # Verify each period has its own settings
        settings_a = FeatureSettings.query.filter_by(
            teacher_id=test_admin.id, block='A'
        ).first()
        settings_b = FeatureSettings.query.filter_by(
            teacher_id=test_admin.id, block='B'
        ).first()

        assert settings_a.rent_enabled is False
        assert settings_b.rent_enabled is True
        assert settings_a.payroll_enabled is True
        assert settings_b.payroll_enabled is False

    def test_unique_constraint_teacher_block(self, client, test_admin):
        """Test that duplicate teacher-block combinations are prevented."""
        settings1 = FeatureSettings(teacher_id=test_admin.id, block='A')
        db.session.add(settings1)
        db.session.commit()

        # Try to add another settings for the same teacher-block
        settings2 = FeatureSettings(teacher_id=test_admin.id, block='A')
        db.session.add(settings2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db.session.commit()

        db.session.rollback()


class TestTeacherOnboarding:
    """Tests for the TeacherOnboarding model."""

    def test_onboarding_model_defaults(self, client, test_admin):
        """Test that TeacherOnboarding has correct defaults."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        assert onboarding.is_completed is False
        assert onboarding.is_skipped is False
        assert onboarding.current_step == 1
        assert onboarding.total_steps == 5
        assert onboarding.steps_completed == {}

    def test_mark_step_completed(self, client, test_admin):
        """Test marking steps as completed."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.mark_step_completed('welcome')
        onboarding.mark_step_completed('features')
        db.session.commit()

        assert onboarding.is_step_completed('welcome') is True
        assert onboarding.is_step_completed('features') is True
        assert onboarding.is_step_completed('periods') is False

    def test_complete_onboarding(self, client, test_admin):
        """Test completing onboarding."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.complete_onboarding()
        db.session.commit()

        assert onboarding.is_completed is True
        assert onboarding.completed_at is not None

    def test_skip_onboarding(self, client, test_admin):
        """Test skipping onboarding."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.skip_onboarding()
        db.session.commit()

        assert onboarding.is_skipped is True
        assert onboarding.skipped_at is not None

    def test_needs_onboarding_property(self, client, test_admin):
        """Test the needs_onboarding property."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        # Initially needs onboarding
        assert onboarding.needs_onboarding is True

        # After completion, no longer needs it
        onboarding.complete_onboarding()
        db.session.commit()
        assert onboarding.needs_onboarding is False

    def test_unique_teacher_onboarding(self, client, test_admin):
        """Test that each teacher can only have one onboarding record."""
        onboarding1 = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding1)
        db.session.commit()

        # Try to add another onboarding for the same teacher
        onboarding2 = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db.session.commit()

        db.session.rollback()


class TestFeatureSettingsRoutes:
    """Tests for feature settings routes."""

    def test_feature_settings_page_requires_login(self, client):
        """Test that feature settings page requires admin login."""
        response = client.get('/admin/feature-settings')
        assert response.status_code == 302  # Redirect to login

    def test_feature_settings_page_accessible_when_logged_in(self, client, test_admin):
        """Test that feature settings page is accessible when logged in."""
        with client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_id'] = test_admin.id

        response = client.get('/admin/feature-settings')
        assert response.status_code == 200


class TestOnboardingRoutes:
    """Tests for onboarding routes."""

    def test_onboarding_page_requires_login(self, client):
        """Test that onboarding page requires admin login."""
        response = client.get('/admin/onboarding')
        assert response.status_code == 302  # Redirect to login

    def test_onboarding_skip(self, client, test_admin):
        """Test skipping onboarding via API."""
        # Create onboarding record
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_id'] = test_admin.id

        response = client.post('/admin/onboarding/skip',
                               content_type='application/json')
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'success'

        # Verify onboarding was skipped
        onboarding = TeacherOnboarding.query.filter_by(
            teacher_id=test_admin.id
        ).first()
        assert onboarding.is_skipped is True
