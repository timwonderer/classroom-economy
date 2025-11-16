# Insurance System Implementation Status

## ✅ COMPLETED

### Database Models (app.py)
- ✅ **InsurancePolicy** - Defines insurance products with all features
  - Includes `is_monetary` field to toggle between monetary claims (students claim dollar amounts) and non-monetary claims (students specify items/services)
- ✅ **StudentInsurance** - Tracks student policy enrollments
- ✅ **InsuranceClaim** - Manages claim submissions and processing
  - Includes `claim_amount` for monetary claims
  - Includes `claim_item` for non-monetary claims (what they're claiming)
  - Includes `comments` for optional student comments

### Forms (forms.py)
- ✅ **InsurancePolicyForm** - Create/edit policies
  - Includes `is_monetary` toggle to configure claim type
- ✅ **InsuranceClaimForm** - Students file claims
  - Includes `claim_amount` for monetary claims
  - Includes `claim_item` for non-monetary claims
  - Includes `comments` for optional additional information
- ✅ **AdminClaimProcessForm** - Admin processes claims

### Admin Templates
- ✅ **admin_insurance.html** - Main insurance dashboard (4 tabs)
  - Insurance policies management with claim type display
  - Active student policies view
  - Cancelled policies history
  - Claims processing with filtering (shows monetary amounts or claimed items)
- ✅ **admin_process_claim.html** - Detailed claim processing page
  - Displays claim type, amount/item, and student comments
  - Shows policy information including claim type
- ✅ **admin_edit_insurance_policy.html** - Policy editing page
  - Includes monetary toggle with explanatory text

### Student Templates
- ✅ **student_insurance_marketplace.html** - Insurance shopping and management
  - Displays claim type badges for all policies
- ✅ **student_file_claim.html** - File insurance claims
  - Conditionally shows claim amount field for monetary policies
  - Conditionally shows claim item field for non-monetary policies
  - Always shows optional comments field
- ✅ **student_view_policy.html** - View policy details and history

## ⏳ PENDING: Backend Routes Implementation

The following routes need to be implemented in app.py:

### Admin Routes

```python
@app.route('/admin/insurance', methods=['GET', 'POST'])
@admin_required
def admin_insurance_management():
    """Main insurance management page - create policies, view enrollments, manage claims"""
    # - Show all policies, active/cancelled enrollments, claims
    # - Handle POST for creating new policies
    # - Calculate pending_claims_count
    pass

@app.route('/admin/insurance/edit/<int:policy_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_insurance_policy(policy_id):
    """Edit existing insurance policy"""
    # - Load policy and pre-fill form
    # - Handle POST to update policy
    pass

@app.route('/admin/insurance/deactivate/<int:policy_id>', methods=['POST'])
@admin_required
def admin_deactivate_insurance_policy(policy_id):
    """Deactivate an insurance policy"""
    # - Set policy.is_active = False
    # - Don't affect existing enrollments
    pass

@app.route('/admin/insurance/claim/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def admin_process_claim(claim_id):
    """Process insurance claim"""
    # - Show claim details
    # - Validate claim (waiting period, time limit, payment status)
    # - Handle POST to approve/reject/pay
    # - Auto-reject if validation fails
    # - For MONETARY claims: Auto-deposit approved amount to student's checking account
    # - For NON-MONETARY claims: Just mark as approved (item/service will be provided offline)
    # - Create transaction record for monetary claims
    pass

@app.route('/admin/insurance/policy-view/<int:enrollment_id>')
@admin_required
def admin_view_student_policy(enrollment_id):
    """View details of a student's policy enrollment"""
    pass
```

### Student Routes

```python
@app.route('/student/insurance')
@login_required
def student_insurance_marketplace():
    """Main insurance marketplace"""
    # - Show active policies
    # - Show available policies for purchase
    # - Check repurchase restrictions
    # - Show claims history
    pass

@app.route('/student/insurance/purchase/<int:policy_id>', methods=['POST'])
@login_required
def student_purchase_insurance(policy_id):
    """Purchase insurance policy"""
    # - Check if already enrolled
    # - Check repurchase restrictions
    # - Check sufficient funds
    # - Create StudentInsurance record
    # - Set coverage_start_date = now + waiting_period_days
    # - Create transaction for premium
    pass

@app.route('/student/insurance/cancel/<int:enrollment_id>', methods=['POST'])
@login_required
def student_cancel_insurance(enrollment_id):
    """Cancel insurance policy"""
    # - Set status = 'cancelled'
    # - Set cancel_date = now
    # - Create transaction (possibly pro-rated refund)
    pass

@app.route('/student/insurance/claim/<int:policy_id>', methods=['GET', 'POST'])
@login_required
def student_file_claim(policy_id):
    """File insurance claim"""
    # - Validate: coverage started (past waiting period)
    # - Validate: payment current
    # - Validate: incident within claim_time_limit_days
    # - Validate: not exceeded max_claims_count
    # - Validate: For MONETARY policies, claim_amount must be provided
    # - Validate: For NON-MONETARY policies, claim_item must be provided
    # - Handle POST to create InsuranceClaim with appropriate fields
    # - Auto-reject if validation fails
    pass

@app.route('/student/insurance/policy/<int:enrollment_id>')
@login_required
def student_view_policy(enrollment_id):
    """View policy details"""
    # - Show enrollment details
    # - Show claims history for this policy
    pass
```

## 🔧 Implementation Logic Required

### Purchase Validation
```python
def can_purchase_policy(student, policy):
    # Check if already enrolled
    # Check if previously cancelled and within repurchase wait period
    # Check no_repurchase_after_cancel flag
    # Return (can_purchase: bool, reason: str)
```

### Claim Validation
```python
def validate_claim(claim, enrollment, policy):
    errors = []

    # Check waiting period
    if not enrollment.coverage_start_date:
        errors.append("Policy still in waiting period")
    elif enrollment.coverage_start_date > datetime.now():
        errors.append("Coverage not yet active")

    # Check payment status
    if not enrollment.payment_current:
        errors.append(f"Payment overdue ({enrollment.days_unpaid} days)")

    # Check time limit
    days_since_incident = (datetime.now() - claim.incident_date).days
    if days_since_incident > policy.claim_time_limit_days:
        errors.append(f"Claim filed too late ({days_since_incident} days, limit is {policy.claim_time_limit_days})")

    # Check max claims
    if policy.max_claims_count:
        # Count approved/paid claims in current period
        # Compare to policy.max_claims_count
        pass

    return errors
```

### Autopay System
```python
# Cron job or scheduled task to:
# - Find enrollments where next_payment_due <= today
# - Charge premium if autopay enabled
# - Update payment status
# - Increment days_unpaid if payment fails
# - Auto-cancel if days_unpaid >= auto_cancel_nonpay_days
```

## 📊 Database Migration

Once routes are implemented, create migration:

```bash
flask db migrate -m "Add comprehensive insurance system"
flask db upgrade
```

## 🔗 Navigation Updates

Add to admin navigation (templates/admin_nav.html or layout_admin.html):
```html
<li><a href="{{ url_for('admin_insurance_management') }}">Insurance</a></li>
```

Student navigation already includes insurance link.

## ✅ Features Summary

The system supports:
- ✅ Multiple insurance policies with custom settings
- ✅ **Monetary vs Non-Monetary Claims**:
  - Monetary policies: Students claim dollar amounts, auto-deposit to checking on approval
  - Non-monetary policies: Students specify items/services being claimed
  - Optional comments field for all claims
- ✅ Waiting periods before coverage starts
- ✅ Claim time limits (days from incident to file)
- ✅ Max claims per period (month/semester/year)
- ✅ Max claim amounts (for monetary policies)
- ✅ Autopay functionality
- ✅ Repurchase restrictions after cancellation
- ✅ Auto-cancel for non-payment
- ✅ Bundle discounts
- ✅ Admin claim processing with validation
- ✅ Student claim filing with automatic validation
- ✅ Claims history and status tracking
- ✅ Auto-deposit for approved monetary claims

All frontend completed! Backend routes are the final step.
