"""
Tests for the Jobs feature.

Tests cover:
- Model creation and relationships
- Job template CRUD operations
- Job assignment to periods
- Application workflow
- Employee management (warnings, firing, cooldowns)
- Contract job workflow
- Penalty system for improper quitting
"""

import pytest
from datetime import datetime, timedelta, timezone

from app import db
from app.models import (
    Admin, Student, TeacherBlock, JobTemplate, Job, JobApplication,
    EmployeeJobAssignment, EmployeeJobWarning, ContractJobClaim,
    JobApplicationBan, JobsSettings, Transaction, FeatureSettings
)
from hash_utils import hash_username, get_random_salt


@pytest.fixture
def admin_user(client):
    """Create a test admin user."""
    admin = Admin(
        username="testteacher",
        totp_secret="JBSWY3DPEHPK3PXP"
    )
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def student_user(client, admin_user):
    """Create a test student user."""
    salt = get_random_salt()
    student = Student(
        first_name="TestStudent",
        last_initial="S",
        block="A",
        salt=salt,
        first_half_hash=hash_username("S2025", salt),
        dob_sum=2025
    )
    db.session.add(student)
    db.session.commit()
    return student


@pytest.fixture
def teacher_block(client, admin_user):
    """Create a teacher block with join code."""
    block = TeacherBlock(
        teacher_id=admin_user.id,
        block="A",
        first_name="TestStudent",
        last_initial="S",
        last_name_hash_by_part=["hash"],
        dob_sum=2025,
        salt=get_random_salt(),
        first_half_hash="test",
        join_code="TEST123",
        is_claimed=False
    )
    db.session.add(block)
    db.session.commit()
    return block


class TestJobModels:
    """Test job model creation and relationships."""

    def test_create_employee_job_template(self, client, admin_user):
        """Test creating an employee job template."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Class Monitor",
            job_description="Monitor classroom activities",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=2,
            requirements="Responsible and punctual",
            notice_period_days=7,
            warning_cooldown_days=3,
            improper_quit_penalty_type="days_ban",
            improper_quit_penalty_days=14,
            application_questions=[
                {"question": "Why do you want this job?", "required": True}
            ]
        )
        db.session.add(template)
        db.session.commit()

        assert template.id is not None
        assert template.job_type == "employee"
        assert template.salary_amount == 50.0
        assert len(template.application_questions) == 1

    def test_create_contract_job_template(self, client, admin_user):
        """Test creating a contract job template."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Organize Library",
            job_description="Organize books in library",
            job_type="contract",
            bounty_amount=25.0
        )
        db.session.add(template)
        db.session.commit()

        assert template.id is not None
        assert template.job_type == "contract"
        assert template.bounty_amount == 25.0

    def test_job_assignment_to_period(self, client, admin_user, teacher_block):
        """Test assigning a job template to a specific period."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code,
            is_active=True
        )
        db.session.add(job)
        db.session.commit()

        assert job.id is not None
        assert job.block == "A"
        assert job.join_code == "TEST123"
        assert job.template == template

    def test_job_application_creation(self, client, admin_user, student_user, teacher_block):
        """Test creating a job application."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1,
            application_questions=[
                {"question": "Why do you want this job?", "required": True}
            ]
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        application = JobApplication(
            job_id=job.id,
            student_id=student_user.id,
            answers=[
                {"question": "Why do you want this job?", "answer": "I am responsible"}
            ],
            status="pending"
        )
        db.session.add(application)
        db.session.commit()

        assert application.id is not None
        assert application.status == "pending"
        assert len(application.answers) == 1


