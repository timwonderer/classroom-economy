# CRITICAL GAP: Teacher Identity Phase 3-4 NOT STARTED

**Date Identified:** 2026-08-09  
**Severity:** MEDIUM  
**Status:** BLOCKING Phase 5+ and downstream phases  
**Update:** Phase 2 now verified as COMPLETE for teacher identity (see below)

---

## Summary

SOP-DEV-002 Phase 2 (Canonical Persistence) has been **VERIFIED COMPLETE** for both student and teacher identity through comprehensive database audit. However, Phase 3-4 work remains incomplete for teacher identity.

**Current Status:**
- ✅ Student identity: Phases 0-4 complete, validated, FEATs created (FEAT-IDEN-001–004)
- ✅ Teacher identity: **Phase 2 NOW VERIFIED COMPLETE** (audit: DOM-IDEN-PHASE-2-VERIFICATION_AUDIT_20260809.md)
- ⏳ Teacher identity: **Phase 3-4 NOT STARTED** (Phase 3 has student-only primitives, Phase 4 missing teacher FEATs)

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
**Status:** ✅ COMPLETE (2026-08-09 Audit)

**Verified in Database:**
- ✅ `recovery_requests` table exists (user_id, status, expires_at for 5-day TTL)
- ✅ `student_recovery_codes` table exists (recovery_request_id, seat_id, class_id, code_hash)
- ✅ `passkey_credentials` table exists (user_id, credential_id, authenticator_name)
- ✅ Teacher-specific field on `users`: totp_secret_encrypted
- ✅ All FK constraints and relationships properly configured
- ✅ Immutability and cascading delete rules correct

**Deliverable:** ✅ DOM-IDEN-PHASE-2-VERIFICATION_AUDIT_20260809.md (created 2026-08-09)

### Phase 3: Primitive Operations (BLOCKED — Waiting for Unified Phase 3)
**Status:** ⏳ TODO

**Problem:** DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md currently defines only student primitives (M-001 through M-004). Teacher primitives are missing.

**Required Work:**
- Expand Phase 3 to define teacher mutation primitives:
  - **T-001:** Teacher Authenticate (TOTP challenge)
  - **T-002:** Enroll TOTP Secret (during teacher setup)
  - **T-003:** Enroll Passkey Credential (optional)
  - **T-004:** Initiate Teacher Recovery (create recovery_request)
  - **T-005:** Generate Student Recovery Code (student action within teacher recovery)
  - **T-006:** Validate Teacher Recovery Codes (submit all codes)
  - **T-007:** Update TOTP Secret (credential change)
  - **T-008:** Revoke Passkey Credential (remove passkey option)

- Expand Phase 3 to define teacher read primitives:
  - **T-R-001:** Get Teacher User
  - **T-R-002:** Get Teacher Seat
  - **T-R-003:** Validate TOTP Secret (check encrypted seed)
  - **T-R-004:** Validate Passkey Enrollment (check if passkey enrolled)
  - **T-R-005:** Get Active Recovery Request
  - **T-R-006:** Get Student Recovery Codes (for active recovery)
  - **T-R-007:** Validate Recovery Code Submission (check all codes)

**Deliverable:** Expand DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md with teacher primitives

### Phase 3: Primitive Operations (See above — Blocked on unification)

### Phase 4: Legal Mutation Boundary (FEATs)
**Status:** ⏳ TODO (Waiting for Phase 3 expansion)

**Required Work:** Create teacher FEAT specifications after Phase 3 primitives are defined

| FEAT | Purpose | Primitive | Status |
|------|---------|-----------|--------|
| FEAT-IDEN-101 | Teacher TOTP Setup | T-002 | ⏳ TODO |
| FEAT-IDEN-102 | Teacher Passkey Enrollment | T-003 | ⏳ TODO |
| FEAT-IDEN-103 | Initiate Teacher Recovery | T-004 | ⏳ TODO |
| FEAT-IDEN-104 | Student Generate Recovery Code (for teacher) | T-005 | ⏳ TODO |
| FEAT-IDEN-105 | Validate Teacher Recovery & Restore Access | T-006 | ⏳ TODO |
| FEAT-IDEN-106 | Update TOTP Secret | T-007 | ⏳ TODO |
| FEAT-IDEN-107 | Revoke Passkey | T-008 | ⏳ TODO |

**Deliverables:** FEAT-IDEN-101 through FEAT-IDEN-107 specifications (post-Phase 3)

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

### Situation Update (2026-08-09)

Phase 2 is now **VERIFIED COMPLETE** for both student and teacher. The identity domain is ONE domain, and both roles must proceed through remaining phases together.

### Option 1: Complete Phase 3-4 for Teacher Identity NOW
1. Expand Phase 3 primitives to include all teacher operations (T-001 through T-008, T-R-001 through T-R-007)
2. Create Phase 3 validation audit for unified Phase 3
3. Create Phase 4 FEATs (FEAT-IDEN-101 through FEAT-IDEN-107)
4. Create Phase 4 validation audit
5. Then proceed to Phase 5 for entire identity domain (student + teacher)
6. **Advantage:** Complete, consistent identity domain ready for Phase 5+
7. **Disadvantage:** Requires focused work on teacher Phase 3-4 (estimated 2-3 sessions)

