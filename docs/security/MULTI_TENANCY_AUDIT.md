# P0 MULTI-TENANCY DATA LEAK AUDIT

**Date:** 2025-11-29
**Severity:** CRITICAL (P0)
**Status:** ACTIVE SECURITY VULNERABILITY

## Executive Summary

The classroom economy application has **CRITICAL multi-tenancy data leaks** that allow students to see and interact with data from multiple teachers' class economies simultaneously. The root cause is that the application uses **teacher_id** as a weak tenant boundary instead of **join codes** as the absolute source of truth.

## Core Principle Violation

**USER REQUIREMENT:**
> The class join code should be the source of truth of how students are associated with a class. When student switch between classes, the join code is what determines the content they see, not teacher. Always use join code (scoped to specific class) as absolute source of truth.

**CURRENT IMPLEMENTATION:**
- Uses `teacher_id` stored in session as primary filter
- Allows students to see aggregated data across ALL their classes
- No proper join-code-based data isolation

## Critical Data Leaks Identified

### 1. **Student Balance Calculations (CRITICAL)**
**Location:** `app/models.py:140-145`

```python
@property
def checking_balance(self):
    return round(sum(tx.amount for tx in self.transactions
                     if tx.account_type == 'checking' and not tx.is_void), 2)
```

**Issue:** Calculates balances across ALL teachers/classes instead of per-class balances.

**Impact:** Students see their total balance across all classes they're enrolled in, breaking economy isolation.

**Fix Required:** Remove these properties and always use the scoped methods `get_checking_balance(teacher_id)`.

---

### 2. **Student Dashboard Transaction Leak**
**Location:** `app/routes/student.py:544`

```python
transactions = Transaction.query.filter_by(student_id=student.id).order_by(Transaction.timestamp.desc()).all()
```

**Issue:** Fetches ALL transactions across all classes without filtering by current teacher/join code.

**Impact:** Students can see transaction history from all their classes mixed together.

**Fix Required:** Filter by `teacher_id`:
```python
teacher_id = get_current_teacher_id()
transactions = Transaction.query.filter_by(
    student_id=student.id,
    teacher_id=teacher_id
).order_by(Transaction.timestamp.desc()).all()
```

---

### 3. **Transfer Function Data Leak**
**Location:** `app/routes/student.py:826-827`

```python
transactions = Transaction.query.filter_by(student_id=student.id, is_void=False).order_by(Transaction.timestamp.desc()).all()
checking_transactions = [t for t in transactions if t.account_type == 'checking']
savings_transactions = [t for t in transactions if t.account_type == 'savings']
```

**Issue:** Shows ALL transactions when displaying transaction history on transfer page.

**Impact:** Cross-class data leak in transfer interface.

**Fix Required:** Add teacher_id scoping to all transaction queries.

---

### 4. **Transaction Creation Missing teacher_id**
**Location:** `app/routes/student.py:791-805` (Transfer function)

```python
db.session.add(Transaction(
    student_id=student.id,
    amount=-amount,
    account_type=from_account,
    type='Withdrawal',
    description=f'Transfer to {to_account}'
))
```

**Issue:** Transactions created without `teacher_id` field populated.

**Impact:** Transactions aren't properly scoped to a specific class economy.

**Fix Required:** Add `teacher_id=get_current_teacher_id()` to ALL transaction creations.

---

### 5. **Student Items Leak**
**Location:** `app/routes/student.py:545-547`

```python
student_items = student.items.filter(
    StudentItem.status.in_(['purchased', 'pending', 'processing', 'redeemed', 'completed', 'expired'])
).order_by(StudentItem.purchase_date.desc()).all()
```

**Issue:** Shows items purchased from ALL teachers' stores.

**Impact:** Students see items from all their classes mixed together.

**Fix Required:** Add join to StoreItem and filter by teacher_id.

---

### 6. **Insurance Marketplace - No Join Code Scoping**
**Location:** `app/routes/student.py:986-992`

