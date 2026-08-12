# SOP-DEV-002: Identity Domain Reconstruction Progress

| Date | Phase | Status | Commits |
|------|-------|--------|---------|
| 2026-08-09 | 0-4 | ✅ COMPLETE | 7a8c3650, 4e4bcd07, 88ab38e3 |
| 2026-08-09 | 5 (Spec) | ✅ COMPLETE | FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md |
| 2026-08-09 | 5b (Impl) | ✅ COMPLETE | app/services/identity/builders.py — 62 tests passing |
| 2026-08-11 | 6 (Surface Inventory) | ✅ COMPLETE | 15 surfaces inventoried; 10 REWIRED, 5 VERIFIED |
| 2026-08-11 | 7 (Rewire) | ✅ COMPLETE (read-model) | 14 files changed; 5 view models wired; 6 legacy vars removed |

---

## Executive Summary

The identity domain (DOM-IDEN) has completed **Phase 0 through Phase 7 (read-model)** of the SOP-DEV-002 Canonical Domain Reconstruction Workflow for BOTH student and teacher identities.

**Key Milestones:**
1. (2026-08-09) Teacher identity Phase 3-4 work completed (FEAT-IDEN-101 through 107)
2. (2026-08-09) Phase 5 Read Models specification and implementation completed (6 view models, 62 tests)
3. (2026-08-11) Phase 6-7 read-model wiring completed (15 surfaces inventoried; 10 REWIRED, 5 VERIFIED; 6 legacy template variables removed; no compatibility bridges)

**Status:** Phase 6-7 read-model surfaces complete. Mutation route rewiring (Phase 7b) deferred pending FEAT orchestration implementation. Ready for Phase 8 verification.

---

## Phases Completed

### ✅ Phase 0: Domain Boundary (Complete)

**Deliverable:** Domain boundary statement

**Documented:** Identity domain owns User, Seat, IdentityProfile; coordinates with Class Configuration for class scoping.

**Authority:** DOM-IDEN-001, DOM-IDEN-002, DOM-IDEN-005

**Status:** ✅ COMPLETE

---

### ✅ Phase 1: Canonical Truth (Complete)

**Deliverable:** Canonical truth table classifying stored, derived, display-only, and cross-domain reference state

**Defined:**
- **Stored facts:** User credentials, reset codes, seat claim artifacts, identity profiles
- **Derived facts:** Credential state (credentialed vs. uncredentialed), claim state (claimed vs. unclaimed)
- **Display-only:** Identity profile names (encrypted)
- **Cross-domain:** Reference to class_id (Class Configuration domain)

**Forbidden:**
- No DOB, email, or external identity linkage (per DOM-IDEN-002 §XI)
- No inference or merging of identities (per DOM-IDEN-005 §VII)
- No ledger/activity state on identity tables

**Status:** ✅ COMPLETE

---

### ✅ Phase 2: Canonical Persistence (Complete & Corrected)

**Deliverable:** Canonical table contract defining owned tables, required/forbidden fields, mutability, constraints

**Owned Tables:**
1. `users` (identity domain owns student-specific fields)
2. `seats` (all fields)
3. `identity_profiles` (all fields)

**Key Corrections Made (2026-08-09):**

1. **Field Name Fix:** `recovery_code*` → `reset_code*` in DOM-IDEN-002 Section VI
2. **Table Reference Fix:** Removed non-existent `user_recovery_tokens` reference
3. **Mutability Clarification:** Documented `username_hash` lifecycle (NULL → hash → recovery → NULL → hash)

**Mutability Semantics:**
- Credentials (pin_hash, passphrase_hash): NULL until activation, mutable during recovery
- Username hashes (username_hash, username_lookup_hash): Set during activation, cleared during recovery
- Reset codes (reset_code*): Mutable, single-use, 10-minute TTL
- Claim artifacts (roster_fingerprint, dedupe_code): Immutable after claim
- Session fields (current_session_*): Mutable, set at login

**Constraints:**
- `UNIQUE(user_id, class_id)` on seats
- `UNIQUE(class_id, roster_fingerprint, dedupe_code)` on seats
- `UNIQUE(username_hash)` on users
- Foreign keys: seats.user_id → users.id, seats.class_id → classes.class_id

