"""
Admin routes for Jobs feature - imported into main admin blueprint.

Handles teacher-side job management including:
- Job bank (template management)
- Job assignments to periods
- Application reviews
- Employee job management
- Contract job reviews
"""

from datetime import datetime, timedelta, timezone
from flask import flash, request, session, redirect, url_for
from sqlalchemy import desc, tuple_

from app.extensions import db
from app.models import (
    ContractJobClaim,
    ContractJobStatus,
    EmployeeJobAssignment,
    EmployeeJobWarning,
    Job,
    JobApplication,
    JobApplicationStatus,
    JobTemplate,
    JobType,
    PaymentFrequency,
    PenaltyType,
    Student,
    TeacherBlock,
    TerminationType,
    Transaction,
)
from app.auth import admin_required
from app.utils.helpers import render_template_with_fallback as render_template
from forms import (
    ContractJobReviewForm,
    EmployeeWarningForm,
    JobApplicationReviewForm,
    JobTemplateForm,
)


def _extract_application_questions_from_form():
    """Extract dynamic application questions from the request form."""
    application_questions = []
    question_count = int(request.form.get('question_count', 0))
    for i in range(question_count):
        question_text = request.form.get(f'question_{i}')
        if question_text:
            application_questions.append({
                'question': question_text,
                'required': True
            })
    return application_questions if application_questions else None


