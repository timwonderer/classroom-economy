# FEAT-IDEN Phase 5: Read Models & Projections

**Phase:** 5 of 10 (SOP-DEV-002)  
**Status:** SPECIFICATION (Producer analysis complete)  
**Date:** 2026-08-09  
**Authority:** SOP-DEV-002 §Phase 5, SPEC-UI-001, INV-ARC-022

---

## I. Phase Purpose

Phase 5 defines the **read models (view models)** that the identity domain must provide to consumer layers (routes, templates). These view models transform domain primitives (Phase 3) and FEAT outputs (Phase 4) into presentation-ready data structures that eliminate template violations and enforce separation of concerns.

**Critical Principle:** View models are PRODUCERS' responsibility. Identity domain must define what view models it provides; routes assemble them into page views; templates consume them passively.

---

## II. Template Violation Audit (Inventory Source)

### Identity Domain Template Status

| Template | Jinja Vars | Jinja Tags | Status | Primary Violation |
|----------|-----------|------------|--------|------------------|
| admin_login.html | 16 | 6 | ✅ CLEAN | None (static form) |
| student_login.html | 13 | 8 | ✅ CLEAN | None (static form) |
| system_admin_login.html | 13 | 10 | ✅ CLEAN | None (static form) |
| admin_signup.html | 8 | 12 | ✅ CLEAN | None (static form) |
| **admin_signup_totp.html** | 8 | 14 | ⚠️ MEDIUM | Raw base64 QR + raw secret string |
| **student_account_claim.html** | 14 | 14 | ⚠️ MEDIUM | Raw identity context (encrypted fields) |
| student_create_username.html | 11 | 8 | ✅ CLEAN | None (static form) |
| student_verify_recovery.html | 5 | 12 | ✅ CLEAN | None (static form) |
| **layout_admin.html** | 53 | 98 | ❌ HIGH | Direct ORM model access, conditional logic |
| **layout_student.html** | 38 | 66 | ❌ HIGH | Direct ORM model access, unformatted display names |
| **admin_select_class_context.html** | 9 | 11 | ⚠️ MEDIUM | Raw class context objects |
| **student_select_class_context.html** | 11 | 12 | ⚠️ MEDIUM | Raw class context objects |

**Templates Requiring View Models (6):**
- Layout templates: `layout_admin.html`, `layout_student.html` (shared across ALL pages)
- Setup templates: `admin_signup_totp.html`, `student_account_claim.html`
- Selection templates: `admin_select_class_context.html`, `student_select_class_context.html`

---

## III. View Model Requirements by Consumer

### A. Layout Templates (Shared - Highest Impact)

#### 3A.1: layout_admin.html

**Current Violations:**

```jinja
{# Line 97: Conditional logic in template #}
data-timezone="{% if admin_current_class_context and admin_current_class_context.class_timezone != 'UTC' %}{{ admin_current_class_context.class_timezone }}{% endif %}"

{# Line 102: Unformatted display name #}
<div class="sidebar-scope-name">{{ current_admin_display_name|upper }}</div>

{# Lines 106-107: Direct ORM property access #}
<div class="sidebar-scope-context sidebar-scope-class-line">
    <span>{{ admin_current_class_context.class_identifier }}</span>
    <span class="sidebar-scope-meta-inline">{{ admin_current_class_context.join_code }}</span>
</div>
```

**Required View Model:** `AdminLayoutContextView`

```python
@dataclass(frozen=True)
class AdminLayoutContextView:
    """
    Represents teacher identity and class context for layout rendering.
    Producer: Identity domain (routes assemble from session + FEAT outputs)
    Consumer: layout_admin.html (shared across all admin pages)
    """
    
    # Teacher identity (from authenticated session)
    teacher_display_name: str  # REQUIRED: Pre-formatted uppercase display name (e.g., "JOHN SMITH")
    
    # Class context (conditional - may be None if no class selected)
    has_class_context: bool    # REQUIRED: Whether class_context is available
    class_timezone: str        # OPTIONAL: If has_class_context, the timezone (else not rendered)
    class_display_name: str    # OPTIONAL: If has_class_context, e.g., "Period 1" or "1st Hour"
    class_join_code: str       # OPTIONAL: If has_class_context, the join code
    
    # Feature flags
    is_maintenance_bypass_active: bool  # Whether maintenance bypass is active
```

**Template Usage (After Refactoring):**

