from datetime import datetime, timedelta, timezone

from app import Transaction, TapEvent, db, Student
from hash_utils import get_random_salt, hash_username


def test_payroll_handles_unmatched_active_tap(client, monkeypatch):
    fixed_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr("app.datetime", FixedDateTime)

    salt = get_random_salt()
    student = Student(
        first_name="Test",
        last_initial="S",
        block="A",
        salt=salt,
        username_hash=hash_username("payrolltester", salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.commit()

    unmatched_start = fixed_now - timedelta(minutes=3)
    tap_event = TapEvent(
        student_id=student.id,
        period="A",
        status="active",
        timestamp=unmatched_start.replace(tzinfo=None),
    )
    db.session.add(tap_event)
    db.session.commit()

    with client.session_transaction() as session:
        session["is_admin"] = True
        session["last_activity"] = fixed_now.strftime("%Y-%m-%d %H:%M:%S")

    response = client.post("/admin/run-payroll")
    assert response.status_code == 302

    transactions = Transaction.query.filter_by(student_id=student.id, type="payroll").all()
    assert len(transactions) == 1

    expected_seconds = (fixed_now - unmatched_start).total_seconds()
    expected_amount = round(expected_seconds * (0.25 / 60), 2)
    assert transactions[0].amount == expected_amount