**Authority Documents:**
- DOM-IDEN-001: Canonical Identity Model
- DOM-IDEN-002: Student Identity Architecture (v2.3, corrected)
- DOM-IDEN-005: Identity Binding and Lifecycle

**Status:** ✅ COMPLETE (Corrected)

---

### ✅ Phase 3: Primitive Operations (Complete & Expanded & Validated)

**Deliverable:** Primitive operation table defining all lawful reads and writes for BOTH student and teacher identities

**Student Mutation Primitives:**
- **M-001:** Claim Seat (unauthenticated, FEAT-IDEN-001)
- **M-002:** Setup Credentials (activate on user, FEAT-IDEN-002)
- **M-003:** Generate Reset Code (teacher action, FEAT-IDEN-003)
- **M-004:** Clear Credentials (recovery, FEAT-IDEN-004)
- **M-005:** Bind Authenticated User to New Class (TBD, FEAT-IDEN-005)

**Teacher Mutation Primitives (NEW):**
- **T-001:** Teacher Authenticate (TOTP challenge — separate auth FEAT)
- **T-002:** Enroll TOTP Secret (FEAT-IDEN-101)
- **T-003:** Enroll Passkey Credential (FEAT-IDEN-102)
- **T-004:** Initiate Teacher Recovery (FEAT-IDEN-103)
- **T-005:** Generate Student Recovery Code (FEAT-IDEN-104)
- **T-006:** Validate Teacher Recovery Codes (FEAT-IDEN-105)
- **T-007:** Update TOTP Secret (FEAT-IDEN-106)
- **T-008:** Revoke Passkey Credential (FEAT-IDEN-107)

**Read Primitives:**
- **R-001:** Resolve Canonical Context
- **R-002–012:** Student identity lookups (User, Seat, IdentityProfile, authorization checks, credential validation)
- **T-R-001–007:** Teacher identity lookups (TOTP validation, passkey enrollment check, recovery request status)

**Documents:** 
- `DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md` (v2.0 — expanded for both student and teacher)

**Validation:** Phase 3 Validation Audit (`DOM-IDEN-PHASE-3-VALIDATION_AUDIT_EXPANDED_20260809.md`)
- ✅ All student mutation primitives (M-001 through M-005) referenced correctly
- ✅ All teacher mutation primitives (T-001 through T-008) referenced correctly
- ✅ All read primitives (R-001 through R-012, T-R-001 through T-R-007) referenced correctly
- ✅ All table references correct (users, seats, identity_profiles, recovery_requests, student_recovery_codes, passkey_credentials)
- ✅ All field references exist and correctly specified in Phase 2
- ✅ Mutability semantics align with Phase 2
- ✅ Constraints correctly documented
- ✅ No cross-domain violations

**Status:** ✅ COMPLETE (Expanded & Validated for BOTH student and teacher)

---

### ✅ Phase 4: Legal Mutation Boundary (Complete & Expanded & Validated)

**Deliverable:** FEAT write contracts naming the one legal writer for each domain-owned table

**Student FEAT Specifications (Previously Created):**

1. **FEAT-IDEN-001 v2.0** (Remediated)
   - **Purpose:** Unauthenticated student seat claim
   - **Orchestrates:** M-001 (Claim Seat)
   - **Governs:** User creation, Seat binding, claim artifact scrubbing, context initialization
   - **Audit:** ACT-IDEN-001 (NEW_USER_CLAIMED)
   - **Security:** Identity inference prohibition enforced

2. **FEAT-IDEN-002 v1.0** (NEW)
   - **Purpose:** Student credential setup on uncredentialed user
   - **Orchestrates:** M-002 (Setup Credentials)
   - **Governs:** Username, PIN, and passphrase hashing; session field initialization
   - **Audit:** ACT-IDEN-002 (CREDENTIAL_ACTIVATED)
   - **Reused by:** Recovery flow (after M-004)

3. **FEAT-IDEN-003 v1.0** (NEW)
   - **Purpose:** Teacher-initiated reset code generation
   - **Orchestrates:** M-003 (Generate Reset Code)
   - **Governs:** Reset code generation, 10-minute TTL, single active code invariant
   - **Audit:** ACT-IDEN-003 (RESET_CODE_GENERATED)
   - **Authorization:** Teacher must have admin seat in class

