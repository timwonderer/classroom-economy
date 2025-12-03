# 🚨 CRITICAL: Same-Teacher Multi-Period Data Leak

**Severity:** P0 CRITICAL
**Date:** 2025-11-29
**Status:** NEWLY DISCOVERED - NOT YET FIXED

---

## Problem Statement

The previous fixes addressed **cross-teacher** data leaks but **FAILED to address same-teacher, different-period isolation**.

### Current Broken Behavior:

```
Teacher: Ms. Smith (teacher_id = 5)
Period A: Math 1st Period (join code: MATH1A, block: "A")
Period B: Math 3rd Period (join code: MATH3B, block: "B")

Student Alice is enrolled in BOTH periods.

EXPECTED: Alice sees separate balances/transactions for each period
ACTUAL: Alice sees COMBINED data from both periods!
```

---

## Root Cause Analysis

### 1. Transaction Table Schema
```python
class Transaction(db.Model):
    student_id = ...
    teacher_id = ...  # ← Only has teacher_id, NOT block or join_code!
    amount = ...
    # NO block field
    # NO join_code field
```

**Problem:** Transactions only track `teacher_id`, not which specific period/class.

### 2. Session Management
```python
def get_current_teacher_id():
    # Only tracks teacher_id in session
    current_teacher_id = session.get('current_teacher_id')
    # Does NOT track which period/block/join_code!
```

**Problem:** Session doesn't know WHICH class within a teacher's periods.

### 3. Query Scoping (From Previous Fixes)
```python
transactions = Transaction.query.filter_by(
    student_id=student.id,
    teacher_id=teacher_id  # ← Filters by teacher only!
).all()
```

**Problem:** This returns ALL transactions for ANY period taught by this teacher.

---

## Data Leak Scenario

### Setup:
```
Teacher: Mr. Johnson (ID: 10)
- Period A (Join Code: ENG1A): English 1st Period
- Period B (Join Code: ENG3B): English 3rd Period

Student Bob enrolled in BOTH periods
```

### Attack Vector:
```
1. Bob logs into Period A (English 1st)
2. Bob earns $100 in Period A
3. Bob logs into Period B (English 3rd)
4. Bob earns $50 in Period B
5. Bob views dashboard in Period A

CURRENT BEHAVIOR (BROKEN):
  Dashboard shows: $150 balance (WRONG!)
  Transactions show: All transactions from BOTH periods

EXPECTED BEHAVIOR:
  Dashboard shows: $100 balance
  Transactions show: Only Period A transactions
```

---

## Impact Assessment

### Affected Users:
- **ANY student enrolled in multiple periods with same teacher**
- Common in schools where students have same teacher for different subjects
- Example: Math teacher teaching Algebra (Period A) and Geometry (Period B)

### Data Exposure:
- ❌ Balances aggregated across periods
- ❌ Transactions visible across periods
- ❌ Store purchases mixed between periods
- ❌ Insurance policies visible across periods
- ❌ Rent payments tracked globally instead of per-period

### Severity:
**CRITICAL** - This violates the fundamental principle:
> "The class join code should be the source of truth"

Each join code = distinct class economy (regardless of teacher)

---

## Technical Analysis

### Current Data Model:
```
Transaction
  ├─ student_id (which student)
  ├─ teacher_id (which teacher)
  └─ ❌ MISSING: Which specific class/period/join_code
```

### What's Needed:
```
Transaction
  ├─ student_id
  ├─ teacher_id
  └─ ✅ join_code OR block (to identify specific class)
```

---

## Solution Architecture

### Option 1: Add join_code Column (RECOMMENDED)
**Pros:**
- Join code is the absolute source of truth
- Directly maps to the user requirement
- No ambiguity about which class

**Cons:**
- Migration required
- Need to backfill existing data

**Implementation:**
```python
class Transaction(db.Model):
    student_id = db.Column(...)
    teacher_id = db.Column(...)
    join_code = db.Column(db.String(20), nullable=True)  # ADD THIS
    # ...

# Query scoping:
transactions = Transaction.query.filter_by(
    student_id=student.id,
    join_code=current_join_code  # Filter by specific class!
).all()
```

### Option 2: Add block Column
**Pros:**
- Simpler than join_code
- Block name is more human-readable

**Cons:**
- Block alone isn't unique (multiple teachers can have "Period A")
- Would need to filter by BOTH teacher_id AND block
- Less precise than join_code

**Implementation:**
```python
class Transaction(db.Model):
    student_id = db.Column(...)
    teacher_id = db.Column(...)
    block = db.Column(db.String(10), nullable=True)  # ADD THIS
    # ...

# Query scoping:
transactions = Transaction.query.filter_by(
    student_id=student.id,
    teacher_id=teacher_id,
    block=current_block  # Filter by specific period!
).all()
```

### Option 3: Add class_period_id (FUTURE)
Create explicit ClassPeriod model linking join_code → teacher + block

**Pros:**
- Most explicit and normalized
- Cleanest architecture

**Cons:**
- Requires new table
- More complex migration
- Larger refactor

---

## Required Changes

### 1. Database Migration
```python
# Add join_code column to transactions table
def upgrade():
    op.add_column('transaction',
        sa.Column('join_code', sa.String(20), nullable=True)
    )

    # Backfill strategy:
    # For each transaction with teacher_id but no join_code:
    #   - Look up student's TeacherBlocks for that teacher
    #   - If only one block: use that join_code
    #   - If multiple blocks: cannot determine, leave NULL
    #   - Log all NULL cases for manual review
```

