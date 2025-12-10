# Jobs Feature Documentation

## Overview

The Jobs feature adds a classroom employment system that allows teachers to create two types of jobs for students:

1. **Employee Jobs**: Long-term positions with regular pay that require applications
2. **Contract Jobs**: One-off bounties that students can claim and complete

## Architecture

### Database Models

#### Core Models

**JobTemplate** (`job_templates`)
- Reusable job templates stored in teacher's "job bank"
- Can be assigned to multiple periods/blocks
- Contains all job configuration (pay, requirements, penalties, etc.)
- Fields:
  - `job_title`, `job_description`, `job_type` (employee/contract)
  - Employee-specific: `salary_amount`, `payment_frequency`, `vacancies`, `requirements`
  - Termination settings: `notice_period_days`, `warning_cooldown_days`, penalty configuration
  - Contract-specific: `bounty_amount`
  - `application_questions` (JSON array of custom questions)

**Job** (`jobs`)
- Instance of a JobTemplate assigned to a specific period
- Links template to block/join_code for class isolation
- Tracks active/inactive status

**JobApplication** (`job_applications`)
- Student applications for employee jobs
- Stores answers to custom questions (JSON)
- Status: `pending`, `accepted`, `rejected`
- Links to Job and Student

**EmployeeJobAssignment** (`employee_job_assignments`)
- Active employee positions
- Tracks start/end dates, warnings, termination details
- Payment schedule tracking
- Links to Job and Student

**EmployeeJobWarning** (`employee_job_warnings`)
- Warning history for employees
- Tracks warning text, issue date, issuing admin
- Multiple warnings can be issued before firing

**ContractJobClaim** (`contract_job_claims`)
- Contract job lifecycle tracking
- Workflow: claimed → submitted → approved/rejected
- Stores student completion notes and teacher review
- Links to payment transaction when approved

**JobApplicationBan** (`job_application_bans`)
- Penalty system for improper quitting
- Can ban from all jobs or specific job
- Time-based bans with expiration
- Uses join_code for class isolation

**JobsSettings** (`jobs_settings`)
- Per-teacher, per-block configuration
- Feature toggles for employee/contract jobs
- Auto-posting and approval requirements
- Setup wizard completion tracking

### Feature Flag

Added `jobs_enabled` to `FeatureSettings` model:
- Default: `False` (new feature, opt-in)
- Controls visibility in navigation when enabled
- Per-period configuration supported

## Backend Routes

All routes located in `app/routes/admin_jobs.py`, registered in `admin.py`.

### Job Bank Management

- `GET /admin/jobs` - Dashboard showing job bank and active jobs
- `GET /admin/jobs/template/create` - Create new job template form
- `POST /admin/jobs/template/create` - Save new job template
- `GET /admin/jobs/template/<id>/edit` - Edit job template form
- `POST /admin/jobs/template/<id>/edit` - Update job template
- `POST /admin/jobs/template/<id>/delete` - Soft delete template (sets `is_active=False`)

### Job Assignment

- `POST /admin/jobs/template/<id>/assign` - Assign template to period(s)
  - Creates Job instances for each selected period
  - Uses TeacherBlock join_codes for class isolation

### Application Management

- `GET /admin/jobs/applications` - View all applications (filter by status)
- `GET /admin/jobs/application/<id>/review` - Review application details
- `POST /admin/jobs/application/<id>/review` - Accept/reject application
  - On accept: Creates EmployeeJobAssignment
  - Checks vacancy availability
  - Calculates next payment date based on frequency

### Employee Management

- `GET /admin/jobs/employees` - View all active employees
- `POST /admin/jobs/employee/<id>/warn` - Issue warning
  - Increments warning count
  - Sets last_warning_date for cooldown tracking
- `POST /admin/jobs/employee/<id>/fire` - Terminate employment
  - Enforces cooldown period after warning
  - Sets termination_type and reason
  - Deactivates assignment

### Contract Job Management

- `GET /admin/jobs/contracts` - View contract claims (filter by status)
- `GET /admin/jobs/contract/<id>/review` - Review completion
- `POST /admin/jobs/contract/<id>/review` - Approve/reject completion
  - On approve: Creates Transaction for payment
  - Links transaction to claim
  - Sets payment_amount

## Business Logic

### Employee Jobs Workflow

1. Teacher creates employee job template in job bank
2. Teacher assigns template to period(s)
3. Students view available positions and apply
4. Teacher reviews applications and accepts/rejects
5. Accepted students become employees (EmployeeJobAssignment created)
6. Teacher can issue warnings with cooldown before firing
7. Students can quit with or without notice
8. Improper quitting (no notice) triggers penalty system

### Contract Jobs Workflow

1. Teacher creates contract job template
2. Teacher assigns to period(s)
3. Students claim available contract jobs
4. Students complete work and mark as complete
5. Teacher reviews and approves/rejects
6. On approval, payment transaction created automatically

### Warning & Firing System

