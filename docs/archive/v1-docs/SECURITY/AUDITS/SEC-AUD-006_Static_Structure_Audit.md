# Stage 1 Audit Report: Static Structural Analysis

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SEC-AUD-006| 1.1 | 2026-03-08 | 1.0 |Normative|

## Summary
- **Total Findings:** 1953
- **By Severity:**
  - High: 40
  - Medium: 1624
  - Low: 289
- **By Category:**
  - Structural Smell: 971
  - Complexity: 703
  - Dead Code: 265
  - Risk Pattern: 14

## Known Limitations
- **Unused Code Detection:** Uses simple string matching. High false positive rate for public APIs and dynamic calls.
- **Inconsistent Returns:** Does not perform type inference, only checks for presence/absence of return values.
- **Commented-out Code:** Heuristic-based, may miss some blocks or flag documentation.
- **Reachability:** Only checks simple control flow after return/raise/break/continue.
- **Scope:** Excludes tests and migrations.

## Detailed Findings

### Finding #1

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 151 |
| **Confidence** | High |

**Description:** Function `create_app` has cyclomatic complexity of 49.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #2

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 59 |
| **Confidence** | High |

**Description:** Function `login_required` has cyclomatic complexity of 33.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #3

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 68 |
| **Confidence** | High |

**Description:** Function `decorated_function` has cyclomatic complexity of 33.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #4

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1058 |
| **Confidence** | High |

**Description:** Function `signup` has cyclomatic complexity of 31.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #5

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1303 |
| **Confidence** | High |

**Description:** Function `recover` has cyclomatic complexity of 24.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #6

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1849 |
| **Confidence** | High |

**Description:** Function `_build_rent_privileges_by_block` has cyclomatic complexity of 25.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #7

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2073 |
| **Confidence** | High |

**Description:** Function `students` has cyclomatic complexity of 37.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #8

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2431 |
| **Confidence** | High |

**Description:** Function `edit_student` has cyclomatic complexity of 44.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #9

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3320 |
| **Confidence** | High |

**Description:** Function `store_management` has cyclomatic complexity of 53.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #10

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3916 |
| **Confidence** | High |

**Description:** Function `rent_settings` has cyclomatic complexity of 99.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #11

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4531 |
| **Confidence** | High |

**Description:** Function `insurance_management` has cyclomatic complexity of 21.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #12

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4950 |
| **Confidence** | High |

**Description:** Function `process_claim` has cyclomatic complexity of 53.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #13

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5181 |
| **Confidence** | High |

**Description:** Function `void_transaction` has cyclomatic complexity of 57.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #14

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5807 |
| **Confidence** | High |

**Description:** Function `payroll` has cyclomatic complexity of 24.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #15

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6867 |
| **Confidence** | High |

**Description:** Function `upload_students` has cyclomatic complexity of 26.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #16

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1111 |
| **Confidence** | High |

**Description:** Function `handle_hall_pass_action` has cyclomatic complexity of 21.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #17

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2197 |
| **Confidence** | High |

**Description:** Function `handle_tap` has cyclomatic complexity of 49.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #18

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 224 |
| **Confidence** | High |

**Description:** Function `purchase_item` has cyclomatic complexity of 101.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #19

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 773 |
| **Confidence** | High |

**Description:** Function `use_item` has cyclomatic complexity of 30.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #20

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 966 |
| **Confidence** | High |

**Description:** Function `reject_redemption` has cyclomatic complexity of 29.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #21

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 201 |
| **Confidence** | High |

**Description:** Function `view_doc` has cyclomatic complexity of 27.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #22

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 386 |
| **Confidence** | High |

**Description:** Function `search` has cyclomatic complexity of 29.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #23

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1091 |
| **Confidence** | High |

**Description:** Function `dashboard` has cyclomatic complexity of 51.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #24

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1509 |
| **Confidence** | High |

**Description:** Function `transfer` has cyclomatic complexity of 34.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #25

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1702 |
| **Confidence** | High |

**Description:** Function `apply_savings_interest` has cyclomatic complexity of 32.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #26

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1923 |
| **Confidence** | High |

**Description:** Function `purchase_insurance` has cyclomatic complexity of 21.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #27

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2107 |
| **Confidence** | High |

**Description:** Function `file_claim` has cyclomatic complexity of 39.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #28

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2366 |
| **Confidence** | High |

**Description:** Function `shop` has cyclomatic complexity of 29.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #29

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2797 |
| **Confidence** | High |

**Description:** Function `rent` has cyclomatic complexity of 29.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #30

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2987 |
| **Confidence** | High |

**Description:** Function `rent_pay` has cyclomatic complexity of 71.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #31

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3412 |
| **Confidence** | High |

**Description:** Function `login` has cyclomatic complexity of 22.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #32

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 543 |
| **Confidence** | High |

**Description:** Function `claim_account` has cyclomatic complexity of 25.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #33

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 878 |
| **Confidence** | High |

**Description:** Function `add_class` has cyclomatic complexity of 36.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #34

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 10 |
| **Confidence** | High |

**Description:** Function `settle_balances` has cyclomatic complexity of 31.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #35

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./app/utils/overdraft.py` |
| **Line Range** | 37 |
| **Confidence** | High |

**Description:** Function `charge_overdraft_fee_if_needed` has cyclomatic complexity of 21.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #36

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 80 |
| **Confidence** | High |

**Description:** Function `analyze_migrations` has cyclomatic complexity of 35.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #37

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 114 |
| **Confidence** | High |

**Description:** Function `migrate_legacy_students` has cyclomatic complexity of 23.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #38

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 54 |
| **Confidence** | High |

**Description:** Function `inspect_database_schema` has cyclomatic complexity of 24.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #39

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 235 |
| **Confidence** | High |

**Description:** Function `validate_migrations` has cyclomatic complexity of 42.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #40

| Property | Value |
|----------|-------|
| **Severity** | High |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 42 |
| **Confidence** | High |

**Description:** Function `verify_migration_chain` has cyclomatic complexity of 33.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #41

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 151-740 |
| **Confidence** | High |

**Description:** Function `create_app` is 590 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #42

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 303 |
| **Confidence** | High |

**Description:** Function `show_maintenance_page` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #43

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 398 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #44

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 406 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #45

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 440 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #46

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 529 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #47

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 538 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #48

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 556 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #49

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 593 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #50

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 609 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #51

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 636 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:636, ./scripts/add-security-headers.py:16

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #52

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 637 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:637, ./scripts/add-security-headers.py:17

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #53

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 638 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:638, ./scripts/add-security-headers.py:18

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #54

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/__init__.py` |
| **Line Range** | 638-729 |
| **Confidence** | High |

**Description:** Function `set_security_headers` is 92 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #55

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 639 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:639, ./scripts/add-security-headers.py:19

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #56

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 640 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:640, ./scripts/add-security-headers.py:20

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #57

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 641 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:641, ./scripts/add-security-headers.py:21

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #58

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 642 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:642, ./scripts/add-security-headers.py:22

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #59

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 643 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:643, ./scripts/add-security-headers.py:23

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #60

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 644 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:644, ./scripts/add-security-headers.py:24

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #61

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 645 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:645, ./scripts/add-security-headers.py:25

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #62

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 646 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:646, ./scripts/add-security-headers.py:26

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #63

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 647 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:647, ./scripts/add-security-headers.py:27

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #64

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 648 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:648, ./scripts/add-security-headers.py:28

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #65

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 649 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:649, ./scripts/add-security-headers.py:29

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #66

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 663 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:663, ./scripts/add-security-headers.py:34

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #67

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 671 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:671, ./scripts/add-security-headers.py:41

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #68

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 676 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:676, ./scripts/add-security-headers.py:50

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #69

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 677 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:677, ./scripts/add-security-headers.py:51

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #70

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 715 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:715, ./scripts/add-security-headers.py:69

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #71

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 716 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:716, ./scripts/add-security-headers.py:70

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #72

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 717 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:717, ./scripts/add-security-headers.py:71

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #73

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 718 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:718, ./scripts/add-security-headers.py:72

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #74

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 719 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:719, ./scripts/add-security-headers.py:73

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #75

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 720 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:720, ./scripts/add-security-headers.py:74

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #76

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 721 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:721, ./scripts/add-security-headers.py:75

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #77

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 722 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:722, ./scripts/add-security-headers.py:76

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #78

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 723 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:723, ./scripts/add-security-headers.py:77

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #79

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 724 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/__init__.py:724, ./scripts/add-security-headers.py:78

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #80

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 121 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:121, ./app/attendance.py:163

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #81

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 122 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:122, ./app/attendance.py:164

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #82

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 123 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:123, ./app/attendance.py:165

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #83

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 124 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:124, ./app/attendance.py:166

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #84

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 125 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:125, ./app/attendance.py:167

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #85

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 126 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:126, ./app/attendance.py:168

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #86

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 127 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:127, ./app/attendance.py:169

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #87

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 128 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:128, ./app/attendance.py:170

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #88

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 129 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:129, ./app/attendance.py:171

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #89

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 130 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:130, ./app/attendance.py:172

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #90

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 131 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:131, ./app/attendance.py:173

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #91

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 134 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:134, ./app/attendance.py:176

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #92

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 135 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:135, ./app/attendance.py:177

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #93

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/attendance.py` |
| **Line Range** | 136 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #94

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 136 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:136, ./app/attendance.py:178

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #95

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 137 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:137, ./app/attendance.py:179

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #96

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/attendance.py` |
| **Line Range** | 178 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #97

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/attendance.py` |
| **Line Range** | 220-307 |
| **Confidence** | High |

**Description:** Function `get_all_block_statuses` is 88 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #98

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/attendance.py` |
| **Line Range** | 30 |
| **Confidence** | High |

**Description:** Function `calculate_unpaid_attendance_seconds` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #99

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 57 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:57, ./app/attendance.py:132, ./app/attendance.py:174

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #100

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/attendance.py` |
| **Line Range** | 58 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/attendance.py:58, ./app/attendance.py:133, ./app/attendance.py:175

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #101

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/attendance.py` |
| **Line Range** | 59 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #102

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/attendance.py` |
| **Line Range** | 91 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #103

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/attendance.py` |
| **Line Range** | 93 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #104

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 106 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:106, ./app/auth.py:163

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #105

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 107 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:107, ./app/auth.py:164, ./app/auth.py:180

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #106

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 117 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #107

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 126 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #108

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 129 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:129, ./app/auth.py:169, ./app/auth.py:185

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #109

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 130 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:130, ./app/auth.py:186

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #110

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 165 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:165, ./app/auth.py:181

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #111

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 166 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:166, ./app/auth.py:182

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #112

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 167 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:167, ./app/auth.py:183

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #113

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 168 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:168, ./app/auth.py:184

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #114

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 199 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #115

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/auth.py` |
| **Line Range** | 208 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/auth.py:208, ./app/auth.py:220

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #116

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 213 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #117

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 225 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #118

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 238 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #119

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 279 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #120

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 308 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #121

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 59-245 |
| **Confidence** | High |

**Description:** Function `login_required` is 187 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #122

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 68-244 |
| **Confidence** | High |

**Description:** Function `decorated_function` is 177 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #123

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/auth.py` |
| **Line Range** | 72 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #124

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 38 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:38, ./app/routes/admin.py:631

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #125

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 39 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:39, ./app/routes/admin.py:632

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #126

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 40 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:40, ./app/routes/admin.py:633

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #127

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 41 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:41, ./app/routes/admin.py:634

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #128

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 42 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:42, ./app/routes/student.py:596, ./app/routes/student.py:993...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #129

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 43 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:43, ./app/routes/admin.py:636

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #130

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 44 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:44, ./app/routes/admin.py:637

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #131

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 45 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:45, ./app/routes/admin.py:638

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #132

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 46 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:46, ./app/routes/admin.py:639

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #133

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 54 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:54, ./app/routes/admin.py:648

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #134

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 55 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:55, ./app/routes/admin.py:649

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #135

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 56 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:56, ./app/routes/student.py:648, ./app/routes/admin.py:650

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #136

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 57 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:57, ./app/routes/admin.py:651

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #137

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 58 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:58, ./app/routes/admin.py:652

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #138

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 59 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:59, ./app/routes/admin.py:653

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #139

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/cli_commands.py` |
| **Line Range** | 60 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/cli_commands.py:60, ./app/routes/admin.py:654

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #140

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/forms.py` |
| **Line Range** | 375 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/forms.py:375, ./app/forms.py:406

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #141

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/forms.py` |
| **Line Range** | 376 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/forms.py:376, ./app/forms.py:407

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #142

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/forms.py` |
| **Line Range** | 377 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/forms.py:377, ./app/forms.py:408

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #143

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/models.py` |
| **Line Range** | 314 |
| **Confidence** | High |

**Description:** Function `get_checking_balance` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #144

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/models.py` |
| **Line Range** | 314-409 |
| **Confidence** | High |

**Description:** Function `get_checking_balance` is 96 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #145

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 317 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:317, ./app/models.py:414, ./app/models.py:495

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #146

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 318 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:318, ./app/models.py:415, ./app/models.py:496

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #147

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 319 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:319, ./app/models.py:416, ./app/models.py:497

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #148

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 320 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:320, ./app/models.py:417, ./app/models.py:498

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #149

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 327 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:327, ./app/models.py:424

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #150

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 328 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:328, ./app/models.py:425

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #151

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 329 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:329, ./app/models.py:426

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #152

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 330 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:330, ./app/models.py:427

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #153

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 331 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:331, ./app/models.py:428

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #154

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 332 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:332, ./app/models.py:429

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #155

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 333 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:333, ./app/models.py:430

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #156

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 334 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:334, ./app/models.py:431

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #157

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 335 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:335, ./app/models.py:432

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #158

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 336 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:336, ./app/models.py:433

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #159

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 337 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:337, ./app/models.py:434

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #160

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 338 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:338, ./app/models.py:435

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #161

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 339 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:339, ./app/models.py:436

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #162

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 340 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:340, ./app/models.py:437

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #163

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 341 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:341, ./app/models.py:438

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #164

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 342 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:342, ./app/models.py:439

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #165

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 355 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:355, ./app/models.py:452

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #166

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 362 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:362, ./app/models.py:459

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #167

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 363 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:363, ./app/models.py:460

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #168

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 364 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:364, ./app/models.py:461

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #169

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 365 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:365, ./app/models.py:462

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #170

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 372 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:372, ./app/models.py:469

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #171

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 373 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:373, ./app/models.py:470

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #172

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 374 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:374, ./app/models.py:471

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #173

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 375 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:375, ./app/models.py:472

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #174

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 376 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:376, ./app/models.py:473

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #175

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/models.py` |
| **Line Range** | 411 |
| **Confidence** | High |

**Description:** Function `get_savings_balance` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #176

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/models.py` |
| **Line Range** | 411-490 |
| **Confidence** | High |

**Description:** Function `get_savings_balance` is 80 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #177

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/models.py` |
| **Line Range** | 42 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #178

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/models.py` |
| **Line Range** | 47 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #179

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/models.py` |
| **Line Range** | 492 |
| **Confidence** | High |

**Description:** Function `get_total_earnings` has cyclomatic complexity of 17.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #180

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 676 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:676, ./app/models.py:1642

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #181

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 677 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:677, ./app/models.py:1643

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #182

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 678 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:678, ./app/models.py:1644

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #183

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 679 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:679, ./app/models.py:1645

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #184

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 680 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:680, ./app/models.py:1646

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #185

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/models.py` |
| **Line Range** | 963 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/models.py:963, ./app/models.py:1255

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #186

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 100 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #187

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 104 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:104, ./app/payroll.py:123

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #188

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 122 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #189

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 137 |
| **Confidence** | High |

**Description:** Function `calculate_payroll_breakdown` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #190

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 137-227 |
| **Confidence** | High |

**Description:** Function `calculate_payroll_breakdown` is 91 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #191

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 188 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #192

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 191 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #193

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 210 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #194

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 221 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #195

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 285-370 |
| **Confidence** | High |

**Description:** Function `_get_batch_attendance_events` is 86 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #196

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 33 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:33, ./app/payroll.py:77

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #197

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 34 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:34, ./app/payroll.py:78

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #198

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 35 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:35, ./app/payroll.py:79

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #199

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 352 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #200

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 372 |
| **Confidence** | High |

**Description:** Function `_calculate_seconds_in_memory` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #201

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 391 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #202

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 403 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #203

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 405 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #204

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 435 |
| **Confidence** | High |

**Description:** Function `get_cached_payroll_with_meta` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #205

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 435-517 |
| **Confidence** | High |

**Description:** Function `get_cached_payroll_with_meta` is 83 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #206

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 48 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:48, ./app/payroll.py:90

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #207

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 481 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #208

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 49 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:49, ./app/payroll.py:91

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #209

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 50 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:50, ./app/payroll.py:92

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #210

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 59 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:59, ./app/payroll.py:112

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #211

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/payroll.py` |
| **Line Range** | 60 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/payroll.py:60, ./app/payroll.py:113

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #212

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/payroll.py` |
| **Line Range** | 74 |
| **Confidence** | High |

**Description:** Function `get_daily_limit_seconds` has cyclomatic complexity of 13.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #213

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1029 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #214

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1058-1298 |
| **Confidence** | High |