4. **FEAT-IDEN-004 v1.0** (NEW)
   - **Purpose:** Student recovery code validation and credential clear
   - **Orchestrates:** M-004 (Clear Credentials for Recovery)
   - **Governs:** Code validation, credential clearing, session state prep for re-setup
   - **Audit:** ACT-IDEN-004 (CREDENTIALS_CLEARED_FOR_RECOVERY)
   - **Security:** Generic error messages (no user existence leaks)

**Teacher FEAT Specifications (NEW — 2026-08-09):**

5. **FEAT-IDEN-101 v1.0** (NEW)
   - **Purpose:** Teacher TOTP enrollment during setup
   - **Orchestrates:** T-002 (Enroll TOTP Secret)
   - **Governs:** TOTP secret generation, encryption, storage; QR code + backup codes display
   - **Audit:** ACT-IDEN-101 (TOTP_ENROLLED)
   - **Prerequisite:** None (initial TOTP setup)

6. **FEAT-IDEN-102 v1.0** (NEW)
   - **Purpose:** Teacher passkey enrollment (optional secondary factor)
   - **Orchestrates:** T-003 (Enroll Passkey Credential)
   - **Governs:** WebAuthn response parsing, credential storage, metadata preservation
   - **Audit:** ACT-IDEN-102 (PASSKEY_ENROLLED)
   - **Prerequisite:** TOTP already enrolled

7. **FEAT-IDEN-103 v1.0** (NEW)
   - **Purpose:** Teacher account recovery initiation (5-day TTL)
   - **Orchestrates:** T-004 (Initiate Teacher Recovery)
   - **Governs:** Recovery request creation, expiration calculation, student population check
   - **Audit:** ACT-IDEN-103 (RECOVERY_INITIATED)
   - **Authorization:** Teacher must have admin seat in class

8. **FEAT-IDEN-104 v1.0** (NEW)
   - **Purpose:** Student recovery code generation for teacher verification
   - **Orchestrates:** T-005 (Generate Student Recovery Code)
   - **Governs:** Code generation, hashing, one-time display, verification of class affiliation
   - **Audit:** ACT-IDEN-104 (CODE_GENERATED)
   - **Prerequisite:** Active recovery request (FEAT-IDEN-103)

9. **FEAT-IDEN-105 v1.0** (NEW)
   - **Purpose:** Teacher recovery code validation (all-or-nothing)
   - **Orchestrates:** T-006 (Validate Teacher Recovery Codes)
   - **Governs:** All-or-nothing code verification, status progression, code consumption
   - **Audit:** ACT-IDEN-105 (RECOVERY_VERIFIED)
   - **Security:** Generic error messages (which code is wrong NOT disclosed)

10. **FEAT-IDEN-106 v1.0** (NEW)
    - **Purpose:** Teacher TOTP secret update (immediate invalidation of old secret)
    - **Orchestrates:** T-007 (Update TOTP Secret)
    - **Governs:** New secret generation, old secret replacement, recovery completion
    - **Audit:** ACT-IDEN-106 (TOTP_UPDATED)
    - **Triggers:** Can be called as part of account recovery or proactive rotation

11. **FEAT-IDEN-107 v1.0** (NEW)
    - **Purpose:** Teacher passkey revocation
    - **Orchestrates:** T-008 (Revoke Passkey Credential)
    - **Governs:** Hard deletion of passkey credentials, ownership verification
    - **Audit:** ACT-IDEN-107 (PASSKEY_REVOKED)
    - **Security:** Cannot revoke last authentication factor (TOTP is mandatory)

**Validation:** 
- Phase 4 Validation Audit (Student) — `FEAT-IDEN-PHASE-4-VALIDATION_AUDIT.md`
  - ✅ FEAT-IDEN-001 through FEAT-IDEN-004 correctly orchestrate M-001 through M-004
- Phase 4 Validation Audit (Teacher) — `FEAT-IDEN-PHASE-4-VALIDATION_AUDIT-TEACHER.md` (NEW)
  - ✅ FEAT-IDEN-101 through FEAT-IDEN-107 correctly orchestrate T-002 through T-008
  - ✅ All FEATs use only Phase 3 primitives
  - ✅ Verification phases read-only, mutation phases atomic
  - ✅ Idempotency keys captured and used correctly
  - ✅ Audit events emitted with required fields
  - ✅ Security posture correct (generic error messages, no PII leaks)
  - ✅ All FEATs comply with DOM-IDEN-003 specifications
  - ✅ All FEATs comply with FEAT-CORE-000 constitutional directive

