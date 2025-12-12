#!/usr/bin/env python3
"""
Comprehensive database seeding script for multi-tenancy testing.

This script creates realistic test data to validate join_code isolation between:
1. Different teachers
2. Same teacher with multiple periods
3. Students enrolled in various combinations

Outputs credentials to console (not to file, to avoid security issues).
"""

import os
import sys
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from app.models import (
    Admin, Student, TeacherBlock, StudentTeacher, Transaction,
    StoreItem, InsurancePolicy, StudentInsurance, InsuranceClaim,
    PayrollSettings, RentSettings
)
from app.utils.join_code import generate_join_code
from hash_utils import get_random_salt, hash_username, hash_username_lookup
from app.utils.claim_credentials import compute_primary_claim_hash
from app.utils.name_utils import hash_last_name_parts
from werkzeug.security import generate_password_hash
import pyotp


# ===================== CONFIGURATION =====================

TEACHERS = [
    {
        'username': 'ms_johnson',
        'periods': [
            {'block': 'A', 'name': 'English 1st Period'},
            {'block': 'B', 'name': 'English 3rd Period'},
            {'block': 'C', 'name': 'English 5th Period'},
        ]
    },
    {
        'username': 'mr_smith',
        'periods': [
            {'block': 'A', 'name': 'Math Period 1'},
            {'block': 'D', 'name': 'Math Period 4'},
        ]
    },
    {
        'username': 'mrs_davis',
        'periods': [
            {'block': 'B', 'name': 'Science 2nd Period'},
            {'block': 'E', 'name': 'Science 6th Period'},
        ]
    },
    {
        'username': 'dr_wilson',
        'periods': [
            {'block': 'F', 'name': 'History Period 7'},
        ]
    },
]

STUDENTS = [
    # Students with single teacher, single period
    {'first_name': 'Alice', 'last_name': 'Anderson', 'dob_sum': 2008, 'enrollments': [('ms_johnson', 'A')]},
    {'first_name': 'Bob', 'last_name': 'Baker', 'dob_sum': 2009, 'enrollments': [('mr_smith', 'A')]},

    # Students with multiple different teachers
    {'first_name': 'Carol', 'last_name': 'Chen', 'dob_sum': 2007, 'enrollments': [('ms_johnson', 'A'), ('mr_smith', 'A')]},
    {'first_name': 'David', 'last_name': 'Davis', 'dob_sum': 2008, 'enrollments': [('mr_smith', 'D'), ('mrs_davis', 'B')]},

    # CRITICAL: Students with same teacher in multiple periods
    {'first_name': 'Emma', 'last_name': 'Evans', 'dob_sum': 2009, 'enrollments': [('ms_johnson', 'A'), ('ms_johnson', 'B')]},
    {'first_name': 'Frank', 'last_name': 'Fisher', 'dob_sum': 2007, 'enrollments': [('ms_johnson', 'B'), ('ms_johnson', 'C')]},
    {'first_name': 'Grace', 'last_name': 'Garcia', 'dob_sum': 2008, 'enrollments': [('mr_smith', 'A'), ('mr_smith', 'D')]},

    # Students with complex multi-enrollment patterns
    {'first_name': 'Henry', 'last_name': 'Harris', 'dob_sum': 2009, 'enrollments': [('ms_johnson', 'A'), ('mr_smith', 'A'), ('mrs_davis', 'B')]},
    {'first_name': 'Isabel', 'last_name': 'Ivanov', 'dob_sum': 2007, 'enrollments': [('ms_johnson', 'C'), ('mrs_davis', 'E')]},

    # More students for variety
    {'first_name': 'Jack', 'last_name': 'Johnson', 'dob_sum': 2008, 'enrollments': [('mrs_davis', 'B')]},
    {'first_name': 'Kate', 'last_name': 'Kim', 'dob_sum': 2009, 'enrollments': [('dr_wilson', 'F')]},
    {'first_name': 'Liam', 'last_name': 'Lopez', 'dob_sum': 2007, 'enrollments': [('ms_johnson', 'B'), ('dr_wilson', 'F')]},
    {'first_name': 'Maya', 'last_name': 'Martinez', 'dob_sum': 2008, 'enrollments': [('mr_smith', 'A'), ('mrs_davis', 'E')]},
    {'first_name': 'Noah', 'last_name': 'Nguyen', 'dob_sum': 2009, 'enrollments': [('ms_johnson', 'C')]},
    {'first_name': 'Olivia', 'last_name': 'OBrien', 'dob_sum': 2007, 'enrollments': [('mr_smith', 'D'), ('mrs_davis', 'B'), ('dr_wilson', 'F')]},
]