**Description:** Function `signup` is 241 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #215

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1090 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #216

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1106 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #217

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1113 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #218

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1133 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #219

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1140 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #220

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1146 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #221

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1154 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #222

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1165 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #223

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1184 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1184, ./app/routes/admin.py:1213

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #224

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1185 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1185, ./app/routes/admin.py:1214

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #225

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1186 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1186, ./app/routes/admin.py:1215

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #226

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1187 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1187, ./app/routes/admin.py:1216

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #227

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1188 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1188, ./app/routes/admin.py:1217

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #228

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1189 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1189, ./app/routes/admin.py:1218, ./app/routes/admin.py:1254

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #229

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1190 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1190, ./app/routes/admin.py:1219, ./app/routes/admin.py:1255

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #230

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1191 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1191, ./app/routes/admin.py:1220, ./app/routes/admin.py:1256

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #231

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1192 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1192, ./app/routes/admin.py:1221, ./app/routes/admin.py:1257

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #232

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1193 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1193, ./app/routes/admin.py:1222

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #233

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1194 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1194, ./app/routes/admin.py:1223

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #234

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1208 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #235

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1211 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1211, ./app/routes/admin.py:1246

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #236

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1212 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1212, ./app/routes/admin.py:1247

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #237

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1242 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #238

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1248 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1248, ./app/routes/admin.py:1580

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #239

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 129 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #240

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1303-1458 |
| **Confidence** | High |

**Description:** Function `recover` is 156 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #241

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1316 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #242

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1336 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #243

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1339 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #244

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1358 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #245

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 136 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #246

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1398 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #247

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1404 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #248

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1465 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1465, ./app/routes/admin.py:1511, ./app/routes/admin.py:1680

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #249

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1466 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1466, ./app/routes/admin.py:1512, ./app/routes/admin.py:1681

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #250

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1506 |
| **Confidence** | High |

**Description:** Function `reset_credentials` has cyclomatic complexity of 15.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #251

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1506-1605 |
| **Confidence** | High |

**Description:** Function `reset_credentials` is 100 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #252

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1513 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1513, ./app/routes/admin.py:1682

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #253

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1514 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1514, ./app/routes/admin.py:1683

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #254

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1515 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1515, ./app/routes/admin.py:1684

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #255

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1516 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:1516, ./app/routes/admin.py:1685

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #256

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1551 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #257

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1849-1990 |
| **Confidence** | High |

**Description:** Function `_build_rent_privileges_by_block` is 142 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #258

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1972 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #259

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1986 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #260

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1993 |
| **Confidence** | High |

**Description:** Function `_get_rent_privileges_for_student` has cyclomatic complexity of 13.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #261

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2056 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #262

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2073-2262 |
| **Confidence** | High |

**Description:** Function `students` is 190 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #263

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2096 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #264

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2148 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #265

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2159 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #266

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2174 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #267

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2196 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #268

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2202 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2202, ./app/routes/admin.py:6924

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #269

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2238 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2238, ./app/routes/admin.py:6933

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #270

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2248 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #271

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2288 |
| **Confidence** | High |

**Description:** Function `student_detail` has cyclomatic complexity of 19.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #272

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2288-2409 |
| **Confidence** | High |

**Description:** Function `student_detail` is 122 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #273

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2384 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #274

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2431-2678 |
| **Confidence** | High |

**Description:** Function `edit_student` is 248 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #275

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2478 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #276

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2487 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #277

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 258-419 |
| **Confidence** | High |

**Description:** Function `_hard_delete_join_code_scope` is 162 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #278

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2614 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #279

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2616 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2616, ./app/routes/admin.py:3107, ./app/routes/admin.py:3273

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #280

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2617 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2617, ./app/routes/admin.py:3108, ./app/routes/admin.py:3274

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #281

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2618 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2618, ./app/routes/admin.py:3109, ./app/routes/admin.py:3275

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #282

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2619 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2619, ./app/routes/admin.py:3110, ./app/routes/admin.py:3276

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #283

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2620 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2620, ./app/routes/admin.py:3111, ./app/routes/admin.py:3277

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #284

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2621 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2621, ./app/routes/admin.py:3112, ./app/routes/admin.py:3278

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #285

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2622 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2622, ./app/routes/admin.py:3113, ./app/routes/admin.py:3279

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #286

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2623 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2623, ./app/routes/admin.py:3114, ./app/routes/admin.py:3280

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #287

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2624 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2624, ./app/routes/admin.py:3115, ./app/routes/admin.py:3281

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #288

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2632 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #289

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2667 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #290

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2736 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #291

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2917 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #292

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2934 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2934, ./app/routes/admin.py:2981

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #293

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2935 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2935, ./app/routes/admin.py:2982

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #294

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2936 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:2936, ./app/routes/admin.py:2983

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #295

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2995 |
| **Confidence** | High |

**Description:** Function `add_individual_student` has cyclomatic complexity of 15.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #296

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2995-3143 |
| **Confidence** | High |

**Description:** Function `add_individual_student` is 149 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #297

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3005 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3005, ./app/routes/admin.py:3166

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #298

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3006 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3006, ./app/routes/admin.py:3167

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #299

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3007 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3007, ./app/routes/admin.py:3168

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #300

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3008 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3008, ./app/routes/admin.py:3169

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #301

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3009 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3009, ./app/routes/admin.py:3170

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #302

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3010 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3010, ./app/routes/admin.py:3171

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #303

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3011 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3011, ./app/routes/admin.py:3172

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #304

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3012 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3012, ./app/routes/admin.py:3173

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #305

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3013 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3013, ./app/routes/admin.py:3174

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #306

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3014 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3014, ./app/routes/admin.py:3175

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #307

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3015 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3015, ./app/routes/admin.py:3176

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #308

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3016 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3016, ./app/routes/admin.py:3177

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #309

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3017 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3017, ./app/routes/admin.py:3178, ./app/routes/admin.py:6979

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #310

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3018 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3018, ./app/routes/admin.py:3179

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #311

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3019 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3019, ./app/routes/admin.py:3180

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #312

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3020 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3020, ./app/routes/admin.py:3181

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #313

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3021 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3021, ./app/routes/admin.py:3182

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #314

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3022 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3022, ./app/routes/admin.py:3183

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #315

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3037 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #316

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3039 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3039, ./app/routes/admin.py:3198

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #317

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3040 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3040, ./app/routes/admin.py:3199

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #318

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3041 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3041, ./app/routes/admin.py:3200

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #319

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3042 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3042, ./app/routes/admin.py:3201

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #320

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3043 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3043, ./app/routes/admin.py:3202

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #321

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3044 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3044, ./app/routes/admin.py:3203

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #322

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3045 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3045, ./app/routes/admin.py:3204

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #323

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3046 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3046, ./app/routes/admin.py:3205

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #324

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3047 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3047, ./app/routes/admin.py:3206

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #325

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3048 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3048, ./app/routes/admin.py:3207

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #326

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3049 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3049, ./app/routes/admin.py:3208

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #327

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3050 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3050, ./app/routes/admin.py:3209

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #328

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3082 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3082, ./app/routes/admin.py:3232

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #329

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3083 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3083, ./app/routes/admin.py:3233

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #330

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3084 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3084, ./app/routes/admin.py:3234

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #331

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3085 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3085, ./app/routes/admin.py:3235

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #332

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3094 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3094, ./app/routes/admin.py:3260

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #333

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3095 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3095, ./app/routes/admin.py:3261

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #334

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3096 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3096, ./app/routes/admin.py:3262

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #335

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3097 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3097, ./app/routes/admin.py:3263

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #336

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3098 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3098, ./app/routes/admin.py:3264

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #337

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3099 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3099, ./app/routes/admin.py:3265

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #338

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3100 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3100, ./app/routes/admin.py:3266

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #339

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3101 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3101, ./app/routes/admin.py:3267

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #340

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3102 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3102, ./app/routes/admin.py:3268

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #341

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3103 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3103, ./app/routes/admin.py:3269

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #342

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3104 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3104, ./app/routes/admin.py:3270

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #343

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3105 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3105, ./app/routes/admin.py:3271

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #344

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3106 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3106, ./app/routes/admin.py:3272

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #345

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3110 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #346

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3120 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3120, ./app/routes/admin.py:3289

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #347

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3121 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3121, ./app/routes/admin.py:3290

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #348

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3122 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3122, ./app/routes/admin.py:3291

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #349

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3123 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3123, ./app/routes/admin.py:3292, ./app/routes/admin.py:6992

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #350

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3124 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3124, ./app/routes/admin.py:3293, ./app/routes/admin.py:6993

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #351

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3125 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3125, ./app/routes/admin.py:3294, ./app/routes/admin.py:6994

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #352

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3133 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3133, ./app/routes/admin.py:3303

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #353

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3134 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3134, ./app/routes/admin.py:3304

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #354

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3148 |
| **Confidence** | High |

**Description:** Function `add_manual_student` has cyclomatic complexity of 18.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #355

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3148-3313 |
| **Confidence** | High |

**Description:** Function `add_manual_student` is 166 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #356

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3196 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #357

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3276 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #358

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3320-3651 |
| **Confidence** | High |

**Description:** Function `store_management` is 332 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #359

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3432 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #360

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3460 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #361

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3469 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #362

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3548 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #363

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3561 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #364

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3589 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #365

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3593 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #366

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3596 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #367

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3600 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #368

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3661 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3661, ./app/routes/admin.py:4733

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #369

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3662 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3662, ./app/routes/admin.py:4734

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #370

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3687 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3687, ./app/routes/admin.py:3706

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #371

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3688 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3688, ./app/routes/admin.py:3707

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #372

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3737 |
| **Confidence** | High |

**Description:** Function `_sync_rent_items_to_store` has cyclomatic complexity of 19.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #373

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3737-3859 |
| **Confidence** | High |

**Description:** Function `_sync_rent_items_to_store` is 123 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #374

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3760 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #375

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3779 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #376

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3785 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #377

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3797 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #378

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3830 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #379

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3840 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #380

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3895 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #381

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3907 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #382

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3916-4409 |
| **Confidence** | High |

**Description:** Function `rent_settings` is 494 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #383

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3921 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3921, ./app/routes/admin.py:4535, ./app/routes/admin.py:7521

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #384

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3922 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3922, ./app/routes/admin.py:4536

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #385

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3923 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3923, ./app/routes/admin.py:4537

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #386

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3924 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3924, ./app/routes/admin.py:4538

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #387

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3925 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:3925, ./app/routes/admin.py:4539

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #388

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3950 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #389

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3958 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #390

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3970 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #391

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3979 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #392

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3991 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #393

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4008 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #394

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4015 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #395

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4019 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #396

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4026 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #397

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4032 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #398

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4039 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #399

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4060 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #400

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4086 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #401

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4094 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #402

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4104 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #403

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4122 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #404

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4170 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #405

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4184 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #406

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4239 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #407

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4279 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #408

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4281 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #409

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4288 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #410

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4299 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #411

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4303 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #412

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4307 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #413

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4310 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #414

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4330 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #415

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4343 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #416

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4371 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #417

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4414 |
| **Confidence** | High |

**Description:** Function `add_rent_waiver` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #418

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4440 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #419

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4531-4719 |
| **Confidence** | High |

**Description:** Function `insurance_management` is 189 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #420

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4595 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #421

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4621 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #422

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4726 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:4726, ./app/routes/admin.py:4794, ./app/routes/admin.py:4815...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #423

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4747 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #424

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4950-5166 |
| **Confidence** | High |

**Description:** Function `process_claim` is 217 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #425

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4968 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #426

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5101 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #427

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5108 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #428

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5111 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #429

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5114 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #430

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5130 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #431

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5150 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #432

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5181-5423 |
| **Confidence** | High |

**Description:** Function `void_transaction` is 243 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #433

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5200 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5200, ./app/routes/admin.py:6460

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #434

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5201 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5201, ./app/routes/admin.py:6461

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #435

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5218 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #436

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5229 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #437

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5232 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #438

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5235 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #439

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5242 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #440

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5247 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #441

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5252 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #442

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5261 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #443

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5267 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #444

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5271 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #445

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5285 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #446

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5291 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5291, ./app/routes/admin.py:5325, ./app/routes/admin.py:5372

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #447

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5292 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5292, ./app/routes/admin.py:5326, ./app/routes/admin.py:5373

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #448

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5293 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5293, ./app/routes/admin.py:5327, ./app/routes/admin.py:5374

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #449

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5294 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5294, ./app/routes/admin.py:5328, ./app/routes/admin.py:5375

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #450

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5295 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5295, ./app/routes/admin.py:5329, ./app/routes/admin.py:5376

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #451

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5296 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5296, ./app/routes/admin.py:5330, ./app/routes/admin.py:5377...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #452

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5297 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5297, ./app/routes/admin.py:5331, ./app/routes/admin.py:5378...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #453

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5298 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5298, ./app/routes/admin.py:5332, ./app/routes/admin.py:5379...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #454

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5299 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5299, ./app/routes/admin.py:5333, ./app/routes/admin.py:5380...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #455

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5300 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5300, ./app/routes/admin.py:5334, ./app/routes/admin.py:5381...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #456

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5306 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #457

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5323 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5323, ./app/routes/admin.py:5370

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #458

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5324 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5324, ./app/routes/admin.py:5371

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #459

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5490 |
| **Confidence** | High |

**Description:** Function `economy_health` has cyclomatic complexity of 20.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #460

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5490-5649 |
| **Confidence** | High |

**Description:** Function `economy_health` is 160 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #461

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5574 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #462

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5599 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:5599, ./app/routes/admin.py:8860

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #463

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5749 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #464

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5807-6065 |
| **Confidence** | High |

**Description:** Function `payroll` is 259 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #465

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5861 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #466

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6070 |
| **Confidence** | High |

**Description:** Function `payroll_settings` has cyclomatic complexity of 13.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #467

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6070-6236 |
| **Confidence** | High |

**Description:** Function `payroll_settings` is 167 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #468

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 613 |
| **Confidence** | High |

**Description:** Function `_normalize_claim_credentials_for_admin` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #469

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6162 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #470

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6214 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #471

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6218 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #472

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6259 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #473

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6265 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6265, ./app/routes/admin.py:6287

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #474

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6266 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6266, ./app/routes/admin.py:6288

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #475

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6267 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6267, ./app/routes/admin.py:6289

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #476

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6268 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6268, ./app/routes/admin.py:6290

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #477

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6282 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #478

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6328 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6328, ./app/routes/admin.py:6373

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #479

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6341 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6341, ./app/routes/admin.py:6386, ./app/routes/admin.py:6822

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #480

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6472 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6472, ./app/routes/admin.py:6527

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #481

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6473 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6473, ./app/routes/admin.py:6528

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #482

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6474 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6474, ./app/routes/admin.py:6529

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #483

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6475 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6475, ./app/routes/admin.py:6530

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #484

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6476 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6476, ./app/routes/admin.py:6531

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #485

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6477 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6477, ./app/routes/admin.py:6532

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #486

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6478 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6478, ./app/routes/admin.py:6533

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #487

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6479 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6479, ./app/routes/admin.py:6534

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #488

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6480 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6480, ./app/routes/admin.py:6535

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #489

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6481 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6481, ./app/routes/admin.py:6536

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #490

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6482 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6482, ./app/routes/admin.py:6537

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #491

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6483 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6483, ./app/routes/admin.py:6538

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #492

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6484 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6484, ./app/routes/admin.py:6539

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #493

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6485 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6485, ./app/routes/admin.py:6540

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #494

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6486 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6486, ./app/routes/admin.py:6541

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #495

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6525 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #496

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6569 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6569, ./app/routes/admin.py:6618

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #497

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6570 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6570, ./app/routes/admin.py:6619

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #498

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6578 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6578, ./app/routes/admin.py:6630, ./app/routes/admin.py:6739

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #499

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6579 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6579, ./app/routes/admin.py:6631, ./app/routes/admin.py:6740

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #500

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6580 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #501

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6580 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6580, ./app/routes/admin.py:6632, ./app/routes/admin.py:6741

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #502

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6581 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6581, ./app/routes/admin.py:6633, ./app/routes/admin.py:6742

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #503

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6582 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6582, ./app/routes/admin.py:6634, ./app/routes/admin.py:6743

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #504

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6583 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6583, ./app/routes/admin.py:6635, ./app/routes/admin.py:6744

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #505

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6584 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6584, ./app/routes/admin.py:6636, ./app/routes/admin.py:6745

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #506

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6614-6710 |
| **Confidence** | High |

**Description:** Function `payroll_apply_fine` is 97 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #507

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6627 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6627, ./app/routes/admin.py:6736

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #508

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6628 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6628, ./app/routes/admin.py:6737

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #509

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6629 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6629, ./app/routes/admin.py:6738

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #510

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6632 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #511

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6657 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6657, ./app/routes/admin.py:6768

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #512

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6658 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6658, ./app/routes/admin.py:6769

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #513

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6659 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6659, ./app/routes/admin.py:6770

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #514

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6660 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:6660, ./app/routes/admin.py:6771

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #515

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6715 |
| **Confidence** | High |

**Description:** Function `payroll_manual_payment` has cyclomatic complexity of 15.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #516

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6715-6825 |
| **Confidence** | High |

**Description:** Function `payroll_manual_payment` is 111 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #517

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6723 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #518

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6739 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #519

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6813 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #520

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6815 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #521

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6867-7033 |
| **Confidence** | High |