**Status:** ✅ COMPLETE (Expanded for teacher identity & Fully Validated)

---

### 📝 Phase 5: Read Models & Projections (SPECIFICATION)

**Deliverable:** View model contracts defining presentation-ready data structures for template consumption

**Status:** 📝 SPECIFICATION COMPLETE (2026-08-09)

**Specification Document:** `FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md`

**Analysis Source:** TEMPLATE_JINJA_INVENTORY.md (2026-08-06) — Template violation audit

**Key Findings:**

1. **Layout Templates (Highest Impact)** — Shared across ALL pages
   - `layout_admin.html` (53 vars, 98 tags, HIGH violation)
     - Violations: Direct ORM model access, conditional logic in template, unformatted display names
     - Required View Model: `AdminLayoutContextView`
   
   - `layout_student.html` (38 vars, 66 tags, HIGH violation)
     - Violations: Direct model access, uppercase filter applied in template
     - Required View Model: `StudentLayoutContextView`

2. **Setup Templates (One-Time Flows)**
   - `admin_signup_totp.html` (8 vars, 14 tags, MEDIUM violation)
     - Violations: Raw base64-encoded QR code, raw TOTP secret string
     - Required View Model: `TOTPSetupView` (output of FEAT-IDEN-101)
   
   - `student_account_claim.html` (14 vars, 14 tags, MEDIUM violation)
     - Violations: Raw encrypted identity fields
     - Required View Model: `AccountClaimView`

3. **Class Selection Templates (Navigation)**
   - `admin_select_class_context.html` (9 vars, 11 tags, MEDIUM violation)
     - Required View Model: `AdminClassSelectionView`
   
   - `student_select_class_context.html` (11 vars, 12 tags, MEDIUM violation)
     - Required View Model: `StudentClassSelectionView`

**View Models Defined (6 Total):**

| View Model | Consumer Template | Producer Responsibility |
|-----------|-------------------|------------------------|
| `AdminLayoutContextView` | layout_admin.html | All admin routes |
| `StudentLayoutContextView` | layout_student.html | All student routes |
| `TOTPSetupView` | admin_signup_totp.html | FEAT-IDEN-101 |
| `AccountClaimView` | student_account_claim.html | Student claim orchestration |
| `AdminClassSelectionView` | admin_select_class_context.html | Class selection route |
| `StudentClassSelectionView` | student_select_class_context.html | Class selection route |

**Critical Design Principles:**

1. **Immutability:** All view models are frozen dataclasses (no mutation post-creation)
2. **No ORM Leakage:** Only primitives (str, int, bool, list, dict) — never ORM objects
3. **Pre-Formatting:** All display fields pre-formatted in builders (no Jinja filters in templates)
4. **Producer Responsibility:** Builders belong to identity domain; routes assemble; templates consume
5. **Single Responsibility:** Each view model serves ONE consumer template (or shared layout)

**Implementation Roadmap:**

- Phase 5a: Define view model dataclasses ✅ (SPECIFICATION)
- Phase 5b: Implement builder functions (NEXT)
- Phase 5c: Verify template violations are eliminated (NEXT)
- Phase 6: Wire routes to use builders (FUTURE)

**Status:** 📝 SPECIFICATION (Ready for Phase 5b implementation)

---

## Commits

| Commit | Message |
|--------|---------|
| 7a8c3650 | docs: fix DOM-IDEN-002 field name and table reference inconsistencies |
| 4e4bcd07 | docs: clarify username_hash mutability lifecycle in DOM-IDEN-002 |
| 88ab38e3 | docs: create Phase 4 validation audit for FEAT-IDEN orchestration |

---

## Validation Documents Created

