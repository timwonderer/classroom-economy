# Identity Domain Phase 5 Completion Summary

**Date:** 2026-08-09  
**Phase:** 5 of 10 (SOP-DEV-002)  
**Status:** ✅ SPECIFICATION COMPLETE

---

## What Was Done

### Phase 5: Read Models & Projections (Specification)

Phase 5 transforms Phase 4 FEAT outputs into presentation-ready view models for consumer layers (routes, templates). This phase defines **6 frozen dataclasses** that eliminate all template violations and enforce immutability.

**Specification Document:** `FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md`

---

## Key Findings from Template Audit

Using the **TEMPLATE_JINJA_INVENTORY.md** (2026-08-06), we identified 6 identity templates requiring view models:

### Layout Templates (Highest Priority)
These are shared across ALL pages — violations affect every page.

#### 1. layout_admin.html (53 vars, 98 tags, HIGH violation)
**Current Violations:**
- Line 97: `{% if admin_current_class_context and admin_current_class_context.class_timezone != 'UTC' %}...`
  - **Issue:** Conditional logic in template (domain authority)
- Line 102: `{{ current_admin_display_name|upper }}`
  - **Issue:** Formatting (uppercase) applied in template, not pre-formatted
- Lines 106-107: `{{ admin_current_class_context.class_identifier }}`, `{{ admin_current_class_context.join_code }}`
  - **Issue:** Direct ORM model access

**Solution View Model:** `AdminLayoutContextView`
```python
@dataclass(frozen=True)
class AdminLayoutContextView:
    teacher_display_name: str  # Pre-formatted uppercase
    has_class_context: bool    # Conditional (prevents template logic)
    class_timezone: str        # Only if has_class_context
    class_display_name: str    # Pre-formatted
    class_join_code: str       # Pre-formatted
```

#### 2. layout_student.html (38 vars, 66 tags, HIGH violation)
**Current Violations:**
- Line 104: `{{ current_class_context.student_full_name|upper }}`
  - **Issue:** Direct model access + uppercase filter
- Lines 108-109: `{{ student_display_first_name }}`, `{{ student_display_last_initial }}`
  - **Issue:** Unformatted names from route (should be pre-formatted)

**Solution View Model:** `StudentLayoutContextView`
```python
@dataclass(frozen=True)
class StudentLayoutContextView:
    student_display_full_name: str  # Pre-formatted uppercase
    student_display_first_name: str  # Pre-formatted
    student_display_last_initial: str  # Pre-formatted
    has_class_context: bool
    class_display_name: str
```

---

### Setup Templates (One-Time Flows)

#### 3. admin_signup_totp.html (8 vars, 14 tags, MEDIUM violation)
**Current Violations:**
- Line 257: `<img src="data:image/png;base64,{{ qr_b64 }}">`
  - **Issue:** Raw base64 string requires template manipulation
- Line 259: `<div class="manual-code">{{ totp_secret }}</div>`
  - **Issue:** Raw TOTP secret, unformatted

**Solution View Model:** `TOTPSetupView`
```python
@dataclass(frozen=True)
class TOTPSetupView:
    qr_code_data_uri: str  # Full "data:image/png;base64,..." (FEAT provides)
    totp_secret_display: str  # Raw secret for manual entry
    backup_codes: list[str]  # 10 backup codes
    backup_codes_formatted: str  # Pre-formatted for copy/paste
    issuer_name: str  # Display value
```

**Producer:** FEAT-IDEN-101 (Teacher TOTP Setup) — must provide view model on success

#### 4. student_account_claim.html (14 vars, 14 tags, MEDIUM violation)
**Current Violations:**
- Receives encrypted identity fields from route (still raw after decryption)

**Solution View Model:** `AccountClaimView`
```python
@dataclass(frozen=True)
class AccountClaimView:
    student_display_full_name: str  # Decrypted + formatted
    student_display_first_name: str
    student_display_last_initial: str
    claim_identifier: str
    claim_remaining_attempts: int
    claim_max_attempts: int
```

---

### Class Selection Templates (Navigation)

#### 5. admin_select_class_context.html (9 vars, 11 tags, MEDIUM violation)
**Solution View Model:** `AdminClassSelectionView`
```python
@dataclass(frozen=True)
class ClassOption:
    class_id: str
    display_name: str  # Pre-formatted, e.g., "Period 1 - 8:30 AM"
    join_code: str
    student_count: int
    is_selected: bool

@dataclass(frozen=True)
class AdminClassSelectionView:
    teacher_display_name: str
    available_classes: list[ClassOption]
    currently_selected_class_id: str | None
    has_any_classes: bool
```

#### 6. student_select_class_context.html (11 vars, 12 tags, MEDIUM violation)
**Solution View Model:** `StudentClassSelectionView`
```python
@dataclass(frozen=True)
class StudentClassOption:
    class_id: str
    display_name: str  # Pre-formatted
    join_code: str
    teacher_display_name: str
    is_selected: bool

@dataclass(frozen=True)
class StudentClassSelectionView:
    student_display_name: str
    available_classes: list[StudentClassOption]
    currently_selected_class_id: str | None
    has_any_classes: bool
```

---

## View Model Design Principles

### 1. Immutability (frozen=True)
All view models are frozen dataclasses. Once created, they cannot be modified. This prevents accidental mutation in routes or templates.

### 2. No ORM Leakage
View models contain ONLY primitives:
- ✅ Strings, integers, booleans, lists
- ❌ Never ORM objects, models, or lazy-loaded fields