**Description:** Function `upload_students` is 167 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #522

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 687 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #523

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6904 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #524

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6912 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #525

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6952 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #526

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6971 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #527

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6976 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #528

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7023 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #529

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7078 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #530

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7133 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #531

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 715-894 |
| **Confidence** | High |

**Description:** Function `dashboard` is 180 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #532

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7187 |
| **Confidence** | High |

**Description:** Function `tap_out_students` has cyclomatic complexity of 19.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #533

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7187-7329 |
| **Confidence** | High |

**Description:** Function `tap_out_students` is 143 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #534

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7217 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #535

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7220 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7220, ./app/routes/admin.py:7248, ./app/routes/admin.py:7369

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #536

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7221 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7221, ./app/routes/admin.py:7249, ./app/routes/admin.py:7370

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #537

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7222 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7222, ./app/routes/admin.py:7250, ./app/routes/admin.py:7371

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #538

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7223 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7223, ./app/routes/admin.py:7251, ./app/routes/admin.py:7372

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #539

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7224 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7224, ./app/routes/admin.py:7252, ./app/routes/admin.py:7373

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #540

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7225 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7225, ./app/routes/admin.py:7253, ./app/routes/admin.py:7374

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #541

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7226 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7226, ./app/routes/admin.py:7254, ./app/routes/admin.py:7375

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #542

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7227 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7227, ./app/routes/admin.py:7255, ./app/routes/admin.py:7376

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #543

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7228 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7228, ./app/routes/admin.py:7377

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #544

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7236 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7236, ./app/routes/admin.py:7357, ./app/routes/admin.py:7462

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #545

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7237 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7237, ./app/routes/admin.py:7358, ./app/routes/admin.py:7463

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #546

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7238 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7238, ./app/routes/admin.py:7359, ./app/routes/admin.py:7464

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #547

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7239 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7239, ./app/routes/admin.py:7360

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #548

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7240 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #549

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7240 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7240, ./app/routes/admin.py:7361

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #550

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7241 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7241, ./app/routes/admin.py:7362

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #551

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7242 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7242, ./app/routes/admin.py:7363

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #552

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7243 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7243, ./app/routes/admin.py:7364

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #553

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7244 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7244, ./app/routes/admin.py:7365

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #554

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7245 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7245, ./app/routes/admin.py:7366

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #555

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7246 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #556

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7246 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7246, ./app/routes/admin.py:7367

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #557

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7247 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7247, ./app/routes/admin.py:7368

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #558

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7261 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #559

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7283 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #560

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7312 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7312, ./app/routes/admin.py:7411

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #561

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7334 |
| **Confidence** | High |

**Description:** Function `tap_in_students` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #562

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7334-7428 |
| **Confidence** | High |

**Description:** Function `tap_in_students` is 95 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #563

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7355 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7355, ./app/routes/admin.py:7460

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #564

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7356 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7356, ./app/routes/admin.py:7461

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #565

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7361 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #566

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7367 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #567

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7382 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #568

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7433 |
| **Confidence** | High |

**Description:** Function `bulk_update_hall_passes` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #569

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7433-7511 |
| **Confidence** | High |

**Description:** Function `bulk_update_hall_passes` is 79 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #570

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7466 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #571

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7471 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #572

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7518 |
| **Confidence** | High |

**Description:** Function `banking` has cyclomatic complexity of 19.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #573

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7518-7704 |
| **Confidence** | High |

**Description:** Function `banking` is 187 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #574

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7591 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #575

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7709 |
| **Confidence** | High |

**Description:** Function `banking_settings_update` has cyclomatic complexity of 17.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #576

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7725 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #577

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7749 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #578

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7760 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #579

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7772-7874 |
| **Confidence** | High |

**Description:** Function `deletion_requests` is 103 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #580

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7795 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #581

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7800 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #582

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7883 |
| **Confidence** | High |

**Description:** Unreachable code detected after return/raise/break/continue.

**Why This Matters:** Unreachable code clutters the codebase and may indicate logic errors.

### Finding #583

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7944 |
| **Confidence** | High |

**Description:** Function `feature_settings` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #584

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7944-8079 |
| **Confidence** | High |

**Description:** Function `feature_settings` is 136 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #585

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7978 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #586

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7980 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7980, ./app/routes/admin.py:8043

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #587

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7981 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7981, ./app/routes/admin.py:8044

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #588

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7982 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:7982, ./app/routes/admin.py:8045

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #589

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8003 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8003, ./app/routes/admin.py:8024

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #590

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8004 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8004, ./app/routes/admin.py:8025

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #591

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8113 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #592

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8137 |
| **Confidence** | High |

**Description:** Function `copy_feature_settings` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #593

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8137-8216 |
| **Confidence** | High |

**Description:** Function `copy_feature_settings` is 80 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #594

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8182 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #595

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8190 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #596

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8195 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #597

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8230 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8230, ./app/routes/admin.py:8287

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #598

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8231 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8231, ./app/routes/admin.py:8288

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #599

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8232 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8232, ./app/routes/admin.py:8289

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #600

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8233 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8233, ./app/routes/admin.py:8290

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #601

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8234 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8234, ./app/routes/admin.py:8291

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #602

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8235 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8235, ./app/routes/admin.py:8292

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #603

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8236 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8236, ./app/routes/admin.py:8293

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #604

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8237 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8237, ./app/routes/admin.py:8294

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #605

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8238 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8238, ./app/routes/admin.py:8295

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #606

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8239 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8239, ./app/routes/admin.py:8296

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #607

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8240 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8240, ./app/routes/admin.py:8297

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #608

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8320 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #609

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8335 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #610

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8360 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8360, ./app/routes/admin.py:8416, ./app/routes/admin.py:8449

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #611

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8361 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8361, ./app/routes/admin.py:8417, ./app/routes/admin.py:8450

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #612

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8362 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8362, ./app/routes/admin.py:8418, ./app/routes/admin.py:8451

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #613

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8363 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8363, ./app/routes/admin.py:8419, ./app/routes/admin.py:8452

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #614

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8364 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8364, ./app/routes/admin.py:8420, ./app/routes/admin.py:8453

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #615

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8365 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8365, ./app/routes/admin.py:8421, ./app/routes/admin.py:8454

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #616

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8366 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8366, ./app/routes/admin.py:8422

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #617

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8367 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8367, ./app/routes/admin.py:8423

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #618

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8368 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8368, ./app/routes/admin.py:8424

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #619

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8483 |
| **Confidence** | High |

**Description:** Function `onboarding_status` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #620

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8483-8603 |
| **Confidence** | High |

**Description:** Function `onboarding_status` is 121 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #621

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8510 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #622

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8545 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #623

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8649 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8649, ./app/routes/admin.py:8678

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #624

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8792-8905 |
| **Confidence** | High |

**Description:** Function `api_economy_analyze` is 114 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #625

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8807 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8807, ./app/routes/admin.py:8939

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #626

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8808 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8808, ./app/routes/admin.py:8940

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #627

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8809 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8809, ./app/routes/admin.py:8941

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #628

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8810 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8810, ./app/routes/admin.py:8942

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #629

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8811 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8811, ./app/routes/admin.py:8943

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #630

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8812 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8812, ./app/routes/admin.py:8944

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #631

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8813 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8813, ./app/routes/admin.py:8945

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #632

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8814 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8814, ./app/routes/admin.py:8946

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #633

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8815 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:8815, ./app/routes/admin.py:8947

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #634

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8910-9013 |
| **Confidence** | High |

**Description:** Function `api_economy_validate` is 104 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #635

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 899-1008 |
| **Confidence** | High |

**Description:** Function `give_bonus_all` is 110 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #636

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9167 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #637

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9301 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:9301, ./app/routes/admin.py:9330, ./app/routes/admin.py:9405

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #638

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9344 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #639

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9359 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #640

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 944 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:944, ./app/routes/admin.py:6753

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #641

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 945 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:945, ./app/routes/admin.py:6754

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #642

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 946 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:946, ./app/routes/admin.py:6755

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #643

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 947 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:947, ./app/routes/admin.py:6645, ./app/routes/admin.py:6756

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #644

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 948 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:948, ./app/routes/admin.py:6646, ./app/routes/admin.py:6757

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #645

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 949 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:949, ./app/routes/admin.py:6647, ./app/routes/admin.py:6758

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #646

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 950 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:950, ./app/routes/admin.py:6648, ./app/routes/admin.py:6759

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #647

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 951 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #648

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 951 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:951, ./app/routes/admin.py:6649, ./app/routes/admin.py:6760

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #649

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 952 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:952, ./app/routes/admin.py:6650, ./app/routes/admin.py:6761

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #650

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 953 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:953, ./app/routes/admin.py:6651, ./app/routes/admin.py:6762

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #651

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 954 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:954, ./app/routes/admin.py:6652, ./app/routes/admin.py:6763

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #652

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 955 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:955, ./app/routes/admin.py:6653, ./app/routes/admin.py:6764

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #653

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 956 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:956, ./app/routes/admin.py:6654, ./app/routes/admin.py:6765

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #654

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 957 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:957, ./app/routes/admin.py:6655, ./app/routes/admin.py:6766

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #655

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 958 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:958, ./app/routes/admin.py:6656, ./app/routes/admin.py:6767

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #656

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 978 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:978, ./app/routes/admin.py:6677, ./app/routes/admin.py:6788

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #657

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 979 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:979, ./app/routes/admin.py:6678, ./app/routes/admin.py:6789

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #658

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 980 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:980, ./app/routes/admin.py:6679, ./app/routes/admin.py:6790

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #659

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 981 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:981, ./app/routes/admin.py:6680, ./app/routes/admin.py:6791

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #660

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 982 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:982, ./app/routes/admin.py:6681, ./app/routes/admin.py:6792

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #661

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 985 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:985, ./app/routes/admin.py:6684, ./app/routes/admin.py:6795

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #662

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 986 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:986, ./app/routes/admin.py:6685, ./app/routes/admin.py:6796

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #663

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 987 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:987, ./app/routes/admin.py:6686, ./app/routes/admin.py:6797

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #664

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 988 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:988, ./app/routes/admin.py:6687, ./app/routes/admin.py:6798

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #665

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 989 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:989, ./app/routes/admin.py:6688, ./app/routes/admin.py:6799

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #666

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 990 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:990, ./app/routes/admin.py:6689, ./app/routes/admin.py:6800

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #667

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 991 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:991, ./app/routes/admin.py:6690, ./app/routes/admin.py:6801

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #668

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 992 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/admin.py:992, ./app/routes/admin.py:6691, ./app/routes/admin.py:6802

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #669

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 120 |
| **Confidence** | High |

**Description:** Function `get_rent_cycle_days` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #670

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 180 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #671

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 212 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:212, ./app/routes/analytics.py:418, ./app/routes/analytics.py:462

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #672

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 213 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:213, ./app/routes/analytics.py:419, ./app/routes/analytics.py:463

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #673

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 214 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:214, ./app/routes/analytics.py:420, ./app/routes/analytics.py:464

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #674

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 223 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:223, ./app/routes/analytics.py:291

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #675

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 224 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:224, ./app/routes/analytics.py:292

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #676

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 234 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:234, ./app/routes/analytics.py:355

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #677

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 235 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/analytics.py:235, ./app/routes/analytics.py:356

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #678

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 454 |
| **Confidence** | High |

**Description:** Function `student_drill_down` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #679

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 454-570 |
| **Confidence** | High |

**Description:** Function `student_drill_down` is 117 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #680

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 83 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #681

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1011 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #682

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1029 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #683

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1036 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #684

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1056 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #685

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1111-1211 |
| **Confidence** | High |

**Description:** Function `handle_hall_pass_action` is 101 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #686

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 113 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #687

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1133 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #688

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1149 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #689

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 115 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #690

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1158 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #691

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1165 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #692

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1173 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #693

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1180 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1180, ./app/routes/api.py:1443, ./app/routes/api.py:1567

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #694

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1215-1300 |
| **Confidence** | High |

**Description:** Function `get_active_hall_passes` is 86 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #695

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1237 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1237, ./app/routes/api.py:1664

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #696

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1238 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1238, ./app/routes/api.py:1665

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #697

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1239 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1239, ./app/routes/api.py:1666

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #698

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1240 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1240, ./app/routes/api.py:1667

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #699

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1241 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1241, ./app/routes/api.py:1668

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #700

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1242 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1242, ./app/routes/api.py:1669

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #701

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1243 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1243, ./app/routes/api.py:1670

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #702

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1244 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1244, ./app/routes/api.py:1671

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #703

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1245 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1245, ./app/routes/api.py:1672

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #704

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1246 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1246, ./app/routes/api.py:1673

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #705

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1247 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #706

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1247 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1247, ./app/routes/api.py:1674

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #707

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1255 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1255, ./app/routes/api.py:1707

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #708

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1315 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1315, ./app/routes/api.py:1740

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #709

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1316 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1316, ./app/routes/api.py:1741

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #710

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1417 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1417, ./app/routes/api.py:1468

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #711

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1418 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1418, ./app/routes/api.py:1469

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #712

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1419 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1419, ./app/routes/api.py:1470

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #713

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1420 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1420, ./app/routes/api.py:1471

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #714

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1421 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1421, ./app/routes/api.py:1472

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #715

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1422 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1422, ./app/routes/api.py:1473

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #716

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1428 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1428, ./app/routes/api.py:1552

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #717

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1429 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1429, ./app/routes/api.py:1553

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #718

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1430 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1430, ./app/routes/api.py:1554

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #719

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1431 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1431, ./app/routes/api.py:1555

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #720

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1432 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1432, ./app/routes/api.py:1556

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #721

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1433 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1433, ./app/routes/api.py:1557

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #722

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1434 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1434, ./app/routes/api.py:1558

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #723

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1435 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1435, ./app/routes/api.py:1559

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #724

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1436 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1436, ./app/routes/api.py:1560

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #725

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1437 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1437, ./app/routes/api.py:1561

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #726

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1438 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1438, ./app/routes/api.py:1562

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #727

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1439 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1439, ./app/routes/api.py:1563

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #728

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1440 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1440, ./app/routes/api.py:1564

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #729

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1441 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1441, ./app/routes/api.py:1565

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #730

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1442 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1442, ./app/routes/api.py:1566

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #731

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1444 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1444, ./app/routes/api.py:1568

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #732

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1445 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1445, ./app/routes/api.py:1569

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #733

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1446 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1446, ./app/routes/api.py:1570

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #734

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1447 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1447, ./app/routes/api.py:1571

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #735

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1448 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1448, ./app/routes/api.py:1572

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #736

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1449 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1449, ./app/routes/api.py:1573

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #737

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1481 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1481, ./app/routes/api.py:1609

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #738

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1482 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1482, ./app/routes/api.py:1610

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #739

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1483 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1483, ./app/routes/api.py:1611

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #740

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1484 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1484, ./app/routes/api.py:1612

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #741

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1485 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1485, ./app/routes/api.py:1613

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #742

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1486 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1486, ./app/routes/api.py:1614

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #743

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1487 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1487, ./app/routes/api.py:1615

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #744

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1488 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1488, ./app/routes/api.py:1616

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #745

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1489 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1489, ./app/routes/api.py:1617

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #746

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1490 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1490, ./app/routes/api.py:1618

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #747

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1491 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1491, ./app/routes/api.py:1619

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #748

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1492 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1492, ./app/routes/api.py:1620

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #749

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1493 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1493, ./app/routes/api.py:1621

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #750

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1494 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1494, ./app/routes/api.py:1622

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #751

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1495 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1495, ./app/routes/api.py:1623

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #752

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1496 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1496, ./app/routes/api.py:1624

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #753

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1516 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1516, ./app/routes/api.py:1545, ./app/routes/api.py:1600

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #754

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1538 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1538, ./app/routes/api.py:1593

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #755

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1539 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1539, ./app/routes/api.py:1594

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #756

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1540 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1540, ./app/routes/api.py:1595

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #757

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1541 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1541, ./app/routes/api.py:1596

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #758

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1542 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1542, ./app/routes/api.py:1597

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #759

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1543 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1543, ./app/routes/api.py:1598

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #760

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1544 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1544, ./app/routes/api.py:1599

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #761

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1640 |
| **Confidence** | High |

**Description:** Function `get_hall_pass_queue` has cyclomatic complexity of 13.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #762

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1640-1765 |
| **Confidence** | High |

**Description:** Function `get_hall_pass_queue` is 126 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #763

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1778 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1778, ./app/routes/api.py:2314

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #764

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1779 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1779, ./app/routes/api.py:2315

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #765

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1780 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1780, ./app/routes/api.py:2316

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #766

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1781 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1781, ./app/routes/api.py:2317

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #767

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1782 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1782, ./app/routes/api.py:2318

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #768

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1783 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1783, ./app/routes/api.py:2319

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #769

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1792 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1792, ./app/routes/api.py:1816

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #770

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1825 |
| **Confidence** | High |

**Description:** Function `hall_pass_history` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #771

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1825-1929 |
| **Confidence** | High |

