# Security & Bug Analysis Report - Insurance Overhaul

**Branch Evaluated:** `codex/add-insurance-claim-processing-modes`
**Audit Date:** 2025-11-24
**Auditor:** Claude Code
**Status:** ⚠️ Critical Issues Found - DO NOT MERGE without fixes

---

## Executive Summary

The insurance overhaul implementation on branch `codex/add-insurance-claim-processing-modes` successfully implements all business logic requirements from the specification. However, comprehensive security analysis has identified **3 P0 critical bugs** and **2 P1 high-severity issues** that pose significant risks to data integrity and financial security.

**Recommendation:** Address all P0 issues before merging to production.

---

## 🔴 P0 CRITICAL BUGS (Must Fix Before Merge)

### P0-1: Race Condition in One-Claim-Per-Transaction Enforcement

**Severity:** P0 - Data Integrity Violation
**Location:** `app/routes/student.py:1081-1133`
**CVSS Score:** 7.5 (High)

#### Description

The duplicate transaction check occurs outside of a database transaction, creating a race condition window between validation and commit. This allows multiple claims to be filed for the same transaction through concurrent requests.

#### Vulnerable Code

```python
# Line 1081-1086: Check if transaction already claimed
transaction_already_claimed = InsuranceClaim.query.filter(
    InsuranceClaim.transaction_id == selected_transaction.id
).first()
if transaction_already_claimed:
    flash("This transaction already has a claim. Each transaction can only be claimed once.", "danger")
    return redirect(url_for('student.file_claim', policy_id=policy_id))

# ... 46 lines of validation code ...

# Line 1132-1133: Actually create the claim
db.session.add(claim)
db.session.commit()  # ⚠️ RACE CONDITION WINDOW!
```

#### Attack Scenario

1. Student opens two browser tabs with the same claim form
2. Both tabs load eligible transactions at the same time
3. Student submits both forms simultaneously (within milliseconds)
4. Both requests pass the duplicate check at line 1081 (neither sees the other)
5. Both commits succeed at line 1133
6. **Result:** Two claims created for the same transaction

#### Impact

- **Business Rule Violation:** Core requirement "one claim per transaction" can be bypassed
- **Financial Loss:** Students can claim the same expense multiple times
- **Audit Trail Corruption:** Multiple claims reference the same transaction
- **Likelihood:** Medium (requires concurrent submission, but trivial to automate)

#### Proof of Concept

```bash
# Terminal 1
curl -X POST http://localhost:5000/student/insurance/claim/1 \
  -d "transaction_id=123&description=Test" &

# Terminal 2 (simultaneous)
curl -X POST http://localhost:5000/student/insurance/claim/1 \
  -d "transaction_id=123&description=Test" &
```

#### Recommended Fix

**Option 1: Database Unique Constraint (Recommended)**

```sql
-- Migration file: add_unique_constraint_transaction_claims.py
CREATE UNIQUE INDEX idx_insurance_claims_transaction_id_unique
ON insurance_claims(transaction_id)
WHERE transaction_id IS NOT NULL;
```

This provides database-level enforcement and prevents duplicates even under race conditions.

**Option 2: Row-Level Locking**

```python
# Before line 1081, add:
from sqlalchemy import select

# Use SELECT FOR UPDATE to lock the transaction row
existing_claim = db.session.execute(
    select(InsuranceClaim)
    .filter(InsuranceClaim.transaction_id == selected_transaction.id)
    .with_for_update()
).scalar_one_or_none()

if existing_claim:
    flash("This transaction already has a claim.", "danger")
    return redirect(...)
```

**Recommended Action:** Implement Option 1 (unique constraint) as the primary defense, with Option 2 as defense-in-depth.

---

### P0-2: Void Transaction Bypass in Claim Processing

**Severity:** P0 - Financial Fraud Risk
**Location:** `app/routes/admin.py:1752-1876`
**CVSS Score:** 8.1 (High)

#### Description

Admin claim approval does NOT validate whether the linked transaction has been voided. This allows admins to approve insurance reimbursements for purchases that were already refunded, resulting in double payment to students.

#### Vulnerable Code

