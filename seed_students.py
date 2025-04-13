from app_full import app, db, Student, TapSession
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

with app.app_context():
    names_blocks = [
        ("Ana Morales", "A"),
        ("Brayan López", "B"),
        ("Carmen Castillo", "C"),
        ("Daniela Méndez", "D"),
        ("Esteban Reyes", "E"),
        ("Fatima Guzmán", "F"),
        ("Gabriel Soto", "G"),
        ("Helena Ruiz", "H"),
    ]

    insurance_options = ["none", "paycheck_protection", "personal_responsibility", "bundle"]

    for i, (name, block) in enumerate(names_blocks):
        insurance = insurance_options[i % len(insurance_options)]
        insurance_paid = None
        if insurance != "none":
            days_ago = random.randint(5, 45)
            insurance_paid = datetime.utcnow() - timedelta(days=days_ago)

        student = Student(
            name=name,
            email=f"{name.split()[0].lower()}@school.com",
            qr_id=f"S100{i+1}",
            pin_hash=generate_password_hash("1234"),
            block=block,
            passes_left=random.randint(1, 5),
            last_tap_in=datetime.utcnow(),
            last_tap_out=datetime.utcnow(),
            owns_seat=(i % 4 == 0),
            is_rent_enabled=(i % 4 != 0),
            is_property_tax_enabled=(i % 4 == 0),
            insurance_plan=insurance,
            insurance_last_paid=insurance_paid
        )
        db.session.add(student)

    db.session.commit()
    print("✅ Seeded students successfully.")

    # Seed tap sessions for testing attendance
    for student in Student.query.all():
        if student.block == "A":
            session = TapSession(
                student_id=student.id,
                period='a',
                tap_in_time=datetime.utcnow() - timedelta(minutes=40),
                tap_out_time=datetime.utcnow() - timedelta(minutes=5),
                reason='done',
                is_done=True
            )
            db.session.add(session)
        elif student.block == "B":
            session = TapSession(
                student_id=student.id,
                period='b',
                tap_in_time=datetime.utcnow() - timedelta(minutes=20),
                tap_out_time=None,
                reason=None,
                is_done=False
            )
            db.session.add(session)

    db.session.commit()
    print("✅ Seeded tap sessions.")

    # Add first-time setup students for testing
    first_time_students = [
        Student(
            name='Jamie Reyes',
            email='jamie.reyes@example.com',
            qr_id='jamie123',
            pin_hash=generate_password_hash('0000'),
            has_completed_setup=False,
            second_factor_type='none',
            second_factor_secret=None,
            passes_left=3,
            block='A'
        ),
        Student(
            name='Kai Mendoza',
            email='kai.mendoza@example.com',
            qr_id='kai456',
            pin_hash=generate_password_hash('0000'),
            has_completed_setup=False,
            second_factor_type='none',
            second_factor_secret=None,
            passes_left=3,
            block='B'
        ),
        Student(
            name='Riley Soto',
            email='riley.soto@example.com',
            qr_id='riley789',
            pin_hash=generate_password_hash('0000'),
            has_completed_setup=False,
            second_factor_type='none',
            second_factor_secret=None,
            passes_left=3,
            block='C'
        ),
    ]

    db.session.add_all(first_time_students)
    db.session.commit()
    print("✅ Added first-time setup students.")