**Description:** Function `hall_pass_history` is 105 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #772

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1835 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1835, ./app/routes/api.py:2075

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #773

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1836 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1836, ./app/routes/api.py:2076

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #774

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1861 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1861, ./app/routes/api.py:2096

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #775

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1863 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #776

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1868 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1868, ./app/routes/api.py:2103

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #777

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1869 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1869, ./app/routes/api.py:2104

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #778

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1870 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1870, ./app/routes/api.py:2105

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #779

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1872 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #780

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1882 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1882, ./app/routes/api.py:2123

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #781

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1883 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1883, ./app/routes/api.py:2124

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #782

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1884 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1884, ./app/routes/api.py:2125

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #783

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1892 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #784

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1895 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #785

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1916 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1916, ./app/routes/api.py:2177

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #786

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1917 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1917, ./app/routes/api.py:2178

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #787

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1918 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1918, ./app/routes/api.py:2179

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #788

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1919 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1919, ./app/routes/api.py:2180

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #789

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1920 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1920, ./app/routes/api.py:2181

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #790

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1921 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1921, ./app/routes/api.py:2182

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #791

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1922 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:1922, ./app/routes/api.py:2183

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #792

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1959 |
| **Confidence** | High |

**Description:** Function `save_hall_pass_setup` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #793

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1991 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #794

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2064 |
| **Confidence** | High |

**Description:** Function `attendance_history` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #795

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2064-2190 |
| **Confidence** | High |

**Description:** Function `attendance_history` is 127 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #796

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2098 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #797

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2107 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #798

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2144 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #799

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2156 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #800

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2197-2573 |
| **Confidence** | High |

**Description:** Function `handle_tap` is 377 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #801

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 224-768 |
| **Confidence** | High |

**Description:** Function `purchase_item` is 545 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #802

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2258 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2258, ./app/routes/admin.py:7284

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #803

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2308 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #804

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2315 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #805

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2333 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #806

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2343 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #807

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2384 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #808

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2429 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #809

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2455 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2455, ./app/routes/api.py:2554

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #810

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2456 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2456, ./app/routes/api.py:2555

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #811

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2478 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #812

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2513 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #813

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2538 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #814

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2577 |
| **Confidence** | High |

**Description:** Function `get_tap_entries` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #815

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2581 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2581, ./app/routes/api.py:2652

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #816

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2582 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2582, ./app/routes/api.py:2653

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #817

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2583 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2583, ./app/routes/api.py:2654

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #818

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2623 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #819

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2631 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #820

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2688 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2688, ./app/routes/api.py:3182

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #821

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2719 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2719, ./app/routes/api.py:3217

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #822

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2735 |
| **Confidence** | High |

**Description:** Function `check_and_auto_tapout_if_limit_reached` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #823

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2735-2888 |
| **Confidence** | High |

**Description:** Function `check_and_auto_tapout_if_limit_reached` is 154 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #824

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2787 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #825

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2797 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #826

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2921 |
| **Confidence** | High |

**Description:** Function `set_timezone` has cyclomatic complexity of 20.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #827

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2929 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2929, ./app/routes/api.py:2946

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #828

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 293 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #829

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2930 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2930, ./app/routes/api.py:2947

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #830

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2931 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #831

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2931 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:2931, ./app/routes/api.py:2948

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #832

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2936 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #833

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2948 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #834

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2953 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #835

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2964 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #836

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2969 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #837

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2996-3122 |
| **Confidence** | High |

**Description:** Function `create_demo_student` is 127 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #838

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 3143 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:3143, ./app/routes/api.py:3198

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #839

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 3144 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:3144, ./app/routes/api.py:3199

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #840

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 3165 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #841

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 320 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #842

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 3213 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #843

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 401 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #844

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 418 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #845

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 435 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #846

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 437 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #847

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 471 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #848

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 474 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #849

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 482 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #850

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 502 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #851

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 552 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:552, ./app/routes/api.py:679

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #852

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 553 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #853

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 553 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:553, ./app/routes/api.py:680

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #854

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 554 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:554, ./app/routes/api.py:681

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #855

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 555 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:555, ./app/routes/api.py:682

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #856

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 556 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:556, ./app/routes/api.py:683

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #857

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 557 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:557, ./app/routes/api.py:684

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #858

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 566 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:566, ./app/routes/api.py:692

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #859

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 567 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:567, ./app/routes/api.py:693

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #860

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 577 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:577, ./app/routes/api.py:702

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #861

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 578 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:578, ./app/routes/api.py:703

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #862

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 599 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #863

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 625 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #864

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 632 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:632, ./app/routes/api.py:648, ./app/routes/api.py:663

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #865

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 633 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:633, ./app/routes/api.py:649, ./app/routes/api.py:664

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #866

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 645 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #867

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 650 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:650, ./app/routes/api.py:665

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #868

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 682 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #869

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 726 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #870

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 731 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #871

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 754 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #872

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 773-909 |
| **Confidence** | High |

**Description:** Function `use_item` is 137 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #873

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 843 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #874

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 846 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #875

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 850 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #876

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 896 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #877

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 915 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:915, ./app/routes/api.py:967

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #878

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 916 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:916, ./app/routes/api.py:968

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #879

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 917 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:917, ./app/routes/api.py:969

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #880

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 918 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:918, ./app/routes/api.py:970

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #881

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 919 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:919, ./app/routes/api.py:971

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #882

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 920 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:920, ./app/routes/api.py:972

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #883

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 921 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:921, ./app/routes/api.py:973

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #884

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 922 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:922, ./app/routes/api.py:974

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #885

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 923 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:923, ./app/routes/api.py:975

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #886

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 924 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:924, ./app/routes/api.py:976

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #887

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 925 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:925, ./app/routes/api.py:977

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #888

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 926 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:926, ./app/routes/api.py:978

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #889

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 927 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:927, ./app/routes/api.py:979

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #890

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 928 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:928, ./app/routes/api.py:980

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #891

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 929 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:929, ./app/routes/api.py:981

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #892

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 930 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/api.py:930, ./app/routes/api.py:982

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #893

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/api.py` |
| **Line Range** | 966-1104 |
| **Confidence** | High |

**Description:** Function `reject_redemption` is 139 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #894

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 201-382 |
| **Confidence** | High |

**Description:** Function `view_doc` is 182 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #895

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 240 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #896

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 245 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #897

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 252 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #898

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 266 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #899

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 276 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #900

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 325 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #901

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 335 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #902

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 338 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #903

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 356 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #904

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 386-536 |
| **Confidence** | High |

**Description:** Function `search` is 151 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #905

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 413 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #906

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/main.py` |
| **Line Range** | 36 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #907

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/recovery.py` |
| **Line Range** | 120 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #908

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/recovery.py` |
| **Line Range** | 142 |
| **Confidence** | High |