STORE_ITEMS_TEMPLATES = [
    # Universal items (appear in all classes)
    {'name': 'Homework Pass', 'price': 50, 'type': 'delayed', 'description': 'Skip one homework assignment'},
    {'name': 'Extra Credit Points', 'price': 75, 'type': 'immediate', 'description': '+5 points on any assignment'},

    # Subject-specific items
    {'name': 'Essay Extension', 'price': 100, 'type': 'delayed', 'description': '2 extra days on essay', 'subjects': ['English']},
    {'name': 'Calculator Rental', 'price': 25, 'type': 'delayed', 'description': 'Rent graphing calculator', 'subjects': ['Math']},
    {'name': 'Lab Partner Choice', 'price': 60, 'type': 'immediate', 'description': 'Choose your lab partner', 'subjects': ['Science']},
    {'name': 'Historical Figure Interview', 'price': 80, 'type': 'delayed', 'description': 'Extra credit project', 'subjects': ['History']},

    # Period-specific items
    {'name': 'Front Row Seat (Week)', 'price': 40, 'type': 'delayed', 'description': 'Reserved front seat'},
    {'name': 'Music During Work', 'price': 30, 'type': 'delayed', 'description': 'Use headphones for 1 week'},
    {'name': 'Group Project Leader', 'price': 90, 'type': 'immediate', 'description': 'Lead next group project'},
    {'name': 'Book Report Waiver', 'price': 120, 'type': 'immediate', 'description': 'Skip one book report'},
]

INSURANCE_TEMPLATES = [
    # Grouped paycheck protection (tiered)
    {
        'title': 'Paycheck Protection - Basic',
        'premium': 20,
        'max_claim_amount': 50,
        'waiting_period': 7,
        'tier_category_id': 1,
        'tier_name': 'Paycheck Protection',
        'shared': True
    },
    {
        'title': 'Paycheck Protection - Standard',
        'premium': 35,
        'max_claim_amount': 100,
        'waiting_period': 7,
        'tier_category_id': 1,
        'tier_name': 'Paycheck Protection',
        'shared': True
    },
    {
        'title': 'Paycheck Protection - Premium',
        'premium': 50,
        'max_claim_amount': 200,
        'waiting_period': 7,
        'tier_category_id': 1,
        'tier_name': 'Paycheck Protection',
        'shared': False  # Only some classes
    },

    # Independent policies
    {
        'title': 'Late Assignment Insurance',
        'premium': 25,
        'max_claim_amount': 75,
        'waiting_period': 5,
        'tier_category_id': None,
        'tier_name': None,
        'shared': True
    },
    {
        'title': 'Test Retake Coverage',
        'premium': 40,
        'max_claim_amount': 150,
        'waiting_period': 10,
        'tier_category_id': None,
        'tier_name': None,
        'shared': False
    },
]


# ===================== HELPER FUNCTIONS =====================

def create_teacher(username, totp_secret=None):
    """Create a teacher account with TOTP secret."""
    if not totp_secret:
        totp_secret = pyotp.random_base32()

    teacher = Admin(
        username=username,
        totp_secret=totp_secret,
        created_at=datetime.now(timezone.utc),
        has_assigned_students=True
    )
    db.session.add(teacher)
    db.session.flush()
    return teacher