```python
# Line 1752-1755: Calculate claim amount from transaction
def _claim_base_amount(target_claim):
    if target_claim.policy.claim_type == 'transaction_monetary' and target_claim.transaction:
        return abs(target_claim.transaction.amount)  # ⚠️ NO check for is_void!
    return target_claim.claim_amount or 0.0

# Line 1839-1857: Approve and pay claim
base_amount = _claim_base_amount(claim)  # Uses voided transaction amount!
approved_amount = base_amount
# ... caps applied ...
claim.approved_amount = approved_amount

# Line 1866-1874: Create reimbursement transaction
transaction = Transaction(
    student_id=student.id,
    amount=approved_amount,  # ⚠️ Paying for a voided transaction!
    type='insurance_reimbursement',
    description=transaction_description,
)
db.session.add(transaction)
```

#### Attack Scenario

1. Student purchases item for $100 (creates Transaction #123, `is_void=False`)
2. Student files insurance claim for Transaction #123
3. Teacher voids Transaction #123 (refund issued, `is_void=True`)
4. Teacher approves insurance claim #456
5. System calculates `approved_amount = $100` from the **voided** transaction
6. System creates new Transaction crediting student $100
7. **Result:** Student received $100 refund + $100 insurance = $200 for a $100 purchase

#### Impact

- **Financial Fraud:** Students can receive double payment
- **Accounting Integrity:** Violates accounting principles (no reimbursement for refunded purchases)
- **Audit Failure:** Financial audits would flag double payments
- **Likelihood:** High (common workflow: void incorrect transactions, process pending claims)

#### Real-World Scenario

A teacher notices a duplicate charge on Student A's account and voids the transaction. Later that day, the teacher processes pending insurance claims and approves Student A's claim that was linked to the now-voided transaction. Student A receives insurance payout for money they were already refunded.

#### Recommended Fix

```python
# In app/routes/admin.py, add validation around line 1768
if claim.policy.claim_type == 'transaction_monetary' and claim.transaction:
    if claim.transaction.is_void:
        validation_errors.append(
            "Cannot approve claim: linked transaction has been voided. "
            "Voiding a transaction invalidates any associated insurance claims."
        )
```

Additionally, consider auto-rejecting claims when their linked transaction is voided:

```python
# In app/routes/admin.py, void_transaction function (around line 1918)
def void_transaction(transaction_id):
    # ... existing code ...
    tx.is_void = True

    # Auto-reject any pending claims linked to this transaction
    pending_claims = InsuranceClaim.query.filter(
        InsuranceClaim.transaction_id == transaction_id,
        InsuranceClaim.status == 'pending'
    ).all()

    for claim in pending_claims:
        claim.status = 'rejected'
        claim.rejection_reason = 'Linked transaction was voided'
        claim.processed_date = datetime.utcnow()
        claim.processed_by_admin_id = session.get('admin_id')

    db.session.commit()
```

---

### P0-3: Transaction Ownership Not Re-Validated on Approval

**Severity:** P0 - Authorization Bypass
**Location:** `app/routes/admin.py:1752-1876`
**CVSS Score:** 7.8 (High)

#### Description

When approving a claim, the system trusts that `claim.transaction_id` belongs to `claim.student_id` without re-validation. While ownership is verified at submission time, database tampering or SQL injection could allow a student to get reimbursed for another student's transaction.

#### Vulnerable Code

```python
# Line 1752-1755: Trusts transaction ownership
def _claim_base_amount(target_claim):
    # Assumes target_claim.transaction belongs to target_claim.student
    # ⚠️ NO ownership validation!
    if target_claim.policy.claim_type == 'transaction_monetary' and target_claim.transaction:
        return abs(target_claim.transaction.amount)
    return target_claim.claim_amount or 0.0
```

#### Attack Scenario

**Via Database Tampering:**
1. Student A files claim #100 for their $20 transaction (#500)
2. Attacker gains database access (SQL injection, compromised credentials, etc.)
3. Attacker updates claim #100: `UPDATE insurance_claims SET transaction_id = 999 WHERE id = 100`
4. Transaction #999 is Student B's $500 purchase
5. Admin approves claim #100
6. Student A receives $500 reimbursement for Student B's transaction

**Via Multi-Tenancy Violation:**
In a multi-teacher environment, if transaction filtering is inadequate:
1. Student A (Teacher 1's class) files claim
2. Claim gets linked to Student B's transaction (Teacher 2's class)
3. Cross-economy financial fraud

#### Impact

- **Authorization Bypass:** Student reimbursed for transaction they didn't make
- **Cross-Student Fraud:** One student's money goes to another
- **Multi-Tenancy Violation:** Breaks economy isolation between teachers
- **Likelihood:** Low (requires database compromise), **Severity:** Critical

#### Recommended Fix

```python
# In app/routes/admin.py, around line 1768, add ownership validation
if claim.policy.claim_type == 'transaction_monetary' and claim.transaction:
    # Validate transaction belongs to the student filing the claim
    if claim.transaction.student_id != claim.student_id:
        validation_errors.append(
            "SECURITY: Transaction ownership mismatch. "
            f"Transaction belongs to student ID {claim.transaction.student_id}, "
            f"but claim filed by student ID {claim.student_id}. "
            "This claim has been flagged for security review."
        )
        # Log security incident
        current_app.logger.error(
            f"SECURITY ALERT: Transaction ownership mismatch in claim {claim.id}. "
            f"Claim student: {claim.student_id}, Transaction student: {claim.transaction.student_id}"
        )
```

---

## 🟠 P1 HIGH SEVERITY ISSUES

### P1-1: SQL Injection in Transaction Date Filtering

**Severity:** P1 - SQL Injection Vulnerability
**Location:** `app/routes/admin.py:3270`
**CWE:** CWE-89 (SQL Injection)
**CVSS Score:** 8.6 (High)

#### Description

User-controlled `end_date` parameter from query string is injected directly into SQL via f-string without validation or sanitization.

#### Vulnerable Code

```python
# Line 3230: User input (no validation)
end_date = request.args.get('end_date')

# Line 3268-3270: Direct SQL injection via f-string
if end_date:
    # ⚠️ CRITICAL: User input directly in SQL!
    query = query.filter(Transaction.timestamp < text(f"'{end_date}'::date + interval '1 day'"))
```

#### Attack Scenario

```http
GET /admin/banking?end_date=2024-01-01'::date); DROP TABLE transactions; -- HTTP/1.1
```

This would execute:
```sql
SELECT * FROM transactions WHERE timestamp < '2024-01-01'::date); DROP TABLE transactions; --'::date + interval '1 day'
```

#### Impact

- **Full SQL Injection:** Attacker can execute arbitrary SQL
- **Data Exfiltration:** Read sensitive data from any table
- **Data Manipulation:** Modify transactions, balances, claims
- **Denial of Service:** Drop tables, corrupt data
- **Privilege Escalation:** Access admin credentials
- **Likelihood:** High (query parameter accessible to all admins)

#### Additional Vulnerable Code

Similar pattern exists for `start_date` (line 3267):
```python
if start_date:
    query = query.filter(Transaction.timestamp >= start_date)
```

While SQLAlchemy typically handles this safely through parameterization, mixing `text()` with f-strings bypasses protections.

#### Recommended Fix

**Option 1: Use SQLAlchemy Functions (Recommended)**

```python
from sqlalchemy import func, cast
from sqlalchemy.types import Date, Interval

if end_date:
    try:
        # Validate date format first
        datetime.strptime(end_date, '%Y-%m-%d')
        # Use SQLAlchemy functions (automatically parameterized)
        end_datetime = func.cast(end_date, Date) + cast('1 day', Interval)
        query = query.filter(Transaction.timestamp < end_datetime)
    except ValueError:
        flash("Invalid end date format. Please use YYYY-MM-DD.", "danger")
        end_date = None
```

**Option 2: Parameterized Query**

```python
from sqlalchemy import text

if end_date:
    try:
        # Validate format
        datetime.strptime(end_date, '%Y-%m-%d')
        # Use parameterized query
        query = query.filter(
            Transaction.timestamp < text("(:end_date::date + interval '1 day')").bindparams(end_date=end_date)
        )
    except ValueError:
        flash("Invalid date format", "danger")
```

**Option 3: Python Date Arithmetic (Simplest)**

```python
from datetime import datetime, timedelta

if end_date:
    try:
        # Parse and validate
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        # Add one day in Python
        end_date_inclusive = end_date_obj + timedelta(days=1)
        # Use safe comparison
        query = query.filter(Transaction.timestamp < end_date_inclusive)
    except ValueError:
        flash("Invalid date format", "danger")
```

**Recommended Action:** Implement Option 3 (simplest and safest).

---

### P1-2: Race Condition in Period Cap Enforcement

**Severity:** P1 - Financial Cap Bypass
**Location:** `app/routes/admin.py:1794-1856`
**CVSS Score:** 6.5 (Medium)

#### Description

Period payout cap calculation happens outside of a database transaction, allowing concurrent claim approvals to exceed the monthly/period budget cap.

#### Vulnerable Code

```python
# Line 1797-1804: Calculate remaining budget (outside transaction lock)
period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
    InsuranceClaim.student_insurance_id == enrollment.id,
    InsuranceClaim.status.in_(['approved', 'paid']),
    InsuranceClaim.processed_date >= period_start,
    InsuranceClaim.processed_date <= period_end,
    InsuranceClaim.approved_amount.isnot(None),
    InsuranceClaim.id != claim.id,
).scalar() or 0.0

remaining_period_cap = max(claim.policy.max_payout_per_period - period_payouts, 0)

# ... many lines later ...

# Line 1847-1855: Check and approve (race condition window)
if remaining_period_cap <= 0:
    flash("Cannot approve: max payout exceeded", "danger")
    db.session.rollback()
    return redirect(...)
approved_amount = min(approved_amount, remaining_period_cap)

# Line 1883: Commit (other approvals may have happened in parallel)
db.session.commit()
```

#### Attack Scenario

**Setup:**
- Policy has $100/month cap
- Currently $90 paid this month
- Two pending claims: Claim A ($20) and Claim B ($20)

**Timeline:**
```
T0: Admin 1 opens Claim A processing page
    - Calculates: period_payouts = $90
    - Calculates: remaining_period_cap = $10

T1: Admin 2 opens Claim B processing page
    - Calculates: period_payouts = $90 (same as Admin 1)
    - Calculates: remaining_period_cap = $10

T2: Admin 1 approves Claim A for $10
    - approved_amount = min($20, $10) = $10
    - Commits to database

T3: Admin 2 approves Claim B for $10
    - approved_amount = min($20, $10) = $10
    - Commits to database

Result: Total paid this month = $90 + $10 + $10 = $110
Cap violated: $110 > $100
```

#### Impact

- **Budget Overruns:** Period spending caps can be exceeded
- **Financial Loss:** More paid out than policy allows
- **Policy Violation:** Undermines insurance budget controls
- **Likelihood:** Low in single-admin environments, Medium in multi-admin schools
- **Severity:** Medium (cap bypass by small margins, unlikely to be catastrophic)

#### Recommended Fix

**Option 1: Optimistic Locking (Recommended)**

```python
# At start of POST processing (line 1821)
if request.method == 'POST' and form.validate_on_submit():
    # Lock the enrollment row to prevent concurrent modifications
    enrollment = StudentInsurance.query.filter_by(
        id=claim.student_insurance_id
    ).with_for_update().first()

    # Recalculate period payouts within the locked transaction
    period_payouts = db.session.query(func.sum(InsuranceClaim.approved_amount)).filter(
        InsuranceClaim.student_insurance_id == enrollment.id,
        InsuranceClaim.status.in_(['approved', 'paid']),
        InsuranceClaim.processed_date >= period_start,
        InsuranceClaim.processed_date <= period_end,
        InsuranceClaim.approved_amount.isnot(None),
        InsuranceClaim.id != claim.id,
    ).scalar() or 0.0

    remaining_period_cap = max(claim.policy.max_payout_per_period - period_payouts, 0)

    # Proceed with approval...
```

**Option 2: Pessimistic Locking with Retry**

Add a version column to track concurrent modifications and retry on conflict.

**Option 3: Accept Risk**

Document this as a known limitation. In practice:
- Most classrooms have single admin
- Concurrent approvals are rare
- Overage would be minimal (one claim's worth)
- Can be monitored and addressed retroactively

**Recommended Action:** Implement Option 1 for production environments with multiple admins. For single-teacher deployments, Option 3 (document limitation) may be acceptable.

---

## 🟡 P2 EFFICIENCY ISSUES

### E1: N+1 Query Problem in Claims List

**Severity:** P2 - Performance
**Location:** `app/routes/admin.py:1445-1450`

#### Description

Claims query doesn't eager-load related objects, triggering additional database queries when template accesses relationships.

#### Vulnerable Code

```python
claims = (
    InsuranceClaim.query
    .join(Student, InsuranceClaim.student_id == Student.id)
    .filter(Student.id.in_(student_ids_subq))
    .order_by(InsuranceClaim.filed_date.desc())
    .all()  # ⚠️ Doesn't eager-load relationships
)
```

When template renders claims:
```jinja2
{% for claim in claims %}
    {{ claim.policy.title }}        <!-- Query 1 per claim -->
    {{ claim.student.full_name }}   <!-- Query 2 per claim -->
    {{ claim.transaction.amount }}  <!-- Query 3 per claim -->
{% endfor %}
```

#### Impact

- **Query Explosion:** 100 claims = 1 + 300 = 301 queries
- **Page Load Slowdown:** Increases linearly with claim count
- **Database Load:** Unnecessary connection overhead

#### Recommended Fix

```python
from sqlalchemy.orm import joinedload

claims = (
    InsuranceClaim.query
    .options(
        joinedload(InsuranceClaim.policy),
        joinedload(InsuranceClaim.student),
        joinedload(InsuranceClaim.transaction),
        joinedload(InsuranceClaim.student_policy),
    )
    .join(Student, InsuranceClaim.student_id == Student.id)
    .filter(Student.id.in_(student_ids_subq))
    .order_by(InsuranceClaim.filed_date.desc())
    .all()
)
```

Result: 100 claims = 5 queries (1 main + 4 joins) instead of 301.

---

### E2: Missing Database Index on transaction_id

**Severity:** P2 - Performance
**Location:** `app/models.py:527`, `migrations/versions/2f3g4h5i6j7k_add_claim_type_and_transaction_link.py`

#### Description

No index on `insurance_claims.transaction_id` despite frequent lookups for duplicate checking and transaction-based queries.

#### Performance Impact

Queries affected:
```python
# Duplicate check (runs on every claim submission)
InsuranceClaim.query.filter(
    InsuranceClaim.transaction_id == selected_transaction.id
).first()

# Eligible transactions filter (runs on every claim form load)
claimed_tx_subq = db.session.query(InsuranceClaim.transaction_id).filter(
    InsuranceClaim.transaction_id.isnot(None)
)
```

Without index:
- Full table scan on `insurance_claims` table
- O(n) complexity where n = total claims
- Degrades linearly as claims accumulate

With index:
- O(log n) lookup via B-tree
- Constant time for duplicate checks

#### Recommended Fix

```python
# Create migration: add_index_insurance_claims_transaction_id.py

def upgrade():
    op.create_index(
        'ix_insurance_claims_transaction_id',
        'insurance_claims',
        ['transaction_id']
    )

def downgrade():
    op.drop_index('ix_insurance_claims_transaction_id', table_name='insurance_claims')
```

---

## 📊 Summary Table

| ID | Severity | Type | Issue | Location | Fix Effort |
|----|----------|------|-------|----------|------------|
| P0-1 | P0 | Data Integrity | Race condition: duplicate claims | student.py:1081-1133 | Medium |
| P0-2 | P0 | Financial Fraud | Void transaction bypass | admin.py:1752-1876 | Low |
| P0-3 | P0 | Authorization | Transaction ownership not validated | admin.py:1752-1876 | Low |
| P1-1 | P1 | SQL Injection | Unsafe date filtering | admin.py:3270 | Low |
| P1-2 | P1 | Race Condition | Period cap bypass | admin.py:1794-1856 | Medium |
| E1 | P2 | Performance | N+1 queries | admin.py:1445-1450 | Low |
| E2 | P2 | Performance | Missing index | models.py:527 | Low |

---

## ✅ Security Aspects That Are Correct

The following were reviewed and found to be secure:

- ✅ **Transaction ownership validated at submission** (student.py:1042)
- ✅ **Admin authorization properly scoped** via `_student_scope_subquery()`
- ✅ **CSRF protection** enabled via WTForms
- ✅ **ORM parameterization** prevents most SQL injection
- ✅ **Multi-tenancy isolation** via teacher_id filtering
- ✅ **Policy ownership validation** (admin.py:1478)
- ✅ **No XSS vulnerabilities** (proper template escaping)
- ✅ **No direct file operations** from user input
- ✅ **Proper use of foreign keys** and referential integrity

---

## 🔧 Recommended Remediation Plan

### Phase 1: Critical Fixes (Before Merge) - Est. 2-4 hours

**Must Fix:**
1. **P0-1:** Add unique constraint on `transaction_id`
   - Create migration with unique index
   - Test concurrent submission scenario

2. **P0-2:** Validate transaction not voided
   - Add `is_void` check in claim processing
   - Auto-reject claims when transaction voided

3. **P0-3:** Re-validate transaction ownership
   - Add ownership check in approval logic
   - Add security logging for mismatches

4. **P1-1:** Sanitize date parameters
   - Use Python datetime parsing
   - Remove SQL f-string injection

### Phase 2: High Priority (Next Sprint) - Est. 2-3 hours

**Should Fix:**
5. **P1-2:** Add row-level locking for period caps
   - Use `.with_for_update()` on enrollment
   - Recalculate within locked transaction

6. **E1:** Add eager loading to claims query
   - Use `joinedload()` for relationships
   - Measure query count improvement

7. **E2:** Add database index
   - Create migration for `transaction_id` index
   - Analyze query performance before/after

### Phase 3: Testing & Validation - Est. 4 hours

**Testing Required:**
- Write concurrency tests for duplicate claim prevention
- Test void transaction rejection
- SQL injection fuzzing on date parameters
- Load test with 1000+ claims (N+1 validation)
- Security regression testing

---

## 📝 Testing Recommendations

### Security Tests

```python
# tests/test_insurance_security.py

def test_duplicate_claim_race_condition():
    """Test that concurrent claims for same transaction are prevented"""
    import threading

    def submit_claim():
        # Submit claim for transaction_id=123
        pass

    threads = [threading.Thread(target=submit_claim) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Assert only ONE claim created
    claims = InsuranceClaim.query.filter_by(transaction_id=123).all()
    assert len(claims) == 1

def test_void_transaction_rejection():
    """Test that claims for voided transactions are rejected"""
    tx = Transaction(student_id=1, amount=-50, is_void=True)
    claim = InsuranceClaim(transaction_id=tx.id, ...)

    # Try to approve
    result = process_claim(claim.id)

    assert "voided" in result.errors
    assert claim.status != 'approved'

def test_sql_injection_in_date_filter():
    """Test SQL injection protection in date filtering"""
    malicious_dates = [
        "2024-01-01'; DROP TABLE transactions; --",
        "2024-01-01' OR '1'='1",
        "2024-01-01' UNION SELECT * FROM admins--",
    ]

    for date in malicious_dates:
        response = client.get(f'/admin/banking?end_date={date}')
        assert response.status_code in [200, 400]  # Should handle safely
        # Verify no SQL executed
        assert Transaction.query.count() > 0  # Table still exists
```

### Load Tests

```python
def test_claims_list_performance():
    """Test that claims list doesn't have N+1 queries"""
    from flask_sqlalchemy import get_debug_queries

    # Create 100 claims
    for i in range(100):
        create_claim(...)

    # Enable query logging
    app.config['SQLALCHEMY_RECORD_QUERIES'] = True

    # Load claims page
    response = client.get('/admin/insurance')

    # Should be < 10 queries (1 main + eager loads)
    queries = get_debug_queries()
    assert len(queries) < 10, f"N+1 detected: {len(queries)} queries"
```

---

## 🎯 Acceptance Criteria for Merge

Before merging `codex/add-insurance-claim-processing-modes` to main:

- [ ] All P0 issues resolved and tested
- [ ] P1-1 (SQL injection) fixed
- [ ] Security test suite passes
- [ ] No new vulnerabilities introduced
- [ ] Code review approved by second developer
- [ ] Database migrations tested on staging
- [ ] Performance benchmarks acceptable (< 10 queries for claims list)
- [ ] Security audit sign-off

---

## 📚 References

- **CWE-89:** SQL Injection
- **CWE-362:** Concurrent Execution using Shared Resource with Improper Synchronization ('Race Condition')
- **OWASP Top 10 2021:** A03:2021 – Injection
- **OWASP Top 10 2021:** A04:2021 – Insecure Design

---

## 📞 Contact

For questions about this security audit, contact the development team or create an issue in the repository.

**Next Steps:** Create a fix branch from `codex/add-insurance-claim-processing-modes` to address P0 and P1 issues before merge to main.
