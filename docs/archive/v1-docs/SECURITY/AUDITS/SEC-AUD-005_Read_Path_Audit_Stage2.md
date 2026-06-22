# Stage 2: Read-Path Re-Audit & Optimization Report

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SEC-AUD-005| 1.1 | 2026-03-08 | 1.0 |Normative|

**Date:** 2025-02-22
**Focus:** Verification of Read-Path Optimizations (Balance Service & Write-on-Read Removal)

## 1. Executive Summary

Following the Stage 1 audit which identified severe N+1 query patterns and a critical "Write-on-Read" side-effect in the financial ledger, a series of optimizations were implemented.

**Key Achievements:**
*   **Write-on-Read Eliminated:** The `Student.checking_balance` and `Student.savings_balance` properties no longer trigger database writes (`settle_balances`). This prevents accidental ledger mutation during simple GET requests.
*   **Roster Page Scalability:** Query count for the Student Roster page was reduced by **99.2%** (1,225 -> 10 queries for 60 students).
*   **Payroll Page Improvement:** Query count for the Payroll page was reduced by **29%** (260 -> 184 queries).

## 2. Methodology

*   **Tools:** Custom `audit_queries.py` script using SQLAlchemy event listeners to count queries.
*   **Dataset:** Synthetic dataset with 3 classes, 60 students, and ~3,000 transactions (50 transactions per student).
*   **Environment:** SQLite (local).

## 3. Comparative Results

| Page | Metric | Stage 1 (Baseline) | Stage 2 (Optimized) | Change |
| :--- | :--- | :--- | :--- | :--- |
| **Student Roster** | Queries | 1,225 | **10** | **-99.2%** |
| | DB Time | ~450ms | ~3ms | -99% |
| **Payroll** | Queries | 260 | **184** | **-29.2%** |
| | DB Time | ~120ms | ~40ms | -66% |
| **Admin Dashboard** | Queries | 402 | 402 | 0% (Out of Scope) |

## 4. Technical Implementation

### 4.1. Disable Write-on-Read
The `Student` model's hybrid properties for balances previously called `self.settle_balances()`, which could create transaction records. This was removed.
*   **Change:** `app/models.py` properties now only sum existing transactions in memory or via simple SQL if not loaded.
*   **Safeguard:** Added `g.read_only` flag in `app/routes/admin.py` and a check in `app/utils/banking.py` to strictly forbid `settle_balances` during GET requests.

### 4.2. BalanceService (Batching)
Introduced `app/services/balance_service.py` to fetch financial data in bulk.
*   **Old Way:** Loop through students -> `student.checking_balance` -> SQL Query (N+1).
*   **New Way:**
    ```python
    # Single query to get all balances for a join_code
    balances = BalanceService.get_balances_for_class(join_code)
    # Map back to students in memory
    ```

### 4.3. Route Refactoring
*   **`admin.students`:** Refactored to use `BalanceService`. The template now receives a `balances` dictionary keyed by `student_id`.
*   **`admin.payroll`:** Refactored to batch fetch `total_earned` and `last_payroll_date` using `db.session.query` with `GROUP BY`, eliminating the loop queries for these metrics.

## 5. Remaining Issues & Future Work

While financial N+1 queries are resolved, the audit revealed remaining N+1 patterns related to other domains:

1.  **Attendance (Payroll & Dashboard):**
    *   The Payroll page still executes ~60 queries for `SELECT attendance ...`.
    *   **Recommendation:** Eager load `student.attendance` or create an `AttendanceService` for batch counting.

2.  **Dashboard Performance:**
    *   The dashboard remains heavy (400+ queries).
    *   **Culprits:** `teacher_block` lookups and `tap_events` loading for every student.
    *   **Recommendation:** Apply similar batching strategies to the Dashboard route in a future sprint.

## 6. Conclusion

The critical performance bottlenecks affecting the financial read-path have been resolved. The application is now safer (no side-effects on reads) and significantly more scalable for large classes.