def create_student_with_seat(first_name, last_name, dob_sum, teacher, block, join_code):
    """
    Create a student account and claim a seat in a teacher's class.

    Returns tuple: (student, teacher_block, username, password_credential)
    """
    salt = get_random_salt()

    # Generate username (first name + last initial + dob_sum)
    last_initial = last_name[0].upper()
    username = f"{first_name.lower()}{last_initial.lower()}{dob_sum}"

    # Generate hashes
    first_half_hash = compute_primary_claim_hash(first_name[0].upper(), dob_sum, salt)
    username_hash = hash_username(username, salt)
    username_lookup_hash = hash_username_lookup(username)
    last_name_hash = hash_last_name_parts(last_name, salt)

    # Password credential is first_initial + dob_sum
    password_credential = f"{first_name[0].upper()}{dob_sum}"

    # Create student
    student = Student(
        first_name=first_name,
        last_initial=last_initial,
        block=block,
        salt=salt,
        first_half_hash=first_half_hash,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
        last_name_hash_by_part=last_name_hash,
        dob_sum=dob_sum,
        hall_passes=3,
        has_completed_setup=True,
        teacher_id=teacher.id,  # Primary owner
        pin_hash=generate_password_hash(password_credential),  # Set PIN for login
    )
    db.session.add(student)
    db.session.flush()

    # Create TeacherBlock (claimed seat)
    teacher_block = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial=last_initial,
        last_name_hash_by_part=last_name_hash,
        dob_sum=dob_sum,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code=join_code,
        student_id=student.id,
        is_claimed=True,
        claimed_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
    )
    db.session.add(teacher_block)

    # Create StudentTeacher link
    student_teacher = StudentTeacher(
        student_id=student.id,
        admin_id=teacher.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
    )
    db.session.add(student_teacher)

    db.session.flush()

    return student, teacher_block, username, password_credential


def create_transactions(student, teacher, join_code, num_transactions=10):
    """Create varied transactions for a student in a specific class."""
    transaction_types = [
        ('Daily Attendance', 10, 'checking', 'Deposit'),
        ('Quiz Bonus', 25, 'checking', 'Deposit'),
        ('Homework Completion', 15, 'checking', 'Deposit'),
        ('Participation Points', 20, 'checking', 'Deposit'),
        ('Late Assignment Penalty', -10, 'checking', 'Fine'),
        ('Transfer to Savings', -50, 'checking', 'Withdrawal'),
        ('Transfer to Savings', 50, 'savings', 'Deposit'),
        ('Interest Payment', 5, 'savings', 'Interest'),
        ('Purchase: Snack', -20, 'checking', 'Purchase'),
        ('Rent Payment', -50, 'checking', 'Rent Payment'),
    ]

    base_date = datetime.now(timezone.utc) - timedelta(days=30)

    for i in range(num_transactions):
        tx_type = random.choice(transaction_types)
        description, amount, account, tx_category = tx_type

        # Add some variation to amounts
        if amount > 0:
            amount = amount + random.randint(-5, 5)
        elif amount < 0:
            amount = amount + random.randint(-5, 5)

        transaction = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,  # CRITICAL: Must have join_code
            amount=amount,
            account_type=account,
            type=tx_category,
            description=description,
            timestamp=base_date + timedelta(days=i),
            is_void=False
        )
        db.session.add(transaction)