| Document | Purpose | Status |
|----------|---------|--------|
| `DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md` | Define all lawful reads and writes (student + teacher) | ✅ |
| `DOM-IDEN-PHASE-3-VALIDATION_AUDIT.md` | Validate Phase 3 against Phase 2 (student) | ✅ |
| `DOM-IDEN-PHASE-3-VALIDATION_AUDIT_EXPANDED_20260809.md` | Validate expanded Phase 3 (student + teacher) | ✅ |
| `FEAT-IDEN-PHASE-4-VALIDATION_AUDIT.md` | Validate Phase 4 FEATs against Phase 3 (student) | ✅ |
| `FEAT-IDEN-PHASE-4-VALIDATION_AUDIT-TEACHER.md` | Validate Phase 4 teacher FEATs against Phase 3 | ✅ |
| `DOM-IDEN-PHASE-2-VERIFICATION_AUDIT_20260809.md` | Verify Phase 2 schema (both student and teacher tables) | ✅ |
| `FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md` | Define view models for identity domain consumers (routes, templates) | ✅ SPECIFICATION |

---

## Critical Correction: Identity Domain Status (2026-08-09)

**The identity domain is ONE domain covering BOTH student AND teacher identities. They move through all phases together.**

### Phase 2 Verification (Completed 2026-08-09)

Phase 2 has now been verified to include both student and teacher tables:

✅ **Student Identity Tables & Fields (DOM-IDEN-002)**
- User credentials: pin_hash, passphrase_hash, reset_code*
- Seat claim artifacts: roster_fingerprint, dedupe_code, claim_*_hashes
- Session management: current_session_*

✅ **Teacher Identity Tables & Fields (DOM-IDEN-003)**
- User credentials: totp_secret_encrypted (TOTP 2FA)
- Recovery mechanism: recovery_requests + student_recovery_codes tables
- Optional auth: passkey_credentials table

**Phase 2 Audit Document:** `DOM-IDEN-PHASE-2-VERIFICATION_AUDIT_20260809.md`

### Phase 3-4 Teacher Identity (Completed 2026-08-09)

Phase 3-4 has now been expanded and completed for teacher identity:

✅ **Phase 3 Teacher Primitives (DOM-IDEN-PHASE-3_PRIMITIVE_OPERATIONS.md v2.0)**
- T-002 through T-008: Teacher mutation operations
- T-R-001 through T-R-007: Teacher read operations

✅ **Phase 4 Teacher FEATs (NEW)**
- FEAT-IDEN-101 through FEAT-IDEN-107: Teacher feature specifications
- All FEATs validated against Phase 3 primitives and DOM-IDEN-003

**Phase 3-4 Teacher Audit Documents:** 
- `DOM-IDEN-PHASE-3-VALIDATION_AUDIT_EXPANDED_20260809.md`
- `FEAT-IDEN-PHASE-4-VALIDATION_AUDIT-TEACHER.md`

**Unified Domain Status:** ✅ Both student and teacher identities fully specified through Phase 4. Ready for Phase 5.

---

## Outstanding Tasks

### Immediate (Before Phase 5)

1. ⏳ Create FEAT-IDEN-005 specification (Authenticated Class Binding)
   - Status: **REQUIRED BEFORE PROCEEDING**
   - Purpose: Orchestrate M-005 (Bind authenticated user to new class seat)
   - Governs: Class switching for credentialed users

2. ✅ Create Phase 3 Primitive Operations for BOTH student and teacher (COMPLETED 2026-08-09)
   - ✅ Phase 3 v2.0 expanded with teacher primitives (T-001 through T-008, T-R-001 through T-R-007)
   - ✅ Unified Phase 3 document now covers both student and teacher roles

3. ✅ Create Phase 4 FEATs for teacher operations (COMPLETED 2026-08-09)
   - ✅ FEAT-IDEN-101 through FEAT-IDEN-107 specifications created
   - ✅ Covers: TOTP setup, passkey enrollment, recovery, credential updates
   - ✅ All FEATs validated against Phase 3 primitives

### ✅ Phase 5 (Read Models and Projections) — SPECIFICATION COMPLETE

**Status:** 📝 SPECIFICATION (2026-08-09) — Ready for Phase 5b implementation

**Specification Document:** `FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md`

**6 View Models Defined:**
1. `AdminLayoutContextView` — Layout context for all admin pages
2. `StudentLayoutContextView` — Layout context for all student pages
3. `TOTPSetupView` — TOTP setup display (QR code, secret, backup codes)
4. `AccountClaimView` — Student claim flow display
5. `AdminClassSelectionView` — Class selection for teachers
6. `StudentClassSelectionView` — Class selection for students

