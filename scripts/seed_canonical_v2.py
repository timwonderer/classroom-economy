import random
import uuid
import os
from datetime import datetime, timedelta
from decimal import Decimal
import sqlalchemy as sa

# Ensure we use a fixed seed for byte-for-byte identity
random.seed('CTH_CANONICAL_V2')

from app import create_app, db
from app.hash_utils import hash_username_lookup
from app.models import (
    User, Admin, ClassEconomy, IdentityProfile, Student, Seat, 
    InsurancePolicy, Transaction, Issue, IssueCategory, 
    AnalyticsSnapshot, TeacherBlock, StudentTeacher,
    TransactionStatus, BalanceCache, UserRole
)
from app.feats.base import FEATBypass

def record_posted_transaction(seat_id, class_id, amount, account_type, description, type="Adjustment"):
    """Helper to record a POSTED transaction and update the balance cache."""
    amount_cents = int(Decimal(str(amount)) * 100)
    
    tx = Transaction(
        seat_id=seat_id,
        class_id=class_id,
        amount=Decimal(str(amount)),
        account_type=account_type,
        status=TransactionStatus.POSTED,
        description=description,
        type=type,
        timestamp=datetime.utcnow()
    )
    db.session.add(tx)
    
    # Update cache
    cache = BalanceCache.query.filter_by(seat_id=seat_id, class_id=class_id).first()
    if not cache:
        cache = BalanceCache(
            seat_id=seat_id,
            class_id=class_id,
            posted_checking_balance_cents=0,
            posted_savings_balance_cents=0
        )
        db.session.add(cache)
    
    if account_type == "checking":
        cache.posted_checking_balance_cents += amount_cents
    else:
        cache.posted_savings_balance_cents += amount_cents
    
    db.session.flush()
    return tx