def create_store_items(teacher, period_name, block):
    """Create store items for a teacher's period."""
    items_created = []

    for item_template in STORE_ITEMS_TEMPLATES:
        # Check if item should be created for this class
        if 'subjects' in item_template:
            # Subject-specific items
            subject = period_name.split()[0]  # e.g., "English" from "English 1st Period"
            if subject not in item_template['subjects']:
                continue

        # Determine if visible to all blocks or just this block
        visible_to_all = item_template.get('name') in ['Homework Pass', 'Extra Credit Points']

        # Check if item already exists for this teacher (for universal items)
        if visible_to_all:
            existing = StoreItem.query.filter_by(
                teacher_id=teacher.id,
                name=item_template['name']
            ).first()
            if existing:
                # Just add this block to visibility
                if block not in existing.blocks_list:
                    existing.set_blocks(existing.blocks_list + [block])
                continue

        item = StoreItem(
            teacher_id=teacher.id,
            name=item_template['name'],
            description=item_template.get('description', ''),
            price=item_template['price'],
            item_type=item_template['type'],
            is_active=True,
            inventory=None,  # Unlimited
            limit_per_student=None
        )
        db.session.add(item)
        db.session.flush()

        # Set block visibility
        if not visible_to_all:
            item.set_blocks([block])

        items_created.append(item)

    return items_created


def create_insurance_policies(teacher, period_name, block):
    """Create insurance policies for a teacher's period."""
    policies_created = []

    for idx, policy_template in enumerate(INSURANCE_TEMPLATES):
        # Determine if this policy should be created
        if policy_template['shared']:
            # Check if already exists for this teacher
            existing = InsurancePolicy.query.filter_by(
                teacher_id=teacher.id,
                title=policy_template['title']
            ).first()
            if existing:
                # Add block to visibility
                if block not in existing.blocks_list:
                    existing.set_blocks(existing.blocks_list + [block])
                continue
        else:
            # Only create for some periods (randomly)
            if random.random() < 0.5:
                continue

        policy_code = f"{teacher.username[:3].upper()}{block}{idx+1:02d}"

        policy = InsurancePolicy(
            policy_code=policy_code,
            teacher_id=teacher.id,
            title=policy_template['title'],
            description=f"Coverage for {policy_template['title'].lower()}",
            premium=policy_template['premium'],
            charge_frequency='monthly',
            autopay=True,
            waiting_period_days=policy_template['waiting_period'],
            max_claim_amount=policy_template['max_claim_amount'],
            max_claims_count=3,
            max_claims_period='month',
            claim_type='transaction_monetary',
            is_monetary=True,
            tier_category_id=policy_template.get('tier_category_id'),
            tier_name=policy_template.get('tier_name'),
            is_active=True
        )
        db.session.add(policy)
        db.session.flush()

        # Set block visibility (empty list = all blocks)
        if not policy_template['shared']:
            policy.set_blocks([block])

        policies_created.append(policy)

    return policies_created


def purchase_insurance_for_student(student, policy, join_code, teacher, past_waiting_period=False):
    """Purchase insurance for a student and optionally create a claim."""
    purchase_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 20))

    if past_waiting_period:
        # Make purchase old enough to be past waiting period
        purchase_date = datetime.now(timezone.utc) - timedelta(days=policy.waiting_period_days + 5)

    coverage_start = purchase_date + timedelta(days=policy.waiting_period_days)

    student_insurance = StudentInsurance(
        student_id=student.id,
        policy_id=policy.id,
        status='active',
        purchase_date=purchase_date,
        last_payment_date=purchase_date,
        next_payment_due=purchase_date + timedelta(days=30),
        coverage_start_date=coverage_start,
        payment_current=True,
        days_unpaid=0
    )
    db.session.add(student_insurance)
    db.session.flush()

    # Create premium payment transaction
    premium_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code=join_code,
        amount=-policy.premium,
        account_type='checking',
        type='insurance_premium',
        description=f"Insurance: {policy.title}",
        timestamp=purchase_date,
        is_void=False
    )
    db.session.add(premium_tx)

    # If past waiting period, maybe create a claim
    if past_waiting_period and random.random() < 0.3:  # 30% chance of claim
        incident_date = coverage_start + timedelta(days=random.randint(1, 10))
        claim_amount = min(random.randint(30, 100), policy.max_claim_amount or 1000)

        claim = InsuranceClaim(
            student_insurance_id=student_insurance.id,
            policy_id=policy.id,
            student_id=student.id,
            incident_date=incident_date,
            filed_date=incident_date + timedelta(days=1),
            description=f"Claim for {policy.title}",
            claim_amount=claim_amount,
            status='approved' if random.random() < 0.7 else 'pending',
            approved_amount=claim_amount,
            processed_date=incident_date + timedelta(days=2),
            processed_by_admin_id=teacher.id
        )
        db.session.add(claim)

        # Create claim payout transaction if approved
        if claim.status == 'approved':
            claim_tx = Transaction(
                student_id=student.id,
                teacher_id=teacher.id,
                join_code=join_code,
                amount=claim_amount,
                account_type='checking',
                type='insurance_claim',
                description=f"Insurance Claim: {policy.title}",
                timestamp=claim.processed_date,
                is_void=False
            )
            db.session.add(claim_tx)


