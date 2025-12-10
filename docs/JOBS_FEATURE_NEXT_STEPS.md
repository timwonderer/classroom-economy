# Jobs Feature - Next Steps for Implementation

## Current Status: ~60% Complete ✅

### What's Been Built

**Backend Infrastructure (100% Complete)**:
- ✅ 9 database models with full relationships
- ✅ Database migration ready to apply
- ✅ 9 WTForms with validation
- ✅ 14 admin route handlers
- ✅ Feature flag integration
- ✅ Comprehensive test suite
- ✅ Full documentation

**What's Working**:
- Job template CRUD operations
- Job assignment to periods
- Application workflow (backend)
- Employee management logic
- Contract approval logic
- Warning system with cooldowns
- Penalty/ban system
- Transaction creation for payments
- Multi-tenancy isolation via join_code

### What's Missing

**Frontend (40% of remaining work)**:
- ❌ Admin HTML templates
- ❌ Student HTML templates
- ❌ Setup wizard UI

**Student Backend (20% of remaining work)**:
- ❌ Student routes for browsing/applying
- ❌ Student dashboard integration

**Integration (20% of remaining work)**:
- ❌ Navigation links
- ❌ Feature toggle UI

**Testing & Polish (20% of remaining work)**:
- ❌ End-to-end testing with UI
- ❌ Payment automation system

---

## Phase 1: Admin Templates (Priority 1)

### Templates Needed

#### 1. Jobs Dashboard (`templates/admin_jobs_dashboard.html`)
**Route**: `GET /admin/jobs`

**Should Display**:
- Job bank section showing all templates
  - Table with: Title, Type, Pay, Vacancies/Bounty, Status
  - Actions: Edit, Delete, Assign to Periods
- Active jobs section (grouped by period)
  - Show which templates are assigned where
  - Link to applications/employees/contracts
- Quick stats cards:
  - Pending applications count (badge)
  - Active employees count
  - Pending contract reviews (badge)
  - Total jobs in bank

**Design Pattern**: Follow `admin_insurance.html` structure
- Use Bootstrap tabs for Job Bank vs Active Jobs
- Use cards for stats
- Use DataTables for sorting/filtering

#### 2. Job Template Form (`templates/admin_jobs_template_form.html`)
**Routes**:
- `GET/POST /admin/jobs/template/create`
- `GET/POST /admin/jobs/template/<id>/edit`

**Form Sections**:
1. **Basic Info**: Title, Description, Type (radio buttons)
2. **Employee-Specific** (show/hide based on type):
   - Salary amount, Payment frequency dropdown
   - Number of vacancies
   - Requirements textarea
   - Application questions (dynamic list with add/remove)
3. **Employee Termination Settings** (collapsible):
   - Notice period days
   - Warning cooldown days
   - Quit penalty type dropdown
   - Penalty duration days
4. **Contract-Specific** (show/hide based on type):
   - Bounty amount
5. **Status**: Active checkbox

**JavaScript Needed**:
- Show/hide sections based on job type selection
- Dynamic application questions:
  - Add question button
  - Remove question button
  - Store as hidden form field (JSON)
- Form validation before submit

**Design Pattern**: Follow `admin_insurance.html` form modal pattern

#### 3. Applications List (`templates/admin_jobs_applications.html`)
**Route**: `GET /admin/jobs/applications?status=pending`

**Should Display**:
- Filter tabs: Pending / Accepted / Rejected
- Table columns:
  - Student name
  - Job title
  - Applied date
  - Status badge
  - Actions: Review button
- Empty state when no applications

**Design Pattern**: Follow `admin_insurance.html` claims list

#### 4. Application Review (`templates/admin_jobs_application_review.html`)
**Route**: `GET/POST /admin/jobs/application/<id>/review`

**Should Display**:
- Student info (auto-filled): Name, Class, Period
- Job details: Title, Description, Salary/Frequency, Vacancies available
- Application answers (Q&A format)
- Review form:
  - Accept/Reject radio buttons
  - Teacher notes textarea
  - Submit button
- Back to applications link

**Design Pattern**: Follow claim review modals

#### 5. Employees List (`templates/admin_jobs_employees.html`)
**Route**: `GET /admin/jobs/employees`

**Should Display**:
- Table columns:
  - Student name
  - Job title
  - Start date
  - Salary & frequency
  - Warnings count (badge if > 0)
  - Last warning date (if exists)
  - Actions: Warn button, Fire button
- Warning modal with form (warning text)
- Fire confirmation modal with reason textarea

**Design Pattern**: Follow student management table patterns

#### 6. Contracts List (`templates/admin_jobs_contracts.html`)
**Route**: `GET /admin/jobs/contracts?status=submitted`