**Phase 5b Implementation (Next):**
- Implement builder functions in `app/services/identity/builders.py`
- Test all view models with frozen dataclass validation
- Verify no ORM leakage, all display fields pre-formatted

**Phase 5c Verification (Next):**
- Audit each template to confirm view model fields satisfy requirements
- Eliminate all template violations (format filters, conditional logic, direct model access)

### ✅ Phase 6: Application Surface Inventory (Complete — Read Model Surfaces)

**Date:** 2026-08-11

Inventoried all identity-domain template surfaces from TEMPLATE_JINJA_INVENTORY.md:

| # | Surface | Template | Route/Provider | Type | Disposition |
|---|---------|----------|---------------|------|-------------|
| 1 | Teacher layout identity | `layout_admin.html` | `inject_admin_layout_view()` context processor | `OUTPUT` | `REWIRED` |
| 2 | Student layout identity | `layout_student.html` | `inject_student_layout_view()` context processor | `OUTPUT` | `REWIRED` |
| 3 | TOTP enrollment display | `admin_signup_totp.html` | `admin.signup()` route | `OUTPUT` | `REWIRED` |
| 4 | Teacher class selection | `admin_select_class_context.html` | `admin.select_class_context()` route | `ACTION` | `REWIRED` |
| 5 | Student class selection | `student_select_class_context.html` | `student.select_class_context()` route | `ACTION` | `REWIRED` |
| 6 | Teacher dashboard greeting | `admin_dashboard.html` | `inject_admin_layout_view()` context processor | `OUTPUT` | `REWIRED` |
| 7 | Student dashboard greeting | `student_dashboard.html` | `inject_student_layout_view()` context processor | `OUTPUT` | `REWIRED` |
| 8 | Admin students JS context | `admin_students.html` | `inject_admin_layout_view()` context processor | `CLIENT_JS` | `REWIRED` |
| 9 | Student rent class context | `student_rent.html` | `inject_student_layout_view()` context processor | `OUTPUT` | `REWIRED` |
| 10 | Student insurance class context | `student_insurance_marketplace.html` | `inject_student_layout_view()` context processor | `OUTPUT` | `REWIRED` |
| 11 | Student account claim | `student_account_claim.html` | `student.claim_account()` route | `ACTION` | `VERIFIED` |
| 12 | Login templates (3) | `admin_login.html`, `student_login.html`, `system_admin_login.html` | auth routes | `ACTION` | `VERIFIED` |
| 13 | Admin signup | `admin_signup.html` | `admin.signup()` route | `ACTION` | `VERIFIED` |
| 14 | Student credential setup | `student_create_username.html` | `student.setup_pin_passphrase()` route | `ACTION` | `VERIFIED` |
| 15 | Student verify recovery | `student_verify_recovery.html` | recovery route | `ACTION` | `VERIFIED` |

**Known Mutation Routes Requiring FEAT Rewire (Phase 7b — future):**
- `app/routes/student.py:claim_account()` — inline domain operations → FEAT-IDEN-001
- `app/routes/student.py:setup_pin_passphrase()` — inline domain operations → FEAT-IDEN-002
- `app/routes/student.py:add_class()` — blocked on FEAT-IDEN-005 spec
- `app/routes/recovery.py:generate_reset_code()` — inline domain operations → FEAT-IDEN-003
- `app/routes/recovery.py:account_lookup()` — inline domain operations → FEAT-IDEN-004

### ✅ Phase 7: Rewire, Remove, or Collapse (Complete — Read Model Surfaces)

**Date:** 2026-08-11

All 10 read-model surfaces rewired. 5 surfaces verified as already clean. No compatibility bridges.

**View models wired:**
| View Model | Provider | Consumers |
|------------|----------|-----------|
| `AdminLayoutContextView` | `inject_admin_layout_view()` | `layout_admin.html`, `admin_dashboard.html`, `admin_students.html` |
| `StudentLayoutContextView` | `inject_student_layout_view()` | `layout_student.html`, `student_dashboard.html`, `student_rent.html`, `student_insurance_marketplace.html` |
| `TOTPSetupView` | `admin.signup()` route | `admin_signup_totp.html` |
| `AdminClassSelectionView` | `admin.select_class_context()` route | `admin_select_class_context.html` |
| `StudentClassSelectionView` | `student.select_class_context()` route | `student_select_class_context.html` |
| `AccountClaimView` | (Phase 5 spec only) | No template violations to fix |

