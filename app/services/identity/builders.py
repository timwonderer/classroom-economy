"""Identity domain view model builders.

Transforms DisplayMetadata and FEAT outputs into display-ready frozen dataclasses.
Pre-formats all name and class context values for template consumption.

Per SPEC-UI-001 § VI: Each view model is immutable (@dataclass(frozen=True)).
Templates receive ONLY these view models — never raw ORM objects or dicts.

Per Phase 5 specification: FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md

Violation elimination targets (from TEMPLATE_JINJA_INVENTORY.md, 2026-08-06):
  - layout_admin.html: ORM access, conditional logic, unformatted display name
  - layout_student.html: Direct model access, |upper filter in template
  - admin_signup_totp.html: Raw base64 QR, raw TOTP secret
  - student_account_claim.html: Raw encrypted identity fields
  - admin_select_class_context.html: Raw class context objects
  - student_select_class_context.html: Raw class context objects
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# View model definitions (frozen dataclasses — SPEC-UI-001 § VI)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdminLayoutContextView:
    """Teacher identity and class context for layout_admin.html.

    Eliminates template-level:
    - Conditional timezone logic (line 97: class_timezone != 'UTC')
    - Uppercase name filter (line 102: |upper)
    - Direct ORM model access (lines 106-107: admin_current_class_context.*)

    Producer: build_admin_layout_context_view()
    Consumer: layout_admin.html (shared across ALL admin pages)
    """

    teacher_display_name: str            # Uppercase pre-formatted, e.g. "JOHN SMITH"
    has_class_context: bool              # False → show "No classes created yet"
    class_timezone: str                  # "" when not set / UTC (data-timezone attr)
    class_display_name: str              # e.g. "Period 1" or join_code fallback
    class_join_code: str                 # Public join code for display
    is_maintenance_bypass_active: bool   # Whether maintenance banner renders


@dataclass(frozen=True)
class StudentLayoutContextView:
    """Student identity and class context for layout_student.html.

    Eliminates template-level:
    - Direct model access (line 104: current_class_context.student_full_name|upper)
    - Unformatted name fragments (lines 108-109: student_display_first_name)

    Producer: build_student_layout_context_view()
    Consumer: layout_student.html (shared across ALL student pages)
    """

    student_display_full_name: str       # Uppercase pre-formatted, e.g. "ALEX JOHNSON"
    student_display_first_name: str      # Pre-formatted first name, e.g. "Alex"
    student_display_last_initial: str    # Single char, e.g. "J"
    has_class_context: bool              # False → show no-class message
    class_display_name: str             # e.g. "Period 1" or ""
    class_join_code: str                # Public join code or ""
    is_maintenance_bypass_active: bool


@dataclass(frozen=True)
class TOTPSetupView:
    """TOTP enrollment output for admin_signup_totp.html.

    Eliminates template-level:
    - Raw base64 inline (line 257: data:image/png;base64,{{ qr_b64 }})
    - Raw TOTP secret (line 259: {{ totp_secret }})

    Producer: build_totp_setup_view() — called by FEAT-IDEN-101
    Consumer: admin_signup_totp.html (teacher TOTP setup step)
    """

    qr_code_data_uri: str               # "data:image/png;base64,..." — ready for <img src="">
    totp_secret_display: str            # 32-char base32 string for manual entry
    backup_codes: tuple[str, ...]       # 10 one-time backup codes (XXXX-XXXX-XXXX-XXXX format)
    backup_codes_formatted: str         # Newline-separated for copy/paste
    issuer_name: str                    # "Classroom Token Hub"


@dataclass(frozen=True)
class AccountClaimView:
    """Student identity for student_account_claim.html.

    Eliminates template-level:
    - Raw decrypted identity fields passed from route

    Producer: build_account_claim_view()
    Consumer: student_account_claim.html (student claim flow)
    """

    student_display_full_name: str      # e.g. "Alex Johnson"
    student_display_first_name: str     # e.g. "Alex"
    student_display_last_initial: str   # e.g. "J"
    claim_identifier: str               # The claim code displayed to student
    remaining_attempts: int             # How many attempts remain
    max_attempts: int                   # Total attempts allowed


@dataclass(frozen=True)
class ClassOption:
    """Single class entry in AdminClassSelectionView."""

    class_id: str
    display_name: str          # Pre-formatted, e.g. "Period 1" or join_code
    join_code: str
    student_count: int
    is_current: bool           # Whether this is the currently selected class


@dataclass(frozen=True)
class AdminClassSelectionView:
    """Class list for admin_select_class_context.html.

    Eliminates template-level:
    - Raw class context dicts/objects passed from route

    Producer: build_admin_class_selection_view()
    Consumer: admin_select_class_context.html
    """

    teacher_display_name: str
    available_classes: tuple[ClassOption, ...]
    current_class_id: Optional[str]    # UUID of currently selected class (None if none)
    has_any_classes: bool              # Whether teacher has ANY classes


@dataclass(frozen=True)
class StudentClassOption:
    """Single class entry in StudentClassSelectionView."""

    class_id: str
    display_name: str
    join_code: str
    teacher_display_name: str
    is_current: bool


@dataclass(frozen=True)
class StudentClassSelectionView:
    """Class list for student_select_class_context.html.

    Eliminates template-level:
    - Raw class context objects from route

    Producer: build_student_class_selection_view()
    Consumer: student_select_class_context.html
    """

    student_display_name: str
    available_classes: tuple[StudentClassOption, ...]
    current_class_id: Optional[str]
    has_any_classes: bool


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def build_admin_layout_context_view(
    admin_display_name: Optional[str],
    class_context: Optional[dict],
    *,
    is_maintenance_bypass_active: bool = False,
) -> AdminLayoutContextView:
    """Build AdminLayoutContextView for layout_admin.html.

    Args:
        admin_display_name: Raw display name from session cache (may be None).
            Comes from get_admin_display_name_cache() in context processor.
        class_context: Raw class context dict from display_metadata.to_class_context()
            (may be None when no class is selected).
        is_maintenance_bypass_active: Whether the maintenance bypass banner renders.

    Returns:
        AdminLayoutContextView with all fields pre-formatted.
        teacher_display_name is always uppercase.
        has_class_context=False when class_context is None or empty.
        class_timezone is "" (not the string "UTC") when timezone is UTC or missing,
        because the template's data-timezone attribute should be empty in that case
        (the JS uses emptiness to show a fallback message).

    Eliminates:
        - layout_admin.html:97  data-timezone conditional logic
        - layout_admin.html:102 |upper filter on display name
        - layout_admin.html:106 admin_current_class_context.class_identifier access
        - layout_admin.html:107 admin_current_class_context.join_code access
    """
    # Pre-format teacher display name (uppercase, empty-string-safe)
    raw_name = (admin_display_name or "").strip()
    teacher_display_name = raw_name.upper() if raw_name else ""

    # Resolve class context fields
    has_class_context = bool(class_context)

    if has_class_context:
        raw_tz = (class_context.get("class_timezone") or "").strip()
        # Timezone attribute is empty string when UTC or unset — JS interprets "" as unset
        class_timezone = "" if (not raw_tz or raw_tz == "UTC") else raw_tz
        class_display_name = (class_context.get("class_identifier") or "").strip()
        class_join_code = (class_context.get("join_code") or "").strip()
    else:
        class_timezone = ""
        class_display_name = ""
        class_join_code = ""

    return AdminLayoutContextView(
        teacher_display_name=teacher_display_name,
        has_class_context=has_class_context,
        class_timezone=class_timezone,
        class_display_name=class_display_name,
        class_join_code=class_join_code,
        is_maintenance_bypass_active=is_maintenance_bypass_active,
    )


def build_student_layout_context_view(
    display_metadata,  # DisplayMetadata | None  (avoid circular import)
    *,
    is_maintenance_bypass_active: bool = False,
) -> StudentLayoutContextView:
    """Build StudentLayoutContextView for layout_student.html.

    Args:
        display_metadata: DisplayMetadata from get_or_resolve_display_metadata().
            Provides pre-decrypted student name fields and class context.
            May be None when no class is in session.
        is_maintenance_bypass_active: Whether the maintenance bypass banner renders.

    Returns:
        StudentLayoutContextView with all name fields uppercase/pre-formatted.

    Eliminates:
        - layout_student.html:104  current_class_context.student_full_name|upper
        - layout_student.html:108  student_display_first_name (unformatted from route)
        - layout_student.html:109  student_display_last_initial
    """
    if display_metadata is None:
        return StudentLayoutContextView(
            student_display_full_name="",
            student_display_first_name="",
            student_display_last_initial="",
            has_class_context=False,
            class_display_name="",
            class_join_code="",
            is_maintenance_bypass_active=is_maintenance_bypass_active,
        )

    first = (display_metadata.student_first_name or "").strip()
    last = (display_metadata.student_last_name or "").strip()
    full_name = f"{first} {last}".strip()
    last_initial = last[0] if last else ""

    class_display_name = (display_metadata.class_identifier or "").strip()
    class_join_code = (display_metadata.join_code or "").strip()
    has_class_context = bool(class_display_name or class_join_code)

    return StudentLayoutContextView(
        student_display_full_name=full_name.upper() if full_name else "",
        student_display_first_name=first,
        student_display_last_initial=last_initial,
        has_class_context=has_class_context,
        class_display_name=class_display_name,
        class_join_code=class_join_code,
        is_maintenance_bypass_active=is_maintenance_bypass_active,
    )


def build_totp_setup_view(
    totp_secret: str,
    qr_b64: str,
    backup_codes: list[str],
    *,
    issuer_name: str = "Classroom Token Hub",
) -> TOTPSetupView:
    """Build TOTPSetupView for admin_signup_totp.html.

    Called by FEAT-IDEN-101 after generating the secret and QR code.
    Encapsulates all TOTP setup display data into a single immutable view model.

    Args:
        totp_secret: Raw 32-char base32 TOTP secret for manual entry display.
        qr_b64: Base64-encoded PNG of the QR code (without the data URI prefix).
        backup_codes: List of 10 backup codes in XXXX-XXXX-XXXX-XXXX format.
        issuer_name: Display name for the authenticator app issuer field.

    Returns:
        TOTPSetupView with qr_code_data_uri pre-assembled as a full data URI.

    Eliminates:
        - admin_signup_totp.html:257  data:image/png;base64,{{ qr_b64 }} inline assembly
        - admin_signup_totp.html:259  {{ totp_secret }} raw secret
    """
    qr_code_data_uri = f"data:image/png;base64,{qr_b64}"
    backup_codes_formatted = "\n".join(backup_codes)

    return TOTPSetupView(
        qr_code_data_uri=qr_code_data_uri,
        totp_secret_display=totp_secret,
        backup_codes=tuple(backup_codes),
        backup_codes_formatted=backup_codes_formatted,
        issuer_name=issuer_name,
    )


def build_account_claim_view(
    first_name: str,
    last_name: str,
    claim_identifier: str,
    remaining_attempts: int,
    max_attempts: int,
) -> AccountClaimView:
    """Build AccountClaimView for student_account_claim.html.

    Args:
        first_name: Decrypted first name from IdentityProfile (already decrypted by caller).
        last_name: Decrypted last name from IdentityProfile.
        claim_identifier: The claim code or token displayed to the student.
        remaining_attempts: How many attempts remain before lockout.
        max_attempts: Total attempts allowed.

    Returns:
        AccountClaimView with names pre-formatted.

    Eliminates:
        - student_account_claim.html: raw decrypted name fields passed from route
    """
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    full_name = f"{first} {last}".strip()
    last_initial = last[0] if last else ""

    return AccountClaimView(
        student_display_full_name=full_name,
        student_display_first_name=first,
        student_display_last_initial=last_initial,
        claim_identifier=claim_identifier,
        remaining_attempts=remaining_attempts,
        max_attempts=max_attempts,
    )


def build_admin_class_selection_view(
    admin_display_name: Optional[str],
    classes: list[dict],
    current_class_id: Optional[str] = None,
) -> AdminClassSelectionView:
    """Build AdminClassSelectionView for admin_select_class_context.html.

    Args:
        admin_display_name: Raw display name from session cache.
        classes: List of class context dicts (from display_metadata.to_available_class_option()).
            Each dict has: class_id, class_identifier, join_code, student_count (optional).
        current_class_id: UUID of currently selected class (None if none selected).

    Returns:
        AdminClassSelectionView with pre-formatted ClassOption entries.

    Eliminates:
        - admin_select_class_context.html: raw class context dicts/objects from route
    """
    raw_name = (admin_display_name or "").strip()
    teacher_display_name = raw_name

    class_options = tuple(
        ClassOption(
            class_id=str(cls.get("class_id") or ""),
            display_name=(cls.get("class_identifier") or cls.get("join_code") or "").strip(),
            join_code=(cls.get("join_code") or "").strip(),
            student_count=int(cls.get("student_count") or 0),
            is_current=str(cls.get("class_id") or "") == str(current_class_id or ""),
        )
        for cls in (classes or [])
    )

    return AdminClassSelectionView(
        teacher_display_name=teacher_display_name,
        available_classes=class_options,
        current_class_id=current_class_id,
        has_any_classes=len(class_options) > 0,
    )


def build_student_class_selection_view(
    student_display_name: Optional[str],
    classes: list[dict],
    current_class_id: Optional[str] = None,
) -> StudentClassSelectionView:
    """Build StudentClassSelectionView for student_select_class_context.html.

    Args:
        student_display_name: Pre-formatted student name (first + last_initial or full).
        classes: List of class context dicts, each with class_id, class_identifier,
            join_code, and teacher_name (optional).
        current_class_id: UUID of currently selected class (None if none selected).

    Returns:
        StudentClassSelectionView with pre-formatted StudentClassOption entries.

    Eliminates:
        - student_select_class_context.html: raw class context objects from route
    """
    class_options = tuple(
        StudentClassOption(
            class_id=str(cls.get("class_id") or ""),
            display_name=(cls.get("class_identifier") or cls.get("join_code") or "").strip(),
            join_code=(cls.get("join_code") or "").strip(),
            teacher_display_name=(cls.get("teacher_name") or "Teacher").strip(),
            is_current=str(cls.get("class_id") or "") == str(current_class_id or ""),
        )
        for cls in (classes or [])
    )

    return StudentClassSelectionView(
        student_display_name=(student_display_name or "").strip(),
        available_classes=class_options,
        current_class_id=current_class_id,
        has_any_classes=len(class_options) > 0,
    )
