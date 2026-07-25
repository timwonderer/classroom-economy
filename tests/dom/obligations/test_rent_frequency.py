
from datetime import datetime, timezone
import uuid

from app import db
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize
from app.routes.student import _calculate_rent_deadlines, _calculate_rent_timeline

# Mocking the settings object
class MockSettings:
    def __init__(self, frequency_type, first_rent_due_date, grace_period_days=3,
                 custom_frequency_value=None, custom_frequency_unit=None, due_day_of_month=1,
                 bill_preview_enabled=False, bill_preview_days=7, class_id="rent-test-class"):
        self.frequency_type = frequency_type
        self.first_rent_due_date = first_rent_due_date
        self.grace_period_days = grace_period_days
        self.custom_frequency_value = custom_frequency_value
        self.custom_frequency_unit = custom_frequency_unit
        self.due_day_of_month = due_day_of_month
        self.bill_preview_enabled = bill_preview_enabled
        self.bill_preview_days = bill_preview_days
        self.class_id = class_id


def _seed_class_id(app) -> str:
    classroom = initialize("chemistry_p1", app)
    return classroom.class_id

def test_DOM_OBL_001__weekly_frequency(app):
    # Start Jan 1 2024 (Monday). Weekly.
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    settings = MockSettings("weekly", start, class_id=_seed_class_id(app))

    # Check on Jan 3 (Wed). Should be Jan 1.
    ref = datetime(2024, 1, 3, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Jan 8 is the next weekly anchor.
    ref = datetime(2024, 1, 8, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 1, 8, tzinfo=timezone.utc)

    # Check on Jan 14 (Sun). Should be Jan 8.
    ref = datetime(2024, 1, 14, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 1, 8, tzinfo=timezone.utc)


def test_DOM_OBL_001__daily_frequency(app):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    settings = MockSettings("daily", start, class_id=_seed_class_id(app))

    ref = datetime(2024, 1, 3, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 1, 3, tzinfo=timezone.utc)


def test_DOM_OBL_001__custom_days(app):
    # Every 3 days. Jan 1, Jan 4, Jan 7...
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    settings = MockSettings("custom", start, custom_frequency_value=3, custom_frequency_unit="days", class_id=_seed_class_id(app))

    # Jan 2 -> Jan 1
    ref = datetime(2024, 1, 2, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Jan 4 is the next 3-day anchor.
    ref = datetime(2024, 1, 4, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 1, 4, tzinfo=timezone.utc)


def test_DOM_OBL_001__custom_months(app):
    # Every 2 months. Jan 15, Mar 15, May 15...
    start = datetime(2024, 1, 15, tzinfo=timezone.utc)
    settings = MockSettings("custom", start, custom_frequency_value=2, custom_frequency_unit="months", class_id=_seed_class_id(app))

    # Feb 1 -> Jan 15
    ref = datetime(2024, 2, 1, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 1, 15, tzinfo=timezone.utc)

    # Mar 1 advances into the Mar 15 cycle.
    ref = datetime(2024, 3, 1, tzinfo=timezone.utc)
    due, grace = _calculate_rent_deadlines(settings, ref)
    assert due == datetime(2024, 3, 15, tzinfo=timezone.utc)


def test_DOM_OBL_001__monthly_upcoming_due_respects_due_day_clamping(app):
    # Traditional monthly schedule on the 31st with no first_rent_due_date.
    settings = MockSettings(
        frequency_type="monthly",
        first_rent_due_date=None,
        due_day_of_month=31,
        bill_preview_enabled=True,
        bill_preview_days=5,
        class_id=_seed_class_id(app),
    )

    # Mar 5 should be in Feb coverage period, with upcoming due on Mar 31.
    ref = datetime(2026, 3, 5, tzinfo=timezone.utc)
    timeline = _calculate_rent_timeline(settings, ref)

    assert timeline["coverage_due_date"] == datetime(2026, 2, 28, tzinfo=timezone.utc)
    assert timeline["upcoming_due_date"] == datetime(2026, 3, 31, tzinfo=timezone.utc)
    assert timeline["preview_start_date"] == datetime(2026, 3, 26, tzinfo=timezone.utc)