**Description:** Function `verify_identity` has cyclomatic complexity of 17.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #909

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/recovery.py` |
| **Line Range** | 142-246 |
| **Confidence** | High |

**Description:** Function `verify_identity` is 105 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #910

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1010 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #911

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1040 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #912

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1091-1425 |
| **Confidence** | High |

**Description:** Function `dashboard` is 335 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #913

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1149 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1149, ./app/routes/api.py:2906

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #914

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1156 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1156, ./app/routes/student.py:1455

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #915

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1157 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1157, ./app/routes/student.py:1456

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #916

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1213 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #917

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1239 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #918

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1247 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1247, ./app/routes/student.py:2914

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #919

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1255 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #920

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1260 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #921

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1329 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #922

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1509-1699 |
| **Confidence** | High |

**Description:** Function `transfer` is 191 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #923

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1531 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #924

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1547 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #925

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1551 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #926

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1557 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1557, ./app/routes/student.py:2003, ./app/routes/student.py:3176

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #927

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1558 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1558, ./app/routes/student.py:2004, ./app/routes/student.py:3177

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #928

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1559 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1559, ./app/routes/student.py:2005, ./app/routes/student.py:3178

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #929

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1560 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1560, ./app/routes/student.py:2006, ./app/routes/student.py:3179

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #930

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1561 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1561, ./app/routes/student.py:2007, ./app/routes/student.py:3180

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #931

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1649 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #932

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1671 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #933

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1702-1801 |
| **Confidence** | High |

**Description:** Function `apply_savings_interest` is 100 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #934

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1759 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #935

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1773 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #936

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1776 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #937

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1779 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #938

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1808 |
| **Confidence** | High |

**Description:** Function `insurance_marketplace` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #939

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1808-1918 |
| **Confidence** | High |

**Description:** Function `insurance_marketplace` is 111 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #940

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1820 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1820, ./app/routes/student.py:2376

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #941

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1848 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1848, ./app/routes/student.py:1943

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #942

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1849 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1849, ./app/routes/student.py:1944

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #943

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1850 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1850, ./app/routes/student.py:1945

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #944

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1861 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1861, ./app/routes/student.py:1955

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #945

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1867 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #946

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1890 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #947

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1923-2082 |
| **Confidence** | High |

**Description:** Function `purchase_insurance` is 160 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #948

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 197 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:197, ./app/routes/admin.py:541

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #949

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1970 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #950

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 198 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:198, ./app/routes/admin.py:542

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #951

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 199 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:199, ./app/routes/admin.py:543

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #952

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1998 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1998, ./app/routes/student.py:3171

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #953

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1999 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:1999, ./app/routes/student.py:3172

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #954

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2000 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2000, ./app/routes/student.py:3173

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #955

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2001 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2001, ./app/routes/student.py:3174

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #956

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2002 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2002, ./app/routes/student.py:3175

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #957

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2008 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2008, ./app/routes/student.py:3181, ./app/routes/api.py:469

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #958

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2009 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2009, ./app/routes/student.py:3182, ./app/routes/api.py:470

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #959

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2054 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2054, ./app/routes/student.py:3251

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #960

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2061 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2061, ./app/routes/student.py:3258

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #961

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2062 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2062, ./app/routes/student.py:3259, ./app/routes/admin.py:983...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #962

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2063 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2063, ./app/routes/student.py:3260, ./app/routes/admin.py:984...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #963

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2064 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2064, ./app/routes/student.py:3261, ./app/routes/api.py:564...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #964

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2071 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2071, ./app/routes/student.py:3268

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #965

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2072 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2072, ./app/routes/student.py:3269, ./app/routes/admin.py:993...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #966

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2073 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2073, ./app/routes/student.py:3270, ./app/routes/admin.py:994...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #967

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2074 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2074, ./app/routes/admin.py:995, ./app/routes/admin.py:6694...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #968

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2075 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2075, ./app/routes/admin.py:996, ./app/routes/admin.py:6695...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #969

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2089 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2089, ./app/routes/student.py:2336

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #970

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2090 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2090, ./app/routes/student.py:2337

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #971

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2091 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2091, ./app/routes/student.py:2338

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #972

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2107-2329 |
| **Confidence** | High |

**Description:** Function `file_claim` is 223 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #973

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2133 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2133, ./app/routes/admin.py:4967

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #974

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2134 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #975

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2134 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2134, ./app/routes/admin.py:4968

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #976

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2135 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2135, ./app/routes/admin.py:4969

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #977

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2136 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2136, ./app/routes/admin.py:4970

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #978

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2137 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2137, ./app/routes/admin.py:4971

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #979

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2138 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2138, ./app/routes/admin.py:4972

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #980

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2139 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2139, ./app/routes/admin.py:4973

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #981

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2140 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2140, ./app/routes/admin.py:4974

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #982

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2141 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2141, ./app/routes/admin.py:4975

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #983

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2142 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2142, ./app/routes/admin.py:4976

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #984

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2143 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2143, ./app/routes/admin.py:4977

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #985

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2144 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2144, ./app/routes/admin.py:4978

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #986

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2145 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2145, ./app/routes/admin.py:4979

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #987

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2146 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2146, ./app/routes/admin.py:4980

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #988

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2183 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2183, ./app/routes/admin.py:5057

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #989

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2230 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #990

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2235 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #991

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2241 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #992

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2252 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #993

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2266 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #994

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2270 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #995

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 229-325 |
| **Confidence** | High |

**Description:** Function `calculate_scoped_balances` is 97 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #996

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2366-2563 |
| **Confidence** | High |

**Description:** Function `shop` is 198 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #997

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2417 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #998

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2422 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2422, ./app/routes/api.py:284

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #999

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2423 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2423, ./app/routes/api.py:285

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1000

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2432 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2432, ./app/routes/student.py:3060

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1001

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2436 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2436, ./app/routes/api.py:293

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1002

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2437 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2437, ./app/routes/api.py:294

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1003

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2460 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2460, ./app/routes/admin.py:2032

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1004

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2476 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2476, ./app/routes/api.py:360

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1005

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2489 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1006

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2508 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1007

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2543 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1008

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2574 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2574, ./app/routes/api.py:211

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1009

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2575 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2575, ./app/routes/api.py:212

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1010

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2576 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2576, ./app/routes/api.py:213

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1011

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2577 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2577, ./app/routes/api.py:214

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1012

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2578 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2578, ./app/routes/api.py:215

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1013

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2579 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2579, ./app/routes/api.py:216

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1014

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2585 |
| **Confidence** | High |

**Description:** Function `_calculate_rent_deadlines` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1015

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2585-2666 |
| **Confidence** | High |

**Description:** Function `_calculate_rent_deadlines` is 82 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1016

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2610 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1017

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2636 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1018

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2643 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1019

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2650 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1020

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2651 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2651, ./app/routes/student.py:2659

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1021

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2680 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2680, ./app/routes/api.py:65

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1022

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2707 |
| **Confidence** | High |

**Description:** Function `_filter_valid_rent_payments` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1023

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2744 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1024

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2746 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1025

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2748 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1026

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2797-2982 |
| **Confidence** | High |

**Description:** Function `rent` is 186 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1027

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2804 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2804, ./app/routes/student.py:2989

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1028

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2805 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2805, ./app/routes/student.py:2990

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1029

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2806 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2806, ./app/routes/student.py:2991

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1030

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 281 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:281, ./app/routes/student.py:307

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1031

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2858 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2858, ./app/routes/student.py:3053

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1032

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2859 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2859, ./app/routes/student.py:3054

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1033

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2860 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2860, ./app/routes/student.py:3055

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1034

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2861 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2861, ./app/routes/student.py:3056

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1035

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2862 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2862, ./app/routes/student.py:3057

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1036

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2863 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2863, ./app/routes/student.py:3058

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1037

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2864 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2864, ./app/routes/student.py:3059

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1038

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2869 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1039

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2899 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2899, ./app/routes/student.py:3093

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1040

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2907 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2907, ./app/routes/student.py:3102

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1041

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2908 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2908, ./app/routes/student.py:3103

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1042

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2909 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2909, ./app/routes/student.py:3104

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1043

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2910 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:2910, ./app/routes/student.py:3105

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1044

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 294 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:294, ./app/routes/student.py:315

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1045

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2987-3405 |
| **Confidence** | High |

**Description:** Function `rent_pay` is 419 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1046

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3150 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1047

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3153 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1048

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3262 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3262, ./app/routes/api.py:565, ./app/routes/api.py:691

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1049

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3271 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3271, ./app/routes/api.py:574, ./app/routes/api.py:699

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1050

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3272 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3272, ./app/routes/api.py:575, ./app/routes/api.py:700

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1051

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3273 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3273, ./app/routes/api.py:576, ./app/routes/api.py:701

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1052

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3301 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1053

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3314 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1054

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3320 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1055

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3333 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1056

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3351 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1057

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3361 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1058

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3396 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1059

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3412-3506 |
| **Confidence** | High |

**Description:** Function `login` is 95 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1060

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3422 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1061

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3436 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1062

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3452 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1063

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3455 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1064

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3461 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1065

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3467 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1066

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3474 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1067

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3511 |
| **Confidence** | High |

**Description:** Function `demo_login` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1068

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3511-3600 |
| **Confidence** | High |

**Description:** Function `demo_login` is 90 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1069

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3539 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1070

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3616 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1071

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3713 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3713, ./app/routes/student.py:3745, ./app/routes/student.py:3791...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1072

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3714 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3714, ./app/routes/student.py:3746, ./app/routes/student.py:3792...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1073

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3715 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3715, ./app/routes/student.py:3747, ./app/routes/student.py:3793...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1074

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 373 |
| **Confidence** | High |

**Description:** Function `complete_profile` has cyclomatic complexity of 15.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1075

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 373-537 |
| **Confidence** | High |

**Description:** Function `complete_profile` is 165 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1076

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3742 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3742, ./app/routes/student.py:3844

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1077

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3743 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3743, ./app/routes/student.py:3845

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1078

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3744 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3744, ./app/routes/student.py:3846

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1079

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3810 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3810, ./app/routes/student.py:3866

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1080

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3811 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3811, ./app/routes/student.py:3867

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1081

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3812 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3812, ./app/routes/student.py:3868

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1082

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3813 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3813, ./app/routes/student.py:3869

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1083

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3814 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3814, ./app/routes/student.py:3870

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1084

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3910 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3910, ./app/routes/student.py:3980

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1085

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3911 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:3911, ./app/routes/student.py:3981

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1086

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 422 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1087

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 425 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1088

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 429 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1089

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 434 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1090

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 454 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:454, ./app/routes/student.py:528

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1091

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 455 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:455, ./app/routes/student.py:529

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1092

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 473 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1093

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 543-789 |
| **Confidence** | High |

**Description:** Function `claim_account` is 247 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1094

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 559 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:559, ./app/routes/student.py:948

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1095

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 560 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:560, ./app/routes/student.py:949

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1096

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 566 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:566, ./app/routes/student.py:956, ./app/routes/admin.py:1105...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1097

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 567 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1098

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 574 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:574, ./app/routes/student.py:978

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1099

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 575 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:575, ./app/routes/student.py:979

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1100

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 576 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:576, ./app/routes/student.py:980

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1101

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 594 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:594, ./app/routes/student.py:991

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1102

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 595 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:595, ./app/routes/student.py:992

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1103

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 597 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:597, ./app/routes/student.py:994

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1104

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 598 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:598, ./app/routes/student.py:995

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1105

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 599 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:599, ./app/routes/student.py:996

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1106

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 600 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:600, ./app/routes/student.py:997

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1107

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 601 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:601, ./app/routes/student.py:998

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1108

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 602 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:602, ./app/routes/student.py:999

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1109

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 603 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:603, ./app/routes/student.py:1000

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1110

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 604 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:604, ./app/routes/student.py:1001

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1111

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 621 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1112

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 622 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:622, ./app/routes/student.py:1011

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1113

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 646 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1114

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 679 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1115

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 682 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:682, ./app/routes/student.py:744

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1116

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 689 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1117

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 729 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1118

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 878-1084 |
| **Confidence** | High |

**Description:** Function `add_class` is 207 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1119

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 905 |
| **Confidence** | High |

**Description:** Function `_get_return_target` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1120

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 922 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1121

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 928 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1122

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 936 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1123

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 943 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1124

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 953 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:953, ./app/routes/admin.py:1312

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1125

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 954 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:954, ./app/routes/admin.py:1313

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1126

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/student.py` |
| **Line Range** | 955 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/student.py:955, ./app/routes/admin.py:1314

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1127

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/student.py` |
| **Line Range** | 957 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1128

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1017 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1017, ./app/routes/system_admin.py:1101

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1129

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1044 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1130

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1083-1172 |
| **Confidence** | High |

**Description:** Function `delete_teacher` is 90 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1131

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1140 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1140, ./app/routes/system_admin.py:1148

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1132

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1266 |
| **Confidence** | High |

**Description:** Function `send_reward_to_reporter` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1133

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1266-1349 |
| **Confidence** | High |

**Description:** Function `send_reward_to_reporter` is 84 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1134

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1402 |
| **Confidence** | High |

**Description:** Function `grafana_proxy` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1135

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1402-1570 |
| **Confidence** | High |

**Description:** Function `grafana_proxy` is 169 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1136

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 142 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:142, ./app/routes/system_admin.py:1371

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1137

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1480 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1480, ./app/routes/system_admin.py:1528

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1138

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1481 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1481, ./app/routes/system_admin.py:1513, ./app/routes/system_admin.py:1529

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1139

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1482 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1482, ./app/routes/system_admin.py:1514, ./app/routes/system_admin.py:1530

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1140

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1618 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1618, ./app/routes/system_admin.py:1675

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1141

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1619 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1619, ./app/routes/system_admin.py:1676

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1142

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1620 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1620, ./app/routes/system_admin.py:1677

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1143

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1621 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1621, ./app/routes/system_admin.py:1678

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1144

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1622 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1622, ./app/routes/system_admin.py:1679

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1145

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1623 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1623, ./app/routes/system_admin.py:1680

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1146

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1624 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1624, ./app/routes/system_admin.py:1681

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1147

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1625 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1625, ./app/routes/system_admin.py:1682

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1148

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1626 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1626, ./app/routes/system_admin.py:1683

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1149

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1629 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1150

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1638 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1638, ./app/routes/admin.py:8324

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1151

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1639 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1639, ./app/routes/admin.py:8325

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1152

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1666 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1666, ./app/routes/system_admin.py:1718

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1153

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1667 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1667, ./app/routes/system_admin.py:1719

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1154

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1668 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1668, ./app/routes/system_admin.py:1720

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1155

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1686 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1156

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1693 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1693, ./app/routes/admin.py:8386

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1157

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1694 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1694, ./app/routes/admin.py:8387

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1158

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1695 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1695, ./app/routes/admin.py:8388

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1159

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1696 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1696, ./app/routes/admin.py:8389

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1160

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1717 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1717, ./app/routes/system_admin.py:1745

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1161

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1725 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1725, ./app/routes/admin.py:8429

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1162

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 173 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1163

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1751 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1751, ./app/routes/admin.py:8460

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1164

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1752 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1752, ./app/routes/admin.py:8461

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1165

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1753 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1753, ./app/routes/admin.py:8462

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1166

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1754 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1754, ./app/routes/admin.py:8463

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1167

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1755 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1755, ./app/routes/admin.py:8464

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1168

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1756 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1756, ./app/routes/admin.py:8465

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1169

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1757 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1757, ./app/routes/admin.py:8466

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1170

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1758 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1758, ./app/routes/admin.py:8467

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1171

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1759 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1759, ./app/routes/admin.py:8468

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1172

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1760 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:1760, ./app/routes/admin.py:8469

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1173

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1871 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1174

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 204 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:204, ./app/routes/admin.py:9020

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1175

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 205 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:205, ./app/routes/admin.py:9021

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1176

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 206 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:206, ./app/routes/admin.py:9022

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1177

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 219 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:219, ./app/routes/admin.py:9037

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1178

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 220 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:220, ./app/routes/admin.py:9038

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1179

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 221 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:221, ./app/routes/admin.py:9039

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1180

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 222 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:222, ./app/routes/admin.py:9040

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1181

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 223 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:223, ./app/routes/admin.py:9041

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1182

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 224 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:224, ./app/routes/system_admin.py:300, ./app/routes/admin.py:9042...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1183

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 225 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:225, ./app/routes/system_admin.py:301, ./app/routes/admin.py:9043...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1184

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 226 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:226, ./app/routes/admin.py:9044

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1185

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 227 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:227, ./app/routes/admin.py:9045

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1186

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 228 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:228, ./app/routes/admin.py:9046

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1187

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 229 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:229, ./app/routes/admin.py:9047

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1188

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 237 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:237, ./app/routes/admin.py:9055

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1189

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 238 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:238, ./app/routes/admin.py:9056

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1190

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 239 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:239, ./app/routes/admin.py:9057

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1191

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 249 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:249, ./app/routes/admin.py:9067

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1192

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 257 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:257, ./app/routes/admin.py:9075

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1193

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 258 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:258, ./app/routes/admin.py:9076

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1194

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 259 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:259, ./app/routes/admin.py:9077

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1195

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 260 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:260, ./app/routes/admin.py:9078

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1196

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 261 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:261, ./app/routes/admin.py:9079

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1197

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 262 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:262, ./app/routes/admin.py:9080

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1198

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 263 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:263, ./app/routes/admin.py:9081

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1199

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 264 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:264, ./app/routes/admin.py:9082

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1200

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 265 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:265, ./app/routes/admin.py:9083

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1201

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 266 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:266, ./app/routes/admin.py:9084

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1202

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 267 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:267, ./app/routes/admin.py:9085

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1203

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 274 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:274, ./app/routes/admin.py:9092

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1204

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 275 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:275, ./app/routes/admin.py:9093

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1205

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 276 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:276, ./app/routes/admin.py:9094

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1206

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 277 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:277, ./app/routes/admin.py:9095

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1207

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 278 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:278, ./app/routes/admin.py:9096

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1208

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 279 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:279, ./app/routes/admin.py:9097

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1209

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 280 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:280, ./app/routes/admin.py:9098

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1210

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 281 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:281, ./app/routes/admin.py:9099

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1211

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 282 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:282, ./app/routes/admin.py:9100

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1212

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 283 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:283, ./app/routes/admin.py:9101

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1213

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 284 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:284, ./app/routes/admin.py:9102

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1214

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 296 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:296, ./app/routes/admin.py:9114

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1215

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 297 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:297, ./app/routes/admin.py:9115

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1216

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 298 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:298, ./app/routes/admin.py:9116

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1217

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 299 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:299, ./app/routes/admin.py:9117

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1218

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 302 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:302, ./app/routes/admin.py:9120

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1219

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 303 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:303, ./app/routes/admin.py:9121

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1220

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 304 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:304, ./app/routes/admin.py:9122

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1221

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 305 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:305, ./app/routes/admin.py:9123

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1222

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 312 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:312, ./app/routes/admin.py:9130

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1223

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 313 |
| **Confidence** | High |

**Description:** Function `passkey_auth_finish` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1224

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 313 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:313, ./app/routes/admin.py:9131

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1225

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 314 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:314, ./app/routes/admin.py:9132

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1226

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 315 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:315, ./app/routes/admin.py:9133

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1227

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 316 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:316, ./app/routes/admin.py:9134

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1228

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 317 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:317, ./app/routes/admin.py:9135

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1229

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 318 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:318, ./app/routes/admin.py:9136

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1230

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 319 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:319, ./app/routes/admin.py:9137

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1231

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 320 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:320, ./app/routes/admin.py:9138

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1232

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 321 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:321, ./app/routes/admin.py:9139

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1233

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 322 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:322, ./app/routes/admin.py:9140

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1234

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 341 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:341, ./app/routes/admin.py:9159

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1235

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 342 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:342, ./app/routes/admin.py:9160

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1236

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 349 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1237

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 370 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:370, ./app/routes/admin.py:9184

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1238

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 371 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:371, ./app/routes/admin.py:9185

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1239

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 391 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:391, ./app/routes/admin.py:9207

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1240

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 405 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:405, ./app/routes/admin.py:9221

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1241

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 406 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:406, ./app/routes/admin.py:9222

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1242

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 413 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:413, ./app/routes/admin.py:9229

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1243

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 414 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:414, ./app/routes/admin.py:9230

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1244

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 415 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:415, ./app/routes/admin.py:9231

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1245

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 487 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1246

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 532 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/routes/system_admin.py:532, ./app/routes/system_admin.py:593

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1247

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 861 |
| **Confidence** | High |

**Description:** Function `teacher_overview` has cyclomatic complexity of 13.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1248

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 861-986 |
| **Confidence** | High |

**Description:** Function `teacher_overview` is 126 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1249

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 943 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1250

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 965 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1251

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 991-1078 |
| **Confidence** | High |

**Description:** Function `delete_period` is 88 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1252

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 107 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1253

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 12 |
| **Confidence** | High |

**Description:** Function `enforce_daily_limits_job` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1254

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 151 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:151, ./scripts/cleanup_orphaned_store_blocks.py:18

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1255

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 152 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:152, ./scripts/cleanup_orphaned_store_blocks.py:19

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1256

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 153 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:153, ./scripts/cleanup_orphaned_store_blocks.py:20

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1257

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 154 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:154, ./scripts/cleanup_orphaned_store_blocks.py:21

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1258

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 155 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:155, ./scripts/cleanup_orphaned_store_blocks.py:22

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1259

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 156 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:156, ./scripts/cleanup_orphaned_store_blocks.py:23

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1260

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 157 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:157, ./scripts/cleanup_orphaned_store_blocks.py:24

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1261

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 158 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:158, ./scripts/cleanup_orphaned_store_blocks.py:25

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1262

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 159 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:159, ./scripts/cleanup_orphaned_store_blocks.py:26

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1263

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 160 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:160, ./scripts/cleanup_orphaned_store_blocks.py:27

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1264

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 161 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:161, ./scripts/cleanup_orphaned_store_blocks.py:28

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1265

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 162 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:162, ./scripts/cleanup_orphaned_store_blocks.py:29

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1266

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 163 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:163, ./scripts/cleanup_orphaned_store_blocks.py:30

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1267

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 164 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:164, ./scripts/cleanup_orphaned_store_blocks.py:31

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1268

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 165 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:165, ./scripts/cleanup_orphaned_store_blocks.py:32

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1269

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 166 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:166, ./scripts/cleanup_orphaned_store_blocks.py:33

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1270

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 167 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:167, ./scripts/cleanup_orphaned_store_blocks.py:34

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1271

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 168 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:168, ./scripts/cleanup_orphaned_store_blocks.py:35

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1272

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 169 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:169, ./scripts/cleanup_orphaned_store_blocks.py:36

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1273

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 179 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:179, ./scripts/cleanup_orphaned_store_blocks.py:57

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1274

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 180 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:180, ./scripts/cleanup_orphaned_store_blocks.py:58

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1275

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 181 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:181, ./scripts/cleanup_orphaned_store_blocks.py:59

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1276

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 182 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:182, ./scripts/cleanup_orphaned_store_blocks.py:60

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1277

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 183 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:183, ./scripts/cleanup_orphaned_store_blocks.py:61

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1278

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 184 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:184, ./scripts/cleanup_orphaned_store_blocks.py:62

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1279

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 185 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:185, ./scripts/cleanup_orphaned_store_blocks.py:63

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1280

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 30 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:30, ./app/routes/admin.py:681

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1281

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 33 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1282

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 38 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:38, ./app/routes/admin.py:687

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1283

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 39 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:39, ./app/routes/admin.py:688

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1284

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 40 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:40, ./app/routes/admin.py:689

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1285

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/scheduled_tasks.py` |
| **Line Range** | 42 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/scheduled_tasks.py:42, ./app/routes/admin.py:7138

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1286

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/analytics_engine.py` |
| **Line Range** | 13 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/analytics_engine.py:13, ./app/utils/analytics_engine.py:441

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1287

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/analytics_engine.py` |
| **Line Range** | 313 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1288

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/analytics_engine.py` |
| **Line Range** | 315 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1289

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/analytics_engine.py` |
| **Line Range** | 537-658 |
| **Confidence** | High |

**Description:** Function `create_snapshot` is 122 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1290

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/analytics_engine.py` |
| **Line Range** | 638 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1291

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 10-224 |
| **Confidence** | High |

**Description:** Function `settle_balances` is 215 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1292

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 106 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:106, ./app/routes/student.py:308

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1293

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 120 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:120, ./app/routes/student.py:316

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1294

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 144 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1295

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 160 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1296

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 163 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1297

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 168 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1298

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 183 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:183, ./app/utils/banking.py:201

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1299

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 184 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1300

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 184 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:184, ./app/utils/banking.py:202

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1301

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 185 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:185, ./app/utils/banking.py:203

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1302

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 186 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:186, ./app/utils/banking.py:204

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1303

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 196 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1304

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 198 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1305

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 202 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1306

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 31 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:31, ./app/utils/banking.py:51

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1307

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 42 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1308

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 68 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:68, ./app/utils/banking.py:88

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1309

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 79 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:79, ./app/utils/banking.py:131

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1310

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 80 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:80, ./app/utils/banking.py:132

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1311

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 81 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:81, ./app/utils/banking.py:133

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1312

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 82 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:82, ./app/utils/banking.py:134

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1313

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/banking.py` |
| **Line Range** | 83 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/banking.py:83, ./app/utils/banking.py:135

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1314

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 136 |
| **Confidence** | High |

**Description:** Function `_normalize_to_weekly` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1315

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 242 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/economy_balance.py:242, ./app/utils/economy_balance.py:312, ./app/utils/economy_balance.py:451...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1316

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 243 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/economy_balance.py:243, ./app/utils/economy_balance.py:313, ./app/utils/economy_balance.py:452...

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1317

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 306 |
| **Confidence** | High |

**Description:** Function `check_insurance_balance` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1318

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 306-443 |
| **Confidence** | High |

**Description:** Function `check_insurance_balance` is 138 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1319

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 341 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1320

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 352 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1321

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 385 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1322

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 438 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1323

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 440 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1324

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 475 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1325

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 486 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1326

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 544 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1327

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 561 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1328

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 586 |
| **Confidence** | High |

**Description:** Function `validate_rent_value` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1329

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 586-697 |
| **Confidence** | High |

**Description:** Function `validate_rent_value` is 112 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1330

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 638 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1331

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 699 |
| **Confidence** | High |

**Description:** Function `validate_insurance_value` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1332

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 699-819 |
| **Confidence** | High |

**Description:** Function `validate_insurance_value` is 121 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1333

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 724 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1334

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 782 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1335

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 786 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1336

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 886 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1337

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 960 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1338

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 983 |
| **Confidence** | High |

**Description:** Function `analyze_economy` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1339

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 983-1062 |
| **Confidence** | High |

**Description:** Function `analyze_economy` is 80 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1340

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./app/utils/help_content.py` |
| **Line Range** | 116 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./app/utils/help_content.py:116, ./app/utils/help_content.py:204

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1341

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/helpers.py` |
| **Line Range** | 40 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1342

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/helpers.py` |
| **Line Range** | 44 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1343

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/ip_handler.py` |
| **Line Range** | 127 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1344

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/ip_handler.py` |
| **Line Range** | 198 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1345

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/issue_helpers.py` |
| **Line Range** | 99-175 |
| **Confidence** | High |

**Description:** Function `create_issue` is 77 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1346

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/overdraft.py` |
| **Line Range** | 37-126 |
| **Confidence** | High |

**Description:** Function `charge_overdraft_fee_if_needed` is 90 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1347

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/overdraft.py` |
| **Line Range** | 72 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1348

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/overdraft.py` |
| **Line Range** | 79 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1349

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/overdraft.py` |
| **Line Range** | 86 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1350

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/turnstile.py` |
| **Line Range** | 13 |
| **Confidence** | High |

**Description:** Function `verify_turnstile_token` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1351

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./app/utils/turnstile.py` |
| **Line Range** | 13-88 |
| **Confidence** | High |