class TestEmployeeJobWorkflow:
    """Test employee job workflow from application to termination."""

    def test_application_acceptance_creates_assignment(self, client, admin_user, student_user, teacher_block):
        """Test that accepting an application creates an employee assignment."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        application = JobApplication(
            job_id=job.id,
            student_id=student_user.id,
            answers=[],
            status="accepted"
        )
        db.session.add(application)
        db.session.commit()

        # Create assignment (simulating what route would do)
        assignment = EmployeeJobAssignment(
            job_id=job.id,
            student_id=student_user.id,
            is_active=True
        )
        db.session.add(assignment)
        db.session.commit()

        assert assignment.is_active
        assert assignment.warnings_count == 0

    def test_warning_system(self, client, admin_user, student_user, teacher_block):
        """Test issuing warnings to employees."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1,
            warning_cooldown_days=3
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        assignment = EmployeeJobAssignment(
            job_id=job.id,
            student_id=student_user.id,
            is_active=True
        )
        db.session.add(assignment)
        db.session.commit()

        # Issue warning
        warning = EmployeeJobWarning(
            assignment_id=assignment.id,
            warning_text="Late to work",
            issued_by_admin_id=admin_user.id
        )
        assignment.warnings_count += 1
        assignment.last_warning_date = datetime.now(timezone.utc)

        db.session.add(warning)
        db.session.commit()

        assert assignment.warnings_count == 1
        assert assignment.last_warning_date is not None

    def test_firing_with_cooldown(self, client, admin_user, student_user, teacher_block):
        """Test that cooldown period is enforced before firing."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1,
            warning_cooldown_days=3
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        assignment = EmployeeJobAssignment(
            job_id=job.id,
            student_id=student_user.id,
            is_active=True,
            last_warning_date=datetime.now(timezone.utc)
        )
        db.session.add(assignment)
        db.session.commit()

        # Check cooldown
        cooldown_end = assignment.last_warning_date + timedelta(days=template.warning_cooldown_days)
        can_fire = datetime.now(timezone.utc) >= cooldown_end

        assert not can_fire  # Should not be able to fire immediately after warning


class TestContractJobWorkflow:
    """Test contract job workflow from claim to payment."""

    def test_contract_job_claim(self, client, admin_user, student_user, teacher_block):
        """Test claiming a contract job."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Organize Library",
            job_type="contract",
            bounty_amount=25.0
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        claim = ContractJobClaim(
            job_id=job.id,
            student_id=student_user.id,
            status="claimed"
        )
        db.session.add(claim)
        db.session.commit()

        assert claim.status == "claimed"
        assert claim.claimed_at is not None

    def test_contract_completion_and_payment(self, client, admin_user, student_user, teacher_block):
        """Test completing a contract job and receiving payment."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Organize Library",
            job_type="contract",
            bounty_amount=25.0
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        claim = ContractJobClaim(
            job_id=job.id,
            student_id=student_user.id,
            status="submitted",
            student_notes="I finished organizing the library"
        )
        db.session.add(claim)
        db.session.commit()

        # Teacher approves and creates transaction
        claim.status = "approved"
        claim.teacher_reviewed_at = datetime.now(timezone.utc)

        transaction = Transaction(
            student_id=student_user.id,
            teacher_id=admin_user.id,
            join_code=teacher_block.join_code,
            amount=template.bounty_amount,
            account_type="checking",
            description=f"Contract job: {template.job_title}",
            type="job_payment"
        )
        db.session.add(transaction)
        db.session.commit()

        claim.transaction_id = transaction.id
        claim.payment_amount = template.bounty_amount
        db.session.commit()

        assert claim.status == "approved"
        assert claim.payment_amount == 25.0
        assert transaction.amount == 25.0


class TestJobPenaltySystem:
    """Test penalty system for improper quitting."""

    def test_improper_quit_creates_ban(self, client, admin_user, student_user, teacher_block):
        """Test that quitting without notice creates a ban."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1,
            notice_period_days=7,
            improper_quit_penalty_type="days_ban",
            improper_quit_penalty_days=14
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        assignment = EmployeeJobAssignment(
            job_id=job.id,
            student_id=student_user.id,
            is_active=False,
            termination_type="quit_without_notice"
        )
        db.session.add(assignment)
        db.session.commit()

        # Create ban (simulating what route would do)
        ban = JobApplicationBan(
            student_id=student_user.id,
            teacher_id=admin_user.id,
            join_code=teacher_block.join_code,
            ban_type="all_jobs",
            banned_until=datetime.now(timezone.utc) + timedelta(days=14),
            reason="Quit without proper notice"
        )
        db.session.add(ban)
        db.session.commit()

        assert ban.ban_type == "all_jobs"
        assert ban.is_active

    def test_job_specific_ban(self, client, admin_user, student_user, teacher_block):
        """Test banning from a specific job only."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1,
            improper_quit_penalty_type="job_specific_ban",
            improper_quit_penalty_days=30
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        ban = JobApplicationBan(
            student_id=student_user.id,
            teacher_id=admin_user.id,
            join_code=teacher_block.join_code,
            ban_type="specific_job",
            job_template_id=template.id,
            banned_until=datetime.now(timezone.utc) + timedelta(days=30),
            reason="Quit without proper notice"
        )
        db.session.add(ban)
        db.session.commit()

        assert ban.ban_type == "specific_job"
        assert ban.job_template_id == template.id


class TestJobsSettings:
    """Test jobs settings configuration."""

    def test_create_jobs_settings(self, client, admin_user):
        """Test creating jobs settings for a teacher."""
        settings = JobsSettings(
            teacher_id=admin_user.id,
            block=None,  # Global settings
            employee_jobs_enabled=True,
            contract_jobs_enabled=True,
            auto_post_new_jobs=True,
            require_application_approval=True,
            setup_completed=False
        )
        db.session.add(settings)
        db.session.commit()

        assert settings.id is not None
        assert settings.employee_jobs_enabled
        assert settings.contract_jobs_enabled

    def test_jobs_enabled_in_feature_settings(self, client, admin_user):
        """Test that jobs_enabled flag exists in FeatureSettings."""
        feature_settings = FeatureSettings(
            teacher_id=admin_user.id,
            block=None,
            jobs_enabled=True
        )
        db.session.add(feature_settings)
        db.session.commit()

        assert feature_settings.jobs_enabled


class TestCascadeDeletes:
    """Test that CASCADE deletes work correctly."""

    def test_delete_teacher_deletes_templates(self, client_with_fk, admin_user):
        """Test that deleting a teacher deletes their job templates."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1
        )
        db.session.add(template)
        db.session.commit()

        template_id = template.id

        # Delete teacher
        db.session.delete(admin_user)
        db.session.commit()

        # Template should be deleted
        deleted_template = JobTemplate.query.get(template_id)
        assert deleted_template is None

    def test_delete_template_deletes_jobs(self, client_with_fk, admin_user, teacher_block):
        """Test that deleting a template deletes all its job instances."""
        template = JobTemplate(
            teacher_id=admin_user.id,
            job_title="Test Job",
            job_type="employee",
            salary_amount=50.0,
            payment_frequency="monthly",
            vacancies=1
        )
        db.session.add(template)
        db.session.commit()

        job = Job(
            template_id=template.id,
            teacher_id=admin_user.id,
            block=teacher_block.block,
            join_code=teacher_block.join_code
        )
        db.session.add(job)
        db.session.commit()

        job_id = job.id

        # Delete template
        db.session.delete(template)
        db.session.commit()

        # Job should be deleted
        deleted_job = Job.query.get(job_id)
        assert deleted_job is None