```jinja
{# All violations eliminated #}
<div class="sidebar-scope-time class-scoped-time"
    id="admin-class-time"
    data-timezone="{{ view.class_timezone or '' }}"
    data-empty-message="No classes yet. Official class time will appear after class creation."
    data-unset-message="Official class time zone not set yet.">
</div>

{% if view.teacher_display_name %}
<div class="sidebar-scope-name">{{ view.teacher_display_name }}</div>
{% endif %}

{% if view.has_class_context %}
<div class="sidebar-scope-context sidebar-scope-class-line">
    <span>{{ view.class_display_name }}</span>
    <span class="sidebar-scope-meta-inline">{{ view.class_join_code }}</span>
</div>
{% else %}
<div class="sidebar-scope-context">No classes created yet</div>
{% endif %}
```

**Producer (Route Responsibility):**

```python
# In app/routes/admin.py (any page extending layout_admin.html)

from app.services.identity.builders import build_admin_layout_context_view

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    # Get current session context
    teacher_id = session.get('user_id')
    class_id = session.get('current_class_id')
    
    # Build view model (producer's job)
    layout_view = build_admin_layout_context_view(
        user_id=teacher_id,
        class_id=class_id  # May be None
    )
    
    # Pass ONLY the view model (+ page-specific data)
    return render_template('layout_admin.html', 
        view=layout_view,
        # ... page-specific data
    )
```

---

#### 3A.2: layout_student.html

**Current Violations:**

```jinja
{# Line 104: Direct model access + formatting in template #}
{{ current_class_context.student_full_name|upper }}

{# Line 108-109: Unformatted display names from route #}
{{ student_display_first_name }}
{{ student_display_last_initial }}
```

**Required View Model:** `StudentLayoutContextView`

```python
@dataclass(frozen=True)
class StudentLayoutContextView:
    """
    Represents student identity and class context for layout rendering.
    Producer: Identity domain (routes assemble from session + identity lookup)
    Consumer: layout_student.html (shared across all student pages)
    """
    
    # Student identity (from authenticated session)
    student_display_full_name: str  # REQUIRED: Pre-formatted uppercase, e.g., "ALEX JOHNSON"
    student_display_first_name: str  # REQUIRED: Pre-formatted first name only, e.g., "Alex"
    student_display_last_initial: str  # REQUIRED: Single letter, e.g., "J"
    
    # Class context (conditional)
    has_class_context: bool  # Whether class_context is available
    class_display_name: str  # OPTIONAL: e.g., "Period 1"
    class_join_code: str  # OPTIONAL: Join code for this class
    
    # Feature flags
    is_maintenance_bypass_active: bool
```

**Template Usage (After Refactoring):**

```jinja
{# All violations eliminated #}
{{ view.student_display_full_name }}

<small class="text-muted d-block">{{ view.student_display_first_name }} {{ view.student_display_last_initial }}</small>
```

---

### B. Setup Templates (One-Time Flows)

#### 3B.1: admin_signup_totp.html (FEAT-IDEN-101 Output)

**Current Violations:**

```jinja
{# Line 257: Raw base64 QR code #}
<img src="data:image/png;base64,{{ qr_b64 }}" alt="TOTP QR Code">

{# Line 259: Raw TOTP secret string #}
<div class="manual-code">{{ totp_secret }}</div>
```

**Required View Model:** `TOTPSetupView`

```python
@dataclass(frozen=True)
class TOTPSetupView:
    """
    Represents TOTP setup output for teacher authenticator enrollment.
    Producer: FEAT-IDEN-101 (Teacher TOTP Setup)
    Consumer: admin_signup_totp.html (step 1 of signup flow)
    """
    
    # QR Code (pre-encoded by FEAT)
    qr_code_data_uri: str  # REQUIRED: Full data:image/png;base64,... ready for <img src="">
    
    # Manual entry fallback
    totp_secret_display: str  # REQUIRED: 32-char base32 secret for manual entry
    
    # Backup codes (one-time display)
    backup_codes: tuple[str, ...]  # REQUIRED: Immutable tuple of 10 codes in XXXX-XXXX-XXXX-XXXX format
    backup_codes_formatted: str  # REQUIRED: Pre-formatted as newline-separated string for copy/paste
    
    # Metadata (for confirmation page)
    issuer_name: str  # REQUIRED: "Classroom Token Hub" (for authenticator app display)
```

**Template Usage (After Refactoring):**

```jinja
{# Line 257: No base64 encoding in template #}
<img src="{{ view.qr_code_data_uri }}" alt="TOTP QR Code">

{# Line 259: No raw secret #}
<div class="manual-code">{{ view.totp_secret_display }}</div>

{# Later on page: Backup codes display (NEW) #}
<div class="backup-codes-panel">
    <h3>Save Your Backup Codes</h3>
    <pre>{{ view.backup_codes_formatted }}</pre>
    <button onclick="copyToClipboard('{{ view.backup_codes_formatted }}')">Copy Codes</button>
</div>
```

**Producer (FEAT-IDEN-101):**