**Description:** Function `verify_turnstile_token` is 76 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1352

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./cleanup_duplicate_tapouts.py` |
| **Line Range** | 130 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1353

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./cleanup_duplicate_tapouts.py` |
| **Line Range** | 82 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1354

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./fix_db_version.py` |
| **Line Range** | 1 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./fix_db_version.py:1, ./scripts/setup_migration_db.py:4

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1355

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./fix_db_version.py` |
| **Line Range** | 2 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./fix_db_version.py:2, ./scripts/setup_migration_db.py:5

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1356

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/add-github-actions-to-firewall.py` |
| **Line Range** | 107 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1357

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/add-github-actions-to-firewall.py` |
| **Line Range** | 50 |
| **Confidence** | High |

**Description:** Function `main` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1358

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/add-github-actions-to-firewall.py` |
| **Line Range** | 50-130 |
| **Confidence** | High |

**Description:** Function `main` is 81 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1359

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/add-pulsetic.py` |
| **Line Range** | 22 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:22, ./scripts/add-github-actions-to-firewall.py:49

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1360

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/add-pulsetic.py` |
| **Line Range** | 23 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:23, ./scripts/add-github-actions-to-firewall.py:50

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1361

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/add-pulsetic.py` |
| **Line Range** | 24 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:24, ./scripts/add-github-actions-to-firewall.py:51

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1362

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/add-pulsetic.py` |
| **Line Range** | 25 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:25, ./scripts/add-github-actions-to-firewall.py:52

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1363

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/add-pulsetic.py` |
| **Line Range** | 26 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:26, ./scripts/add-github-actions-to-firewall.py:53

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1364

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/add-pulsetic.py` |
| **Line Range** | 27 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/add-pulsetic.py:27, ./scripts/add-github-actions-to-firewall.py:54

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1365

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 102 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:102, ./scripts/verify_chain.py:66

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1366

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 103 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:103, ./scripts/verify_chain.py:67

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1367

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 104 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:104, ./scripts/verify_chain.py:68

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1368

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 105 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:105, ./scripts/verify_chain.py:69

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1369

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 106 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1370

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 14 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:14, ./scripts/verify_chain.py:8

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1371

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 147 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1372

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 15 |
| **Confidence** | High |

**Description:** Function `parse_migration_file` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1373

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 15 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:15, ./scripts/verify_chain.py:9

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1374

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 161 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1375

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 166 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1376

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 200 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1377

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 215 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/analyze_migrations.py:215, ./scripts/verify_chain.py:175

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1378

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 39 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1379

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 53 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1380

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 56 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #1381

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 63 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1382

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Risk Pattern |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 66 |
| **Confidence** | High |

**Description:** Empty except block detected.

**Why This Matters:** Swallowing exceptions hides errors and makes debugging difficult.

### Finding #1383

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 80-212 |
| **Confidence** | High |

**Description:** Function `analyze_migrations` is 133 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1384

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/backfill_join_codes.py` |
| **Line Range** | 115 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1385

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/backfill_join_codes.py` |
| **Line Range** | 38 |
| **Confidence** | High |

**Description:** Function `backfill_join_codes` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1386

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/backfill_join_codes.py` |
| **Line Range** | 38-123 |
| **Confidence** | High |

**Description:** Function `backfill_join_codes` is 86 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1387

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/backfill_join_codes.py` |
| **Line Range** | 66 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1388

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/backfill_join_codes.py` |
| **Line Range** | 84 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1389

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/backfill_join_codes.py` |
| **Line Range** | 98 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1390

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/check_migration.py` |
| **Line Range** | 29 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1391

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 100 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1392

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 124 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1393

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 27 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:27, ./scripts/cleanup_duplicates_flask.py:92

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1394

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 28 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:28, ./scripts/cleanup_duplicates_flask.py:93

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1395

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 29 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:29, ./scripts/cleanup_duplicates_flask.py:94

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1396

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 30 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:30, ./scripts/cleanup_duplicates_flask.py:95

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1397

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 31 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:31, ./scripts/cleanup_duplicates_flask.py:96

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1398

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 32 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:32, ./scripts/cleanup_duplicates_flask.py:97

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1399

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 33 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:33, ./scripts/cleanup_duplicates_flask.py:98

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1400

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 34 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:34, ./scripts/cleanup_duplicates_flask.py:99

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1401

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 35 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1402

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 35 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:35, ./scripts/cleanup_duplicates_flask.py:100

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1403

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 36 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:36, ./scripts/cleanup_duplicates_flask.py:101

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1404

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 37 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:37, ./scripts/cleanup_duplicates_flask.py:102

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1405

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 38 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:38, ./scripts/cleanup_duplicates_flask.py:103

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1406

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 39 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/cleanup_duplicates_flask.py:39, ./scripts/cleanup_duplicates_flask.py:104

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1407

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 61 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1408

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 90 |
| **Confidence** | High |

**Description:** Function `delete_duplicates` has cyclomatic complexity of 17.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1409

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/cleanup_duplicates_flask.py` |
| **Line Range** | 90-198 |
| **Confidence** | High |

**Description:** Function `delete_duplicates` is 109 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1410

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/cleanup_invite_codes.py` |
| **Line Range** | 25 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1411

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 114-277 |
| **Confidence** | High |

**Description:** Function `migrate_legacy_students` is 164 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1412

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 138 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:138, ./scripts/comprehensive_legacy_migration.py:638

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1413

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 139 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:139, ./scripts/comprehensive_legacy_migration.py:639

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1414

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 201 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1415

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 229 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:229, ./scripts/comprehensive_legacy_migration.py:345

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1416

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 230 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:230, ./scripts/comprehensive_legacy_migration.py:346

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1417

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 231 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:231, ./scripts/comprehensive_legacy_migration.py:347

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1418

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 232 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:232, ./scripts/comprehensive_legacy_migration.py:348

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1419

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 233 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:233, ./scripts/comprehensive_legacy_migration.py:349

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1420

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 234 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:234, ./scripts/comprehensive_legacy_migration.py:350

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1421

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 235 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1422

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 235 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:235, ./scripts/comprehensive_legacy_migration.py:351

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1423

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 236 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:236, ./scripts/comprehensive_legacy_migration.py:352

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1424

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 237 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:237, ./scripts/comprehensive_legacy_migration.py:353

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1425

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 238 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:238, ./scripts/comprehensive_legacy_migration.py:354

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1426

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 239 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:239, ./scripts/comprehensive_legacy_migration.py:355

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1427

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 240 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:240, ./scripts/comprehensive_legacy_migration.py:356

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1428

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 241 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:241, ./scripts/comprehensive_legacy_migration.py:357

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1429

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 242 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1430

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 242 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:242, ./scripts/comprehensive_legacy_migration.py:358

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1431

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 243 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:243, ./scripts/comprehensive_legacy_migration.py:359

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1432

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 244 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:244, ./scripts/comprehensive_legacy_migration.py:360

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1433

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 245 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/comprehensive_legacy_migration.py:245, ./scripts/comprehensive_legacy_migration.py:361

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1434

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 254 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1435

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 280 |
| **Confidence** | High |

**Description:** Function `backfill_teacher_block_join_codes` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1436

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 280-373 |
| **Confidence** | High |

**Description:** Function `backfill_teacher_block_join_codes` is 94 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1437

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 329 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1438

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 351 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1439

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 358 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1440

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 491 |
| **Confidence** | High |

**Description:** Function `backfill_related_tables` has cyclomatic complexity of 14.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1441

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 491-619 |
| **Confidence** | High |

**Description:** Function `backfill_related_tables` is 129 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1442

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 536 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1443

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 545 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1444

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 552 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1445

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 593 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1446

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 608 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1447

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 622-699 |
| **Confidence** | High |

**Description:** Function `verify_migration` is 78 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1448

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 654 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1449

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 739 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1450

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/comprehensive_legacy_migration.py` |
| **Line Range** | 752 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1451

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 10 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:10, ./scripts/add-github-actions-to-firewall.py:10

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1452

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 103 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1453

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 114 |
| **Confidence** | High |

**Description:** Function `main` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1454

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 147 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1455

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 16 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:16, ./scripts/add-github-actions-to-firewall.py:17

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1456

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 43 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:43, ./scripts/add-github-actions-to-firewall.py:43

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1457

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 44 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create-github-actions-firewall.py:44, ./scripts/add-github-actions-to-firewall.py:44

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1458

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 163 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1459

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 174 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1460

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 197 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1461

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 203 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1462

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 48 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:48, ./scripts/create_admin.py:105

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1463

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 55 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:55, ./scripts/create_admin.py:112

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1464

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 56 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:56, ./scripts/create_admin.py:113

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1465

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 63 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:63, ./scripts/create_admin.py:120

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1466

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 64 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:64, ./scripts/create_admin.py:121

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1467

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 65 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:65, ./scripts/create_admin.py:122

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1468

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 66 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:66, ./scripts/create_admin.py:123

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1469

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 67 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:67, ./scripts/create_admin.py:124

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1470

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 68 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:68, ./scripts/create_admin.py:125

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1471

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 75 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:75, ./scripts/create_admin.py:132

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1472

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 76 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:76, ./scripts/create_admin.py:133

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1473

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 77 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:77, ./scripts/create_admin.py:134

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1474

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 78 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:78, ./scripts/create_admin.py:135

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1475

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 79 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:79, ./scripts/create_admin.py:136

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1476

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 80 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:80, ./scripts/create_admin.py:137

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1477

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 81 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:81, ./scripts/create_admin.py:138

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1478

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 82 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:82, ./scripts/create_admin.py:139

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1479

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 89 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:89, ./scripts/create_admin.py:146

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1480

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 90 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:90, ./scripts/create_admin.py:147

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1481

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 91 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:91, ./scripts/create_admin.py:148

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1482

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/create_admin.py` |
| **Line Range** | 92 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/create_admin.py:92, ./scripts/create_admin.py:149

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1483

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/debug_student_state.py` |
| **Line Range** | 100 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1484

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/debug_student_state.py` |
| **Line Range** | 138 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1485

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/debug_student_state.py` |
| **Line Range** | 15 |
| **Confidence** | High |

**Description:** Function `debug_student_state` has cyclomatic complexity of 13.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1486

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/debug_student_state.py` |
| **Line Range** | 15-173 |
| **Confidence** | High |

**Description:** Function `debug_student_state` is 159 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1487

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/debug_student_state.py` |
| **Line Range** | 77 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1488

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/debug_student_state.py` |
| **Line Range** | 79 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1489

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/debug_student_state.py` |
| **Line Range** | 98 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1490

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/diagnose_migrations.py` |
| **Line Range** | 11 |
| **Confidence** | High |

**Description:** Function `check_migration_files` has cyclomatic complexity of 11.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1491

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/diagnose_migrations.py` |
| **Line Range** | 110 |
| **Confidence** | High |

**Description:** Function `main` has cyclomatic complexity of 12.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1492

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/diagnose_migrations.py` |
| **Line Range** | 147 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1493

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/diagnose_migrations.py` |
| **Line Range** | 32 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1494

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/diagnose_migrations.py` |
| **Line Range** | 44 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1495

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/diagnose_migrations.py` |
| **Line Range** | 58 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1496

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/diagnose_migrations.py` |
| **Line Range** | 95 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1497

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/reset_database.py` |
| **Line Range** | 48 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1498

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 10 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:10, ./scripts/dev-utilities/reset_database.py:10

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1499

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 105 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:105, ./scripts/dev-utilities/reset_database.py:88

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1500

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 106 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:106, ./scripts/dev-utilities/reset_database.py:89

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1501

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 107 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:107, ./scripts/dev-utilities/reset_database.py:90

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1502

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 108 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:108, ./scripts/dev-utilities/reset_database.py:91

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1503

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 109 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:109, ./scripts/dev-utilities/reset_database.py:92

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1504

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 11 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:11, ./scripts/dev-utilities/reset_database.py:11

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1505

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 110 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:110, ./scripts/dev-utilities/reset_database.py:93

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1506

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 111 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:111, ./scripts/dev-utilities/reset_database.py:94

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1507

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 112 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:112, ./scripts/dev-utilities/reset_database.py:95

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1508

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 113 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:113, ./scripts/dev-utilities/reset_database.py:96

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1509

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 114 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:114, ./scripts/dev-utilities/reset_database.py:97

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1510

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 115 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:115, ./scripts/dev-utilities/reset_database.py:98

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1511

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 116 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:116, ./scripts/dev-utilities/reset_database.py:99

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1512

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 117 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:117, ./scripts/dev-utilities/reset_database.py:100

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1513

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 118 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:118, ./scripts/dev-utilities/reset_database.py:101

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1514

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 119 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:119, ./scripts/dev-utilities/reset_database.py:102

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1515

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 12 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:12, ./scripts/dev-utilities/reset_database.py:12

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1516

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 120 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:120, ./scripts/dev-utilities/reset_database.py:103

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1517

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 121 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:121, ./scripts/dev-utilities/reset_database.py:104

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1518

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 122 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:122, ./scripts/dev-utilities/reset_database.py:105

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1519

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 123 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:123, ./scripts/dev-utilities/reset_database.py:106

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1520

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 124 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:124, ./scripts/dev-utilities/reset_database.py:107

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1521

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 125 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:125, ./scripts/dev-utilities/reset_database.py:108

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1522

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 126 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:126, ./scripts/dev-utilities/reset_database.py:109

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1523

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 127 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:127, ./scripts/dev-utilities/reset_database.py:110

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1524

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 128 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:128, ./scripts/dev-utilities/reset_database.py:111

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1525

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 129 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:129, ./scripts/dev-utilities/reset_database.py:112

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1526

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 13 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:13, ./scripts/dev-utilities/reset_database.py:13

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1527

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 130 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:130, ./scripts/dev-utilities/reset_database.py:113

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1528

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 131 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:131, ./scripts/dev-utilities/reset_database.py:114

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1529

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 132 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:132, ./scripts/dev-utilities/reset_database.py:115

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1530

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 133 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:133, ./scripts/dev-utilities/reset_database.py:116

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1531

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 134 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:134, ./scripts/dev-utilities/reset_database.py:117

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1532

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 135 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:135, ./scripts/dev-utilities/reset_database.py:118

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1533

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 136 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:136, ./scripts/dev-utilities/reset_database.py:119

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1534

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 137 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:137, ./scripts/dev-utilities/reset_database.py:120

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1535

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 138 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:138, ./scripts/dev-utilities/reset_database.py:121

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1536

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 14 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:14, ./scripts/dev-utilities/reset_database.py:14

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1537

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 15 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:15, ./scripts/dev-utilities/reset_database.py:15

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1538

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 16 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:16, ./scripts/dev-utilities/reset_database.py:16

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1539

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 17 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:17, ./scripts/dev-utilities/reset_database.py:17

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1540

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 18 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:18, ./scripts/dev-utilities/reset_database.py:18

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1541

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 19 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:19, ./scripts/dev-utilities/reset_database.py:19

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1542

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 20 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:20, ./scripts/dev-utilities/reset_database.py:20

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1543

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 30 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:30, ./scripts/dev-utilities/reset_database.py:29

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1544

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 31 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:31, ./scripts/dev-utilities/reset_database.py:30

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1545

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 32 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:32, ./scripts/dev-utilities/reset_database.py:31

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1546

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 33 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:33, ./scripts/dev-utilities/reset_database.py:32

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1547

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 34 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:34, ./scripts/dev-utilities/reset_database.py:33

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1548

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 52 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1549

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 62 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1550

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 69 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:69, ./scripts/dev-utilities/reset_database.py:61

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1551

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 70 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:70, ./scripts/dev-utilities/reset_database.py:62

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1552

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 71 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:71, ./scripts/dev-utilities/reset_database.py:63

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1553

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 72 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:72, ./scripts/dev-utilities/reset_database.py:64

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1554

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 73 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:73, ./scripts/dev-utilities/reset_database.py:65

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1555

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 74 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:74, ./scripts/dev-utilities/reset_database.py:66

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1556

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 89 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:89, ./scripts/dev-utilities/reset_database.py:77

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1557

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 9 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:9, ./scripts/dev-utilities/reset_database.py:9

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1558

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 90 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:90, ./scripts/dev-utilities/reset_database.py:78

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1559

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 91 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:91, ./scripts/dev-utilities/reset_database.py:79

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1560

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 92 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:92, ./scripts/dev-utilities/reset_database.py:80

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1561

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/dev-utilities/reset_database_no_schema.py` |
| **Line Range** | 93 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/dev-utilities/reset_database_no_schema.py:93, ./scripts/dev-utilities/reset_database.py:81

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1562

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 10 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:10, ./scripts/pulsetic_firewall.py:10

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1563

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 131 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:131, ./scripts/pulsetic_firewall.py:135

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1564

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 132 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:132, ./scripts/pulsetic_firewall.py:136

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1565

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 133 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:133, ./scripts/pulsetic_firewall.py:137

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1566

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 134 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:134, ./scripts/pulsetic_firewall.py:138

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1567

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 135 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:135, ./scripts/pulsetic_firewall.py:139

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1568

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 136 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:136, ./scripts/pulsetic_firewall.py:140

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1569

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 137 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:137, ./scripts/pulsetic_firewall.py:141

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1570

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 175 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:175, ./scripts/pulsetic_firewall.py:164

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1571

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 176 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:176, ./scripts/pulsetic_firewall.py:165

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1572

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 177 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:177, ./scripts/pulsetic_firewall.py:166

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1573

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 178 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:178, ./scripts/pulsetic_firewall.py:167

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1574

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 187 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:187, ./scripts/pulsetic_firewall.py:180

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1575

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 188 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:188, ./scripts/pulsetic_firewall.py:181

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1576

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 189 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:189, ./scripts/pulsetic_firewall.py:182

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1577

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 190 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:190, ./scripts/pulsetic_firewall.py:183

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1578

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 191 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:191, ./scripts/pulsetic_firewall.py:184

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1579

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 192 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:192, ./scripts/pulsetic_firewall.py:185

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1580

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 193 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:193, ./scripts/pulsetic_firewall.py:186

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1581

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 217 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:217, ./scripts/pulsetic_firewall.py:205

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1582

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 218 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:218, ./scripts/pulsetic_firewall.py:206

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1583

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 22 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:22, ./scripts/pulsetic_firewall.py:26

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1584

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 23 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:23, ./scripts/pulsetic_firewall.py:27

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1585

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 24 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:24, ./scripts/pulsetic_firewall.py:28

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1586

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 25 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:25, ./scripts/pulsetic_firewall.py:29

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1587

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 26 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:26, ./scripts/pulsetic_firewall.py:30

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1588

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 27 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:27, ./scripts/pulsetic_firewall.py:31

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1589

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 28 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:28, ./scripts/pulsetic_firewall.py:32

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1590

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 29 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:29, ./scripts/pulsetic_firewall.py:33

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1591

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 30 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:30, ./scripts/pulsetic_firewall.py:34

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1592

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 31 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:31, ./scripts/pulsetic_firewall.py:35

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1593

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 32 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:32, ./scripts/pulsetic_firewall.py:36

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1594

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 33 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:33, ./scripts/pulsetic_firewall.py:37

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1595

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 34 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:34, ./scripts/pulsetic_firewall.py:38

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1596

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 41 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:41, ./scripts/pulsetic_firewall.py:51

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1597

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 8 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:8, ./scripts/pulsetic_firewall.py:8

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1598

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 9 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/firewall_complete.py:9, ./scripts/pulsetic_firewall.py:9

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1599

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/fix_alembic_version.py` |
| **Line Range** | 22 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1600

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/fix_missing_student_teacher_associations.py` |
| **Line Range** | 46 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1601

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/fix_teacher_id_nulls.py` |
| **Line Range** | 58 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1602

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/fix_teacher_id_nulls.py` |
| **Line Range** | 66 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1603

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 102 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1604

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 113 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1605

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 124 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1606

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 135 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1607

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 153 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1608

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 164 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1609

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 179 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1610

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 188 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1611

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 54-198 |
| **Confidence** | High |