**Should Display**:
- Filter tabs: Submitted / Approved / Rejected
- Table columns:
  - Student name
  - Job title
  - Claimed date
  - Submitted date
  - Status badge
  - Actions: Review button
- Empty state when no contracts

#### 7. Contract Review (`templates/admin_jobs_contract_review.html`)
**Route**: `GET/POST /admin/jobs/contract/<id>/review`

**Should Display**:
- Student info
- Job details: Title, Description, Bounty
- Student's completion notes
- Approve/Reject form:
  - Radio buttons for decision
  - Teacher notes textarea
  - Submit button (shows payment amount if approving)

---

## Phase 2: Student Templates (Priority 2)

### Templates Needed

#### 1. Jobs Marketplace (`templates/student_jobs.html`)
**Route**: `GET /student/jobs` (not yet created)

**Two Sections**:
- **Employee Jobs** (if enabled):
  - Grid/list of available positions
  - Show: Title, Description, Salary, Frequency, Vacancies available
  - "Apply" button (opens application modal)
  - Show "Applied" badge if already applied
  - Show "Hired!" badge if employed
- **Contract Jobs - Bounty Board** (if enabled):
  - Grid of available bounties
  - Show: Title, Description, Bounty amount
  - "Claim" button
  - Show "Claimed" badge if already claimed
  - Show "In Progress" if working on it

**Design Pattern**: Mix of store shop grid + insurance marketplace

#### 2. Job Application Modal (`templates/student_jobs_apply_modal.html`)
**Embedded in marketplace or separate route**

**Should Display**:
- Job details reminder
- Auto-filled fields (read-only): Name, Class, Period
- Dynamic questions from template
- Submit button

**JavaScript**: Dynamic form generation from JSON questions

#### 3. My Jobs Dashboard (`templates/student_jobs_dashboard.html`)
**Route**: `GET /student/my-jobs` (not yet created)

**Tabs**:
1. **Active Employment**:
   - Current employee job(s)
   - Show: Title, Salary, Start date, Next payment
   - Warnings received (if any)
   - "Quit Job" button (opens quit modal)
2. **Active Contracts**:
   - Claimed contracts in progress
   - Show: Title, Bounty, Claimed date
   - "Mark Complete" button
3. **Application Status**:
   - Pending applications
   - Show: Job title, Applied date, Status
4. **Job History**:
   - Past jobs and contracts
   - Show: Title, Type, Duration, Total earned

#### 4. Quit Job Modal (`templates/student_jobs_quit_modal.html`)

**Should Display**:
- Warning about notice requirement
- Two options:
  - "Give Notice" (X days required)
  - "Quit Immediately" (may incur penalty warning)
- Reason textarea (optional)
- Confirm button

#### 5. Contract Completion Modal (`templates/student_jobs_complete_contract_modal.html`)

**Should Display**:
- Job details
- "What did you do?" textarea (required)
- Submit for review button

---

## Phase 3: Student Routes (Priority 3)

### Routes to Create in `app/routes/student.py`

#### 1. Browse Jobs
```python
@student_bp.route('/jobs')
@student_required
def browse_jobs():
    """Show available jobs in current class."""
    # Get current join_code from session
    # Query active jobs for that join_code
    # Check if student has applied/claimed/employed
    # Filter out jobs where student is banned
    return render_template('student_jobs.html')
```

#### 2. Apply for Job
```python
@student_bp.route('/jobs/<int:job_id>/apply', methods=['POST'])
@student_required
def apply_for_job(job_id):
    """Submit application for employee job."""
    # Check if student is banned
    # Check if already applied
    # Create JobApplication with answers
    # Flash success message
    return redirect(url_for('student.browse_jobs'))
```

#### 3. Claim Contract
```python
@student_bp.route('/jobs/contract/<int:job_id>/claim', methods=['POST'])
@student_required
def claim_contract(job_id):
    """Claim a contract job."""
    # Check if already claimed by someone
    # Check if student is banned
    # Create ContractJobClaim
    # Flash success message
    return redirect(url_for('student.my_jobs'))
```

#### 4. My Jobs Dashboard
```python
@student_bp.route('/my-jobs')
@student_required
def my_jobs():
    """Show student's current and past jobs."""
    # Get active assignments
    # Get claimed contracts
    # Get pending applications
    # Get job history
    return render_template('student_jobs_dashboard.html')
```

#### 5. Mark Contract Complete
```python
@student_bp.route('/jobs/contract/<int:claim_id>/complete', methods=['POST'])
@student_required
def complete_contract(claim_id):
    """Mark contract job as complete."""
    # Update status to 'submitted'
    # Set student_marked_complete_at
    # Save student_notes
    # Flash success message
    return redirect(url_for('student.my_jobs'))
```

