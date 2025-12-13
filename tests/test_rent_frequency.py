
import unittest
from datetime import datetime, timedelta
from app.routes.student import _calculate_rent_deadlines

# Mocking the settings object
class MockSettings:
    def __init__(self, frequency_type, first_rent_due_date, grace_period_days=3,
                 custom_frequency_value=None, custom_frequency_unit=None, due_day_of_month=1):
        self.frequency_type = frequency_type
        self.first_rent_due_date = first_rent_due_date
        self.grace_period_days = grace_period_days
        self.custom_frequency_value = custom_frequency_value
        self.custom_frequency_unit = custom_frequency_unit
        self.due_day_of_month = due_day_of_month

class TestRentDeadlines(unittest.TestCase):
    def test_weekly_frequency(self):
        # Start Jan 1 2024 (Monday). Weekly.
        start = datetime(2024, 1, 1)
        settings = MockSettings('weekly', start)

        # Check on Jan 3 (Wed). Should be Jan 1.
        ref = datetime(2024, 1, 3)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 1))

        # Check on Jan 8 (Mon). Should be Jan 8.
        ref = datetime(2024, 1, 8)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 8))

        # Check on Jan 14 (Sun). Should be Jan 8.
        ref = datetime(2024, 1, 14)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 8))

    def test_daily_frequency(self):
        start = datetime(2024, 1, 1)
        settings = MockSettings('daily', start)

        ref = datetime(2024, 1, 3)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 3))

    def test_custom_days(self):
        # Every 3 days. Jan 1, Jan 4, Jan 7...
        start = datetime(2024, 1, 1)
        settings = MockSettings('custom', start, custom_frequency_value=3, custom_frequency_unit='days')

        # Jan 2 -> Jan 1
        ref = datetime(2024, 1, 2)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 1))

        # Jan 4 -> Jan 4
        ref = datetime(2024, 1, 4)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 4))

    def test_custom_months(self):
        # Every 2 months. Jan 15, Mar 15, May 15...
        start = datetime(2024, 1, 15)
        settings = MockSettings('custom', start, custom_frequency_value=2, custom_frequency_unit='months')

        # Feb 1 -> Jan 15
        ref = datetime(2024, 2, 1)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 1, 15))

        # Mar 1 -> Mar 15
        ref = datetime(2024, 3, 1)
        due, grace = _calculate_rent_deadlines(settings, ref)
        self.assertEqual(due, datetime(2024, 3, 15))

if __name__ == '__main__':
    unittest.main()