**Legacy variables removed from context processors:**
- `current_admin_display_name` — replaced by `admin_layout_view.teacher_display_name`
- `admin_current_class_context` — replaced by `admin_layout_view.*` fields
- `current_class_context` — replaced by `student_layout_view.*` fields
- `student_display_first_name` — replaced by `student_layout_view.student_display_first_name`
- `student_name` — replaced by `student_layout_view.student_display_full_name`
- `current_admin` — removed (unused)

**View model fields added during rewiring:**
- `AdminLayoutContextView.class_id` — needed by `admin_students.html` JS
- `StudentLayoutContextView.class_timezone` — needed by layout clock widget
- `StudentLayoutContextView.teacher_display_name` — needed by page header meta
- `StudentLayoutContextView.block_display` — needed by page header meta

**Mutation route rewiring status:** Deferred to Phase 7b (requires FEAT orchestration implementation, not view model wiring)

### Phases 8-10 (Verification, Legacy Deletion, Certification)

---

## Architecture Summary

### Student Identity Workflow

```
Initial Claim → Credential Setup → Authentication → Class Switching
FEAT-IDEN-001 → FEAT-IDEN-002 → Authenticate (R-009) → FEAT-IDEN-005

Student Recovery Workflow
FEAT-IDEN-003 (reset code) → FEAT-IDEN-004 (code validation) → FEAT-IDEN-002 (re-setup)
```

### Teacher Identity Workflow

```
TOTP Setup → Passkey Setup (Optional) → Authentication
FEAT-IDEN-101 → FEAT-IDEN-102 → Authenticate (TOTP + Passkey)

Teacher Recovery Workflow (5-day TTL)
FEAT-IDEN-103 (initiate) → FEAT-IDEN-104 (student codes) → FEAT-IDEN-105 (validate) → FEAT-IDEN-106 (reset TOTP)

Passkey Management
FEAT-IDEN-102 (enroll) → Use in auth → FEAT-IDEN-107 (revoke)
```

### Atomic Operations

- M-001 (Claim): Create User + Bind Seat + Initialize Context = atomic
- M-002 (Setup): Hash 4 credentials + Session fields = atomic
- M-003 (Reset Code): Generate code + Set 3 timestamp fields = atomic
- M-004 (Recovery): Clear 4 credential hashes + 3 code fields = atomic

### Security Guarantees

- Identity inference prohibited (no user search in M-001)
- Atomic credential clearing (M-004 clears all 4 hashes together)
- Generic error messages (no user existence leaks)
- Single-use reset codes (cleared immediately after use)
- Rate limiting documented for code generation and submission
- Session nonce for replay attack prevention

---

## Authority Alignment

**Constitutional Documents:**
- ✅ INV-CORE-000: Core Invariants (7 foundational principles observed)
- ✅ INV-ARC-008: Identity Resolution and Seat Scope
- ✅ INV-ARC-019: Identity and Ownership Model
- ✅ DOM-IDEN-001: Canonical Identity Model
- ✅ DOM-IDEN-002: Student Identity Architecture (v2.3)
- ✅ DOM-IDEN-005: Identity Binding and Lifecycle
- ✅ DOM-IDEN-006: Canonical Context Resolution
- ✅ FEAT-CORE-000: Feature Execution Constitutional Directive

**Compliance:** All specs validated against governing authority documents. No constitutional violations found.

---

## Phase Progress Matrix