def seed():
    app = create_app()
    with app.app_context():
        with FEATBypass():
            print(f"ACTIVE DATABASE_URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
            inspector = sa.inspect(db.engine)
            actual_tables = inspector.get_table_names()
            print(f"ACTUAL DB TABLES: {actual_tables}")
            if 'insurance_policies' in actual_tables:
                 print(f"INSURANCE_POLICIES COLUMNS: {[col['name'] for col in inspector.get_columns('insurance_policies')]}")
            print(f"ORM METADATA TABLES: {list(db.metadata.tables.keys())}")
            
            # Manual fix for table name discrepancy if needed
            if 'admins' in actual_tables and 'teachers' not in actual_tables:
                print("REPAIRING TABLE NAME: admins -> teachers")
                db.session.execute(sa.text("ALTER TABLE admins RENAME TO teachers;"))
                if 'admin_credentials' in actual_tables:
                     db.session.execute(sa.text("ALTER TABLE admin_credentials RENAME TO teacher_credentials;"))
                db.session.commit()
                # Refresh inspector
                inspector = sa.inspect(db.engine)
                actual_tables = inspector.get_table_names()
                print(f"ACTUAL DB TABLES (AFTER REPAIR): {actual_tables}")

            print("Database is clean (recreated by script).")

            print("Seeding foundational entities...")
            
            # 1. Legacy teacher compatibility shadows.
            teacher_happy = Admin(
                public_id="adm_happy_001",
                teacher_public_id="HAPPY-TEACHER",
                totp_secret="MFRGGZDFMZTWQ2LK",
                has_assigned_students=True,
                tos_accepted=True
            )
            teacher_adversarial = Admin(
                public_id="adm_adv_001",
                teacher_public_id="ADV-TEACHER",
                totp_secret="MFRGGZDFMZTWQ2LK",
                has_assigned_students=True,
                tos_accepted=True
            )
            db.session.add_all([teacher_happy, teacher_adversarial])
            db.session.flush()

            # 2. Class universe.
            economy = ClassEconomy(
                class_id=str(uuid.uuid4()),
                join_code="GOLDEN-V2",
                join_code_token="GOLDEN-V2",
                display_name="Canonical V2 Simulation",
                section="Period 1",
                teacher_id=teacher_happy.id,
                class_timezone="UTC"
            )
            db.session.add(economy)
            db.session.flush()

            # 3. Canonical global users.
            user_happy_teacher = User(
                user_role=UserRole.TEACHER,
                username_hash=hash_username_lookup("teacher_happy"),
                username_lookup_hash=hash_username_lookup("teacher_happy"),
                totp_secret_encrypted=teacher_happy.totp_secret,
                has_completed_setup=True,
            )
            user_adversarial_teacher = User(
                user_role=UserRole.TEACHER,
                username_hash=hash_username_lookup("teacher_adversarial"),
                username_lookup_hash=hash_username_lookup("teacher_adversarial"),
                totp_secret_encrypted=teacher_adversarial.totp_secret,
                has_completed_setup=True,
            )
            user_happy_student = User(
                user_role=UserRole.STUDENT,
                username_hash=hash_username_lookup("student_happy"),
                username_lookup_hash=hash_username_lookup("student_happy"),
                passphrase_hash="pbkdf2:sha256:260000$hashedpassword",
                has_completed_setup=True,
            )
            user_adv_student = User(
                user_role=UserRole.STUDENT,
                username_hash=hash_username_lookup("student_adversarial"),
                username_lookup_hash=hash_username_lookup("student_adversarial"),
                passphrase_hash="pbkdf2:sha256:260000$hashedpassword",
                has_completed_setup=True,
            )
            db.session.add_all([
                user_happy_teacher,
                user_adversarial_teacher,
                user_happy_student,
                user_adv_student,
            ])
            db.session.flush()

            # 4. Display profiles and legacy student compatibility shadows.
            ip_teacher = IdentityProfile(
                profile_type="teacher",
                first_name="Happy",
                last_name="T",
            )
            ip_happy = IdentityProfile(
                profile_type="student",
                first_name="Happy",
                last_name="H"
            )
            ip_adv = IdentityProfile(
                profile_type="student",
                first_name="Adversarial",
                last_name="A"
            )
            ip_unclaimed = IdentityProfile(
                profile_type="student",
                first_name="Unclaimed",
                last_name="S",
            )
            db.session.add_all([ip_teacher, ip_happy, ip_adv, ip_unclaimed])
            db.session.flush()
            
            student_happy = Student(
                identity_profile=ip_happy,
                block="A",
                class_id=economy.class_id,
                salt=os.urandom(16)
            )
            student_adv = Student(
                identity_profile=ip_adv,
                block="A",
                class_id=economy.class_id,
                salt=os.urandom(16)
            )
            db.session.add_all([student_happy, student_adv])
            db.session.flush()

            # 4.5 Link Students to Teachers (Invariant requirement)
            from app.models import StudentTeacher
            link_happy = StudentTeacher(student_id=student_happy.id, teacher_id=teacher_happy.id)
            link_adv = StudentTeacher(student_id=student_adv.id, teacher_id=teacher_happy.id) # Both in same class
            db.session.add_all([link_happy, link_adv])
            db.session.flush()

            # 5. Canonical class-local seats.
            teacher_seat = Seat(
                user_id=user_happy_teacher.id,
                class_id=economy.class_id,
                join_code=economy.join_code,
                role="teacher",
                claimed_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            seat_happy = Seat(
                user_id=user_happy_student.id,
                student_id=student_happy.id,
                class_id=economy.class_id,
                join_code=economy.join_code,
                role="student",
                claimed_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            seat_adv = Seat(
                user_id=user_adv_student.id,
                student_id=student_adv.id,
                class_id=economy.class_id,
                join_code=economy.join_code,
                role="student",
                claimed_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            unclaimed_seat = Seat(
                user_id=None,
                class_id=economy.class_id,
                join_code=economy.join_code,
                role="student",
                claim_first_name_hash=hash_username_lookup("unclaimed"),
                claim_last_name_hash=hash_username_lookup("student"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add_all([teacher_seat, seat_happy, seat_adv, unclaimed_seat])
            db.session.flush()

            ip_teacher.seat_id = teacher_seat.id
            ip_happy.seat_id = seat_happy.id
            ip_adv.seat_id = seat_adv.id
            ip_unclaimed.seat_id = unclaimed_seat.id
            user_happy_teacher.last_active_seat_id = teacher_seat.id
            user_happy_student.last_active_seat_id = seat_happy.id
            user_adv_student.last_active_seat_id = seat_adv.id
            db.session.flush()

            # 6. Insurance Policies
            policy_basic = InsurancePolicy(
                policy_code="BASIC-001",
                class_id=economy.class_id,
                teacher_id=teacher_happy.id,
                title="Basic Protection",
                premium=Decimal("10.00"),
                claim_type="legacy_monetary",
                version_number=1,
                bypass_cwi_warnings=False
            )
            db.session.add(policy_basic)
            db.session.flush()

            # 7. Ledger Mutations
            print("Recording ledger transactions...")
            
            # Happy Student: Income and Savings
            record_posted_transaction(
                seat_id=seat_happy.id,
                class_id=economy.class_id,
                amount=Decimal("100.00"),
                description="Initial Grant",
                account_type="checking",
                type="Grant"
            )
            record_posted_transaction(
                seat_id=seat_happy.id,
                class_id=economy.class_id,
                amount=Decimal("-50.00"),
                description="Transfer to Savings",
                account_type="checking",
                type="Transfer"
            )
            record_posted_transaction(
                seat_id=seat_happy.id,
                class_id=economy.class_id,
                amount=Decimal("50.00"),
                description="Transfer from Checking",
                account_type="savings",
                type="Transfer"
            )

            # Adversarial Student: Overdraft and Debt
            record_posted_transaction(
                seat_id=seat_adv.id,
                class_id=economy.class_id,
                amount=Decimal("10.00"),
                description="Small Grant",
                account_type="checking",
                type="Grant"
            )
            record_posted_transaction(
                seat_id=seat_adv.id,
                class_id=economy.class_id,
                amount=Decimal("-25.00"),
                description="Overdraft Purchase",
                account_type="checking",
                type="Purchase"
            )

            # 8. Issues & Resolution
            print("Seeding issues...")
            cat = IssueCategory(name="Accounting", category_type="transaction")
            db.session.add(cat)
            db.session.flush()
            
            issue = Issue(
                student_id=student_adv.id,
                actor_public_id=seat_adv.public_id,
                teacher_id=teacher_adversarial.id,
                class_id=economy.class_id,
                seat_id=seat_adv.id,
                join_code=economy.join_code,
                category_id=cat.id,
                issue_type="transaction",
                student_explanation="Incorrect Balance: I think I'm missing $5",
                status="OPEN"
            )
            db.session.add(issue)
            db.session.flush()

            # 9. Analytics and legacy roster compatibility shadow.
            print("Seeding analytics and legacy roster shadow...")
            snapshot = AnalyticsSnapshot(
                teacher_id=teacher_happy.id,
                class_id=economy.class_id,
                join_code=economy.join_code,
                window_type="week",
                window_start=datetime.utcnow() - timedelta(days=7),
                window_end=datetime.utcnow(),
                cwi_value=100.0,
                total_students=2,
                computed_at=datetime.utcnow(),
                is_complete=True
            )
            db.session.add(snapshot)
            
            block = TeacherBlock(
                teacher_id=teacher_happy.id,
                class_id=economy.class_id,
                join_code=economy.join_code,
                block="A",
                class_label="Period 1",
                first_name="Unclaimed",
                last_initial="S",
                identity_id=ip_unclaimed.id,
                salt=os.urandom(16),
                first_half_hash="dummy_hash_" + str(uuid.uuid4())
            )
            db.session.add(block)
            db.session.flush()

            # 10. Activity Logs (Taps, Hall Pass)
            # Assuming we need to import these
            from app.models import TapEvent, HallPassLog
            print("Seeding activity logs...")
            tap = TapEvent(
                student_id=student_happy.id,
                seat_id=seat_happy.id,
                class_id=economy.class_id,
                period="A",
                status="active",
                timestamp=datetime.utcnow()
            )
            db.session.add(tap)
            
            log = HallPassLog(
                student_id=student_happy.id,
                seat_id=seat_happy.id,
                class_id=economy.class_id,
                request_time=datetime.utcnow(),
                reason="Restroom",
                status="approved",
                period="A"
            )
            db.session.add(log)

            # 11. Rent & Insurance Activity
            from app.models import RentPayment, StudentInsurance
            print("Seeding rent and insurance...")
            rent = RentPayment(
                seat_id=seat_happy.id,
                class_id=economy.class_id,
                period="A",
                amount_paid=Decimal("20.00"),
                payment_date=datetime.utcnow(),
                coverage_month=datetime.utcnow().month,
                coverage_year=datetime.utcnow().year
            )
            db.session.add(rent)
            
            ins = StudentInsurance(
                seat_id=seat_happy.id,
                class_id=economy.class_id,
                policy_id=policy_basic.id,
                purchase_date=datetime.utcnow(),
                status="active"
            )
            db.session.add(ins)

            db.session.commit()

    print("Seeding complete.")

if __name__ == "__main__":
    seed()