def register_jobs_routes(admin_bp):
    """Register all jobs-related routes to the admin blueprint."""

    # -------------------- JOB BANK / DASHBOARD --------------------

    @admin_bp.route('/jobs')
    @admin_required
    def jobs_dashboard():
        """Main jobs dashboard - view job bank and active jobs."""
        admin_id = session.get('admin_id')
        selected_period = request.args.get('period', session.get('selected_period', 'all'))

        # Get job templates for this teacher
        templates = JobTemplate.query.filter_by(
            teacher_id=admin_id,
            is_active=True
        ).order_by(desc(JobTemplate.created_at)).all()

        # Get active jobs
        if selected_period != 'all':
            active_jobs = Job.query.filter_by(
                teacher_id=admin_id,
                block=selected_period,
                is_active=True
            ).all()
        else:
            active_jobs = Job.query.filter_by(
                teacher_id=admin_id,
                is_active=True
            ).all()

        # Get pending applications count
        pending_apps_count = JobApplication.query.join(Job).filter(
            Job.teacher_id == admin_id,
            JobApplication.status == JobApplicationStatus.PENDING
        ).count()

        # Get pending contract completions count
        pending_contracts_count = ContractJobClaim.query.join(Job).filter(
            Job.teacher_id == admin_id,
            ContractJobClaim.status == ContractJobStatus.SUBMITTED
        ).count()

        return render_template('admin_jobs_dashboard.html',
            templates=templates,
            active_jobs=active_jobs,
            pending_apps_count=pending_apps_count,
            pending_contracts_count=pending_contracts_count,
            selected_period=selected_period
        )


    # -------------------- JOB TEMPLATE MANAGEMENT --------------------

    @admin_bp.route('/jobs/template/create', methods=['GET', 'POST'])
    @admin_required
    def create_job_template():
        """Create a new job template for the job bank."""
        admin_id = session.get('admin_id')
        form = JobTemplateForm()

        if form.validate_on_submit():
            # Get application questions from form data (dynamically added via JavaScript)
            application_questions = _extract_application_questions_from_form()

            template = JobTemplate(
                teacher_id=admin_id,
                job_title=form.job_title.data,
                job_description=form.job_description.data,
                job_type=JobType(form.job_type.data),
                is_active=form.is_active.data
            )

            # Set type-specific fields
            if template.job_type == JobType.EMPLOYEE:
                template.salary_amount = form.salary_amount.data
                template.payment_frequency = (
                    PaymentFrequency(form.payment_frequency.data)
                    if form.payment_frequency.data else None
                )
                template.vacancies = form.vacancies.data
                template.requirements = form.requirements.data
                template.notice_period_days = form.notice_period_days.data or 0
                template.warning_cooldown_days = form.warning_cooldown_days.data or 0
                template.improper_quit_penalty_type = PenaltyType(form.improper_quit_penalty_type.data)
                template.improper_quit_penalty_days = form.improper_quit_penalty_days.data or 0
                template.application_questions = application_questions
            elif template.job_type == JobType.CONTRACT:
                template.bounty_amount = form.bounty_amount.data

            try:
                db.session.add(template)
                db.session.commit()
                flash(f'Job template "{template.job_title}" created successfully!', 'success')
                return redirect(url_for('admin.jobs_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating job template: {str(e)}', 'danger')

        return render_template('admin_jobs_template_form.html', form=form, mode='create')


    @admin_bp.route('/jobs/template/<int:template_id>/edit', methods=['GET', 'POST'])
    @admin_required
    def edit_job_template(template_id):
        """Edit an existing job template."""
        admin_id = session.get('admin_id')
        template = JobTemplate.query.filter_by(
            id=template_id,
            teacher_id=admin_id
        ).first_or_404()

        form = JobTemplateForm(obj=template)

        if request.method == 'GET':
            form.job_type.data = template.job_type.value
            form.payment_frequency.data = (
                template.payment_frequency.value if template.payment_frequency else ''
            )
            form.improper_quit_penalty_type.data = template.improper_quit_penalty_type.value

        if form.validate_on_submit():
            # Update application questions
            application_questions = _extract_application_questions_from_form()

            template.job_title = form.job_title.data
            template.job_description = form.job_description.data
            template.job_type = JobType(form.job_type.data)
            template.is_active = form.is_active.data

            # Update type-specific fields
            if template.job_type == JobType.EMPLOYEE:
                template.salary_amount = form.salary_amount.data
                template.payment_frequency = (
                    PaymentFrequency(form.payment_frequency.data)
                    if form.payment_frequency.data else None
                )
                template.vacancies = form.vacancies.data
                template.requirements = form.requirements.data
                template.notice_period_days = form.notice_period_days.data or 0
                template.warning_cooldown_days = form.warning_cooldown_days.data or 0
                template.improper_quit_penalty_type = PenaltyType(form.improper_quit_penalty_type.data)
                template.improper_quit_penalty_days = form.improper_quit_penalty_days.data or 0
                template.application_questions = application_questions
                # Clear contract fields
                template.bounty_amount = None
            elif template.job_type == JobType.CONTRACT:
                template.bounty_amount = form.bounty_amount.data
                # Clear employee fields
                template.salary_amount = None
                template.payment_frequency = None
                template.vacancies = None
                template.application_questions = None

            try:
                db.session.commit()
                flash(f'Job template "{template.job_title}" updated successfully!', 'success')
                return redirect(url_for('admin.jobs_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating job template: {str(e)}', 'danger')

        return render_template('admin_jobs_template_form.html',
            form=form,
            mode='edit',
            template=template
        )


    @admin_bp.route('/jobs/template/<int:template_id>/delete', methods=['POST'])
    @admin_required
    def delete_job_template(template_id):
        """Delete a job template (soft delete by setting is_active=False)."""
        admin_id = session.get('admin_id')
        template = JobTemplate.query.filter_by(
            id=template_id,
            teacher_id=admin_id
        ).first_or_404()

        try:
            template.is_active = False
            db.session.commit()
            flash(f'Job template "{template.job_title}" deleted.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting template: {str(e)}', 'danger')

        return redirect(url_for('admin.jobs_dashboard'))


    # -------------------- JOB ASSIGNMENT --------------------

    @admin_bp.route('/jobs/template/<int:template_id>/assign', methods=['POST'])
    @admin_required
    def assign_job_to_periods(template_id):
        """Assign a job template to one or more periods."""
        admin_id = session.get('admin_id')
        template = JobTemplate.query.filter_by(
            id=template_id,
            teacher_id=admin_id
        ).first_or_404()

        periods = request.form.getlist('periods')
        if not periods:
            flash('Please select at least one period.', 'warning')
            return redirect(url_for('admin.jobs_dashboard'))

        # Get join codes for selected periods
        blocks = TeacherBlock.query.filter_by(teacher_id=admin_id).filter(
            TeacherBlock.block.in_(periods)
        ).all()

        block_keys = [(block.block, block.join_code) for block in blocks]
        existing_jobs = Job.query.filter_by(
            template_id=template_id,
            teacher_id=admin_id
        ).filter(
            tuple_(Job.block, Job.join_code).in_(block_keys)
        ).all()
        existing_job_blocks = {(job.block, job.join_code) for job in existing_jobs}

        # Create jobs for each period
        created_count = 0
        for block in blocks:
            if (block.block, block.join_code) not in existing_job_blocks:
                job = Job(
                    template_id=template_id,
                    teacher_id=admin_id,
                    block=block.block,
                    join_code=block.join_code,
                    is_active=True
                )
                db.session.add(job)
                created_count += 1

        try:
            db.session.commit()
            flash(f'Job "{template.job_title}" assigned to {created_count} period(s).', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error assigning job: {str(e)}', 'danger')

        return redirect(url_for('admin.jobs_dashboard'))


    # -------------------- APPLICATION REVIEWS --------------------

    @admin_bp.route('/jobs/applications')
    @admin_required
    def view_applications():
        """View all job applications."""
        admin_id = session.get('admin_id')
        status_filter = request.args.get('status', JobApplicationStatus.PENDING.value)
        if status_filter not in {status.value for status in JobApplicationStatus}:
            status_filter = JobApplicationStatus.PENDING.value

        applications = JobApplication.query.join(Job).join(Student).filter(
            Job.teacher_id == admin_id,
            JobApplication.status == JobApplicationStatus(status_filter)
        ).order_by(desc(JobApplication.applied_at)).all()

        return render_template('admin_jobs_applications.html',
            applications=applications,
            status_filter=status_filter
        )


    @admin_bp.route('/jobs/application/<int:app_id>/review', methods=['GET', 'POST'])
    @admin_required
    def review_application(app_id):
        """Review and approve/reject a job application."""
        admin_id = session.get('admin_id')
        application = JobApplication.query.join(Job).filter(
            JobApplication.id == app_id,
            Job.teacher_id == admin_id
        ).first_or_404()

        form = JobApplicationReviewForm()

        if form.validate_on_submit():
            application.status = JobApplicationStatus(form.status.data)
            application.teacher_notes = form.teacher_notes.data
            application.reviewed_at = datetime.now(timezone.utc)

            # If accepted, create employee assignment
            if application.status == JobApplicationStatus.ACCEPTED:
                # Check if vacancies still available
                job = application.job
                template = job.template
                current_employees = EmployeeJobAssignment.query.filter_by(
                    job_id=job.id,
                    is_active=True
                ).count()

                if current_employees >= template.vacancies:
                    flash('No vacancies available for this position.', 'warning')
                    return redirect(url_for('admin.view_applications'))

                # Create assignment
                assignment = EmployeeJobAssignment(
                    job_id=job.id,
                    student_id=application.student_id,
                    start_date=datetime.now(timezone.utc),
                    is_active=True
                )
                db.session.add(assignment)

                # Calculate next payment date based on frequency
                if template.payment_frequency == PaymentFrequency.MONTHLY:
                    from dateutil.relativedelta import relativedelta
                    next_payment = datetime.now(timezone.utc) + relativedelta(months=1)
                elif template.payment_frequency == PaymentFrequency.BIWEEKLY:
                    next_payment = datetime.now(timezone.utc) + timedelta(weeks=2)
                else:
                    next_payment = None

                assignment.next_payment_due = next_payment

            try:
                db.session.commit()
                flash(f'Application {application.status.value}.', 'success')
                return redirect(url_for('admin.view_applications'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error processing application: {str(e)}', 'danger')

        return render_template('admin_jobs_application_review.html',
            application=application,
            form=form
        )


    # -------------------- EMPLOYEE MANAGEMENT --------------------

    @admin_bp.route('/jobs/employees')
    @admin_required
    def view_employees():
        """View all active employee job assignments."""
        admin_id = session.get('admin_id')

        assignments = EmployeeJobAssignment.query.join(Job).join(Student).filter(
            Job.teacher_id == admin_id,
            EmployeeJobAssignment.is_active == True
        ).order_by(desc(EmployeeJobAssignment.start_date)).all()

        return render_template('admin_jobs_employees.html', assignments=assignments)


    @admin_bp.route('/jobs/employee/<int:assignment_id>/warn', methods=['POST'])
    @admin_required
    def issue_warning(assignment_id):
        """Issue a warning to an employee."""
        admin_id = session.get('admin_id')
        assignment = EmployeeJobAssignment.query.join(Job).filter(
            EmployeeJobAssignment.id == assignment_id,
            Job.teacher_id == admin_id
        ).first_or_404()

        form = EmployeeWarningForm()

        if form.validate_on_submit():
            warning = EmployeeJobWarning(
                assignment_id=assignment_id,
                warning_text=form.warning_text.data,
                issued_at=datetime.now(timezone.utc),
                issued_by_admin_id=admin_id
            )

            assignment.warnings_count += 1
            assignment.last_warning_date = datetime.now(timezone.utc)

            try:
                db.session.add(warning)
                db.session.commit()
                flash('Warning issued successfully.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error issuing warning: {str(e)}', 'danger')

        return redirect(url_for('admin.view_employees'))


    @admin_bp.route('/jobs/employee/<int:assignment_id>/fire', methods=['POST'])
    @admin_required
    def fire_employee(assignment_id):
        """Fire an employee from their job."""
        admin_id = session.get('admin_id')
        assignment = EmployeeJobAssignment.query.join(Job).filter(
            EmployeeJobAssignment.id == assignment_id,
            Job.teacher_id == admin_id
        ).first_or_404()

        # Check warning cooldown
        template = assignment.job.template
        if template.warning_cooldown_days > 0 and assignment.last_warning_date:
            cooldown_end = assignment.last_warning_date + timedelta(days=template.warning_cooldown_days)
            if datetime.now(timezone.utc) < cooldown_end:
                days_remaining = (cooldown_end - datetime.now(timezone.utc)).days
                flash(f'Cannot fire yet. Cooldown period: {days_remaining} days remaining.', 'warning')
                return redirect(url_for('admin.view_employees'))

        reason = request.form.get('reason', '')
        assignment.is_active = False
        assignment.end_date = datetime.now(timezone.utc)
        assignment.termination_type = TerminationType.FIRED
        assignment.termination_reason = reason

        try:
            db.session.commit()
            flash('Employee terminated.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Error firing employee: {str(e)}', 'danger')

        return redirect(url_for('admin.view_employees'))


    # -------------------- CONTRACT JOB REVIEWS --------------------

    @admin_bp.route('/jobs/contracts')
    @admin_required
    def view_contract_claims():
        """View all contract job claims."""
        admin_id = session.get('admin_id')
        status_filter = request.args.get('status', ContractJobStatus.SUBMITTED.value)
        if status_filter not in {status.value for status in ContractJobStatus}:
            status_filter = ContractJobStatus.SUBMITTED.value

        claims = ContractJobClaim.query.join(Job).join(Student).filter(
            Job.teacher_id == admin_id,
            ContractJobClaim.status == ContractJobStatus(status_filter)
        ).order_by(desc(ContractJobClaim.student_marked_complete_at)).all()

        return render_template('admin_jobs_contracts.html',
            claims=claims,
            status_filter=status_filter
        )


    @admin_bp.route('/jobs/contract/<int:claim_id>/review', methods=['GET', 'POST'])
    @admin_required
    def review_contract(claim_id):
        """Review and approve/reject a contract job completion."""
        admin_id = session.get('admin_id')
        claim = ContractJobClaim.query.join(Job).filter(
            ContractJobClaim.id == claim_id,
            Job.teacher_id == admin_id
        ).first_or_404()

        form = ContractJobReviewForm()

        if form.validate_on_submit():
            claim.status = ContractJobStatus(form.status.data)
            claim.teacher_notes = form.teacher_notes.data
            claim.teacher_reviewed_at = datetime.now(timezone.utc)

            # If approved, create payment transaction
            if claim.status == ContractJobStatus.APPROVED:
                job = claim.job
                template = job.template

                transaction = Transaction(
                    student_id=claim.student_id,
                    teacher_id=admin_id,
                    join_code=job.join_code,
                    amount=template.bounty_amount,
                    account_type='checking',
                    description=f'Contract job completed: {template.job_title}',
                    type='job_payment',
                    timestamp=datetime.now(timezone.utc)
                )

                claim.payment_amount = template.bounty_amount
                claim.transaction_id = transaction.id

                db.session.add(transaction)

            try:
                db.session.commit()
                flash(f'Contract {claim.status.value}.', 'success')
                return redirect(url_for('admin.view_contract_claims'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error processing contract: {str(e)}', 'danger')

        return render_template('admin_jobs_contract_review.html',
            claim=claim,
            form=form
        )
