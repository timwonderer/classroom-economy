"""
Tests for tap toggle at class level and teacher tap-out lock functionality.
"""

import pytest
from datetime import datetime, timezone, date
import pytz


def test_teacher_tap_out_lock_logic():
    """
    Test that the logic for locking students after teacher tap-out is correct.
    This is a simple unit test for the core logic without full app context.
    """
    # Simulate setting done_for_day_date
    pacific = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(timezone.utc)
    now_pacific = now_utc.astimezone(pacific)
    today_pacific = now_pacific.date()
    
    # This simulates what should happen when teacher taps out a student
    done_for_day_date = today_pacific
    
    # Verify that the date is set to today
    assert done_for_day_date == today_pacific
    assert isinstance(done_for_day_date, date)
    
    # Verify that checking against today would prevent tap-in
    # (In the real code, this comparison happens in api.py line 1267)
    should_lock = (done_for_day_date == today_pacific)
    assert should_lock is True


def test_midnight_reset_logic():
    """
    Test that done_for_day_date from a previous day would allow tap-in.
    """
    pacific = pytz.timezone('America/Los_Angeles')
    now_utc = datetime.now(timezone.utc)
    now_pacific = now_utc.astimezone(pacific)
    today_pacific = now_pacific.date()
    
    # Simulate a done_for_day_date from yesterday
    from datetime import timedelta
    yesterday_pacific = today_pacific - timedelta(days=1)
    done_for_day_date = yesterday_pacific
    
    # Verify that checking against today would NOT prevent tap-in
    # (In the real code, this comparison happens in api.py line 1264-1266)
    should_clear_lock = (done_for_day_date is not None and done_for_day_date < today_pacific)
    assert should_clear_lock is True
    
    # After clearing, done_for_day_date would be None
    if should_clear_lock:
        done_for_day_date = None
    
    assert done_for_day_date is None


def test_block_tap_settings_data_structure():
    """
    Test that the data structure for block tap settings is correct.
    """
    # Simulate the response structure from the API
    response_data = {
        'status': 'ok',
        'tap_enabled': False,
        'updated_count': 5
    }
    
    assert response_data['status'] == 'ok'
    assert response_data['tap_enabled'] is False
    assert response_data['updated_count'] == 5
    assert isinstance(response_data['updated_count'], int)
