import os
import random
from datetime import datetime, timedelta, timezone
from app import create_app, db
from app.models import (
    Admin, Student, StudentTeacher, StoreItem, StoreItemBlock,
    InsurancePolicy, InsurancePolicyBlock, StudentInsurance,
    PayrollSettings, RentSettings, RentPayment, Transaction,
    FeatureSettings, TeacherBlock
)
from werkzeug.security import generate_password_hash
from hash_utils import hash_username, get_random_salt, hash_username_lookup
from app.utils.claim_credentials import compute_primary_claim_hash
from app.utils.name_utils import hash_last_name_parts

def seed():
    print("🌱 Starting complex seeding...")

    # 1. Teachers
    # T1, T2, T3
    # Blocks: T1(A,B), T2(A,C), T3(B,D)

    t_data = [
        ("teacher1", ["A", "B"]),
        ("teacher2", ["A", "C"]),
        ("teacher3", ["B", "D"])
    ]

    teacher_objs = {}

    for username, blocks in t_data:
        admin = Admin.query.filter_by(username=username).first()
        if not admin:
            admin = Admin(
                username=username,
                totp_secret="base32secret3232",
                has_assigned_students=True
            )
            db.session.add(admin)
            db.session.flush()

        teacher_objs[username] = admin

        # Feature Settings
        if not FeatureSettings.query.filter_by(teacher_id=admin.id, block=None).first():
            db.session.add(FeatureSettings(teacher_id=admin.id, block=None))

        # Payroll Settings
        if not PayrollSettings.query.filter_by(teacher_id=admin.id, block=None).first():
            # T3 different pay rate
            rate = 1.00 if username == "teacher3" else 0.25
            db.session.add(PayrollSettings(teacher_id=admin.id, pay_rate=rate, payroll_frequency_days=7))

        # Rent Settings
        if not RentSettings.query.filter_by(teacher_id=admin.id, block=None).first():
            amount = 500.0 if username == "teacher1" else 800.0
            db.session.add(RentSettings(teacher_id=admin.id, rent_amount=amount, frequency_type='monthly'))

    t1 = teacher_objs["teacher1"]
    t2 = teacher_objs["teacher2"]
    t3 = teacher_objs["teacher3"]
    teachers = [t1, t2, t3]

    # Specific Block Settings
    # T1-B Payroll
    if not PayrollSettings.query.filter_by(teacher_id=t1.id, block='B').first():
        db.session.add(PayrollSettings(teacher_id=t1.id, block='B', pay_rate=0.50))

    # T2-C Rent
    if not RentSettings.query.filter_by(teacher_id=t2.id, block='C').first():
        db.session.add(RentSettings(teacher_id=t2.id, block='C', rent_amount=1000.0))

    db.session.commit()

    # 3. Students
    # Helper to create student
    def create_student(fname, lname, username_base, blocks, teacher_list, pin="1234"):
        salt = get_random_salt()
        username = f"{username_base}-{fname[0]}{lname[0]}"

        # Check if exists using deterministic hash
        lookup_hash = hash_username_lookup(username)
        s = Student.query.filter_by(username_lookup_hash=lookup_hash).first()

        if not s:
            s = Student(
                first_name=fname,
                last_initial=lname[0],
                block=",".join(sorted(list(set(blocks)))), # Unique blocks
                salt=salt,
                username_hash=hash_username(username, salt),
                username_lookup_hash=hash_username_lookup(username),
                pin_hash=generate_password_hash(pin),
                passphrase_hash=generate_password_hash("passphrase"),
                dob_sum=2000, # Dummy
                is_rent_enabled=True,
                has_completed_setup=True
            )
            db.session.add(s)
            db.session.flush()
        else:
            username = "EXISTING (check DB)"
            # Update blocks if needed
            current_blocks = set(s.block.split(','))
            current_blocks.update(blocks)
            s.block = ",".join(sorted(list(current_blocks)))

        # Link teachers
        for teacher in teacher_list:
            if not StudentTeacher.query.filter_by(student_id=s.id, admin_id=teacher.id).first():
                st = StudentTeacher(student_id=s.id, admin_id=teacher.id)
                db.session.add(st)

        return s, username

    created_students = []

    # S1: T1-A
    s1, u1 = create_student("Student1", "One", "s1", ["A"], [t1])
    created_students.append((s1, u1, "1234"))

    # S2: T1-B
    s2, u2 = create_student("Student2", "Two", "s2", ["B"], [t1])
    created_students.append((s2, u2, "1234"))

    # S3: T2-A
    s3, u3 = create_student("Student3", "Three", "s3", ["A"], [t2])
    created_students.append((s3, u3, "1234"))

    # S4: T2-C
    s4, u4 = create_student("Student4", "Four", "s4", ["C"], [t2])
    created_students.append((s4, u4, "1234"))

    # S5: T3-B
    s5, u5 = create_student("Student5", "Five", "s5", ["B"], [t3])
    created_students.append((s5, u5, "1234"))

    # S6: T3-D
    s6, u6 = create_student("Student6", "Six", "s6", ["D"], [t3])
    created_students.append((s6, u6, "1234"))

    # S7: T1-A, T2-A (Shared)
    s7, u7 = create_student("Student7", "Seven", "s7", ["A"], [t1, t2])
    created_students.append((s7, u7, "1234"))

    # S8: T1-B, T3-B (Shared)
    s8, u8 = create_student("Student8", "Eight", "s8", ["B"], [t1, t3])
    created_students.append((s8, u8, "1234"))

    # S9: T1-A, T1-B (Same teacher, diff blocks)
    s9, u9 = create_student("Student9", "Nine", "s9", ["A", "B"], [t1])
    created_students.append((s9, u9, "1234"))

    db.session.commit()

    # 4. Store Items
    # T1 Items
    if not StoreItem.query.filter_by(teacher_id=t1.id, name="Pencil").first():
        item = StoreItem(teacher_id=t1.id, name="Pencil", price=10.0, item_type='immediate')
        db.session.add(item)

    if not StoreItem.query.filter_by(teacher_id=t1.id, name="Homework Pass").first():
        item = StoreItem(teacher_id=t1.id, name="Homework Pass", price=50.0, item_type='delayed')
        db.session.add(item)
        db.session.flush()
        db.session.add(StoreItemBlock(store_item_id=item.id, block='A'))

    # T2 Items
    if not StoreItem.query.filter_by(teacher_id=t2.id, name="Pencil").first():
        item = StoreItem(teacher_id=t2.id, name="Pencil", price=15.0, item_type='immediate')
        db.session.add(item)

    # Mixed types
    if not StoreItem.query.filter_by(teacher_id=t3.id, name="Pizza Party").first():
        item = StoreItem(teacher_id=t3.id, name="Pizza Party", price=1000.0, item_type='collective', collective_goal_type='fixed', collective_goal_target=100)
        db.session.add(item)

    db.session.commit()

    # 5. Insurance Policies
    # T1 Policies
    if not InsurancePolicy.query.filter_by(teacher_id=t1.id, title="Health").first():
        p = InsurancePolicy(
            teacher_id=t1.id,
            policy_code="T1-HEALTH",
            title="Health",
            premium=20.0,
            waiting_period_days=0
        )
        db.session.add(p)

    if not InsurancePolicy.query.filter_by(teacher_id=t1.id, title="Theft").first():
        p = InsurancePolicy(
            teacher_id=t1.id,
            policy_code="T1-THEFT",
            title="Theft",
            premium=10.0,
            waiting_period_days=7
        )
        db.session.add(p)
        db.session.flush()
        # Block A only
        if not InsurancePolicyBlock.query.filter_by(policy_id=p.id, block='A').first():
             p.set_blocks(['A'])

    # T2 Grouped Policies
    if not InsurancePolicy.query.filter_by(teacher_id=t2.id, title="Basic Protection").first():
        p = InsurancePolicy(
            teacher_id=t2.id,
            policy_code="T2-BASIC",
            title="Basic Protection",
            premium=50.0,
            tier_category_id=1,
            tier_name="Protection Plan"
        )
        db.session.add(p)

    if not InsurancePolicy.query.filter_by(teacher_id=t2.id, title="Premium Protection").first():
        p = InsurancePolicy(
            teacher_id=t2.id,
            policy_code="T2-PREMIUM",
            title="Premium Protection",
            premium=100.0,
            tier_category_id=1,
            tier_name="Protection Plan"
        )
        db.session.add(p)

    db.session.commit()

    # 6. Insurance Purchases
    # S1 buys T1-Health (Past waiting)
    p_health = InsurancePolicy.query.filter_by(teacher_id=t1.id, title="Health").first()
    if p_health:
        if not StudentInsurance.query.filter_by(student_id=s1.id, policy_id=p_health.id).first():
            si = StudentInsurance(
                student_id=s1.id,
                policy_id=p_health.id,
                status='active',
                purchase_date=datetime.utcnow() - timedelta(days=10),
                coverage_start_date=datetime.utcnow() - timedelta(days=10)
            )
            db.session.add(si)

    # S2 buys T1-Theft (In waiting)
    p_theft = InsurancePolicy.query.filter_by(teacher_id=t1.id, title="Theft").first()
    if p_theft:
         if not StudentInsurance.query.filter_by(student_id=s2.id, policy_id=p_theft.id).first():
            si = StudentInsurance(
                student_id=s2.id,
                policy_id=p_theft.id,
                status='active',
                purchase_date=datetime.utcnow() - timedelta(days=1),
                coverage_start_date=datetime.utcnow() + timedelta(days=6)
            )
            db.session.add(si)

    db.session.commit()

    # 7. Transactions
    for s, _, _ in created_students:
        db.session.add(Transaction(
            student_id=s.id,
            amount=2000.0,
            account_type='checking',
            type='Deposit',
            description='Initial Deposit'
        ))
        db.session.add(Transaction(
            student_id=s.id,
            amount=500.0,
            account_type='savings',
            type='Deposit',
            description='Savings Starter'
        ))
        for _ in range(5):
            amount = random.randint(10, 100)
            db.session.add(Transaction(
                student_id=s.id,
                amount=-float(amount),
                account_type='checking',
                type='Purchase',
                description=f'Random Purchase {random.randint(1, 100)}'
            ))

    db.session.commit()

    # 8. Unclaimed / Add Class
    print("\n--- Generating Unclaimed/Add-Class Data ---")

    # 8a. Unclaimed Student (T1-B)
    salt_uc = get_random_salt()
    fname_uc = "New"
    lname_uc = "Student"
    dob_sum_uc = 2025

    if not TeacherBlock.query.filter_by(teacher_id=t1.id, join_code="T1B-JOIN").first():
        tb_uc = TeacherBlock(
            teacher_id=t1.id,
            block='B',
            first_name=fname_uc,
            last_initial=lname_uc[0],
            last_name_hash_by_part=hash_last_name_parts(lname_uc, salt_uc),
            dob_sum=dob_sum_uc,
            salt=salt_uc,
            first_half_hash=compute_primary_claim_hash(fname_uc[0], dob_sum_uc, salt_uc),
            join_code="T1B-JOIN",
            is_claimed=False
        )
        db.session.add(tb_uc)
        print("Created Unclaimed Seat in T1-B.")

    # 8b. Add Class Student (Setup in T2-A, needs to add T3-D)
    # Create Student
    s_add, u_add = create_student("Add", "Class", "s_add", ["A"], [t2])
    created_students.append((s_add, u_add, "1234"))

    # Create TeacherBlock in T3-D
    salt_tb = get_random_salt()
    if not TeacherBlock.query.filter_by(teacher_id=t3.id, join_code="T3D-JOIN").first():
        tb_add = TeacherBlock(
            teacher_id=t3.id,
            block='D',
            first_name="Add",
            last_initial="C", # First char of "Class"
            last_name_hash_by_part=hash_last_name_parts("Class", salt_tb),
            dob_sum=2000,
            salt=salt_tb,
            first_half_hash=compute_primary_claim_hash("A", 2000, salt_tb),
            join_code="T3D-JOIN",
            is_claimed=False
        )
        db.session.add(tb_add)
        print("Created Student 'Add Class' (setup in T2, needs to add T3).")

    db.session.commit()

    print("\n✅ Seeding Complete!")
    print("\n--- CREDENTIALS ---")
    print("Teachers (Password: Not set / TOTP only - Secret: base32secret3232):")
    for t in teachers:
        print(f"  - {t.username}")

    print("\nStudents (PIN: 1234, Passphrase: passphrase):")
    for s, u, pin in created_students:
        print(f"  - Name: {s.first_name} {s.last_initial}. | Username: {u} | Blocks: {s.block} | Teachers: {[t.username for t in s.get_all_teachers()]}")

    print("\nUnclaimed / Add Class Scenarios:")
    print("  1. Unclaimed Student (Needs to Claim Account):")
    print(f"     - Join Code: T1B-JOIN")
    print(f"     - Name Code: N{dob_sum_uc} (First Initial + DOB Sum)")
    print(f"     - Details: {fname_uc} {lname_uc}, DOB Sum: {dob_sum_uc}")

    print("  2. Add Class Student (Needs to 'Add Class' in dashboard):")
    print(f"     - Login as: {u_add} (PIN: 1234)")
    print(f"     - Go to 'Add Class'")
    print(f"     - Join Code: T3D-JOIN")
    print(f"     - Name Code: A2000")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        seed()
