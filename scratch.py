import os
import sys

# Setup flask app context
from app import app, db
from app.models import User, ClassEconomy, Seat, ClassMembership
from tests.test_api_tenancy import _create_admin, _create_student, _create_tap_event, _login_admin
from tests.helpers.v2_fixtures import make_admin

def debug_test():
    with app.app_context():
        # Clean DB
        db.drop_all()
        db.create_all()

        client = app.test_client()

        teacher_a, secret_a = _create_admin("teacher-a")
        teacher_b, secret_b = _create_admin("teacher-b")
    
        student_a = _create_student("StudentA", primary_teacher=teacher_a)
        student_b = _create_student("StudentB", primary_teacher=teacher_b)
    
        tap_a = _create_tap_event(student_a, teacher_a, "ATTEND_A", status="active")
        tap_b = _create_tap_event(student_b, teacher_b, "ATTEND_B", status="active")
    
        response = _login_admin(client, teacher_a, secret_a)
        print("Login response:", response.status_code)

        with client.session_transaction() as sess:
            print("Session after login:", dict(sess))

        response = client.get("/api/attendance/history")
        print("API response:", response.status_code)
        if response.status_code == 302:
            print("Redirect location:", response.location)

        # Check DB states
        teacher_user = User.query.filter_by(username_hash=teacher_a.username_hash).first()
        print("Teacher User class_id:", teacher_user.last_active_class_id)
        
        class_row = ClassEconomy.query.filter_by(user_id=teacher_user.id).first()
        print("ClassEconomy id:", class_row.class_id if class_row else None)

        seat = Seat.query.filter_by(user_id=teacher_user.id).first()
        print("Teacher Seat:", seat.class_id if seat else None)

if __name__ == "__main__":
    debug_test()
