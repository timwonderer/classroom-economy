# CodeRabbit Comments - Resolution Plan (44 Comments)

## Priority 1: Critical Specification Updates (High Impact)

### Category 1A: Audit Artifact Cleanup (3 files)
**Issue:** Legacy FEAT-IDEN-001 recommendations and TODO statuses need to be marked as historical

Files affected:
- [ ] AUDIT_CLAIM_FLOW_20260809.md (lines 323-367)
- [ ] CONFORMANCE_CHAIN_COMPLETE_20260809.txt (lines 147-194)
- [ ] CRITICAL_GAP_TEACHER_IDENTITY_RECONSTRUCTION.md (lines 59-103)

**Fix:** Mark as historical, update to reflect Phase 5 completion

---

### Category 1B: DOM-IDEN Phase 3 Primitive Corrections (7 files)

#### M-004 Recovery Operation (Critical)
- [ ] DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md (lines 241-255)
- **Issue:** M-004 must not mutate Seat.claimed_at; require already-claimed seat
- **Fix:** Replace conditional write with failure on invalid seat state

#### R-010 Recovery Code Visibility (Critical)
- [ ] DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md (lines 1023-1048)
- **Issue:** Missing teacher + class context authorization check
- **Fix:** Add teacher and class verification before disclosing plaintext reset_code

#### TOTP Enrollment Pending States (Critical)
- [ ] DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md (lines 396-414, 671-689)
- **Issue:** TOTP enrollment lacks pending/confirmation separation
- **Fix:** Add pending enrollment state and atomic confirmation flow

#### Field Ownership Corrections (Critical)
- [ ] DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md (lines 64-76, 123-131)
- [ ] DOM-IDEN-PHASE-3-VALIDATION_AUDIT.md (lines 77-111)
- **Issue:** M-001/M-002 write to Seat.last_active_class_id (wrong model)
- **Fix:** Change to User.last_active_class_id, update validation matrix

#### Recovery Quorum Snapshots (Critical)
- [ ] DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md (lines 513-536, 619-653)
- **Issue:** Recovery lacks eligible seat snapshot for quorum validation
- **Fix:** Add recovery_class_id + seat snapshot in RecoveryRequest

#### Revocation Behavior (Important)
- [ ] DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md (lines 710-752)
- **Issue:** Conflicting hard delete vs soft delete for PasskeyCredential
- **Fix:** Choose one approach, document consistently

---

## Priority 2: FEAT Specification Refinements (Medium Impact)

### Category 2A: Idempotency Protocol (3 files)
- [ ] FEAT-IDEN-001_UNAUTHENTICATED_STUDENT_SEAT_CLAIM_REMEDIATED.md (lines 198-212)
- [ ] FEAT-IDEN-002_STUDENT_CREDENTIAL_SETUP.md (lines 182-196)
- [ ] FEAT-IDEN-PHASE-4-VALIDATION_AUDIT.md (lines 471-482)
- **Issue:** Lacks durable idempotency record definition
- **Fix:** Define atomic idempotency store with request matching

### Category 2B: WebAuthn Binding (2 files)
- [ ] FEAT-IDEN-102_TEACHER_PASSKEY_ENROLLMENT.md (lines 64-75, 98-106)
- **Issue:** WebAuthn validation missing ceremony binding checks
- **Fix:** Add clientDataJSON.type validation, challenge consumption, origin/RP ID verification

### Category 2C: Backup Code Lifecycle (2 files)
- [ ] FEAT-IDEN-101_TEACHER_TOTP_SETUP.md (lines 87-94, 157-159)
- [ ] FEAT-IDEN-106_TEACHER_UPDATE_TOTP_SECRET.md (lines 104-111)
- **Issue:** Backup code hashing and validation behavior undefined
- **Fix:** Define one-way hash persistence, used_at state tracking

### Category 2D: Seat Role Binding (5 files)
- [ ] FEAT-IDEN-101_TEACHER_TOTP_SETUP.md (lines 59-63)
- [ ] FEAT-IDEN-102_TEACHER_PASSKEY_ENROLLMENT.md (lines 64-75)
- [ ] FEAT-IDEN-103_TEACHER_RECOVERY_INITIATION.md (lines 52-55)
- [ ] FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md (lines 64-69)
- [ ] FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md (lines 49-54)
- **Issue:** Identity binding comparisons not fully qualified with field names
- **Fix:** Require Seat.user_id == user_id consistently across all FEATs

---

## Priority 3: Validation & Audit Documents (Lower Impact)

### Category 3A: Phase 3 Validation Updates
- [ ] DOM-IDEN-PHASE-3-VALIDATION_AUDIT.md (lines 48-51, 369-397)
- **Issue:** username_hash mutability and Phase 3 sign-off coverage incomplete
- **Fix:** Update to cover teacher primitives T-001 through T-008, T-R-001 through T-R-007

### Category 3B: Phase 4-5 Status Sync
- [ ] FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md (lines 493-510)
- [ ] IDENTITY_PHASE5_COMPLETION_SUMMARY_20260809.md (lines 179-203, 325-326)
- [ ] SOP-DEV-002_IDENTITY_DOMAIN_COMPLETION_20260809.md (lines 13-20, 507-524)
- **Issue:** Phase 5b completion not reflected in status docs
- **Fix:** Mark Phase 5b as complete, Phase 6 as next step

### Category 3C: Phase 4 Audit Matrix Updates
- [ ] FEAT-IDEN-PHASE-4-VALIDATION_AUDIT-TEACHER.md (lines 80-91, 124-137, 323-337, 359-373, 466-472)
- **Issue:** Incomplete audit coverage for teacher FEATs
- **Fix:** Add failure outcomes, concurrency controls, test coverage requirements

---

## Priority 4: Code Quality Improvements (Low Impact)

### Category 4A: Docstring Coverage
- [ ] app/services/identity/builders.py (dataclass docstrings)
- **Issue:** Docstring coverage 23.61%, need 80%
- **Fix:** Add field-level docstrings to all dataclasses

### Category 4B: Documentation Artifacts
- [ ] DOM-IDEN-PHASE-2-VERIFICATION_AUDIT_20260809.md (lines 27-44, 48-65, 183-201)
- [ ] FEAT_IDEN_REMEDIATION_ROADMAP.md (lines 13-22)
- **Issue:** Schema documentation misalignments, hardcoded paths
- **Fix:** Update seats schema docs, remove hardcoded locations

---

## Resolution Order (Recommended)

1. **Week 1 (Priority 1):** Critical primitives and audit cleanup
   - M-004, R-010, TOTP pending states (3-4 hours)
   - Field ownership corrections (2 hours)
   - Recovery quorum snapshots (2 hours)
   - Revocation behavior decision (1 hour)

2. **Week 2 (Priority 2):** FEAT refinements
   - Idempotency protocol (2 hours)
   - WebAuthn binding (2 hours)
   - Backup code lifecycle (1 hour)
   - Seat role binding consistency (1 hour)

3. **Week 3 (Priority 3):** Validation and status
   - Phase 3 validation updates (2 hours)
   - Phase 4-5 status sync (1 hour)
   - Phase 4 audit matrix (2 hours)

4. **Week 4 (Priority 4):** Code quality
   - Docstring coverage (1 hour)
   - Documentation cleanup (1 hour)

**Total estimated effort:** 20-24 hours

---

## Risk Assessment

**High Risk:**
- Field ownership changes (affects multiple primitives)
- Revocation behavior choice (affects implementation)

**Medium Risk:**
- Quorum snapshot addition (schema impact)
- Idempotency protocol (distributed systems complexity)

**Low Risk:**
- Documentation updates
- Status synchronization