| Phase | Document | Status | Scope | Audit | Commits |
|-------|----------|--------|-------|-------|---------|
| **0** | Domain Boundary | ✅ COMPLETE | Student + Teacher | N/A | 0 |
| **1** | Canonical Truth | ✅ COMPLETE | Student + Teacher | Implicit | 0 |
| **2** | Canonical Persistence | ✅ COMPLETE | Student + Teacher | Phase-2-Verification-Audit | 2 |
| **3** | Primitive Operations | ✅ COMPLETE | Student + Teacher | Phase-3-Validation-Audit-Expanded | 1 (create) |
| **4** | Legal Mutation Boundary (FEATs) | ✅ COMPLETE | Student + Teacher | Phase-4-Validation-Audit-Teacher (NEW) | 7 (FEAT-IDEN-101–107) |
| **5** | Read Models & Projections | ✅ COMPLETE (Spec+Impl) | 6 View Models | 62 tests passing | app/services/identity/builders.py |
| **6** | Application Surface Inventory | ✅ COMPLETE | 15 surfaces inventoried | 10 REWIRED, 5 VERIFIED | 2026-08-11 |
| **7** | Rewire, Remove, or Collapse | ✅ COMPLETE (read-model) | 14 files, 5 view models wired | 6 legacy vars removed | 5 mutation routes → Phase 7b |
| **8** | Verification | 📝 TODO | Integration Tests | 0 | 0 |
| **9** | Legacy Deletion | 📝 TODO | Cleanup | 0 | 0 |
| **10** | Certification Audit | 📝 TODO | Final Audit | 0 | 0 |

---

## Next Steps

1. **Phase 7b: Mutation Route Rewiring** (deferred)
   - Rewire `claim_account()`, `setup_pin_passphrase()`, recovery routes to call FEAT orchestration
   - Blocked on FEAT-IDEN-001/002/003/004 implementation (specs exist, orchestration layer pending)
   - FEAT-IDEN-005 (class binding) specification still needed

2. **Phase 8: Verification**
   - Route-level integration tests proving context processors inject view models correctly
   - Template render tests proving no `UndefinedError` on new view model fields
   - 62 builder unit tests already pass

3. **Phase 9: Legacy Deletion**
   - Remove `current_admin` variable (already removed from context processor, verify no consumers)
   - Audit for dead helper functions exposed by context processor merge

4. **Phase 10: Certification Audit**
   - Final DOM-IDEN compliance check per SOP-DEV-002a

---

## Notes

### What Went Well

1. ✅ Constitutional audit identified 7 violations in FEAT-IDEN-001 v1.0
2. ✅ Remediated all violations in v2.0
3. ✅ Created missing FEAT-IDEN-002/003/004 specifications (student)
4. ✅ Documented complete primitive operation table (Phase 3) for student
5. ✅ Discovered and fixed documentation inconsistencies in DOM-IDEN-002
6. ✅ Verified Phase 2 schema compliance for BOTH student and teacher tables (2026-08-09)
7. ✅ Expanded Phase 3 with teacher primitives (T-001 through T-008, T-R-001 through T-R-007)
8. ✅ Created comprehensive teacher FEATs (FEAT-IDEN-101 through FEAT-IDEN-107)
9. ✅ Validated all FEATs against Phase 3 and DOM-IDEN-003 specifications
10. ✅ Validated all phases against upstream authority for unified identity domain

### What Required Clarification

1. ⚠️ Field names: `recovery_code*` vs. `reset_code*` (resolved)
2. ⚠️ Table reference: `user_recovery_tokens` doesn't exist (resolved)
3. ⚠️ Mutability: `username_hash` lifecycle (resolved)

### Key Design Insights

1. **Unauthenticated vs. Authenticated:** M-001 (claim) is for new users; M-005 (class binding) is for existing users joining new class
2. **Credential Reuse:** FEAT-IDEN-002 is reused in both claim flow and recovery flow
3. **Atomicity:** All mutations are atomic per transaction; rollback on any failure
4. **Security:** Generic error messages prevent user existence leaks
5. **Identity Inference:** Strictly prohibited; each claim creates new User

---

**Milestone 1:** Phase 4 (Teacher Identity FEATs) completed 2026-08-09

**Milestone 2:** Phase 5 (Read Models & Projections) SPECIFICATION + IMPLEMENTATION completed 2026-08-09

**Status:** ✅ Phase 0-7 (read-model) COMPLETE — Ready for Phase 8 (Verification)

**Date:** 2026-08-09

**Auditor:** Claude Code

**Authority:** SOP-DEV-002 Canonical Domain Reconstruction Workflow v1.0

**Next Phase:** Phase 5 (Read Models and Projections) — View models for claim flow, credential setup, recovery, class binding