def create_payroll_settings(teacher, block):
    """Create payroll settings for a teacher's period."""
    settings = PayrollSettings(
        teacher_id=teacher.id,
        block=block,
        pay_rate=round(random.uniform(0.20, 0.40), 2),
        payroll_frequency_days=random.choice([7, 14, 30]),
        next_payroll_date=datetime.now(timezone.utc) + timedelta(days=7),
        is_active=True,
        settings_mode='simple',
        overtime_multiplier=1.5,
        time_unit='minutes',
        pay_schedule_type='biweekly',
        rounding_mode='down'
    )
    db.session.add(settings)
    return settings


def create_rent_settings(teacher, block):
    """Create rent settings for a teacher's period."""
    settings = RentSettings(
        teacher_id=teacher.id,
        block=block,
        is_enabled=True,
        rent_amount=random.choice([40, 50, 60, 75]),
        frequency_type='monthly',
        grace_period_days=3,
        late_penalty_amount=10,
        late_penalty_type='once',
        bill_preview_enabled=True,
        bill_preview_days=7,
        allow_incremental_payment=False,
        prevent_purchase_when_late=True
    )
    db.session.add(settings)
    return settings


# ===================== MAIN SEEDING FUNCTION =====================

def seed_database():
    """Main seeding function."""
    print("🌱 Starting database seeding...")
    print("=" * 60)

    credentials = {
        'teachers': [],
        'students': [],
        'class_info': []
    }

    teacher_map = {}  # username -> {teacher_obj, periods: {block -> {join_code, ...}}}
    student_map = {}  # name -> student_obj

    # ===== CREATE TEACHERS AND PERIODS =====
    print("\n📚 Creating teachers and class periods...")
    for teacher_config in TEACHERS:
        username = teacher_config['username']
        totp_secret = pyotp.random_base32()

        teacher = create_teacher(username, totp_secret)
        print(f"  ✓ Created teacher: {username}")

        teacher_map[username] = {
            'teacher': teacher,
            'totp_secret': totp_secret,
            'periods': {}
        }

        credentials['teachers'].append({
            'username': username,
            'totp_secret': totp_secret,
            'totp_url': pyotp.totp.TOTP(totp_secret).provisioning_uri(
                name=username,
                issuer_name='ClassroomEconomy'
            )
        })

        # Create periods for this teacher
        for period in teacher_config['periods']:
            block = period['block']
            period_name = period['name']
            join_code = generate_join_code()

            teacher_map[username]['periods'][block] = {
                'join_code': join_code,
                'name': period_name
            }

            print(f"    • Period {block}: {period_name} (Join: {join_code})")

            credentials['class_info'].append({
                'teacher': username,
                'period': block,
                'name': period_name,
                'join_code': join_code
            })

            # Create period-specific settings
            create_payroll_settings(teacher, block)
            create_rent_settings(teacher, block)

            # Create store items and insurance for this period
            create_store_items(teacher, period_name, block)
            create_insurance_policies(teacher, period_name, block)

    db.session.commit()
    print(f"\n✅ Created {len(TEACHERS)} teachers with {sum(len(t['periods']) for t in TEACHERS)} total periods")

    # ===== CREATE STUDENTS =====
    print("\n👥 Creating students...")
    for student_config in STUDENTS:
        first_name = student_config['first_name']
        last_name = student_config['last_name']
        dob_sum = student_config['dob_sum']
        enrollments = student_config['enrollments']

        print(f"\n  Student: {first_name} {last_name}")

        student_obj = None
        student_creds = {
            'name': f"{first_name} {last_name}",
            'enrollments': []
        }

        for idx, (teacher_username, block) in enumerate(enrollments):
            teacher_info = teacher_map[teacher_username]
            teacher = teacher_info['teacher']
            period_info = teacher_info['periods'][block]
            join_code = period_info['join_code']
            period_name = period_info['name']

            if student_obj is None:
                # Create student on first enrollment
                student_obj, seat, username, password = create_student_with_seat(
                    first_name, last_name, dob_sum, teacher, block, join_code
                )
                student_map[first_name] = student_obj
                student_creds['username'] = username
                student_creds['password'] = password
            else:
                # Additional enrollment - just create seat and link
                salt = student_obj.salt
                last_name_hash = student_obj.last_name_hash_by_part
                first_half_hash = student_obj.first_half_hash

                seat = TeacherBlock(
                    teacher_id=teacher.id,
                    block=block,
                    first_name=first_name,
                    last_initial=last_name[0].upper(),
                    last_name_hash_by_part=last_name_hash,
                    dob_sum=dob_sum,
                    salt=salt,
                    first_half_hash=first_half_hash,
                    join_code=join_code,
                    student_id=student_obj.id,
                    is_claimed=True,
                    claimed_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
                )
                db.session.add(seat)

                # Create StudentTeacher link if doesn't exist
                existing_link = StudentTeacher.query.filter_by(
                    student_id=student_obj.id,
                    admin_id=teacher.id
                ).first()

                if not existing_link:
                    student_teacher = StudentTeacher(
                        student_id=student_obj.id,
                        admin_id=teacher.id
                    )
                    db.session.add(student_teacher)

            # Create transactions for this enrollment
            num_transactions = random.randint(8, 15)
            create_transactions(student_obj, teacher, join_code, num_transactions)

            # Maybe purchase insurance
            if random.random() < 0.4:  # 40% chance
                available_policies = InsurancePolicy.query.filter_by(
                    teacher_id=teacher.id,
                    is_active=True
                ).all()

                # Filter by block visibility
                available_policies = [
                    p for p in available_policies
                    if not p.blocks_list or block in p.blocks_list
                ]

                if available_policies:
                    policy = random.choice(available_policies)
                    past_waiting = random.random() < 0.6  # 60% past waiting period
                    purchase_insurance_for_student(
                        student_obj, policy, join_code, teacher, past_waiting
                    )

                    student_creds['enrollments'].append({
                        'teacher': teacher_username,
                        'period': block,
                        'join_code': join_code,
                        'class_name': period_name,
                        'insurance': policy.title if past_waiting else None
                    })
                    continue

            student_creds['enrollments'].append({
                'teacher': teacher_username,
                'period': block,
                'join_code': join_code,
                'class_name': period_name
            })

            print(f"    ✓ Enrolled in {teacher_username} - {period_name} ({join_code})")

        credentials['students'].append(student_creds)

    db.session.commit()
    print(f"\n✅ Created {len(STUDENTS)} students with varied enrollments")

    # ===== OUTPUT CREDENTIALS TO CONSOLE =====
    print("\n" + "=" * 80)
    print("📝 TEST CREDENTIALS (dynamically generated)")
    print("=" * 80)

    # Teachers
    print("\n" + "-" * 80)
    print("TEACHER ACCOUNTS")
    print("-" * 80)
    for teacher_cred in credentials['teachers']:
        print(f"\nUsername: {teacher_cred['username']}")
        print(f"TOTP Secret: {teacher_cred['totp_secret']}")
        print(f"TOTP Setup URL: {teacher_cred['totp_url']}")

    # Class periods
    print("\n" + "-" * 80)
    print("CLASS PERIODS & JOIN CODES")
    print("-" * 80)
    for class_info in credentials['class_info']:
        print(f"\n{class_info['teacher']} - Period {class_info['period']}: {class_info['name']}")
        print(f"  Join Code: {class_info['join_code']}")

    # Students
    print("\n" + "-" * 80)
    print("STUDENT ACCOUNTS")
    print("-" * 80)
    print("\nStudent Login Format: Username + Password (PIN)")

    for student_cred in credentials['students']:
        print(f"\n{student_cred['name']}")
        print(f"  Username: {student_cred['username']}")
        print(f"  Password: {student_cred['password']}")
        print(f"  Enrollments:")
        for enrollment in student_cred['enrollments']:
            print(f"    • {enrollment['class_name']} ({enrollment['teacher']}, Period {enrollment['period']})")
            print(f"      Join Code: {enrollment['join_code']}")
            if enrollment.get('insurance'):
                print(f"      Insurance: {enrollment['insurance']} ✓")

    # Test scenarios
    print("\n" + "=" * 80)
    print("CRITICAL TEST SCENARIOS")
    print("=" * 80)

    print("\n1. SAME TEACHER, DIFFERENT PERIODS (Critical!):")
    print("   Emma Evans: Enrolled in ms_johnson Periods A & B")
    print("   Frank Fisher: Enrolled in ms_johnson Periods B & C")
    print("   Grace Garcia: Enrolled in mr_smith Periods A & D")
    print("   → Test: Balances and transactions should be ISOLATED per period")

    print("\n2. DIFFERENT TEACHERS, SAME STUDENT:")
    print("   Carol Chen: ms_johnson + mr_smith")
    print("   Henry Harris: ms_johnson + mr_smith + mrs_davis")
    print("   → Test: Each teacher's class should show separate data")

    print("\n3. SINGLE ENROLLMENT (Control):")
    print("   Alice Anderson: ms_johnson Period A only")
    print("   Bob Baker: mr_smith Period A only")
    print("   → Test: Simple baseline - should see only their own data")

    print("\n" + "=" * 80)
    print("VALIDATION CHECKLIST")
    print("=" * 80)
    print("\n□ Students in same teacher's different periods see isolated balances")
    print("□ Transactions filtered correctly by join_code")
    print("□ Store items respect block visibility settings")
    print("□ Insurance policies respect block visibility")
    print("□ Switching between classes changes visible data")
    print("□ No cross-period data leaks for same teacher")
    print("□ No cross-teacher data leaks")
    print("□ All transactions have join_code populated")
    print("□ Database queries filter by join_code, not just teacher_id")

    # Summary statistics
    print("\n" + "=" * 60)
    print("📊 SEEDING SUMMARY")
    print("=" * 60)
    print(f"Teachers created: {Admin.query.count()}")
    print(f"Students created: {Student.query.count()}")
    print(f"Class periods (seats): {TeacherBlock.query.filter_by(is_claimed=True).count()}")
    print(f"Transactions created: {Transaction.query.count()}")
    print(f"  - With join_code: {Transaction.query.filter(Transaction.join_code.isnot(None)).count()}")
    print(f"  - Without join_code: {Transaction.query.filter(Transaction.join_code.is_(None)).count()}")
    print(f"Store items: {StoreItem.query.count()}")
    print(f"Insurance policies: {InsurancePolicy.query.count()}")
    print(f"Student insurance purchases: {StudentInsurance.query.count()}")
    print(f"Insurance claims: {InsuranceClaim.query.count()}")
    print(f"Payroll settings: {PayrollSettings.query.count()}")
    print(f"Rent settings: {RentSettings.query.count()}")
    print("=" * 60)

    print("\n✨ Seeding complete!")
    print("\n⚠️  Note: Credentials are displayed above (not saved to file for security)")


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed_database()
