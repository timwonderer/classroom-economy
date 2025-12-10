"""
Tests for Economy API endpoints.

Tests the /admin/api/economy/* endpoints to ensure they correctly use
expected_weekly_hours from payroll_settings rather than hardcoded values.
"""
import pytest
from datetime import datetime, timezone
from app import db
from app.models import Admin, PayrollSettings


@pytest.fixture
def admin_with_payroll(client):
    """Create an admin with payroll settings for testing."""
    # Create admin
    admin = Admin(
        username="testeconomyadmin",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(admin)
    db.session.flush()

    # Create payroll settings with specific expected_weekly_hours
    payroll_settings = PayrollSettings(
        teacher_id=admin.id,
        block="A",
        pay_rate=0.25,  # $0.25/min = $15/hour
        expected_weekly_hours=8.0,  # Custom value, not 5.0
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True
    )
    db.session.add(payroll_settings)
    db.session.commit()

    return admin, payroll_settings


@pytest.fixture
def logged_in_admin_client(client, admin_with_payroll):
    """A client with a logged-in admin."""
    admin, _ = admin_with_payroll
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    return client


def test_validate_endpoint_uses_payroll_settings_hours(logged_in_admin_client, admin_with_payroll):
    """Test that /admin/api/economy/validate reads expected_weekly_hours from payroll_settings."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test validation endpoint - should use expected_weekly_hours from payroll_settings (8.0)
    response = client.post(
        '/admin/api/economy/validate/rent',
        json={
            'value': 100.0,
            'frequency_type': 'weekly'
            # Note: NOT sending expected_weekly_hours
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.get_json()
    assert data['status'] in ['success', 'warning']
    assert 'cwi' in data
    assert 'cwi_breakdown' in data

    # Verify the expected_weekly_hours in breakdown matches payroll_settings
    breakdown = data['cwi_breakdown']
    assert 'expected_weekly_hours' in breakdown
    assert breakdown['expected_weekly_hours'] == 8.0, \
        f"Expected 8.0 hours from payroll_settings, got {breakdown['expected_weekly_hours']}"

    # Verify CWI is calculated correctly with 8 hours
    # CWI = pay_rate_per_minute * expected_weekly_minutes
    # CWI = 0.25 * (8.0 * 60) = 0.25 * 480 = 120.0
    expected_cwi = 0.25 * 8.0 * 60
    assert abs(data['cwi'] - expected_cwi) < 0.01, \
        f"Expected CWI {expected_cwi}, got {data['cwi']}"


def test_validate_endpoint_not_hardcoded_5_hours(logged_in_admin_client, admin_with_payroll):
    """Test that validation doesn't use hardcoded 5.0 hours."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    response = client.post(
        '/admin/api/economy/validate/store_item',
        json={'value': 10.0}
    )

    assert response.status_code == 200
    data = response.get_json()

    # CWI with 8 hours should be 120.0, not 75.0 (which would be 5 hours)
    assert abs(data['cwi'] - 120.0) < 0.01, \
        f"CWI should be 120.0 (8 hours), not {data['cwi']} (suggests hardcoded 5 hours)"