```python
teacher_ids = [teacher.id for teacher in student.teachers]
available_policies = InsurancePolicy.query.filter(
    InsurancePolicy.is_active == True,
    InsurancePolicy.teacher_id.in_(teacher_ids)
).all() if teacher_ids else []
```

**Issue:** Shows insurance from ALL teachers instead of just current class.

**Impact:** Students can purchase insurance from wrong class context.

**Fix Required:** Filter by current teacher_id only:
```python
teacher_id = get_current_teacher_id()
available_policies = InsurancePolicy.query.filter(
    InsurancePolicy.is_active == True,
    InsurancePolicy.teacher_id == teacher_id
).all() if teacher_id else []
```

---

### 7. **Rent Status Calculation Issues**
**Location:** `app/routes/student.py:599-660`

**Issue:** Gets rent settings by teacher_id (correct) but calculations use student.block which may include blocks from multiple teachers.

**Impact:** Rent status may show incorrect data when student is in multiple classes.

**Fix Required:** Scope rent calculations to current teacher's blocks only.

---

### 8. **Session Management - Teacher ID Instead of Join Code**
**Location:** `app/routes/student.py:48-79` (`get_current_teacher_id()`)

```python
def get_current_teacher_id():
    """Get the currently selected teacher ID from session."""
    student = get_logged_in_student()
    current_teacher_id = session.get('current_teacher_id')
    # ... defaults to first linked teacher
```

**FUNDAMENTAL ISSUE:** The session stores `current_teacher_id` but should store `current_join_code` or `current_class_id`.

**Impact:** The entire app's tenant boundary is based on teacher rather than join code/class.

**Fix Required:** Refactor to use join codes or class identifiers as primary session key.

---

### 9. **Hall Pass System**
**Location:** Multiple locations

**Issue:** Student model has single `hall_passes` column (line 121) instead of per-class tracking.

**Impact:** Hall passes are shared across all classes instead of per-class.

**Fix Required:** Either:
- Store hall passes per teacher in a separate table
- Add JSON column tracking per-teacher hall pass counts

---

### 10. **Total Earnings and Recent Deposits**
**Location:** `app/models.py:179-204`

```python
@property
def total_earnings(self):
    return round(sum(tx.amount for tx in self.transactions
                     if tx.amount > 0 and not tx.is_void
                     and not tx.description.startswith("Transfer")), 2)
```

**Issue:** Calculates across all classes.

**Impact:** Earnings shown are aggregated across all economies.

**Fix Required:** Always pass teacher_id to these calculations.

---

## Join Code vs Teacher ID: The Core Problem

### Current Broken Model:
```
Student Session → current_teacher_id → Filter Data
```

### Required Correct Model:
```
Student Session → current_join_code → Resolve TeacherBlock → teacher_id + block → Filter Data
```

### Why This Matters:
1. **Join codes are the contract between teacher and student**
   - When a teacher creates a class with join code "ABC123", that code represents a specific class/period
   - Students claim seats using join codes
   - Join code should be the immutable identifier for a class economy

2. **Teacher ID alone is insufficient**
   - A teacher may have multiple periods (Block A, B, C)
   - Each period should have its own join code and economy
   - Current system conflates all periods under one teacher

3. **Students switching classes should change contexts**
   - Switching should change the join code context
   - ALL data (transactions, balances, items, insurance) should filter by that context

## Recommended Architecture Changes

### 1. Add Class/Period Model
```python
class ClassPeriod(db.Model):
    """Represents a distinct class period with its own economy."""
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'))
    join_code = db.Column(db.String(20), unique=True, nullable=False)
    block = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### 2. Update Session Management
```python
def get_current_class_context():
    """Get currently selected class context (join code, teacher_id, block)."""
    student = get_logged_in_student()
    if not student:
        return None

    # Use join code as primary key
    current_join_code = session.get('current_join_code')

    # Resolve to class period
    if current_join_code:
        seat = TeacherBlock.query.filter_by(
            student_id=student.id,
            join_code=current_join_code
        ).first()

        if seat:
            return {
                'join_code': current_join_code,
                'teacher_id': seat.teacher_id,
                'block': seat.block,
                'class_id': seat.id  # or ClassPeriod.id if we add that model
            }

    # Default to first class
    first_seat = TeacherBlock.query.filter_by(
        student_id=student.id,
        is_claimed=True
    ).first()

    if first_seat:
        session['current_join_code'] = first_seat.join_code
        return {
            'join_code': first_seat.join_code,
            'teacher_id': first_seat.teacher_id,
            'block': first_seat.block,
            'class_id': first_seat.id
        }

    return None