### Option 2: Keep Student and Teacher Separate Through Phase 5+
1. Continue with student identity Phase 5+ (read models, surface inventory, rewiring)
2. Defer teacher identity Phase 3-4 to later
3. **Advantage:** Makes progress on student workflows quickly
4. **Disadvantage:** Violates the "one domain" principle; creates confusion about teacher routes/FEATs; blocks Phase 5 read models from being comprehensive

### Recommendation

**Complete teacher identity Phase 3-4 NOW** (before Phase 5) because:
1. Phase 2 is already done — the persistence layer is in place
2. Phase 3-4 work is now unblocked (can use existing primitives as template)
3. Phase 5+ (read models) needs BOTH student and teacher defined to create complete view models
4. Teacher recovery is complex — should follow SOP-DEV-002 rigor with proper phase separation
5. Identity domain is ONE — student and teacher must move together through all phases

---

## Estimated Effort (Updated 2026-08-09)

- **Phase 2 (Canonical Persistence):** ✅ COMPLETE (database audit confirms all tables/fields/constraints in place)
- **Phase 3 (Primitive Operations):** 1 session (expand existing Phase 3 to include teacher T-001 through T-008, T-R-001 through T-R-007)
- **Phase 3 Validation Audit:** 1 session (validate expanded Phase 3 against Phase 2 for both roles)
- **Phase 4 (FEAT Orchestration):** 1-2 sessions (create FEAT-IDEN-101 through FEAT-IDEN-107)
- **Phase 4 Validation Audit:** 1 session (validate Phase 4 FEATs against expanded Phase 3)

**Total for Remaining Work:** 4-5 sessions

---

## Files to Create (2026-08-09 Revision)

### Phase 2
- ✅ `DOM-IDEN-PHASE-2-VERIFICATION_AUDIT_20260809.md` (COMPLETED)

### Phase 3
- ✅ `DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md` (EXISTS — Student only)
- **TODO:** Expand with teacher primitives (T-001 through T-008, T-R-001 through T-R-007)
- **TODO:** `DOM-IDEN-PHASE-3-VALIDATION_AUDIT.md` (Re-audit after expansion)

### Phase 4
- **TODO:** `FEAT-IDEN-101_TEACHER_TOTP_SETUP.md`
- **TODO:** `FEAT-IDEN-102_TEACHER_PASSKEY_ENROLLMENT.md`
- **TODO:** `FEAT-IDEN-103_TEACHER_RECOVERY_INITIATION.md`
- **TODO:** `FEAT-IDEN-104_STUDENT_RECOVERY_CODE_GENERATION_FOR_TEACHER.md`
- **TODO:** `FEAT-IDEN-105_TEACHER_RECOVERY_CODE_VALIDATION.md`
- **TODO:** `FEAT-IDEN-106_TEACHER_UPDATE_TOTP_SECRET.md`
- **TODO:** `FEAT-IDEN-107_TEACHER_REVOKE_PASSKEY.md`
- **TODO:** `FEAT-IDEN-PHASE-4-VALIDATION_AUDIT-TEACHER.md`

---

## Next Steps

**Decision Point:** Phase 2 is now verified complete. Should we complete Phase 3-4 for teacher before Phase 5?

### Recommended Immediate Actions

1. ✅ **READ:** Review Phase 2 audit: `DOM-IDEN-PHASE-2-VERIFICATION_AUDIT_20260809.md`
2. ✅ **CONFIRM:** Phase 2 is complete — all tables/fields/constraints in place for both student and teacher
3. **DECIDE:** Proceed with Phase 3-4 for teacher (recommended) or defer to later

### If Proceeding with Phase 3-4 (Recommended)

1. Expand `DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md` with teacher primitives:
   - Add T-001 through T-008 (mutations)
   - Add T-R-001 through T-R-007 (reads)
   - Validate against Phase 2 schema

2. Create Phase 3 validation audit for unified domain

3. Create FEAT-IDEN-101 through FEAT-IDEN-107 specifications using expanded Phase 3 primitives

4. Create Phase 4 validation audit

5. Then proceed to Phase 5 (Read Models) with complete identity domain

### If Deferring Phase 3-4

1. Document as known gap
2. Continue with student identity Phase 5+ work
3. Schedule teacher identity Phase 3-4 for next cycle
4. Note: Phase 5+ read models will be student-only until teacher phase completes

---

**Status:** PHASE 2 VERIFIED ✅ — PHASE 3-4 DECISION REQUIRED

**Identified By:** Claude Code (2026-08-09 session, Phase 2 verification audit)

**Blocking:** Phase 5 (Read Models and Projections) — cannot define complete identity view models without Phase 3-4 for teacher