def test_analyze_endpoint_uses_payroll_settings_hours(logged_in_admin_client, admin_with_payroll):
    """Test that /admin/api/economy/analyze reads expected_weekly_hours from payroll_settings."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test analyze endpoint - should use expected_weekly_hours from payroll_settings (8.0)
    response = client.post(
        '/admin/api/economy/analyze',
        json={
            'block': 'A'
            # Note: NOT sending expected_weekly_hours
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.get_json()
    assert data['status'] == 'success'
    assert 'cwi' in data
    assert 'cwi_breakdown' in data

    # Verify the expected_weekly_hours in breakdown matches payroll_settings
    breakdown = data['cwi_breakdown']
    assert 'expected_weekly_hours' in breakdown
    assert breakdown['expected_weekly_hours'] == 8.0, \
        f"Expected 8.0 hours from payroll_settings, got {breakdown['expected_weekly_hours']}"

    # Verify CWI calculation
    expected_cwi = 0.25 * 8.0 * 60  # 120.0
    assert abs(data['cwi'] - expected_cwi) < 0.01


def test_analyze_endpoint_override_hours(logged_in_admin_client, admin_with_payroll):
    """Test that /admin/api/economy/analyze accepts override when explicitly provided."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test with explicit override to 10 hours
    response = client.post(
        '/admin/api/economy/analyze',
        json={
            'block': 'A',
            'expected_weekly_hours': 10.0  # Override value
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should use the override value (10.0), not payroll_settings (8.0)
    breakdown = data['cwi_breakdown']
    assert breakdown['expected_weekly_hours'] == 10.0, \
        f"Expected override value 10.0, got {breakdown['expected_weekly_hours']}"

    # Verify CWI with override
    expected_cwi = 0.25 * 10.0 * 60  # 150.0
    assert abs(data['cwi'] - expected_cwi) < 0.01


def test_analyze_endpoint_null_override_uses_payroll(logged_in_admin_client, admin_with_payroll):
    """Test that null expected_weekly_hours falls back to payroll_settings."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test with explicit null - should fall back to payroll_settings
    response = client.post(
        '/admin/api/economy/analyze',
        json={
            'block': 'A',
            'expected_weekly_hours': None
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should use payroll_settings value (8.0), not null
    breakdown = data['cwi_breakdown']
    assert breakdown['expected_weekly_hours'] == 8.0, \
        f"Expected payroll_settings value 8.0 when override is null, got {breakdown['expected_weekly_hours']}"


def test_different_expected_hours_per_block(client):
    """Test that different blocks can have different expected_weekly_hours."""
    # Create admin
    admin = Admin(
        username="testmultiblock",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(admin)
    db.session.flush()

    # Create payroll settings for different blocks with different hours
    payroll_a = PayrollSettings(
        teacher_id=admin.id,
        block="A",
        pay_rate=0.25,
        expected_weekly_hours=5.0,  # Block A: 5 hours
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True
    )

    payroll_b = PayrollSettings(
        teacher_id=admin.id,
        block="B",
        pay_rate=0.25,
        expected_weekly_hours=10.0,  # Block B: 10 hours
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True
    )

    db.session.add(payroll_a)
    db.session.add(payroll_b)
    db.session.commit()

    # Login as admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Test Block A
    response_a = client.post(
        '/admin/api/economy/analyze',
        json={'block': 'A'}
    )
    assert response_a.status_code == 200
    data_a = response_a.get_json()
    assert data_a['cwi_breakdown']['expected_weekly_hours'] == 5.0
    assert abs(data_a['cwi'] - (0.25 * 5.0 * 60)) < 0.01  # 75.0

    # Test Block B
    response_b = client.post(
        '/admin/api/economy/analyze',
        json={'block': 'B'}
    )
    assert response_b.status_code == 200
    data_b = response_b.get_json()
    assert data_b['cwi_breakdown']['expected_weekly_hours'] == 10.0
    assert abs(data_b['cwi'] - (0.25 * 10.0 * 60)) < 0.01  # 150.0


def test_validate_rent_with_monthly_frequency(logged_in_admin_client, admin_with_payroll):
    """Test that monthly rent recommendations are correctly calculated per AGENTS spec."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test with monthly rent of $440
    # CWI = 0.25 * 8 * 60 = 120.0 per week
    # Per AGENTS spec: monthly rent ratios are 2.0-2.5x CWI (weekly)
    # Recommended MONTHLY rent range: $240 - $300 (2.0-2.5 × $120 weekly CWI)
    # Weekly equivalent: $240/4.348 = ~$55.20/week to $300/4.348 = ~$69.00/week
    response = client.post(
        '/admin/api/economy/validate/rent',
        json={
            'value': 440.0,
            'frequency_type': 'monthly'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Verify CWI is calculated correctly
    expected_cwi = 0.25 * 8.0 * 60  # 120.0 per week
    assert abs(data['cwi'] - expected_cwi) < 0.01

    # Verify recommendations are MONTHLY values per AGENTS spec
    # Monthly rent_min = 2.0 * CWI (weekly) = 2.0 * 120 = 240
    recommendations = data['recommendations']
    assert abs(recommendations['min'] - (expected_cwi * 2.0)) < 0.01  # 240.0 per month
    assert abs(recommendations['max'] - (expected_cwi * 2.5)) < 0.01  # 300.0 per month
    assert abs(recommendations['recommended'] - (expected_cwi * 2.25)) < 0.01  # 270.0 per month

    # Monthly rent of $440 is ABOVE the recommended maximum of $300/month
    assert data['is_valid'] is False
    assert len(data['warnings']) > 0
    warning_msg = data['warnings'][0]['message'].lower()
    # Warning should mention "per month" since that's the input frequency
    assert 'per month' in warning_msg or 'month' in warning_msg
