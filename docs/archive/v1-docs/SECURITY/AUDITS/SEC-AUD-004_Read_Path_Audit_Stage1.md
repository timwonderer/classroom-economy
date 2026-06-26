# Stage 1 Read-Path Performance Audit

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SEC-AUD-004| 1.1 | 2026-03-08 | 1.0 |Normative|

**Date:** 2025-02-22
**Auditor:** Jules
**Scope:** Admin Dashboard, Student Roster, Payroll Management

## Executive Summary

The audit reveals critical performance bottlenecks in the read path, primarily driven by **N+1 query patterns** and an anti-pattern of **performing database writes during read operations**.

*   **Critical Finding**: Loading the Student Roster for 40 students triggers **1,225 SQL queries**.
*   **Critical Finding**: Calculating student balances triggers "Eager Settlement" writes (`INSERT`/`UPDATE` to `balance_cache`) during simple GET requests.
*   **High Impact**: Balance calculations are repeated hundreds of times per page load (248x aggregate queries on Roster page).

## Methodology

*   **Environment**: Local SQLite database seeded with 1 Admin, 40 Students, 3 Class Blocks, and ~2400 transactions/attendance records.
*   **Tooling**: Custom audit script capturing SQLAlchemy events.
*   **Metrics**: Total Query Count, Total DB Execution Time (SQLite).

## Detailed Findings

### 1. Student Roster Page (`/admin/students`)

*   **Total Queries**: 1,225 (!!!)
*   **DB Time**: ~47ms (SQLite - would be significantly higher on networked Postgres)
*   **Issues**:
    1.  **Balance Calculation N+1 (248x)**: The template iterates `blocks` -> `students` and calls `student.get_checking_balance` and `get_savings_balance`. Each call triggers a `SELECT SUM(...)` query.
    2.  **Writes on Read (62x)**: `get_checking_balance` calls `settle_balances` which attempts to insert/update `balance_cache` records. This locks rows and degrades concurrency.
    3.  **Lazy Loading**: `Transaction` loading triggers lazy loads if not properly joined.

### 2. Admin Dashboard (`/admin/`)

*   **Total Queries**: 402
*   **DB Time**: ~50ms
*   **Issues**:
    1.  **Attendance Status N+1 (62x)**: `SELECT tap_events.id ...` is executed for each student/block to determine active status or unpaid time.
    2.  **Entity Fetching N+1 (62x)**: `SELECT teacher_blocks.id ...` and `SELECT payroll_settings.id ...` are repeated for each loop iteration.
    3.  **Lazy Loading (40x)**: `SELECT students.id ...` triggered when accessing student attributes from transaction lists.

### 3. Payroll Page (`/admin/payroll`)

*   **Total Queries**: 260
*   **DB Time**: ~44ms
*   **Issues**:
    1.  **Attendance N+1 (62x)**: Similar to Dashboard, calculating unpaid time iterates repeatedly.
    2.  **Balance Aggregates (40x)**: `SELECT sum("transaction".amount)` repeated for each student.

## Cross-Page Metric Analysis

| Metric | Used In | Current Implementation | Issues |
| :--- | :--- | :--- | :--- |
| **Student Balance** | All Pages | `student.get_checking_balance()` | Triggers writes on read; N+1 aggregates. |
| **Active Status** | Dashboard, Students | Query latest `TapEvent` | N+1 query per student per block. |
| **Unpaid Minutes** | Dashboard, Payroll | `calculate_unpaid_attendance_seconds` | Iterates all tap events; complex logic in loop. |

## Recommendations (Ranked)

### Phase 1: Critical Fixes (High Impact, Low Risk)

1.  **Disable Eager Settlement on Read**:
    *   **Action**: Modify `get_checking_balance` to *never* call `settle_balances`. Settlement should only happen during write operations (ledger insertion) or async background tasks.
    *   **Impact**: Eliminates 62+ write queries per page load; massive concurrency improvement.

2.  **Batch Balance Calculation**:
    *   **Action**: Create a `BalanceReadModel` that fetches all balances for a teacher's students in a single query:
        ```sql
        SELECT student_id, join_code, account_type, SUM(amount)
        FROM transaction
        WHERE teacher_id = ?
        GROUP BY student_id, join_code, account_type
        ```
    *   **Impact**: Reduces queries from ~250 to 1 per page.

### Phase 2: Architectural Improvements

3.  **Attendance Read Model**:
    *   **Action**: Introduce `StudentBlock.current_status` (active/inactive) and `StudentBlock.last_tap_at` to avoid querying `TapEvents` table for simple status checks.
    *   **Impact**: Eliminates 62+ queries on Dashboard.

4.  **Eager Loading Optimization**:
    *   **Action**: Use `joinedload` for `Transaction.student` and `Student.items` where lists are displayed.
    *   **Impact**: Eliminates ~40 queries per page.

## Conclusion

The application suffers from severe "death by a thousand cuts" (N+1 queries). The most critical architectural flaw is the **write-on-read behavior** in the balance calculation logic. Fixing this and implementing batch fetching for balances will reduce query volume by >90%.