#### 6. Quit Job
```python
@student_bp.route('/jobs/employee/<int:assignment_id>/quit', methods=['POST'])
@student_required
def quit_job(assignment_id):
    """Quit an employee job."""
    # Check quit_type (with_notice / immediate)
    # Calculate effective date
    # Check if penalty applies
    # Create JobApplicationBan if needed
    # Update assignment
    # Flash message about consequences
    return redirect(url_for('student.my_jobs'))
```

---

## Phase 4: Setup Wizard (Priority 4)

### Wizard Steps

#### Step 1: Introduction
- Explain employee vs contract jobs
- Benefits for classroom economy
- Next button

#### Step 2: Choose Job Types
- Checkbox: Enable Employee Jobs
- Checkbox: Enable Contract Jobs
- Description of each type
- Must select at least one

#### Step 3: Employee Settings (if enabled)
- Default payment frequency
- Application approval required (toggle)
- Default notice period (optional)

#### Step 4: Contract Settings (if enabled)
- Auto-post new jobs (toggle)
- Teacher approval required for completion (toggle)

#### Step 5: Create First Job (optional)
- Quick form to create template
- Or skip to dashboard

**Implementation Pattern**: Follow existing `admin_onboarding.html` wizard structure
- Use same progress indicator
- Same step navigation
- Store progress in JobsSettings.setup_completed

---

## Phase 5: Navigation Integration (Priority 5)

### Admin Navigation
**File**: `templates/admin_nav.html`

Add link after "Payroll":
```html
{% if feature_settings and feature_settings.jobs_enabled %}
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('admin.jobs_dashboard') }}">
        <span class="material-symbols-outlined">work</span>
        Jobs
        {% if pending_apps_count > 0 %}
        <span class="badge bg-danger">{{ pending_apps_count }}</span>
        {% endif %}
    </a>
</li>
{% endif %}
```

### Student Navigation
**File**: `templates/layout_student.html`

Add link in sidebar:
```html
{% if feature_settings and feature_settings.jobs_enabled %}
<li>
    <a href="{{ url_for('student.browse_jobs') }}">
        <span class="material-symbols-outlined">work</span>
        Jobs
    </a>
</li>
{% endif %}
```

---

## Phase 6: Payment Automation (Priority 6)

### Current State
- Payment schedules are tracked (`next_payment_due`)
- No automatic execution

### Implementation Options

#### Option A: Cron Job (Recommended)
Create `scripts/process_job_payments.py`:
```python
#!/usr/bin/env python
"""
Process due employee job payments.
Run daily via cron: 0 0 * * * /path/to/process_job_payments.py
"""
from datetime import datetime, timezone
from app import app, db
from app.models import EmployeeJobAssignment, Transaction

with app.app_context():
    # Find assignments with payment due
    due_payments = EmployeeJobAssignment.query.filter(
        EmployeeJobAssignment.is_active == True,
        EmployeeJobAssignment.next_payment_due <= datetime.now(timezone.utc)
    ).all()

    for assignment in due_payments:
        # Create transaction
        # Update next_payment_due
        # Commit
```

#### Option B: Route Trigger
Add route that processes payments when called:
```python
@admin_bp.route('/jobs/process-payments', methods=['POST'])
@admin_required
def process_job_payments():
    """Manually trigger payment processing."""
    # Same logic as cron job
```

#### Option C: Background Task (Advanced)
Use Celery or similar for scheduled tasks.

---

## Phase 7: Feature Toggle UI (Priority 7)

### Add to Feature Settings Page

**File**: `templates/admin_feature_settings.html`

Add toggle in feature settings form:
```html
<div class="form-check form-switch">
    <input class="form-check-input" type="checkbox"
           id="jobs_enabled" name="jobs_enabled"
           {% if feature_settings.jobs_enabled %}checked{% endif %}>
    <label class="form-check-label" for="jobs_enabled">
        Enable Jobs Feature
        <small class="text-muted d-block">
            Allows students to apply for employee positions or claim contract jobs
        </small>
    </label>
</div>
```

Handle in route:
```python
feature_settings.jobs_enabled = 'jobs_enabled' in request.form
```

---

## Testing Checklist

### Unit Tests (Already Written)
- ✅ Model creation
- ✅ Relationships
- ✅ Workflow logic
- ✅ CASCADE deletes

### Integration Tests (To Write)
- [ ] Full application workflow with routes
- [ ] Full contract workflow with routes
- [ ] Warning and firing workflow
- [ ] Quit with/without notice workflow
- [ ] Ban enforcement
- [ ] Payment creation

### Manual Testing (To Do)
- [ ] Create job template
- [ ] Assign to multiple periods
- [ ] Student applies for job
- [ ] Accept application
- [ ] Issue warning
- [ ] Fire employee (with cooldown)
- [ ] Student claims contract
- [ ] Student completes contract
- [ ] Approve contract (check payment)
- [ ] Student quits without notice (check ban)
- [ ] Verify ban prevents application