```

### 3. Update All Data Queries
Every query for student-facing data MUST include:
```python
context = get_current_class_context()
if not context:
    # Handle error

# Then filter by context['teacher_id'] AND validate join_code
transactions = Transaction.query.filter_by(
    student_id=student.id,
    teacher_id=context['teacher_id']
).all()
```

### 4. Add teacher_id to ALL Transactions
Ensure EVERY transaction created includes `teacher_id`:
```python
context = get_current_class_context()
Transaction(
    student_id=student.id,
    teacher_id=context['teacher_id'],  # REQUIRED
    amount=amount,
    account_type=account_type,
    description=description
)
```

## Immediate Action Items

### Phase 1: Stop the Bleeding (CRITICAL)
1. ✅ Add teacher_id filter to ALL transaction queries in student routes
2. ✅ Add teacher_id to ALL transaction creations
3. ✅ Replace balance properties with scoped method calls
4. ✅ Add teacher_id filter to student items queries
5. ✅ Add teacher_id filter to insurance queries

### Phase 2: Architecture Refactor (HIGH PRIORITY)
1. Create migration to add missing teacher_id values to existing transactions
2. Refactor session management to use join codes
3. Create comprehensive test suite for multi-tenancy
4. Add database constraints to prevent unscoped queries

### Phase 3: Validation (REQUIRED)
1. Audit all API endpoints
2. Audit all admin endpoints for proper scoping
3. Create automated tests that verify data isolation
4. Perform penetration testing

## Test Scenarios to Validate Fixes

### Scenario 1: Student in Multiple Classes
```
Given: Student "Alice" is enrolled in Teacher A's Period 1 (join code "ABC123")
       and Teacher B's Period 2 (join code "XYZ789")
When: Alice logs in and selects Teacher A's class
Then: She should ONLY see:
  - Balances from Teacher A's economy
  - Transactions from Teacher A's economy
  - Store items from Teacher A
  - Insurance policies from Teacher A
And: She should NOT see any data from Teacher B
```

### Scenario 2: Cross-Teacher Data Leak Test
```
Given: Student "Bob" in Teacher A's class earns $100
       Student "Bob" in Teacher B's class earns $50
When: Bob views dashboard in Teacher A's class context
Then: Balance should show $100 (NOT $150)
When: Bob switches to Teacher B's class context
Then: Balance should show $50 (NOT $150 or $100)
```

### Scenario 3: Transaction Creation Scoping
```
Given: Student in Teacher A's class with $100 balance
When: Student makes transfer of $50 from checking to savings
Then: Transaction should have teacher_id = Teacher A's ID
And: When viewing in Teacher B's class context, this transaction should NOT appear
```

## Files Requiring Immediate Changes

1. `app/models.py` - Remove unscoped balance properties
2. `app/routes/student.py` - Add teacher_id to ALL queries and transactions
3. `app/routes/api.py` - Add teacher_id scoping to all endpoints
4. `app/routes/admin.py` - Verify admin queries properly scope to their students
5. Create migration for backfilling missing teacher_id values

## Severity Assessment

**Risk Level:** CRITICAL (P0)
**Data Breach:** Active - Students can see data from other teachers' classes
**Privacy Impact:** HIGH - Financial data visible across class boundaries
**Compliance Impact:** Potential FERPA violation if students see other students' data

## Conclusion

This is a **critical security vulnerability** requiring immediate remediation. The entire application's tenant isolation is broken. Every student-facing route must be audited and fixed to respect join code boundaries.

**Next Step:** Begin systematic fixes starting with transaction scoping in student routes.