- Teachers issue warnings via button press
- Each warning increments `warnings_count` and sets `last_warning_date`
- Cooldown period (configurable per job) must pass before firing
- Cooldown calculated: `last_warning_date + warning_cooldown_days`
- Firing marks assignment inactive and records termination details

### Quit Notice System

- Employee jobs have required notice period (configurable, default 0)
- Students can:
  - Give proper notice (quit_notice_date set, effective after X days)
  - Quit immediately (no notice)
- Improper quit triggers penalty:
  - **days_ban**: Ban from all jobs for X days
  - **job_specific_ban**: Ban from that specific job
  - **none**: No penalty

### Penalty System

- JobApplicationBan created when student quits improperly
- Ban types:
  - `all_jobs`: Student cannot apply to any job until expiration
  - `specific_job`: Student cannot apply to that job template
- Bans have `banned_until` date for automatic expiration
- Uses `join_code` for class isolation (penalties don't cross classes)

## Data Isolation

The jobs feature follows the codebase's multi-tenancy patterns:

- **join_code**: Primary source of truth for class isolation
  - Jobs assigned to specific join_code
  - Applications and claims scoped to join_code
  - Bans use join_code for per-class penalties

- **teacher_id**: Secondary isolation
  - All models have teacher_id for ownership
  - Routes check teacher_id for authorization

- **CASCADE deletes**: All relationships use proper CASCADE
  - Delete teacher → deletes templates, jobs, settings
  - Delete template → deletes job instances
  - Delete job → deletes applications, assignments, claims
  - Delete student → deletes their applications, assignments, claims

## Forms

All forms in `forms.py`:

- **JobTemplateForm**: Create/edit job templates
  - Dynamic field validation based on job_type
  - Custom validators for required fields per type

- **JobApplicationReviewForm**: Accept/reject applications
- **EmployeeWarningForm**: Issue warnings
- **ContractJobReviewForm**: Approve/reject completions
- **JobsSettingsForm**: Configure jobs feature
- **StudentJobApplicationForm**: Student applications (dynamic questions)
- **StudentContractJobClaimForm**: Mark contracts complete
- **StudentQuitJobForm**: Quit employee jobs

## Testing

Comprehensive test suite in `tests/test_jobs_feature.py`:

- **Model Tests**: Creation, relationships, field validation
- **Employee Workflow Tests**: Application → assignment → warning → firing
- **Contract Workflow Tests**: Claim → complete → approve → payment
- **Penalty System Tests**: Ban creation and enforcement
- **CASCADE Tests**: Foreign key cascade behavior
- **Settings Tests**: Configuration and feature flags

## Security Considerations

### Authorization
- All routes use `@admin_required` decorator
- Queries filtered by `teacher_id` from session
- Student access controlled via `get_student_for_admin()`

### Data Validation
- WTForms validation on all inputs
- Job type-specific field requirements enforced
- Vacancy checks before accepting applications
- Cooldown period enforcement before firing

### Multi-Tenancy
- join_code isolation prevents cross-class access
- CASCADE deletes maintain referential integrity
- Scoped queries follow existing patterns

## Payment Integration

### Employee Salaries
- Stored in EmployeeJobAssignment
- Payment schedule: monthly or biweekly
- `next_payment_due` tracked per assignment
- **Note**: Payment processing NOT implemented (future work)
- Separate from attendance-based payroll

### Contract Bounties
- Immediate payment on approval
- Creates Transaction record
- Links transaction to ContractJobClaim
- Uses join_code for class isolation
- Account type: 'checking'
- Description: auto-generated

## Configuration

### Feature Toggle
```python
# Enable jobs feature for a teacher/period
feature_settings.jobs_enabled = True
```

### Jobs Settings
```python
jobs_settings = JobsSettings(
    teacher_id=teacher.id,
    block='A',  # or None for global
    employee_jobs_enabled=True,
    contract_jobs_enabled=True,
    auto_post_new_jobs=True,
    require_application_approval=True
)
```

## Database Migration

Migration file: `migrations/versions/aa1bb2cc3dd4_add_jobs_feature_tables.py`

**Creates 8 new tables:**
1. job_templates
2. jobs
3. job_applications
4. employee_job_assignments
5. employee_job_warnings
6. contract_job_claims
7. job_application_bans
8. jobs_settings

**Alters 1 table:**
- Adds `jobs_enabled` column to `feature_settings`

**To apply migration:**
```bash
flask db upgrade
```

**To rollback:**
```bash
flask db downgrade
```

## API Endpoints

None yet - all routes are traditional server-rendered views.

## Known Limitations & Future Work

### Not Yet Implemented

1. **Frontend Templates**: No HTML templates created yet
   - Admin dashboard
   - Job creation forms
   - Application review interfaces
   - Employee management pages
   - Contract review pages

2. **Student Routes**: No student-facing routes yet
   - Browse jobs
   - Submit applications
   - View assignments
   - Claim/complete contracts
   - Quit jobs

3. **Setup Wizard**: First-time configuration flow not built

4. **Payment Automation**: Employee salaries not auto-paid
   - Payment schedules tracked but not executed
   - Would need cron job or similar for automated payments

5. **Navigation Links**: Routes exist but not linked in nav
   - Hidden until templates are ready
   - Feature can be tested via direct URLs

### Future Enhancements

1. **Job Analytics**:
   - Track application rates
   - Employee performance metrics
   - Contract completion rates

2. **Advanced Features**:
   - Job categories/tags
   - Skill requirements matching
   - Student job history/resume
   - Performance reviews
   - Promotion system

3. **Notifications**:
   - New job postings
   - Application status updates
   - Warning notifications
   - Payment confirmations

4. **Reporting**:
   - Jobs analytics dashboard
   - Student employment reports
   - Payment history exports

## Integration Points

### Existing Systems

- **Transactions**: Contract payments create Transaction records
- **FeatureSettings**: jobs_enabled toggle
- **TeacherBlock**: Uses join_codes for job assignment
- **Student**: Links for applications and assignments

### Does NOT Integrate With

- **Payroll**: Attendance-based payroll is separate
- **Store**: No connection to store items
- **Insurance**: No job-related insurance
- **Rent**: Independent of housing costs

## Testing the Feature

Since templates aren't built yet, test via direct route access:

1. Enable feature:
   ```python
   # In Flask shell or migration
   feature_settings = FeatureSettings.query.first()
   feature_settings.jobs_enabled = True
   db.session.commit()
   ```

2. Access routes directly:
   - `/admin/jobs` - Dashboard
   - `/admin/jobs/template/create` - Create job
   - `/admin/jobs/applications` - View applications
   - `/admin/jobs/employees` - View employees
   - `/admin/jobs/contracts` - View contracts

3. Use curl or Postman for POST requests

4. Check database directly:
   ```sql
   SELECT * FROM job_templates;
   SELECT * FROM jobs;
   SELECT * FROM job_applications;
   ```

## Troubleshooting

### Common Issues

**Issue**: Migration fails with "multiple heads"
- **Solution**: Run `flask db merge heads` before migration

**Issue**: Jobs not showing for students
- **Solution**: Check `jobs_enabled` in FeatureSettings
- Check job is assigned to correct join_code

**Issue**: Cannot fire employee (cooldown error)
- **Solution**: Check `warning_cooldown_days` setting
- Verify `last_warning_date` + cooldown has passed

**Issue**: Application acceptance fails (no vacancies)
- **Solution**: Check `vacancies` in JobTemplate
- Count current active assignments for that job

## Code Examples

### Creating a Job Template

```python
template = JobTemplate(
    teacher_id=current_teacher.id,
    job_title="Class Monitor",
    job_description="Monitor classroom during breaks",
    job_type="employee",
    salary_amount=50.0,
    payment_frequency="monthly",
    vacancies=2,
    requirements="Must be responsible and punctual",
    notice_period_days=7,
    warning_cooldown_days=3,
    improper_quit_penalty_type="days_ban",
    improper_quit_penalty_days=14,
    application_questions=[
        {"question": "Why do you want this job?", "required": True},
        {"question": "What relevant experience do you have?", "required": True}
    ]
)
db.session.add(template)
db.session.commit()
```

### Assigning to Periods

```python
# Get teacher's blocks
blocks = TeacherBlock.query.filter_by(
    teacher_id=teacher_id,
    block__in=['A', 'B', 'C']
).all()

# Create job instance for each period
for block in blocks:
    job = Job(
        template_id=template.id,
        teacher_id=teacher_id,
        block=block.block,
        join_code=block.join_code,
        is_active=True
    )
    db.session.add(job)
db.session.commit()
```

### Accepting an Application

```python
application.status = 'accepted'
application.reviewed_at = datetime.now(timezone.utc)

# Create assignment
assignment = EmployeeJobAssignment(
    job_id=application.job_id,
    student_id=application.student_id,
    start_date=datetime.now(timezone.utc),
    is_active=True
)

# Calculate next payment
if template.payment_frequency == 'monthly':
    assignment.next_payment_due = datetime.now(timezone.utc) + timedelta(days=30)
elif template.payment_frequency == 'biweekly':
    assignment.next_payment_due = datetime.now(timezone.utc) + timedelta(days=14)

db.session.add(assignment)
db.session.commit()
```

### Approving Contract and Creating Payment

```python
claim.status = 'approved'
claim.teacher_reviewed_at = datetime.now(timezone.utc)

# Create payment transaction
transaction = Transaction(
    student_id=claim.student_id,
    teacher_id=current_teacher.id,
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
db.session.commit()
```

## Contributing

When extending this feature:

1. Follow existing patterns in codebase
2. Use join_code for class isolation
3. Add CASCADE deletes for relationships
4. Write tests for new functionality
5. Update this documentation
6. Follow AGENTS.md guidelines for migrations

## References

- Models: `app/models.py` (lines 1264-1549)
- Routes: `app/routes/admin_jobs.py`
- Forms: `forms.py` (lines 351-481)
- Migration: `migrations/versions/aa1bb2cc3dd4_add_jobs_feature_tables.py`
- Tests: `tests/test_jobs_feature.py`