```python
# In app/feats/identity/feat_iden_101.py

def execute_feat_totp_setup(...) -> TOTPSetupView:
    """Orchestrate TOTP setup and produce view model."""
    
    # Generate secret
    totp_secret = pyotp.random_base32()
    encrypted_secret = NORMALIZE_TOTP_FOR_STORAGE(totp_secret)
    
    # Generate QR code
    qr = qrcode.QRCode()
    qr.add_data(f'otpauth://totp/classroom-economy:{user_id}@{class_id}?secret={totp_secret}&issuer=ClassroomEconomy')
    qr.make()
    qr_img = qr.make_image()
    
    # Encode as data URI (FEAT's responsibility, not template's)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_b64 = base64.b64encode(qr_buffer.getvalue()).decode()
    qr_data_uri = f'data:image/png;base64,{qr_b64}'
    
    # Generate backup codes
    backup_codes = [generate_backup_code() for _ in range(10)]
    
    # Build view model (FEAT provides complete producer)
    return TOTPSetupView(
        qr_code_data_uri=qr_data_uri,
        totp_secret_display=totp_secret,
        backup_codes=backup_codes,
        backup_codes_formatted='\n'.join(backup_codes),
        issuer_name='Classroom Token Hub',
        enrollment_deadline=None
    )
```

---

#### 3B.2: student_account_claim.html

**Current Violations:**

```jinja
{# Receives encrypted identity fields from route #}
{{ student_first_name }}  {# Decrypted in route, still raw #}
{{ student_last_initial }}
```

**Required View Model:** `AccountClaimView`

```python
@dataclass(frozen=True)
class AccountClaimView:
    """
    Represents student identity information during account claim flow.
    Producer: Identity domain (S-IDEN-006 primitive or FEAT-IDEN-* claim orchestration)
    Consumer: student_account_claim.html (step 2 of student claim flow)
    """
    
    # Student identity (from claim context)
    student_display_full_name: str  # REQUIRED: Pre-formatted, e.g., "Alex Johnson"
    student_display_first_name: str  # REQUIRED: First name only
    student_display_last_initial: str  # REQUIRED: Single character
    
    # Claim metadata
    claim_identifier: str  # REQUIRED: The claim code or identifier displayed to student
    remaining_attempts: int  # REQUIRED: How many attempts left
    max_attempts: int  # REQUIRED: Total attempts allowed
```

---

### C. Class Selection Templates

#### 3C.1: admin_select_class_context.html

**Current Violations:**

```jinja
{# Receives raw ClassEconomy objects or class context dicts #}
{{ class.display_name }}
{{ class.join_code }}
```

**Required View Model:** `AdminClassSelectionView`

```python
@dataclass(frozen=True)
class ClassOption:
    """Single class option in selection list."""
    class_id: str  # UUID
    display_name: str  # Pre-formatted, e.g., "Period 1"
    join_code: str
    student_count: int  # Number of enrolled students (metadata)
    is_current: bool  # Whether this is the current selection

@dataclass(frozen=True)
class AdminClassSelectionView:
    """
    Represents list of classes available to teacher.
    Producer: Identity domain (resolves teacher's classes)
    Consumer: admin_select_class_context.html (class selection dropdown/page)
    """
    
    teacher_display_name: str  # REQUIRED
    available_classes: tuple[ClassOption, ...]  # REQUIRED: Immutable tuple of classes teacher owns
    current_class_id: Optional[str]  # OPTIONAL: UUID of currently selected class (None if none)
    has_any_classes: bool  # REQUIRED: Whether teacher has ANY classes
```

---

#### 3C.2: student_select_class_context.html

**Current Violations:**

```jinja
{# Receives raw class context #}
{{ class.display_name }}
```

**Required View Model:** `StudentClassSelectionView`

```python
@dataclass(frozen=True)
class StudentClassOption:
    """Single class option for student."""
    class_id: str
    display_name: str  # Pre-formatted
    join_code: str
    teacher_display_name: str  # Teacher's name for this class
    is_current: bool

@dataclass(frozen=True)
class StudentClassSelectionView:
    """
    Represents list of classes available to student.
    Producer: Identity domain (resolves student's enrollments)
    Consumer: student_select_class_context.html (class selection)
    """
    
    student_display_name: str  # REQUIRED
    available_classes: tuple[StudentClassOption, ...]  # REQUIRED: Immutable tuple of available classes
    current_class_id: Optional[str]  # OPTIONAL: UUID of currently selected class (None if none)
    has_any_classes: bool  # REQUIRED
```

---

## IV. View Model Builder Functions

All view models are produced by builder functions in `app/services/identity/builders.py`:

