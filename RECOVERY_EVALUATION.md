# Teacher Account Recovery Evaluation

## Overview
The "student-assisted" account recovery method allows a teacher to reset their credentials by validating their identity through a trusted network of students. This approach is designed to be "self-serve" (avoiding System Administrator intervention) while collecting minimal PII.

## Analysis

### ✅ Strengths
*   **Self-Serve & Autonomous:** Completely eliminates the need for IT support or System Administrator tickets, empowering the teacher to resolve lockouts immediately in the classroom.
*   **Minimal Data Collection:** Avoids storing sensitive recovery emails or phone numbers, adhering to strict privacy constraints.
*   **Contextual Security:** Relies on "something you have" (a class of students) and "something you know" (your roster structure), which is a unique and context-aware security factor.
*   **Distributed Trust:** By requiring multiple students to verify, the risk of a single compromised student account hijacking the teacher's account is mitigated (once the "one from each period" rule is enforced).

### ⚠️ Risks & Weaknesses
*   **Student Dependency:** Recovery is impossible if no students are available (e.g., summer break, empty classroom).
    *   *Mitigation:* This is considered acceptable as teachers typically create new accounts for new classes at the start of a school year.
*   **Collusion Risk:** Without strict enforcement of student diversity (different periods), a small group of colluding students in a single class could theoretically takeover a teacher's account if they guess the `dob_sum`. (Mitigated by the new enforcement logic).

## Identified Issues & Planned Fixes

### 1. Critical Bug: Username Lookup Failure
**Issue:** The current recovery logic attempts to find students using `hash_hmac(username, b'')` (empty salt). However, students created via the standard flow store a randomized `username_hash` (salted) and a deterministic `username_lookup_hash` (peopered).
**Impact:** The current code will fail to find any valid student accounts, rendering recovery impossible.
**Fix:** Update the query to filter by `username_lookup_hash`, matching the authentication logic used in `app/routes/student.py`.

### 2. Privacy: Plaintext PII (`dob_sum`)
**Issue:** The `dob_sum` (Sum of MM+DD+YYYY) is stored as a raw integer in the `admins` table.
**Impact:** If the database is compromised, this PII is exposed.
**Fix:**
*   Add `dob_sum_hash` (String) and `salt` (Binary) columns to the `Admin` model.
*   Migrate existing data by hashing the integer values.
*   Drop the plaintext `dob_sum` column.
*   Update `signup` and `recover` workflows to use the hashed value.

### 3. Security: Missing "One from Each Period" Enforcement
**Issue:** The form instructs teachers to select "one student from each class," but the backend only verifies that the students belong to the *same* teacher. It does not enforce class diversity.
**Impact:** A teacher could select just one student (or students from a single class), weakening the security model.
**Fix:**
*   Identify all active periods (blocks) associated with the teacher.
*   Verify that the set of blocks represented by the selected students fully covers the teacher's active blocks.
*   Enforce a minimum number of students equal to the number of active blocks.

### 4. Legacy Account Support
**Issue:** Teachers who created accounts before this update will have no `dob_sum` stored (since it was nullable or plaintext and now we require hashed), effectively locking them out of the recovery feature.
**Fix:**
*   Added logic to detect if `dob_sum_hash` is missing.
*   Added a dashboard prompt urging teachers to "Setup Account Recovery".
*   Implemented a self-serve flow to input and hash the DOB sum post-registration.

## Conclusion
The proposed solution is innovative and well-aligned with the privacy and self-serve goals. With the implementation of the fixes above—specifically the hashing of PII and the strict enforcement of roster diversity—the system will provide a secure and robust recovery mechanism without reliance on traditional contact methods.