### 3. Pre-Formatting
All display fields are pre-formatted in builders:
- ✅ `display_name` (pre-formatted string)
- ❌ NOT raw fields that need Jinja filters like `|upper` or `|format()`

### 4. Producer Responsibility
- **Phase 4 (FEATs):** Produce raw data (Phase 3 primitives)
- **Phase 5 (Builders):** Transform to view models (belong to domain)
- **Phase 6 (Routes):** Assemble view models into page contexts
- **Phase 7+ (Templates):** Consume ONLY view models (no raw data)

### 5. Single Responsibility
Each view model serves ONE consumer:
- `AdminLayoutContextView` → `layout_admin.html`
- `TOTPSetupView` → `admin_signup_totp.html`
- etc.

This makes contracts explicit and prevents scope creep.

---

## Builder Function Responsibility (Phase 5b — Next)

Each view model will have a builder function in `app/services/identity/builders.py`:

```python
def build_admin_layout_context_view(user_id: int, class_id: str | None) -> AdminLayoutContextView:
    """
    Assemble teacher identity and class context for layout rendering.
    - Lookup teacher user
    - Get display name (uppercase)
    - Resolve class context if available
    - Return frozen view model
    """
    pass

def build_totp_setup_view(...) -> TOTPSetupView:
    """
    Called by FEAT-IDEN-101 to provide template data.
    FEAT generates secret, QR code, backup codes.
    Builder encodes QR as data URI and formats backup codes.
    """
    pass

# ... 4 more builders
```

---

## Critical Insight: Producer-Consumer Architecture

**The key principle:** Each layer doesn't need to know what upper layers will do.

```
Domain Data (Phase 3)
    ↓
FEAT Orchestration (Phase 4) — Produces raw phase-3-primitives
    ↓
View Model Builders (Phase 5) — Transforms to presentation-ready structures
    ↓
Routes (Phase 6) — Assembles view models into page contexts
    ↓
Templates (Phase 7+) — Consumes ONLY view models
```

FEAT-IDEN-101 doesn't need to know how `admin_signup_totp.html` will display the QR code. It just produces the data. The builder (Phase 5) decides to encode it as a data URI. The route (Phase 6) passes the view model. The template (Phase 7) uses it as-is.

---

## What Templates Get (After Phase 7 Rewiring)

### Example: admin_signup_totp.html

**Before (Current — Anti-Pattern):**
```jinja
<img src="data:image/png;base64,{{ qr_b64 }}" />
<div>{{ totp_secret }}</div>
```
Raw data, template does assembly.

**After (Phase 5-7 Complete):**
```jinja
<img src="{{ view.qr_code_data_uri }}" />
<div>{{ view.totp_secret_display }}</div>
```
Pre-formatted view model, template just displays.

### Example: layout_admin.html

**Before (Current — Anti-Pattern):**
```jinja
<div>{{ current_admin_display_name|upper }}</div>
{% if admin_current_class_context and admin_current_class_context.class_timezone != 'UTC' %}
    {{ admin_current_class_context.class_timezone }}
{% endif %}
```
Formatting logic + conditional logic in template.

**After (Phase 5-7 Complete):**
```jinja
<div>{{ view.teacher_display_name }}</div>
{% if view.has_class_context %}
    {{ view.class_timezone }}
{% endif %}
```
Only display logic remains. All formatting and domain conditional logic moved to builder.

---

## Implementation Roadmap

### Phase 5b (Immediate Next Step)
**Implement builder functions:**
- Create `app/services/identity/builders.py`
- Implement 6 builder functions
- Write unit tests for immutability and format verification
- Verify no ORM leakage

**Estimated Scope:** 300-400 lines of code + 200 lines of tests

### Phase 5c (Verification)
**Audit templates:**
- Review each template field mapping
- Confirm view model satisfies all template needs
- Document any remaining violations

### Phase 6 (Application Surface Inventory)
**Map all identity routes and templates**

---

## Authority & Documentation

**Specification:** `FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md` (just created)

**Authority Documents:**
- TEMPLATE_JINJA_INVENTORY.md (violation source)
- INV-ARC-022 (Immutable Record System)
- SPEC-UI-001 (Canonical Page Rendering Specification)
- DOM-IDEN-001 through DOM-IDEN-003 (domain authority)

---

## Summary Table

| View Model | Consumer Template | Status | Violations Fixed |
|-----------|-------------------|--------|------------------|
| AdminLayoutContextView | layout_admin.html | 📝 Specified | Conditional logic, ORM access, unformatted display |
| StudentLayoutContextView | layout_student.html | 📝 Specified | Direct model access, filter in template |
| TOTPSetupView | admin_signup_totp.html | 📝 Specified | Raw base64, raw secret string |
| AccountClaimView | student_account_claim.html | 📝 Specified | Raw encrypted fields |
| AdminClassSelectionView | admin_select_class_context.html | 📝 Specified | Raw class objects |
| StudentClassSelectionView | student_select_class_context.html | 📝 Specified | Raw class objects |

---

## What This Achieves

✅ **Separation of Concerns:** Templates no longer perform domain logic or formatting  
✅ **Immutability:** All view models frozen; prevents mutation bugs  
✅ **No ORM Leakage:** Templates work with primitives only  
✅ **Reusability:** Same view models can serve multiple consumers  
✅ **Testability:** View models are easily unit testable  
✅ **Type Safety:** Frozen dataclasses provide static type checking  

---

**Status:** Phase 5 SPECIFICATION COMPLETE (2026-08-09)  
**Ready for:** Phase 5b implementation and Phase 6 planning