| Builder Function | Output Type | Producer | Consumer Template |
|------------------|------------|----------|------------------|
| `build_admin_layout_context_view()` | `AdminLayoutContextView` | Any admin route | `layout_admin.html` |
| `build_student_layout_context_view()` | `StudentLayoutContextView` | Any student route | `layout_student.html` |
| `build_totp_setup_view()` | `TOTPSetupView` | FEAT-IDEN-101 | `admin_signup_totp.html` |
| `build_account_claim_view()` | `AccountClaimView` | Student claim orchestration | `student_account_claim.html` |
| `build_admin_class_selection_view()` | `AdminClassSelectionView` | Class selection route | `admin_select_class_context.html` |
| `build_student_class_selection_view()` | `StudentClassSelectionView` | Class selection route | `student_select_class_context.html` |

**Shared Responsibility:**
- FEAT outputs (Phase 4) provide raw data
- Builders (Phase 5) transform to view models
- Routes assemble view models into page contexts
- Templates consume ONLY view models (no raw ORM objects)

---

## V. Implementation Checklist

### Phase 5a: View Model Definitions

- [ ] Define `AdminLayoutContextView` (frozen dataclass)
- [ ] Define `StudentLayoutContextView` (frozen dataclass)
- [ ] Define `TOTPSetupView` (frozen dataclass)
- [ ] Define `AccountClaimView` (frozen dataclass)
- [ ] Define `AdminClassSelectionView` + `ClassOption` (frozen dataclass)
- [ ] Define `StudentClassSelectionView` + `StudentClassOption` (frozen dataclass)
- [ ] All dataclasses use `frozen=True`
- [ ] All dataclasses have docstrings indicating producer/consumer
- [ ] All string fields that are display-ready are pre-formatted

### Phase 5b: Builder Functions

- [ ] Implement `build_admin_layout_context_view(user_id, class_id)` 
- [ ] Implement `build_student_layout_context_view(user_id, class_id)`
- [ ] Implement `build_totp_setup_view(...)` (called by FEAT-IDEN-101)
- [ ] Implement `build_account_claim_view(...)`
- [ ] Implement `build_admin_class_selection_view(user_id)`
- [ ] Implement `build_student_class_selection_view(user_id)`
- [ ] All builders handle edge cases (missing context, no classes, etc.)
- [ ] All builders return immutable view models

### Phase 5c: Template Verification (No Code Changes Yet)

- [ ] Audit `layout_admin.html` to identify all violations
- [ ] Audit `layout_student.html` to identify all violations
- [ ] Audit `admin_signup_totp.html` to identify all violations
- [ ] Audit `student_account_claim.html` to identify all violations
- [ ] Audit `admin_select_class_context.html` to identify all violations
- [ ] Audit `student_select_class_context.html` to identify all violations
- [ ] Document expected view model field names in each template

---

## VI. Transition to Phase 6

**Phase 6 Task (Wiring):** Update routes to use builders and pass view models to templates.

**Phase 6 will:**
1. Modify all admin routes to call `build_admin_layout_context_view()` before rendering
2. Modify all student routes to call `build_student_layout_context_view()` before rendering
3. Modify signup flow to receive `TOTPSetupView` from FEAT-IDEN-101
4. Modify class selection routes to use builder-provided views
5. Verify all templates receive ONLY view models (no raw ORM objects)

**Phase 5 produces the contracts; Phase 6 wires them.**

---

## VII. Critical Design Principles

### Immutability
All view models are frozen dataclasses. Once built, they cannot be modified. This prevents accidental mutation in routes or templates.

### No ORM Leakage
View models contain ONLY primitives (str, int, bool, list, dict). ORM objects are never passed to templates.

### Pre-Formatting
All display strings (`display_*`, `_formatted`, `_display_*`) are pre-formatted in builders. Templates use them as-is without Jinja filters.

### Producer Responsibility
Builders belong to the domain that produces the data. Identity domain produces identity view models. Routes orchestrate, templates consume.

### Single Responsibility
Each view model serves ONE consumer template (or ONE layout shared across templates). This makes contracts explicit and prevents scope creep.

---

## VIII. Audit Trail

**Violation Source:** TEMPLATE_JINJA_INVENTORY.md (2026-08-06)  
**Phase 5 Analysis:** 2026-08-09  
**Status:** SPECIFICATION (view models defined; Phase 5b implementation pending)

---

## IX. Dependencies

- `docs/TRACKING/TEMPLATE_JINJA_INVENTORY.md` (violation audit source)
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-022_IMMUTABLE_RECORD_SYSTEM.md` (frozen dataclass requirement)
- `docs/DOMAIN/SPEC-UI-001_CANONICAL_PAGE_RENDERING_SPECIFICATION.md` (view model pattern)
- `docs/FEATURE-EXECUTION/FEAT-IDEN-101_TEACHER_TOTP_SETUP.md` through `FEAT-IDEN-107` (Phase 4)

---

**This document is SPECIFICATION. Phase 5b (builder implementation) begins after user review and approval.**
