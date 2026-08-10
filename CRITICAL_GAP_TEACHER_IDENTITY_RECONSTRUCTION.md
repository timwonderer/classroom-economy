# CRITICAL GAP: Teacher Identity Reconstruction Not Started

**Date Identified:** 2026-08-09  
**Severity:** HIGH  
**Status:** BLOCKING Phase 5+ for complete identity domain

---

## Summary

SOP-DEV-002 Phase 2-4 reconstruction has been completed for **student identity** (DOM-IDEN-002) but **teacher identity** (DOM-IDEN-003) has not yet begun Phase 2-4 work.

This creates an incomplete identity domain:
- ✅ Student identity: Phases 0-4 complete, validated, FEATs created (FEAT-IDEN-001–004)
- ⏳ Teacher identity: Phase 0-1 only, Phase 2-4 NOT STARTED

---

## Teacher Identity Complexity

DOM-IDEN-003 defines teacher identity with unique characteristics:

### Owned Tables (Not Yet Inventoried in Phase 2)
1. **`recovery_requests`** — Teacher-initiated recovery with 5-day TTL
2. **`student_recovery_codes`** — Student-assisted recovery verification
3. **`passkey_credentials`** — Passkey metadata (unified with sysadmin)

### Unique Authentication Model (No Phase 4 FEATs Yet)
- **TOTP** (required) — 2FA using encrypted seed
- **Passkey** (optional) — Biometric/security key auth
- **No PIN/passphrase** — Different from student model

### Unique Recovery Model (No Phase 3-4 Spec Yet)
- **Student-Assisted:** Students help verify teacher identity
- **Self-Serve:** No sysadmin involvement
- **5-Day TTL:** (vs. 10 minutes for students)
- **Multi-Code Validation:** Multiple students must provide codes (all-or-nothing)
- **Roster-Based:** Proves identity through class roster, not DOB or external ID

---

## Phase 2-4 Work Required for Teachers

### Phase 2: Canonical Persistence
**Status:** ⏳ TODO

Need to create schema contract for:
- `recovery_requests` table (constraints, TTL, state transitions)
- `student_recovery_codes` table (code generation, hashing, validation)
- `passkey_credentials` table (unified credential metadata)
- Teacher-specific fields on `users` (totp_secret_encrypted)
- Teacher-specific fields on `seats`

**Deliverable:** DOM-IDEN-PHASE-2-TEACHER schema specification

### Phase 3: Primitive Operations
**Status:** ⏳ TODO

Need to define:

**Mutation Primitives:**
- **T-001:** Teacher Authenticate (TOTP challenge)
- **T-002:** Enroll TOTP Secret (during teacher setup)
- **T-003:** Enroll Passkey Credential (optional)
- **T-004:** Initiate Teacher Recovery (create recovery_request)
- **T-005:** Generate Student Recovery Code (student action within teacher recovery)
- **T-006:** Validate Teacher Recovery Codes (submit all codes)
- **T-007:** Update TOTP Secret (credential change)
- **T-008:** Revoke Passkey Credential (remove passkey option)

**Read Primitives:**
- **T-R-001:** Get Teacher User
- **T-R-002:** Get Teacher Seat
- **T-R-003:** Validate TOTP Secret (check encrypted seed)
- **T-R-004:** Validate Passkey Enrollment (check if passkey enrolled)
- **T-R-005:** Get Active Recovery Request
- **T-R-006:** Get Student Recovery Codes (for active recovery)
- **T-R-007:** Validate Recovery Code Submission (check all codes)
- ... (and others)

**Deliverable:** DOM-IDEN-PHASE-3-PRIMITIVE_OPERATIONS-TEACHER.md

### Phase 4: Legal Mutation Boundary (FEATs)
**Status:** ⏳ TODO

Need to create FEAT specifications:

| FEAT | Purpose | Primitive |
|------|---------|-----------|
| FEAT-IDEN-101 | Teacher TOTP Setup | T-002 |
| FEAT-IDEN-102 | Teacher Passkey Enrollment | T-003 |
| FEAT-IDEN-103 | Initiate Teacher Recovery | T-004 |
| FEAT-IDEN-104 | Student Generate Recovery Code (for teacher) | T-005 |
| FEAT-IDEN-105 | Validate Teacher Recovery & Restore Access | T-006 |
| FEAT-IDEN-106 | Update TOTP Secret | T-007 |
| FEAT-IDEN-107 | Revoke Passkey | T-008 |

