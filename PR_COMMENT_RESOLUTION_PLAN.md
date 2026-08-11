# PR #1323 Comment Resolution Plan

## Critical Issues (Blocks Merge)

### Category 1: Seat Role Validation (Affects 7 FEAT specs)
**Issue:** All teacher FEATs validate `Seat.role = 'admin'` but codebase uses `role = 'teacher'`

Files affected:
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-101_TEACHER_TOTP_SETUP.md (line 63)
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-102_TEACHER_PASSKEY_ENROLLMENT.md (line 62)
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-106_TEACHER_UPDATE_TOTP_SECRET.md (line 63)
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-107_TEACHER_REVOKE_PASSKEY.md (line 59)

Fix: Change all `role = 'admin'` to `role = 'teacher'`

---

### Category 2: RecoveryRequest Status Enum Mismatch
**Issue:** Specs reference `status = 'in_progress'` which doesn't exist in RecoveryRequest enum

Valid enum values: `pending`, `verified`, `expired`, `cancelled`

Files affected:
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md
  - Line 114: Remove 'in_progress' transition
  - Line 145: Remove 'in_progress' from invariant
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md
  - Line 103: Remove 'in_progress' from status chain
  - Line 144: Remove 'in_progress' from invariant
  - Line 150: Remove 'in_progress' from active check

Fix: Use only `pending` and `verified` states, remove all 'in_progress' references

---

### Category 3: StudentRecoveryCode Schema Mismatch
**Issue:** Specs reference `student_recovery_codes.used_at` which doesn't exist

Actual schema fields: `verified_at`, `dismissed`

Files affected:
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md
  - Line 150: Replace used_at reference
  - Line 285: Remove used_at from checklist

Fix: Use existing schema fields or update to align with actual schema

---

### Category 4: RecoveryRequest Missing updated_at Field
**Issue:** FEAT-IDEN-103 specifies writing `updated_at` on insert but schema has no updated_at

Files affected:
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-103_TEACHER_RECOVERY_INITIATION.md (line 93)

Fix: Remove updated_at from insert specification or add to schema

---

### Category 5: Phase 5 Specification Sync
**Issue:** FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md doesn't match actual builder implementation

Files affected:
- [ ] docs/FEATURE-EXECUTION/FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md
  - Lines 66-140: AdminLayoutContextView field names don't match
  - Lines 209-230: TOTPSetupView field structure mismatch
  - Lines 339-397: SelectionView structure mismatch

Fix: Align spec with actual builder.py implementation

---

## Secondary Issues (Affects Quality)

### Category 6: Idempotency Protocols
- [ ] Define durable idempotency across FEAT-IDEN-001 through FEAT-IDEN-004
- [ ] Add idempotency record requirements

### Category 7: Field Ownership Corrections
- [ ] M-001/M-002 primitives: Correct User vs Seat field assignments
- [ ] Update audit matrix accordingly

### Category 8: Backup Code Lifecycle
- [ ] FEAT-IDEN-101, FEAT-IDEN-106: Define backup code hashing and validation

### Category 9: WebAuthn Binding
- [ ] FEAT-IDEN-102: Add ceremony binding validation
- [ ] Validate clientDataJSON.type and challenge matching

### Category 10: Recovery Quorum Snapshots
- [ ] FEAT-IDEN-103: Add recovery request class_id and seat snapshot

---

## Docstring Coverage
- [ ] Add missing docstrings to reach 80% coverage (currently 23.61%)

---

## Resolution Order
1. Fix seat role validation (5 min per file, 7 files)
2. Fix recovery status enum (5 min per file, 5 files)
3. Fix StudentRecoveryCode fields (3 min per file, 2 files)
4. Remove updated_at reference (2 min, 1 file)
5. Sync Phase 5 specification (15 min)
6. Add docstrings (10 min)
7. Address secondary issues (30 min total)

**Estimated total time: ~90 minutes**