---

## Database Migration Deployment

### Before Deploying

1. **Backup database**:
   ```bash
   pg_dump database_name > backup_before_jobs_feature.sql
   ```

2. **Test migration locally**:
   ```bash
   flask db upgrade
   flask db downgrade
   flask db upgrade  # Test rollback works
   ```

3. **Check migration heads**:
   ```bash
   flask db heads  # Should show exactly 1 head
   ```

### Deployment Steps

1. Enable maintenance mode (optional)
2. Run migration:
   ```bash
   flask db upgrade
   ```
3. Verify tables created:
   ```sql
   SELECT table_name FROM information_schema.tables
   WHERE table_name LIKE 'job%';
   ```
4. Disable maintenance mode

---

## Performance Considerations

### Database Indexes
Already included in migration:
- `ix_jobs_teacher_block` - Fast job lookups by teacher/period
- `ix_jobs_join_code` - Fast job lookups by class
- `ix_job_applications_student` - Fast student application lookups
- `ix_job_applications_status` - Fast filtering by status
- `ix_employee_assignments_student` - Fast student assignment lookups
- `ix_contract_claims_student` - Fast student claim lookups

### Query Optimization Tips
- Use `.join()` when querying across tables
- Filter by `is_active=True` to exclude old data
- Use `join_code` in WHERE clause for class scoping
- Index on `join_code` is critical for performance

---

## Security Review

### Already Implemented
- ✅ @admin_required on all admin routes
- ✅ teacher_id verification in queries
- ✅ WTForms CSRF protection
- ✅ Input validation
- ✅ join_code isolation

### To Add in Student Routes
- [ ] @student_required decorator
- [ ] Verify student has access to join_code
- [ ] Check ban status before allowing actions
- [ ] Prevent double-application
- [ ] Prevent double-claiming contracts

---

## Estimated Time to Complete

**Phase 1 (Admin Templates)**: 8-12 hours
- Dashboard: 2-3 hours
- Template form: 2-3 hours
- Application review: 2-3 hours
- Employee/contract management: 2-3 hours

**Phase 2 (Student Templates)**: 6-8 hours
- Marketplace: 3-4 hours
- Dashboard: 2-3 hours
- Modals: 1-2 hours

**Phase 3 (Student Routes)**: 4-6 hours
- 6 routes × 30-60 min each

**Phase 4 (Setup Wizard)**: 3-4 hours

**Phase 5 (Navigation)**: 1 hour

**Phase 6 (Payment Automation)**: 2-4 hours

**Phase 7 (Testing & Polish)**: 4-6 hours

**Total**: 28-41 hours (~1-2 weeks for one developer)

---

## Quick Start for Next Developer

1. **Read documentation**:
   - `docs/JOBS_FEATURE.md` - Full feature docs
   - `AGENTS.md` - Repo guidelines
   - This file - Implementation roadmap

2. **Review existing code**:
   - Models: `app/models.py` (lines 1264-1549)
   - Routes: `app/routes/admin_jobs.py`
   - Forms: `forms.py` (lines 351-481)
   - Tests: `tests/test_jobs_feature.py`

3. **Start with Phase 1**:
   - Pick template: `admin_jobs_dashboard.html`
   - Use `admin_insurance.html` as reference
   - Test route at `/admin/jobs`

4. **Questions?**:
   - Check docs first
   - Review similar features (Insurance, Store)
   - Follow existing patterns

---

## Success Criteria

Feature is complete when:
- ✅ All templates render correctly
- ✅ Teachers can create and manage jobs
- ✅ Students can apply/claim and work jobs
- ✅ Payments are created correctly
- ✅ Warning/firing system works
- ✅ Ban system prevents applications
- ✅ All tests pass
- ✅ Feature flag toggles correctly
- ✅ Navigation links work
- ✅ Documentation is updated

---

## Maintenance Notes

### When Adding New Features
1. Update `JOBS_FEATURE.md` documentation
2. Add tests to `test_jobs_feature.py`
3. Follow CASCADE delete patterns
4. Use join_code for isolation
5. Update this roadmap if structure changes

### Common Modifications
- **Add new job type**: Update JobTemplate.job_type enum, add fields, update forms
- **Change payment schedule**: Modify EmployeeJobAssignment payment logic
- **Add new penalty type**: Update improper_quit_penalty_type enum, add logic
- **Add job categories**: New model with M2M relationship to JobTemplate

---

## Contact & Support

For questions about this implementation:
- Review: `docs/JOBS_FEATURE.md`
- Check: Existing similar features (Insurance, Store, Payroll)
- Follow: Patterns in `AGENTS.md`
- Test: Run `pytest tests/test_jobs_feature.py`

Feature designed and implemented by Claude (Assistant) in collaboration with project maintainer.
