"""
Test to validate rent calculation with user's exact values.

User's setup:
- Pay rate: $1.25 per minute
- Period duration: 75 minutes
- Meetings per week: 3
- Rent: $450 per month

Expected results:
- CWI: $281.25/week (3 × 75 × $1.25)
- Weekly rent: $103.49 ($450 / 4.348)
- Recommended range: $562.50 - $703.13 (2.0x - 2.5x CWI)
- Ideal: $632.81 (2.25x CWI)

Bug Found: The frontend validation was not passing the 'block' parameter to the API,
causing it to use the first available payroll settings (potentially from a different
class/block) instead of the correct block's settings.

Fix: Updated economy-balance.js to always include the block parameter when validating
any feature (rent, insurance, fines, store items).
"""
import pytest
from datetime import datetime, timezone
from app import db
from app.models import Admin, PayrollSettings
from app.utils.economy_balance import EconomyBalanceChecker


@pytest.fixture
def admin_with_exact_payroll(client):
    """Create admin with exact user payroll settings."""
    admin = Admin(
        username="testrentcalc",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(admin)
    db.session.flush()

    # User's exact settings
    # 75 minutes per period, 3 times a week = 225 minutes total
    # 225 minutes = 3.75 hours
    payroll_settings = PayrollSettings(
        teacher_id=admin.id,
        block="A",
        pay_rate=1.25,  # $1.25 per minute
        expected_weekly_hours=3.75,  # 225 minutes = 3.75 hours
        payroll_frequency_days=7,
        settings_mode='simple',
        is_active=True
    )
    db.session.add(payroll_settings)
    db.session.commit()

    return admin, payroll_settings


def test_cwi_calculation_exact(admin_with_exact_payroll):
    """Test CWI calculation with exact user values."""
    admin, payroll_settings = admin_with_exact_payroll

    checker = EconomyBalanceChecker(admin.id, "A")
    cwi_calc = checker.calculate_cwi(payroll_settings)

    # Expected: 225 minutes × $1.25/min = $281.25
    expected_cwi = 225 * 1.25
    assert cwi_calc.cwi == pytest.approx(expected_cwi, abs=0.01), \
        f"Expected CWI ${expected_cwi}, got ${cwi_calc.cwi}"

    print(f"\n✓ CWI calculation correct: ${cwi_calc.cwi:.2f}/week")


def test_rent_validation_monthly(admin_with_exact_payroll):
    """Test rent validation with $450/month against CWI of $281.25."""
    admin, payroll_settings = admin_with_exact_payroll

    checker = EconomyBalanceChecker(admin.id, "A")
    cwi_calc = checker.calculate_cwi(payroll_settings)
    cwi = cwi_calc.cwi

    # User enters $450 per month
    rent_amount = 450.0
    frequency_type = 'monthly'

    warnings, recommendations, ratio = checker.validate_rent_value(
        rent_amount=rent_amount,
        frequency_type=frequency_type,
        cwi=cwi,
        custom_frequency_value=None,
        custom_frequency_unit=None
    )

    # Verify weekly rent conversion
    expected_weekly_rent = rent_amount / checker.AVERAGE_WEEKS_PER_MONTH  # ~103.49
    print(f"\n✓ Weekly rent: ${expected_weekly_rent:.2f}")

    # Verify recommendations are based on CWI
    expected_min = round(cwi * checker.RENT_MIN_RATIO, 2)  # $281.25 × 2.0 = $562.50
    expected_max = round(cwi * checker.RENT_MAX_RATIO, 2)  # $281.25 × 2.5 = $703.13
    expected_ideal = round(cwi * checker.RENT_DEFAULT_RATIO, 2)  # $281.25 × 2.25 = $632.81

    print(f"\nExpected recommendations (weekly):")
    print(f"  Min: ${expected_min}")
    print(f"  Max: ${expected_max}")
    print(f"  Ideal: ${expected_ideal}")

    print(f"\nActual recommendations returned:")
    print(f"  Min: ${recommendations['min']}")
    print(f"  Max: ${recommendations['max']}")
    print(f"  Ideal: ${recommendations['recommended']}")

    # THE BUG: Recommendations should be based on CWI, not rent_amount!
    assert recommendations['min'] == expected_min, \
        f"BUGBUG: Expected min ${expected_min}, got ${recommendations['min']}"
    assert recommendations['max'] == expected_max, \
        f"BUG: Expected max ${expected_max}, got ${recommendations['max']}"
    assert recommendations['recommended'] == expected_ideal, \
        f"BUG: Expected ideal ${expected_ideal}, got ${recommendations['recommended']}"

    # Verify warning message
    assert len(warnings) > 0, "Should have at least one warning"
    warning_msg = warnings[0]['message']
    print(f"\nWarning message: {warning_msg}")

    # Warning should reference weekly rent and weekly recommendation
    assert f"${expected_weekly_rent:.2f}/week" in warning_msg or f"${expected_weekly_rent:.0f}" in warning_msg, \
        f"Warning should mention weekly rent ${expected_weekly_rent:.2f}"
    assert f"${expected_min:.2f}" in warning_msg or f"${expected_min:.0f}" in warning_msg, \
        f"Warning should mention recommendation ${expected_min:.2f}, got: {warning_msg}"

    print("\n✓ All validation checks passed!")


def test_api_endpoint_with_exact_values(client, admin_with_exact_payroll):
    """Test the full API endpoint with exact user values."""
    admin, payroll_settings = admin_with_exact_payroll

    # Login
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Call API with exact values
    response = client.post(
        '/api/economy/validate/rent',
        json={
            'value': 450.0,
            'frequency_type': 'monthly',
            'block': 'A'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    print(f"\nAPI Response:")
    print(f"  CWI: ${data['cwi']:.2f}")
    print(f"  Recommendations: ${data['recommendations']['min']} - ${data['recommendations']['max']}")
    print(f"  Ideal: ${data['recommendations']['recommended']}")

    # Verify CWI is correct
    expected_cwi = 281.25
    assert abs(data['cwi'] - expected_cwi) < 0.01

    # Verify recommendations (this is where the bug manifests!)
    expected_min = 562.50
    expected_max = 703.13
    expected_ideal = 632.81

    assert abs(data['recommendations']['min'] - expected_min) < 0.01, \
        f"BUG DETECTED: API returned min ${data['recommendations']['min']}, expected ${expected_min}"
    assert abs(data['recommendations']['max'] - expected_max) < 0.01, \
        f"BUG DETECTED: API returned max ${data['recommendations']['max']}, expected ${expected_max}"
    assert abs(data['recommendations']['recommended'] - expected_ideal) < 0.01, \
        f"BUG DETECTED: API returned ideal ${data['recommendations']['recommended']}, expected ${expected_ideal}"

    print("\n✓ API endpoint validation passed!")


def test_multi_block_validation_uses_correct_cwi(client):
    """
    Test that validates the bug fix: when a teacher has multiple blocks with different
    payroll settings, the validation API uses the correct block's CWI.

    This test creates two blocks with very different CWI values to make the bug obvious.
    """
    # Create admin with two blocks
    admin = Admin(
        username="multiblockteacher",
        totp_secret="TESTSECRET789"
    )
    db.session.add(admin)
    db.session.flush()

    # Block A: User's exact settings (CWI = $281.25)
    payroll_a = PayrollSettings(
        teacher_id=admin.id,
        block="A",
        pay_rate=1.25,  # $1.25/min
        expected_weekly_hours=3.75,  # 225 min
        payroll_frequency_days=7,
        settings_mode='simple',
        is_active=True
    )

    # Block B: Different settings that would give CWI = $375
    # To get $375/week: 375 / 60 = 6.25 hours at $1/min OR 5 hours at $1.25/min = $375
    payroll_b = PayrollSettings(
        teacher_id=admin.id,
        block="B",
        pay_rate=1.25,  # $1.25/min
        expected_weekly_hours=5.0,  # 300 min × $1.25 = $375
        payroll_frequency_days=7,
        settings_mode='simple',
        is_active=True
    )

    db.session.add(payroll_a)
    db.session.add(payroll_b)
    db.session.commit()

    # Login
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Test validation WITHOUT block parameter (the bug!)
    # This should use the first payroll settings found (might be Block B!)
    response_no_block = client.post(
        '/api/economy/validate/rent',
        json={
            'value': 450.0,
            'frequency_type': 'monthly'
            # Missing 'block' parameter!
        }
    )

    assert response_no_block.status_code == 200
    data_no_block = response_no_block.get_json()

    # Test validation WITH block parameter (the fix!)
    response_with_block = client.post(
        '/api/economy/validate/rent',
        json={
            'value': 450.0,
            'frequency_type': 'monthly',
            'block': 'A'  # Explicitly specify Block A
        }
    )

    assert response_with_block.status_code == 200
    data_with_block = response_with_block.get_json()

    print(f"\n=== Multi-Block Validation Test ===")
    print(f"Block A CWI (expected): $281.25")
    print(f"Block B CWI (expected): $375.00")
    print(f"\nWithout block parameter:")
    print(f"  CWI used: ${data_no_block['cwi']:.2f}")
    print(f"  Recommendations: ${data_no_block['recommendations']['min']} - ${data_no_block['recommendations']['max']}")
    print(f"\nWith block='A' parameter:")
    print(f"  CWI used: ${data_with_block['cwi']:.2f}")
    print(f"  Recommendations: ${data_with_block['recommendations']['min']} - ${data_with_block['recommendations']['max']}")

    # The WITH block parameter should use Block A's CWI correctly
    assert abs(data_with_block['cwi'] - 281.25) < 0.01, \
        f"With block='A', CWI should be $281.25, got ${data_with_block['cwi']}"

    assert abs(data_with_block['recommendations']['min'] - 562.50) < 0.01, \
        f"With block='A', min recommendation should be $562.50, got ${data_with_block['recommendations']['min']}"

    assert abs(data_with_block['recommendations']['max'] - 703.13) < 0.01, \
        f"With block='A', max recommendation should be $703.13, got ${data_with_block['recommendations']['max']}"

    print("\n✓ Multi-block validation test passed!")
    print("  Frontend MUST pass the 'block' parameter to ensure correct CWI is used.")
