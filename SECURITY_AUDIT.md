# Security Audit Report

**Date:** 2025-02-19
**Auditor:** Jules

This report outlines security vulnerabilities and risks identified during the audit of the Classroom Token Hub codebase. Findings are categorized by priority (Critical, High, Medium, Low).

## Critical Priority

### 1. Dangerous Data Deletion in System Admin
**File:** `app/routes/system_admin.py`
**Line:** 317 (inside `delete_admin`)
**Description:**
The `delete_admin` function (lines 292-328) contains a catastrophic data loss vulnerability. When a system administrator deletes a single admin (teacher) account, the code executes `Student.query.delete()`, which deletes **ALL** students in the entire database, not just the students associated with the deleted admin.

```python
# app/routes/system_admin.py:317
Student.query.delete()
```
**Recommendation:**
Replace this with a scoped deletion that only targets students owned by the deleted admin. However, given multi-tenancy requirements, it is safer to reassign students or implement soft-deletion. Ensure `Student.query.filter_by(teacher_id=admin.id).delete()` is used if deletion is intended.

## High Priority

### 2. DoS Vector in Student Login
**File:** `app/routes/student.py`
**Line:** 1559 (inside `login`)
**Description:**
The student login process (lines 1532-1588) iterates through **all** students who have a username hash set. For each student, it performs an HMAC operation (`hash_username`) to check for a match. This O(N) operation with cryptographic overhead is a Denial of Service (DoS) vector. As the student database grows, login response times will degrade significantly, and concurrent login attempts could exhaust server CPU resources.

```python
# app/routes/student.py:1559
candidate_hash = hash_username(username, s.salt)
```
**Recommendation:**
Implement a deterministic lookup mechanism. Store a separate deterministic hash (e.g., SHA256 of username + global pepper) for indexing and lookup, while keeping the salt for password/credential hashing. Alternatively, enforce rate limiting strictly.

## Medium Priority

### 3. CSV Injection Vulnerability
**File:** `app/routes/admin.py`
**Line:** 2956 (inside `export_students`)
**Description:**
The `export_students` function exports student data to CSV. It writes the `first_name` and other fields directly to the CSV file without sanitization. If a student's name begins with special characters like `=`, `@`, `+`, or `-`, it could be interpreted as a formula by spreadsheet software (Excel, Google Sheets) when an admin opens the file, potentially leading to command execution on the admin's machine.

```python
# app/routes/admin.py:2956
writer.writerow([
    student.first_name,
    # ...
])
```
**Recommendation:**
Sanitize fields before writing to CSV. Prepend a single quote `'` to any field starting with `=`, `@`, `+`, or `-` to force it to be treated as text.

### 4. Inefficient Bulk Operations (Performance Risk)
**File:** `app/routes/admin.py`
**Lines:** 693 (`bulk_delete_students`), 803 (`delete_block`)
**Description:**
Bulk deletion operations iterate through students and issue individual delete queries for related records (Transactions, TapEvents, etc.). This "N+1" query pattern for deletion is inefficient and may cause timeouts when deleting blocks with many students.

**Recommendation:**
Use database-level `ON DELETE CASCADE` constraints or bulk delete queries (e.g., `Transaction.query.filter(Transaction.student_id.in_(student_ids)).delete()`) to improve performance.

## Low Priority

### 5. Sensitive Information in Logs / Inefficient Log Viewing
**File:** `app/routes/system_admin.py`
**Line:** 105 (`logs`)
**Description:**
The `/sysadmin/logs` route reads the raw `app.log` file. If any PII or secrets are inadvertently logged by the application, they will be exposed here. Additionally, `f.readlines()` reads the entire file into memory, which can cause memory exhaustion if the log file is large.

**Recommendation:**
Ensure strict logging policies to prevent PII/secrets from being logged. Use `seek` to read only the tail of the file without loading the entire content into memory.

### 6. Missing Explicit Session Cookie Settings
**File:** `app/__init__.py`
**Description:**
While `SESSION_COOKIE_SECURE` is set to `True`, `SESSION_COOKIE_HTTPONLY` is not explicitly set (though Flask defaults to True).

**Recommendation:**
Explicitly set `SESSION_COOKIE_HTTPONLY = True` in `app.config` to prevent JavaScript access to session cookies, mitigating XSS risks.