**Deliverables:** FEAT-IDEN-101 through FEAT-IDEN-107 specifications

---

## Why This Matters

### Incomplete Identity Domain

Currently:
- ✅ Student claim → credential setup → recovery workflow fully specified
- ❌ Teacher authentication (TOTP setup) → **NOT SPECIFIED**
- ❌ Teacher passkey management → **NOT SPECIFIED**
- ❌ Teacher recovery (student-assisted) → **NOT SPECIFIED**

### Blocking Subsequent Phases

**Phase 5 (Read Models):** Cannot define view models for teacher setup/recovery without Phase 3-4

**Phase 6 (Surface Inventory):** Cannot map teacher auth routes without Phase 4 FEATs

**Phase 7+ (Rewire Routes):** Cannot rewrite `app/routes/admin.py` teacher routes without Phase 4 FEATs

### Code Patterns Issue

Teacher identity routes likely perform domain operations inline (same as old student routes). Examples:
- TOTP enrollment
- Passkey registration
- Recovery request initiation
- Code verification

These need to be extracted into FEAT layer (Phase 4 work).

---

## Recommended Path Forward

### Option 1: Complete Identity Domain Reconstruction Now
1. Do Phase 2-4 for teacher identity (1-2 sessions)
2. Then proceed to Phase 5+ for entire identity domain
3. **Advantage:** Complete, consistent identity domain
4. **Disadvantage:** Delays Phase 5+ work

### Option 2: Defer Teacher Identity to Later Phase
1. Continue with student identity Phase 5+ (routing, etc.)
2. Come back to teacher identity Phase 2-4 in next cycle
3. **Advantage:** Makes progress on student workflows quickly
4. **Disadvantage:** Leaves identity domain incomplete temporarily

### Recommendation

**Complete teacher identity Phase 2-4 NOW** (before Phase 5) because:
1. Student identity already has Phase 2-4 done (similar effort for teachers)
2. Both workflows are part of same domain (DOM-IDEN)
3. Phase 5+ (read models) needs both to define complete view models
4. Teacher recovery is complex and needs careful SOP-DEV-002 rigor

---

## Estimated Effort

- **Phase 2 (Canonical Persistence):** 1 session (create schema contract for 3 tables)
- **Phase 3 (Primitive Operations):** 1 session (define 8 mutations + reads)
- **Phase 4 (FEAT Orchestration):** 1-2 sessions (create + validate 7 FEATs)
- **Validation audits:** 1 session (validate Phase 3 against Phase 2, Phase 4 against Phase 3)

**Total:** 4-5 sessions

---

## Files to Create

### Phase 2
- `DOM-IDEN-PHASE-2-TEACHER_CANONICAL_PERSISTENCE.md`

### Phase 3
- `DOM-IDEN-PHASE-3-PRIMITIVE_OPERATIONS-TEACHER.md`
- `DOM-IDEN-PHASE-3-VALIDATION_AUDIT-TEACHER.md`

### Phase 4
- `FEAT-IDEN-101_TEACHER_TOTP_SETUP.md`
- `FEAT-IDEN-102_TEACHER_PASSKEY_ENROLLMENT.md`
- `FEAT-IDEN-103_TEACHER_RECOVERY_INITIATION.md`
- `FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md`
- `FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md`
- `FEAT-IDEN-106_TEACHER_UPDATE_TOTP_SECRET.md`
- `FEAT-IDEN-107_TEACHER_REVOKE_PASSKEY.md`
- `FEAT-IDEN-PHASE-4-VALIDATION_AUDIT-TEACHER.md`

---

## Next Steps

**Decision Needed:** Should we complete teacher identity Phase 2-4 before proceeding to Phase 5?

If **YES:**
1. Create DOM-IDEN Phase 2 schema contract for teacher
2. Create DOM-IDEN Phase 3 primitive operations for teacher
3. Validate Phase 3 against Phase 2
4. Create FEAT-IDEN-101 through 107 specifications
5. Validate Phase 4 against Phase 3
6. Then proceed to Phase 5 (Read Models) for complete identity domain

If **NO:**
1. Document this as known gap
2. Continue with student identity Phase 5+ work
3. Schedule teacher identity Phase 2-4 for next cycle
4. Note: Phase 5+ deliverables will be student-only until teacher phase completes

---

**Status:** BLOCKING DECISION REQUIRED

**Identified By:** Claude Code (2026-08-09 session)

**Blocking:** Phase 5 (Read Models and Projections) — cannot fully define identity view models without teacher identity Phase 2-4
