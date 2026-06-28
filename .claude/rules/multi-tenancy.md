# Multi-Tenancy Scoping Rules

**CRITICAL:** This project had a P0 same-teacher multi-period data leak. Student data must always be resolved in the active class scope identified by `join_code`.

---

## The Golden Rules

1. **`join_code` is the class isolation key.**
2. **`ClassMembership` is the class-boundary authority.**
3. **`StudentTeacher` defines teacher ownership, not class membership.**
4. **`StudentBlock` stores per-student per-period state, not balances or membership authority.**
5. **Never scope student data by `teacher_id` alone.**

---

## Runtime Model

### Class scope

```python
ClassEconomy
├── join_code (PK)
└── display_name / status / metadata

ClassMembership
├── join_code (FK to ClassEconomy)
├── admin_id OR student_id
├── role      # admin | student
└── status    # active | archived
```

### Teacher ownership

```python
StudentTeacher
├── student_id
└── teacher_id
```

### Student records and per-class state

```python
Student
├── id
├── identity_id
├── block
├── join_code / join_code_id   # compatibility + claim flows
├── credential hashes
├── recovery fields
└── opaque/internal references

StudentBlock
├── student_id
├── seat_id
├── period
├── join_code
├── tap_enabled
├── done_for_day_date
└── rent_hall_passes
```

### Financial and attendance scope

- `Transaction.join_code`
- `TapEvent.join_code`
- `HallPassLog.join_code`
- `PayrollSettings.join_code`
- `RentSettings.join_code`
- `BankingSettings.join_code`
- `FeatureSettings.join_code`
- `BalanceCache.join_code`

`BalanceCache` stores posted balances. Student balances are read through scoped methods on `Student`, not from `StudentBlock`.

---

## Correct Scoping Patterns

### Pattern 1: Get students for the selected class

Resolve canonical context first, then add class membership scope.

```python
from app.models import ClassMembership, Student
from app.services.context_resolver import resolve_canonical_context


def get_students_for_current_class(join_code):
    if not resolve_canonical_context():
        return []
    students = (
        Student.query
        .join(
            ClassMembership,
            ClassMembership.student_id == Student.id,
        )
        .filter(
            ClassMembership.join_code == join_code,
            ClassMembership.role == "student",
            ClassMembership.status == "active",
        )
        .all()
    )
    return students
```

```python
# WRONG: teacher ownership is not enough to identify one class
students = Student.query.filter_by(teacher_id=teacher_id).all()
```

### Pattern 2: Get class-scoped transactions

```python
def get_student_transactions(student_id, join_code):
    return (
        Transaction.query
        .filter_by(student_id=student_id, join_code=join_code)
        .order_by(Transaction.timestamp.desc())
        .all()
    )
```

### Pattern 3: Get class-scoped balances

```python
def get_student_balance(student, join_code, teacher_id):
    return {
        "checking": student.get_checking_balance(
            join_code=join_code,
            teacher_id=teacher_id,
        ),
        "savings": student.get_savings_balance(
            join_code=join_code,
            teacher_id=teacher_id,
        ),
    }
```

```python
# WRONG: StudentBlock does not store balances
student_block.checking_balance
student_block.savings_balance
```

### Pattern 4: Update class-scoped settings

```python
def get_payroll_settings(join_code):
    return PayrollSettings.query.filter_by(join_code=join_code).first()
```

```python
# WRONG: teacher-global settings can affect multiple periods
PayrollSettings.query.filter_by(teacher_id=teacher_id).first()
```

---

## Getting Current Class Context

### Student routes

```python
from app.routes.student import get_current_class_context


context = get_current_class_context()
if not context:
    return redirect(url_for("student.select_class"))

join_code = context["join_code"]
teacher_id = context["teacher_id"]
```

Use both values when you need a class-scoped balance read:

```python
checking = student.get_checking_balance(
    join_code=join_code,
    teacher_id=teacher_id,
)
```

### Admin routes

```python
join_code = session.get("current_join_code")
if not join_code:
    return redirect(url_for("admin.index"))
```

For admin-accessible students:

```python
student = get_student_for_admin(student_id)
if not student:
    abort(404)
```

If the route is class-specific, validate the selected `join_code` before performing mutations or rendering class-bound data.

---

## Scoped Helper Functions

Legacy helper names in `app/auth.py` are removed; use canonical context and class joins.

### Canonical student query

- Returns students only after canonical class scope is established
- Must still be combined with `join_code` / `ClassMembership` / route-specific class checks when the route is period-specific

### Canonical student lookup

- Returns a single student only after canonical class scope is established
- For class-specific operations, still validate the selected class context

---

## Common Mistakes

### Mistake 1: Treating ownership as class scope

```python
# WRONG
students = Student.query.all()
```

```python
# CORRECT
students = (
    Student.query
    .join(ClassMembership, ClassMembership.student_id == Student.id)
    .filter(ClassMembership.join_code == join_code)
    .all()
)
```

### Mistake 2: Reading balances from `StudentBlock`

```python
# WRONG
student_block = StudentBlock.query.filter_by(student_id=student.id, join_code=join_code).first()
balance = student_block.checking_balance
```

```python
# CORRECT
balance = student.get_checking_balance(join_code=join_code, teacher_id=teacher_id)
```

### Mistake 3: Creating ledger records without `join_code`

```python
# WRONG
db.session.add(Transaction(student_id=student.id, amount=50))
```

```python
# CORRECT
db.session.add(
    Transaction(
        student_id=student.id,
        join_code=join_code,
        amount=50,
    )
)
```

### Mistake 4: Mixing hall-pass state with student lock state

- `HallPassLog.status` supports `pending`, `approved`, `rejected`, `left`, `returned`
- `StudentBlock.done_for_day_date` is a separate per-class student lock state

---

## Current Status of Legacy Teacher Scoping

- The runtime model does **not** include `students.teacher_id`.
- Teacher ownership lives in `student_teachers`.
- Class membership lives in `class_memberships`.
- Some comments or legacy utilities still refer to older teacher-global assumptions; do not copy that pattern into new code.

---

## Session Checklist

- [ ] Resolve or validate the active `join_code`
- [ ] Use ownership helpers for teacher access
- [ ] Add class membership or route-specific class checks for period-specific reads/writes
- [ ] Include `join_code` on new attendance, ledger, and hall-pass records
- [ ] Use `Student.get_checking_balance()` / `get_savings_balance()` for balances
- [ ] Do not use `teacher_id` alone for student scoping

---

## Tables That Must Be Class-Scoped

- `transactions`
- `tap_events`
- `hall_pass_logs`
- `student_blocks`
- `balance_cache`
- `payroll_settings`
- `rent_settings`
- `rent_payments`
- `rent_waivers`
- `banking_settings`
- `feature_settings`
- `student_items`
- `student_insurance`
- `insurance_claims`

---

**Last Updated:** 2026-03-08
**Critical Incident:** P0 same-teacher multi-period data leak