**Description:** Function `inspect_database_schema` is 145 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1612

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/inspect_join_code_columns.py` |
| **Line Range** | 76 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1613

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 147 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1614

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 208 |
| **Confidence** | High |

**Description:** Function `main` has cyclomatic complexity of 20.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1615

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 208-336 |
| **Confidence** | High |

**Description:** Function `main` is 129 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1616

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 276 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1617

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 280 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1618

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 305 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1619

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 307 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1620

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 312 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1621

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 314 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1622

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/manage_invites.py` |
| **Line Range** | 120 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1623

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/manage_invites.py` |
| **Line Range** | 32 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/manage_invites.py:32, ./scripts/manage_invites.py:80

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1624

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/manage_invites.py` |
| **Line Range** | 35 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1625

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/manage_invites.py` |
| **Line Range** | 63 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1626

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/manage_invites.py` |
| **Line Range** | 68 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1627

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/manage_invites.py` |
| **Line Range** | 83 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1628

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/pulsetic_firewall.py` |
| **Line Range** | 67 |
| **Confidence** | High |

**Description:** Function `load_token` has cyclomatic complexity of 13.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1629

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/pulsetic_firewall.py` |
| **Line Range** | 86 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1630

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 125 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/seed_multi_tenancy_test_data.py:125, ./scripts/seed_multi_tenancy_test_data.py:134

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1631

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 283 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1632

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 309 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1633

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 321 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1634

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 361 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1635

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 368 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1636

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 518 |
| **Confidence** | High |

**Description:** Function `seed_database` has cyclomatic complexity of 15.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1637

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 518-792 |
| **Confidence** | High |

**Description:** Function `seed_database` is 275 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1638

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 610 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1639

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 658 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1640

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/seed_multi_tenancy_test_data.py` |
| **Line Range** | 736 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1641

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 122 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1642

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 127 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1643

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 135 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1644

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 235-394 |
| **Confidence** | High |

**Description:** Function `validate_migrations` is 160 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1645

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 251 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1646

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 257 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1647

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 288 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1648

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 307 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1649

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 332 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1650

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 47 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1651

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 78 |
| **Confidence** | High |

**Description:** Function `check_idempotency` has cyclomatic complexity of 16.

**Why This Matters:** High complexity indicates hard-to-test logic.

### Finding #1652

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 78-170 |
| **Confidence** | High |

**Description:** Function `check_idempotency` is 93 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1653

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 98 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1654

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/validate_students_hash.py` |
| **Line Range** | 2 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/validate_students_hash.py:2, ./scripts/fix_teacher_id_nulls.py:7

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1655

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/validate_students_hash.py` |
| **Line Range** | 3 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/validate_students_hash.py:3, ./scripts/fix_teacher_id_nulls.py:8

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1656

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 120 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1657

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 126 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1658

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 150 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1659

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 159 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1660

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 26 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1661

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 42-172 |
| **Confidence** | High |

**Description:** Function `verify_migration_chain` is 131 lines long (max 75).

**Why This Matters:** Long functions are harder to read, test, and maintain.

### Finding #1662

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 70 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1663

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Structural Smell |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 90 |
| **Confidence** | High |

**Description:** Duplicated logic block detected in: ./scripts/verify_chain.py:90, ./scripts/verify_chain.py:124

**Why This Matters:** Duplicated code violates DRY principle and complicates maintenance.

### Finding #1664

| Property | Value |
|----------|-------|
| **Severity** | Medium |
| **Category** | Complexity |
| **File** | `./scripts/verify_chain.py` |
| **Line Range** | 94 |
| **Confidence** | High |

**Description:** Nesting depth > 3 detected.

**Why This Matters:** Deep nesting reduces readability and increases complexity.

### Finding #1665

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/__init__.py` |
| **Line Range** | 53 |
| **Confidence** | Medium |

**Description:** Found TODO/FIXME marker: # TODO: [DEPENDABOT PR #463] MarkupSafe 3.x introduces breaking changes:

**Why This Matters:** Incomplete code markers should be addressed or tracked.

### Finding #1666

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/attendance.py` |
| **Line Range** | 104 |
| **Confidence** | Low |

**Description:** Potential unused definition: `calculate_period_attendance`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1667

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/attendance.py` |
| **Line Range** | 185 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_session_status`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1668

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/auth.py` |
| **Line Range** | 432 |
| **Confidence** | Low |

**Description:** Potential unused definition: `can_access_student_routes`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1669

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/auth.py` |
| **Line Range** | 7 |
| **Confidence** | Low |

**Description:** Potential unused definition: `urllib.parse`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1670

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/demo_cleanup.py` |
| **Line Range** | 7 |
| **Confidence** | Low |

**Description:** Potential unused definition: `cleanup_demo_student_records`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1671

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/extensions.py` |
| **Line Range** | 13 |
| **Confidence** | Medium |

**Description:** Found TODO/FIXME marker: # TODO: [DEPENDABOT PR #648] Flask-Limiter 4.x introduces breaking changes:

**Why This Matters:** Incomplete code markers should be addressed or tracked.

### Finding #1672

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/forms.py` |
| **Line Range** | 57 |
| **Confidence** | Low |

**Description:** Potential unused definition: `validate_bundle_quantity`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1673

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/forms.py` |
| **Line Range** | 62 |
| **Confidence** | Low |

**Description:** Potential unused definition: `validate_bulk_discount_quantity`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1674

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/forms.py` |
| **Line Range** | 67 |
| **Confidence** | Low |

**Description:** Potential unused definition: `validate_bulk_discount_percentage`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1675

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/forms.py` |
| **Line Range** | 75 |
| **Confidence** | Low |

**Description:** Potential unused definition: `validate_collective_goal_type`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1676

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/forms.py` |
| **Line Range** | 80 |
| **Confidence** | Low |

**Description:** Potential unused definition: `validate_collective_goal_target`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1677

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 1260 |
| **Confidence** | Low |

**Description:** Potential unused definition: `blocks_list`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1678

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 1529 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_student_visible_status`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1679

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 1541 |
| **Confidence** | Low |

**Description:** Potential unused definition: `is_locked`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1680

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2004 |
| **Confidence** | Low |

**Description:** Potential unused definition: `mark_step_completed`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1681

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2013 |
| **Confidence** | Low |

**Description:** Potential unused definition: `is_step_completed`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1682

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2019 |
| **Confidence** | Low |

**Description:** Potential unused definition: `complete_onboarding`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1683

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2032 |
| **Confidence** | Low |

**Description:** Potential unused definition: `needs_onboarding`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1684

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2045 |
| **Confidence** | Low |

**Description:** Potential unused definition: `is_widget_task_completed`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1685

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2128 |
| **Confidence** | Low |

**Description:** Potential unused definition: `should_display`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1686

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2132 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_priority_class`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1687

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 2142 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_priority_icon`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1688

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 283 |
| **Confidence** | Low |

**Description:** Potential unused definition: `full_name`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1689

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 543 |
| **Confidence** | Low |

**Description:** Potential unused definition: `total_earnings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1690

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 552 |
| **Confidence** | Low |

**Description:** Potential unused definition: `recent_deposits`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1691

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 570 |
| **Confidence** | Low |

**Description:** Potential unused definition: `amount_needed_to_cover_bills`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1692

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 744 |
| **Confidence** | Medium |

**Description:** Potential unused definition: `_sync_transaction_amount_cents`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1693

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/models.py` |
| **Line Range** | 968 |
| **Confidence** | Low |

**Description:** Potential unused definition: `blocks_list`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1694

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1015 |
| **Confidence** | Low |

**Description:** Potential unused definition: `login`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1695

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1058 |
| **Confidence** | Low |

**Description:** Potential unused definition: `signup`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1696

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 130 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1697

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1303 |
| **Confidence** | Low |

**Description:** Potential unused definition: `recover`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1698

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 137 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1699

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1462 |
| **Confidence** | Low |

**Description:** Potential unused definition: `recovery_status`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1700

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1506 |
| **Confidence** | Low |

**Description:** Potential unused definition: `reset_credentials`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1701

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1676 |
| **Confidence** | Low |

**Description:** Potential unused definition: `save_recovery_progress`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1702

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1723 |
| **Confidence** | Low |

**Description:** Potential unused definition: `resume_credentials`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1703

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1764 |
| **Confidence** | Low |

**Description:** Potential unused definition: `setup_recovery`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1704

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 1838 |
| **Confidence** | Low |

**Description:** Potential unused definition: `logout`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1705

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2267 |
| **Confidence** | Low |

**Description:** Potential unused definition: `set_current_class`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1706

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2288 |
| **Confidence** | Low |

**Description:** Potential unused definition: `student_detail`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1707

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2414 |
| **Confidence** | Low |

**Description:** Potential unused definition: `set_hall_passes`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1708

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2431 |
| **Confidence** | Low |

**Description:** Potential unused definition: `edit_student`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1709

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2576 |
| **Confidence** | Medium |

**Description:** Potential commented-out code detected.

**Why This Matters:** Commented-out code rots and confuses readers. Use version control instead.

### Finding #1710

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2684 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_student`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1711

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2724 |
| **Confidence** | Low |

**Description:** Potential unused definition: `bulk_delete_students`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1712

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2753 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_block`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1713

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2803 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_join_code`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1714

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2831 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_pending_student`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1715

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2886 |
| **Confidence** | Low |

**Description:** Potential unused definition: `bulk_delete_pending_students`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1716

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2948 |
| **Confidence** | Low |

**Description:** Potential unused definition: `bulk_delete_legacy_unclaimed_students`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1717

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 2995 |
| **Confidence** | Low |

**Description:** Potential unused definition: `add_individual_student`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1718

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3148 |
| **Confidence** | Low |

**Description:** Potential unused definition: `add_manual_student`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1719

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3320 |
| **Confidence** | Low |

**Description:** Potential unused definition: `store_management`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1720

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3594 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1721

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3601 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1722

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3656 |
| **Confidence** | Low |

**Description:** Potential unused definition: `edit_store_item`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1723

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3685 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_store_item`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1724

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3704 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hard_delete_store_item`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1725

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 3909 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1726

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4043 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1727

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4414 |
| **Confidence** | Low |

**Description:** Potential unused definition: `add_rent_waiver`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1728

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4483 |
| **Confidence** | Low |

**Description:** Potential unused definition: `remove_rent_waiver`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1729

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4531 |
| **Confidence** | Low |

**Description:** Potential unused definition: `insurance_management`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1730

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4724 |
| **Confidence** | Low |

**Description:** Potential unused definition: `edit_insurance_policy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1731

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4792 |
| **Confidence** | Low |

**Description:** Potential unused definition: `deactivate_insurance_policy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1732

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4808 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_insurance_policy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1733

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4879 |
| **Confidence** | Low |

**Description:** Potential unused definition: `mass_remove_policy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1734

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4926 |
| **Confidence** | Low |

**Description:** Potential unused definition: `view_student_policy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1735

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 4950 |
| **Confidence** | Low |

**Description:** Potential unused definition: `process_claim`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1736

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 515 |
| **Confidence** | Medium |

**Description:** Potential unused definition: `_get_feature_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1737

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5181 |
| **Confidence** | Low |

**Description:** Potential unused definition: `void_transaction`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1738

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5481 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hall_pass_setup`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1739

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5490 |
| **Confidence** | Low |

**Description:** Potential unused definition: `economy_health`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1740

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 553 |
| **Confidence** | Medium |

**Description:** Potential unused definition: `_get_or_create_onboarding`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1741

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5732 |
| **Confidence** | Low |

**Description:** Potential unused definition: `run_payroll`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1742

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 5807 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1743

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6241 |
| **Confidence** | Low |

**Description:** Potential unused definition: `update_expected_weekly_hours`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1744

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6320 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_add_reward`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1745

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6349 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_delete_reward`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1746

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6365 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_add_fine`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1747

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6394 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_delete_fine`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1748

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6410 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_edit_reward`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1749

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6433 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_edit_fine`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1750

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6456 |
| **Confidence** | Low |

**Description:** Potential unused definition: `void_payroll_transaction`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1751

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6506 |
| **Confidence** | Low |

**Description:** Potential unused definition: `void_transactions_bulk`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1752

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6565 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_apply_reward`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1753

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6614 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_apply_fine`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1754

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6715 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll_manual_payment`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1755

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6832 |
| **Confidence** | Low |

**Description:** Potential unused definition: `attendance_log`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1756

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 6867 |
| **Confidence** | Low |

**Description:** Potential unused definition: `upload_students`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1757

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7038 |
| **Confidence** | Low |

**Description:** Potential unused definition: `download_csv_template`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1758

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7048 |
| **Confidence** | Low |

**Description:** Potential unused definition: `export_students`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1759

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7113 |
| **Confidence** | Low |

**Description:** Potential unused definition: `enforce_daily_limits`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1760

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 715 |
| **Confidence** | Low |

**Description:** Potential unused definition: `dashboard`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1761

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7187 |
| **Confidence** | Low |

**Description:** Potential unused definition: `tap_out_students`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1762

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7334 |
| **Confidence** | Low |

**Description:** Potential unused definition: `tap_in_students`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1763

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7433 |
| **Confidence** | Low |

**Description:** Potential unused definition: `bulk_update_hall_passes`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1764

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7518 |
| **Confidence** | Low |

**Description:** Potential unused definition: `banking`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1765

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7709 |
| **Confidence** | Low |

**Description:** Potential unused definition: `banking_settings_update`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1766

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7772 |
| **Confidence** | Low |

**Description:** Potential unused definition: `deletion_requests`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1767

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 7879 |
| **Confidence** | Low |

**Description:** Potential unused definition: `help_support`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1768

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8084 |
| **Confidence** | Low |

**Description:** Potential unused definition: `update_period_feature_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1769

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8137 |
| **Confidence** | Low |

**Description:** Potential unused definition: `copy_feature_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1770

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8282 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_create`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1771

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8357 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_edit`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1772

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8414 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_delete`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1773

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8447 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_toggle`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1774

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8483 |
| **Confidence** | Low |

**Description:** Potential unused definition: `onboarding_status`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1775

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8620 |
| **Confidence** | Low |

**Description:** Potential unused definition: `onboarding_skip`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1776

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8638 |
| **Confidence** | Low |

**Description:** Potential unused definition: `onboarding_skip_task`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1777

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8673 |
| **Confidence** | Low |

**Description:** Potential unused definition: `onboarding_dismiss_widget`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1778

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8702 |
| **Confidence** | Low |

**Description:** Potential unused definition: `onboarding_undismiss_widget`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1779

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8733 |
| **Confidence** | Low |

**Description:** Potential unused definition: `api_calculate_cwi`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1780

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8792 |
| **Confidence** | Low |

**Description:** Potential unused definition: `api_economy_analyze`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1781

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 8910 |
| **Confidence** | Low |

**Description:** Potential unused definition: `api_economy_validate`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1782

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 899 |
| **Confidence** | Low |

**Description:** Potential unused definition: `give_bonus_all`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1783

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9021 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_register_start`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1784

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9056 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_register_finish`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1785

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9093 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_auth_start`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1786

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9131 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_auth_finish`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1787

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9193 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_list`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1788

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9216 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_delete`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1789

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9239 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1790

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9254 |
| **Confidence** | Low |

**Description:** Potential unused definition: `issues_queue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1791

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9298 |
| **Confidence** | Low |