### 2. Session Management Refactor
```python
def get_current_class_context():
    """Get current class context (join_code, teacher_id, block)."""
    student = get_logged_in_student()

    # Get current join code from session
    current_join_code = session.get('current_join_code')

    if not current_join_code:
        # Default to first class
        first_seat = TeacherBlock.query.filter_by(
            student_id=student.id,
            is_claimed=True
        ).first()

        if first_seat:
            current_join_code = first_seat.join_code
            session['current_join_code'] = current_join_code

    # Resolve join code to full context
    seat = TeacherBlock.query.filter_by(
        student_id=student.id,
        join_code=current_join_code
    ).first()

    return {
        'join_code': current_join_code,
        'teacher_id': seat.teacher_id,
        'block': seat.block
    }
```

### 3. Update All Transaction Queries
```python
# BEFORE (BROKEN for same-teacher multi-period):
transactions = Transaction.query.filter_by(
    student_id=student.id,
    teacher_id=teacher_id
).all()

# AFTER (FIXED):
context = get_current_class_context()
transactions = Transaction.query.filter_by(
    student_id=student.id,
    join_code=context['join_code']
).all()
```

### 4. Update All Transaction Creations
```python
# BEFORE:
Transaction(
    student_id=student.id,
    teacher_id=teacher_id,
    amount=amount
)

# AFTER:
context = get_current_class_context()
Transaction(
    student_id=student.id,
    teacher_id=context['teacher_id'],
    join_code=context['join_code'],  # ADD THIS
    amount=amount
)
```

---

## Files Requiring Changes

### High Priority:
1. `app/models.py` - Add join_code column to Transaction
2. `migrations/` - Create migration to add join_code
3. `app/routes/student.py` - Update all transaction queries and creations
4. `app/routes/api.py` - Update API transaction handling
5. `app/routes/admin.py` - Update admin transaction queries

### Medium Priority:
6. Update all other tables that should be scoped by join_code:
   - `StudentItem` - should have join_code
   - `StudentInsurance` - should have join_code
   - `RentPayment` - should have join_code
   - `HallPassLog` - should have join_code
   - `TapEvent` - already has period field

---

## Migration Strategy

### Phase 1: Add Column (Non-Breaking)
1. Add `join_code` column as nullable
2. Update all transaction creations to include join_code
3. Deploy - new transactions will have join_code

### Phase 2: Backfill Data
1. Script to backfill join_code for existing transactions
2. Where ambiguous, log for manual review
3. Validate backfill results

### Phase 3: Enforce (Breaking)
1. Make join_code NOT NULL
2. Add database index on join_code
3. Remove old teacher_id-only queries

---

## Test Cases

### Test Case 1: Same Teacher, Different Periods
```
Setup:
  - Teacher: Ms. Lee (ID: 15)
  - Period A: Science 1st (Join: SCI1A)
  - Period B: Science 4th (Join: SCI4B)
  - Student: Carol enrolled in both

Steps:
  1. Carol logs into SCI1A
  2. Carol earns $200
  3. Carol switches to SCI4B
  4. Carol earns $75
  5. Carol switches back to SCI1A

Expected Results:
  - In SCI1A context: Balance = $200
  - In SCI4B context: Balance = $75
  - Transaction queries return only current period
  - Store items show only current period purchases

Actual Results (BEFORE FIX):
  - Both contexts show: Balance = $275 ❌
```

### Test Case 2: Transaction Creation
```
Setup:
  - Same as Test Case 1
  - Carol in SCI1A context

Steps:
  1. Carol makes a $50 transfer from checking to savings
  2. Inspect transaction records

Expected Results:
  - Transaction has join_code = "SCI1A"
  - Transaction has teacher_id = 15
  - Transaction visible in SCI1A context only
  - Transaction NOT visible in SCI4B context

Actual Results (BEFORE FIX):
  - Transaction has NO join_code ❌
  - Transaction visible in BOTH contexts ❌
```

---

## Recommended Action Plan

### IMMEDIATE (TODAY):
1. ✅ Document this issue (THIS FILE)
2. ⬜ Create migration to add join_code to Transaction
3. ⬜ Refactor get_current_teacher_id() → get_current_class_context()
4. ⬜ Update all transaction creations to include join_code

### HIGH PRIORITY (THIS WEEK):
5. ⬜ Update all transaction queries to filter by join_code
6. ⬜ Update other models (StudentItem, StudentInsurance, etc.)
7. ⬜ Create comprehensive tests for same-teacher multi-period
8. ⬜ Backfill join_code for existing transactions

### MEDIUM PRIORITY (NEXT SPRINT):
9. ⬜ Make join_code NOT NULL after backfill
10. ⬜ Refactor session to use join_code as primary key
11. ⬜ Add database constraints

---

## Status

- **Issue Identified:** ✅ 2025-11-29
- **Documentation Created:** ✅ This file
- **Migration Created:** ⬜ Not yet
- **Code Updated:** ⬜ Not yet
- **Tests Created:** ⬜ Not yet
- **Deployed:** ⬜ Not yet

---

## References

- Original requirement: "The class join code should be the source of truth"
- Previous fixes: MULTI_TENANCY_AUDIT.md (only fixed cross-teacher leaks)
- Related models: TeacherBlock, Transaction, StudentTeacher

---

**CRITICAL:** This issue affects EVERY student with the same teacher in multiple periods.
**ACTION REQUIRED:** Immediate fix needed to properly isolate period data.