**Description:** Potential unused definition: `view_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1792

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9323 |
| **Confidence** | Low |

**Description:** Potential unused definition: `resolve_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1793

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/admin.py` |
| **Line Range** | 9398 |
| **Confidence** | Low |

**Description:** Potential unused definition: `escalate_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1794

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 203 |
| **Confidence** | Low |

**Description:** Potential unused definition: `dashboard`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1795

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 277 |
| **Confidence** | Low |

**Description:** Potential unused definition: `api_snapshot`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1796

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 333 |
| **Confidence** | Low |

**Description:** Potential unused definition: `api_alerts`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1797

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 385 |
| **Confidence** | Low |

**Description:** Potential unused definition: `acknowledge_alert`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1798

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/analytics.py` |
| **Line Range** | 454 |
| **Confidence** | Low |

**Description:** Potential unused definition: `student_drill_down`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1799

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1037 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1800

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1111 |
| **Confidence** | Low |

**Description:** Potential unused definition: `handle_hall_pass_action`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1801

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1215 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_active_hall_passes`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1802

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1304 |
| **Confidence** | Low |

**Description:** Potential unused definition: `lookup_hall_pass`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1803

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1415 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hall_pass_terminal_use`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1804

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1466 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hall_pass_terminal_return`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1805

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1513 |
| **Confidence** | Low |

**Description:** Potential unused definition: `cancel_hall_pass`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1806

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1536 |
| **Confidence** | Low |

**Description:** Potential unused definition: `checkout_hall_pass`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1807

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 158 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_tips`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1808

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1591 |
| **Confidence** | Low |

**Description:** Potential unused definition: `checkin_hall_pass`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1809

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1640 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_hall_pass_queue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1810

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1825 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hall_pass_history`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1811

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1934 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_hall_pass_setup`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1812

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 1959 |
| **Confidence** | Low |

**Description:** Potential unused definition: `save_hall_pass_setup`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1813

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2035 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_available_hall_pass_types`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1814

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2064 |
| **Confidence** | Low |

**Description:** Potential unused definition: `attendance_history`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1815

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2197 |
| **Confidence** | Low |

**Description:** Potential unused definition: `handle_tap`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1816

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 224 |
| **Confidence** | Low |

**Description:** Potential unused definition: `purchase_item`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1817

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2300 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1818

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2336 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1819

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2577 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_tap_entries`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1820

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2648 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_tap_entry`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1821

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2685 |
| **Confidence** | Low |

**Description:** Potential unused definition: `update_student_block_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1822

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2893 |
| **Confidence** | Low |

**Description:** Potential unused definition: `student_status`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1823

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2921 |
| **Confidence** | Low |

**Description:** Potential unused definition: `set_timezone`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1824

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2937 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1825

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2954 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1826

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2970 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1827

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 2996 |
| **Confidence** | Low |

**Description:** Potential unused definition: `create_demo_student`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1828

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 3127 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_block_tap_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1829

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 3178 |
| **Confidence** | Low |

**Description:** Potential unused definition: `update_block_tap_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1830

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 3245 |
| **Confidence** | Low |

**Description:** Potential unused definition: `view_as_student_status`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1831

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 462 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1832

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 773 |
| **Confidence** | Low |

**Description:** Potential unused definition: `use_item`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1833

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/routes/api.py` |
| **Line Range** | 861 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1834

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 914 |
| **Confidence** | Low |

**Description:** Potential unused definition: `approve_redemption`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1835

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/api.py` |
| **Line Range** | 966 |
| **Confidence** | Low |

**Description:** Potential unused definition: `reject_redemption`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1836

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 195 |
| **Confidence** | Low |

**Description:** Potential unused definition: `index`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1837

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/docs.py` |
| **Line Range** | 201 |
| **Confidence** | Low |

**Description:** Potential unused definition: `view_doc`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1838

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 133 |
| **Confidence** | Low |

**Description:** Potential unused definition: `privacy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1839

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 139 |
| **Confidence** | Low |

**Description:** Potential unused definition: `terms`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1840

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 145 |
| **Confidence** | Low |

**Description:** Potential unused definition: `offline`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1841

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 152 |
| **Confidence** | Low |

**Description:** Potential unused definition: `service_worker`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1842

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 164 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hall_pass_terminal`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1843

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 170 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hall_pass_verification`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1844

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 176 |
| **Confidence** | Low |

**Description:** Potential unused definition: `hall_pass_queue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1845

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 184 |
| **Confidence** | Low |

**Description:** Potential unused definition: `debug_filters`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1846

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 190 |
| **Confidence** | Low |

**Description:** Potential unused definition: `switch_view`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1847

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 207 |
| **Confidence** | Low |

**Description:** Potential unused definition: `debug_admin_db_test`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1848

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 46 |
| **Confidence** | Low |

**Description:** Potential unused definition: `health_check`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1849

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/main.py` |
| **Line Range** | 57 |
| **Confidence** | Low |

**Description:** Potential unused definition: `health_check_deep`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1850

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/recovery.py` |
| **Line Range** | 142 |
| **Confidence** | Low |

**Description:** Potential unused definition: `verify_identity`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1851

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/recovery.py` |
| **Line Range** | 36 |
| **Confidence** | Low |

**Description:** Potential unused definition: `generate_reset_code`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1852

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/recovery.py` |
| **Line Range** | 75 |
| **Confidence** | Low |

**Description:** Potential unused definition: `landing`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1853

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/recovery.py` |
| **Line Range** | 82 |
| **Confidence** | Low |

**Description:** Potential unused definition: `account_lookup`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1854

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1091 |
| **Confidence** | Low |

**Description:** Potential unused definition: `dashboard`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1855

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1430 |
| **Confidence** | Low |

**Description:** Potential unused definition: `payroll`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1856

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1509 |
| **Confidence** | Low |

**Description:** Potential unused definition: `transfer`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1857

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 152 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_current_join_code`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1858

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1808 |
| **Confidence** | Low |

**Description:** Potential unused definition: `insurance_marketplace`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1859

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 1923 |
| **Confidence** | Low |

**Description:** Potential unused definition: `purchase_insurance`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1860

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2087 |
| **Confidence** | Low |

**Description:** Potential unused definition: `cancel_insurance`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1861

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2107 |
| **Confidence** | Low |

**Description:** Potential unused definition: `file_claim`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1862

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2334 |
| **Confidence** | Low |

**Description:** Potential unused definition: `view_policy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1863

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2366 |
| **Confidence** | Low |

**Description:** Potential unused definition: `shop`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1864

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2690 |
| **Confidence** | Medium |

**Description:** Potential unused definition: `_add_rent_period`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1865

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 2987 |
| **Confidence** | Low |

**Description:** Potential unused definition: `rent_pay`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1866

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Risk Pattern |
| **File** | `./app/routes/student.py` |
| **Line Range** | 331 |
| **Confidence** | Medium |

**Description:** Function `check_legacy_profile` has inconsistent return statements (mixed value/no-value).

**Why This Matters:** Inconsistent returns can lead to type errors and confusing behavior.

### Finding #1867

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 331 |
| **Confidence** | Low |

**Description:** Potential unused definition: `check_legacy_profile`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1868

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3412 |
| **Confidence** | Low |

**Description:** Potential unused definition: `login`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1869

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3511 |
| **Confidence** | Low |

**Description:** Potential unused definition: `demo_login`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1870

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3605 |
| **Confidence** | Low |

**Description:** Potential unused definition: `logout`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1871

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3635 |
| **Confidence** | Low |

**Description:** Potential unused definition: `switch_class`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1872

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3671 |
| **Confidence** | Low |

**Description:** Potential unused definition: `switch_period`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1873

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3710 |
| **Confidence** | Low |

**Description:** Potential unused definition: `help_support`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1874

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 373 |
| **Confidence** | Low |

**Description:** Potential unused definition: `complete_profile`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1875

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3740 |
| **Confidence** | Low |

**Description:** Potential unused definition: `submit_general_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1876

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3786 |
| **Confidence** | Low |

**Description:** Potential unused definition: `report_transaction_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1877

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3842 |
| **Confidence** | Low |

**Description:** Potential unused definition: `report_tap_event_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1878

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3901 |
| **Confidence** | Low |

**Description:** Potential unused definition: `verify_recovery`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1879

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 3972 |
| **Confidence** | Low |

**Description:** Potential unused definition: `dismiss_recovery`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1880

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 543 |
| **Confidence** | Low |

**Description:** Potential unused definition: `claim_account`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1881

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 793 |
| **Confidence** | Low |

**Description:** Potential unused definition: `create_username`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1882

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 837 |
| **Confidence** | Low |

**Description:** Potential unused definition: `setup_pin_passphrase`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1883

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/student.py` |
| **Line Range** | 878 |
| **Confidence** | Low |

**Description:** Potential unused definition: `add_class`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1884

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1083 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_teacher`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1885

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1179 |
| **Confidence** | Low |

**Description:** Potential unused definition: `user_reports`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1886

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1219 |
| **Confidence** | Low |

**Description:** Potential unused definition: `view_user_report`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1887

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1233 |
| **Confidence** | Low |

**Description:** Potential unused definition: `update_user_report`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1888

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1266 |
| **Confidence** | Low |

**Description:** Potential unused definition: `send_reward_to_reporter`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1889

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 128 |
| **Confidence** | Low |

**Description:** Potential unused definition: `auth_check`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1890

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1354 |
| **Confidence** | Low |

**Description:** Potential unused definition: `grafana_auth_check`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1891

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1402 |
| **Confidence** | Low |

**Description:** Potential unused definition: `grafana_proxy`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1892

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 159 |
| **Confidence** | Low |

**Description:** Potential unused definition: `login`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1893

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1610 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_create`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1894

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1660 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_edit`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1895

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1715 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_delete`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1896

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1743 |
| **Confidence** | Low |

**Description:** Potential unused definition: `announcement_toggle`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1897

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1800 |
| **Confidence** | Low |

**Description:** Potential unused definition: `view_escalated_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1898

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1823 |
| **Confidence** | Low |

**Description:** Potential unused definition: `start_review_escalated_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1899

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 1850 |
| **Confidence** | Low |

**Description:** Potential unused definition: `resolve_escalated_issue`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1900

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 190 |
| **Confidence** | Low |

**Description:** Potential unused definition: `logout`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1901

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 205 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_register_start`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1902

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 238 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_register_finish`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1903

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 275 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_auth_start`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1904

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 313 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_auth_finish`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1905

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 379 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_list`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1906

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 400 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_delete`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1907

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 423 |
| **Confidence** | Low |

**Description:** Potential unused definition: `passkey_settings`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1908

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 438 |
| **Confidence** | Low |

**Description:** Potential unused definition: `dashboard`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1909

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 474 |
| **Confidence** | Low |

**Description:** Potential unused definition: `logs`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1910

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 517 |
| **Confidence** | Low |

**Description:** Potential unused definition: `error_logs`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1911

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 556 |
| **Confidence** | Low |

**Description:** Potential unused definition: `logs_testing`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1912

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 577 |
| **Confidence** | Low |

**Description:** Potential unused definition: `network_activity`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1913

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 632 |
| **Confidence** | Low |

**Description:** Potential unused definition: `test_error_400`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1914

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 639 |
| **Confidence** | Low |

**Description:** Potential unused definition: `test_error_401`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1915

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 646 |
| **Confidence** | Low |

**Description:** Potential unused definition: `test_error_403`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1916

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 653 |
| **Confidence** | Low |

**Description:** Potential unused definition: `test_error_404`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1917

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 660 |
| **Confidence** | Low |

**Description:** Potential unused definition: `test_error_500`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1918

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 669 |
| **Confidence** | Low |

**Description:** Potential unused definition: `test_error_503`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1919

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 678 |
| **Confidence** | Low |

**Description:** Potential unused definition: `manage_admins`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1920

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 710 |
| **Confidence** | Low |

**Description:** Potential unused definition: `reset_teacher_totp`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1921

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 755 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_admin`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1922

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 826 |
| **Confidence** | Low |

**Description:** Potential unused definition: `manage_teachers`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1923

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 861 |
| **Confidence** | Low |

**Description:** Potential unused definition: `teacher_overview`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1924

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/routes/system_admin.py` |
| **Line Range** | 991 |
| **Confidence** | Low |

**Description:** Potential unused definition: `delete_period`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1925

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/claim_credentials.py` |
| **Line Range** | 8 |
| **Confidence** | Low |

**Description:** Potential unused definition: `annotations`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1926

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 1120 |
| **Confidence** | Low |

**Description:** Potential unused definition: `format_warnings_for_display`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1927

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Risk Pattern |
| **File** | `./app/utils/economy_balance.py` |
| **Line Range** | 699 |
| **Confidence** | Medium |

**Description:** Function `validate_insurance_value` has inconsistent return statements (mixed value/no-value).

**Why This Matters:** Inconsistent returns can lead to type errors and confusing behavior.

### Finding #1928

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/encryption.py` |
| **Line Range** | 26 |
| **Confidence** | Low |

**Description:** Potential unused definition: `process_bind_param`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1929

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/encryption.py` |
| **Line Range** | 33 |
| **Confidence** | Low |

**Description:** Potential unused definition: `process_result_value`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1930

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/utils/helpers.py` |
| **Line Range** | 17 |
| **Confidence** | Medium |

**Description:** Found TODO/FIXME marker: # TODO: [DEPENDABOT PR #463] MarkupSafe 3.x introduces breaking changes:

**Why This Matters:** Incomplete code markers should be addressed or tracked.

### Finding #1931

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/ip_handler.py` |
| **Line Range** | 16 |
| **Confidence** | Low |

**Description:** Potential unused definition: `urllib.request`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1932

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./app/utils/ip_handler.py` |
| **Line Range** | 167 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1933

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/ip_handler.py` |
| **Line Range** | 17 |
| **Confidence** | Low |

**Description:** Potential unused definition: `urllib.error`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1934

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/ip_handler.py` |
| **Line Range** | 214 |
| **Confidence** | Low |

**Description:** Potential unused definition: `get_request_info`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1935

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/join_code.py` |
| **Line Range** | 54 |
| **Confidence** | Low |

**Description:** Potential unused definition: `is_valid_join_code_format`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1936

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/money_guard.py` |
| **Line Range** | 1 |
| **Confidence** | Low |

**Description:** Potential unused definition: `annotations`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1937

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/money_guard.py` |
| **Line Range** | 8 |
| **Confidence** | Low |

**Description:** Potential unused definition: `check_financial_cooldown`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1938

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/name_utils.py` |
| **Line Range** | 101 |
| **Confidence** | Low |

**Description:** Potential unused definition: `fuzzy_match_last_name`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1939

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/turnstile.py` |
| **Line Range** | 7 |
| **Confidence** | Low |

**Description:** Potential unused definition: `urllib.request`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1940

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./app/utils/turnstile.py` |
| **Line Range** | 8 |
| **Confidence** | Low |

**Description:** Potential unused definition: `urllib.parse`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1941

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/add-github-actions-to-firewall.py` |
| **Line Range** | 15 |
| **Confidence** | Low |

**Description:** Potential unused definition: `urllib.request`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1942

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 57 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1943

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./scripts/analyze_migrations.py` |
| **Line Range** | 67 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1944

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/create-github-actions-firewall.py` |
| **Line Range** | 15 |
| **Confidence** | Low |

**Description:** Potential unused definition: `urllib.request`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1945

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/firewall_complete.py` |
| **Line Range** | 10 |
| **Confidence** | Low |

**Description:** Potential unused definition: `annotations`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1946

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/lint_migrations.py` |
| **Line Range** | 120 |
| **Confidence** | Low |

**Description:** Potential unused definition: `has_helper_function`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1947

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/pulsetic_firewall.py` |
| **Line Range** | 10 |
| **Confidence** | Low |

**Description:** Potential unused definition: `annotations`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1948

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 106 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

### Finding #1949

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 113 |
| **Confidence** | Low |

**Description:** Potential unused definition: `visit_Call`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1950

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 139 |
| **Confidence** | Low |

**Description:** Potential unused definition: `visit_If`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1951

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Dead Code |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 144 |
| **Confidence** | Low |

**Description:** Potential unused definition: `visit_FunctionDef`

**Why This Matters:** Unused code adds noise and cognitive load.

### Finding #1952

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Risk Pattern |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 235 |
| **Confidence** | Medium |

**Description:** Function `validate_migrations` has inconsistent return statements (mixed value/no-value).

**Why This Matters:** Inconsistent returns can lead to type errors and confusing behavior.

### Finding #1953

| Property | Value |
|----------|-------|
| **Severity** | Low |
| **Category** | Structural Smell |
| **File** | `./scripts/validate-migrations.py` |
| **Line Range** | 259 |
| **Confidence** | High |

**Description:** `pass` statement detected.

**Why This Matters:** Explicit `pass` should be avoided if possible, or replaced with docstrings/comments.

