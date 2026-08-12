"""Tests for identity domain view model builders.

Verifies:
- All view models are immutable (frozen=True dataclasses)
- All display fields are pre-formatted strings (no raw ORM objects)
- Name formatting (uppercase, initial extraction) done in builder
- Class context fields safely handle None/missing cases
- TOTPSetupView assembles the data URI and backup codes correctly
- No ORM models or dicts leaked into views

Per SPEC-UI-001: templates receive ONLY frozen view models.
Per Phase 5 specification: FEAT-IDEN-PHASE-5-READ-MODELS_PROJECTIONS.md
"""

import pytest
from types import SimpleNamespace

from app.services.identity.builders import (
    # View model types
    AdminLayoutContextView,
    StudentLayoutContextView,
    TOTPSetupView,
    AccountClaimView,
    ClassOption,
    AdminClassSelectionView,
    StudentClassOption,
    StudentClassSelectionView,
    # Builder functions
    build_admin_layout_context_view,
    build_student_layout_context_view,
    build_totp_setup_view,
    build_account_claim_view,
    build_admin_class_selection_view,
    build_student_class_selection_view,
)


# ---------------------------------------------------------------------------
# Pattern A: Immutability — all view models are frozen dataclasses
# ---------------------------------------------------------------------------

class TestImmutability:
    """All view models must be frozen (immutable) per SPEC-UI-001 § VI."""

    def test_admin_layout_context_view_is_frozen(self):
        view = build_admin_layout_context_view("Teacher Name", None)
        with pytest.raises((AttributeError, TypeError)):
            view.teacher_display_name = "CHANGED"  # type: ignore[misc]

    def test_student_layout_context_view_is_frozen(self):
        view = build_student_layout_context_view(None)
        with pytest.raises((AttributeError, TypeError)):
            view.student_display_full_name = "CHANGED"  # type: ignore[misc]

    def test_totp_setup_view_is_frozen(self):
        view = build_totp_setup_view(
            totp_secret="ABCDEFGHIJKLMNOP1234567890123456",
            qr_b64="abc123base64data==",
            backup_codes=["AAAA-BBBB-CCCC-DDDD"] * 10,
        )
        with pytest.raises((AttributeError, TypeError)):
            view.totp_secret_display = "CHANGED"  # type: ignore[misc]

    def test_account_claim_view_is_frozen(self):
        view = build_account_claim_view(
            first_name="Alex", last_name="Johnson",
            claim_identifier="CLM-001", remaining_attempts=3, max_attempts=5,
        )
        with pytest.raises((AttributeError, TypeError)):
            view.student_display_full_name = "CHANGED"  # type: ignore[misc]

    def test_admin_class_selection_view_is_frozen(self):
        view = build_admin_class_selection_view("Teacher", [])
        with pytest.raises((AttributeError, TypeError)):
            view.has_any_classes = True  # type: ignore[misc]

    def test_student_class_selection_view_is_frozen(self):
        view = build_student_class_selection_view("Alex J.", [])
        with pytest.raises((AttributeError, TypeError)):
            view.has_any_classes = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pattern B: AdminLayoutContextView
# ---------------------------------------------------------------------------

class TestAdminLayoutContextView:
    """Tests for build_admin_layout_context_view()."""

    def test_teacher_name_is_uppercased(self):
        """Display name must be pre-formatted uppercase — eliminates |upper in template."""
        view = build_admin_layout_context_view("Jane Smith", None)
        assert view.teacher_display_name == "JANE SMITH"

    def test_teacher_name_already_uppercase_stays_uppercase(self):
        view = build_admin_layout_context_view("JANE SMITH", None)
        assert view.teacher_display_name == "JANE SMITH"

    def test_teacher_name_none_gives_empty_string(self):
        view = build_admin_layout_context_view(None, None)
        assert view.teacher_display_name == ""

    def test_no_class_context_sets_has_class_context_false(self):
        view = build_admin_layout_context_view("Teacher", None)
        assert view.has_class_context is False

    def test_no_class_context_gives_empty_display_fields(self):
        view = build_admin_layout_context_view("Teacher", None)
        assert view.class_display_name == ""
        assert view.class_join_code == ""
        assert view.class_timezone == ""

    def test_class_context_dict_populates_fields(self):
        ctx = {
            "class_identifier": "Period 1",
            "join_code": "ABC123",
            "class_timezone": "America/Chicago",
        }
        view = build_admin_layout_context_view("Teacher", ctx)
        assert view.has_class_context is True
        assert view.class_display_name == "Period 1"
        assert view.class_join_code == "ABC123"
        assert view.class_timezone == "America/Chicago"

    def test_utc_timezone_becomes_empty_string(self):
        """UTC timezone → empty string, so data-timezone attr is empty (JS shows fallback msg)."""
        ctx = {"class_identifier": "P1", "join_code": "X1", "class_timezone": "UTC"}
        view = build_admin_layout_context_view("Teacher", ctx)
        assert view.class_timezone == ""

    def test_missing_timezone_key_becomes_empty_string(self):
        ctx = {"class_identifier": "P1", "join_code": "X1"}
        view = build_admin_layout_context_view("Teacher", ctx)
        assert view.class_timezone == ""

    def test_maintenance_bypass_defaults_to_false(self):
        view = build_admin_layout_context_view("Teacher", None)
        assert view.is_maintenance_bypass_active is False

    def test_maintenance_bypass_propagated_when_set(self):
        view = build_admin_layout_context_view("Teacher", None, is_maintenance_bypass_active=True)
        assert view.is_maintenance_bypass_active is True

    def test_all_display_fields_are_strings(self):
        ctx = {"class_identifier": "P1", "join_code": "JC1", "class_timezone": "US/Eastern"}
        view = build_admin_layout_context_view("Dr. Adams", ctx)
        assert isinstance(view.teacher_display_name, str)
        assert isinstance(view.class_display_name, str)
        assert isinstance(view.class_join_code, str)
        assert isinstance(view.class_timezone, str)

    def test_returns_correct_type(self):
        view = build_admin_layout_context_view("Teacher", None)
        assert isinstance(view, AdminLayoutContextView)


# ---------------------------------------------------------------------------
# Pattern C: StudentLayoutContextView
# ---------------------------------------------------------------------------

class TestStudentLayoutContextView:
    """Tests for build_student_layout_context_view()."""

    def _make_display_metadata(self, **kwargs):
        """Build a minimal DisplayMetadata-like SimpleNamespace."""
        defaults = {
            "student_first_name": "Alex",
            "student_last_name": "Johnson",
            "class_identifier": "Period 1",
            "join_code": "ABC123",
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_full_name_is_uppercased(self):
        """Eliminates layout_student.html line 104: |upper filter in template."""
        meta = self._make_display_metadata()
        view = build_student_layout_context_view(meta)
        assert view.student_display_full_name == "ALEX JOHNSON"

    def test_first_name_is_uppercased(self):
        """First name is pre-formatted to uppercase for layout display."""
        meta = self._make_display_metadata(student_first_name="Casey")
        view = build_student_layout_context_view(meta)
        assert view.student_display_first_name == "CASEY"

    def test_last_initial_extracted_correctly(self):
        """Last initial is single uppercase character from last name."""
        meta = self._make_display_metadata(student_last_name="Williams")
        view = build_student_layout_context_view(meta)
        assert view.student_display_last_initial == "W"

    def test_none_metadata_gives_empty_fields(self):
        view = build_student_layout_context_view(None)
        assert view.student_display_full_name == ""
        assert view.student_display_first_name == ""
        assert view.student_display_last_initial == ""
        assert view.has_class_context is False

    def test_class_context_populated_when_metadata_present(self):
        meta = self._make_display_metadata()
        view = build_student_layout_context_view(meta)
        assert view.has_class_context is True
        assert view.class_display_name == "Period 1"
        assert view.class_join_code == "ABC123"

    def test_missing_class_identifier_falls_back_gracefully(self):
        meta = self._make_display_metadata(class_identifier=None, join_code="XY99")
        view = build_student_layout_context_view(meta)
        # join_code still present → has context
        assert view.has_class_context is True
        assert view.class_join_code == "XY99"

    def test_all_display_fields_are_strings(self):
        meta = self._make_display_metadata()
        view = build_student_layout_context_view(meta)
        assert isinstance(view.student_display_full_name, str)
        assert isinstance(view.student_display_first_name, str)
        assert isinstance(view.student_display_last_initial, str)
        assert isinstance(view.class_display_name, str)
        assert isinstance(view.class_join_code, str)

    def test_returns_correct_type(self):
        view = build_student_layout_context_view(None)
        assert isinstance(view, StudentLayoutContextView)


# ---------------------------------------------------------------------------
# Pattern D: TOTPSetupView
# ---------------------------------------------------------------------------

class TestTOTPSetupView:
    """Tests for build_totp_setup_view()."""

    def _sample_view(self, **kwargs):
        defaults = {
            "totp_secret": "JBSWY3DPEHPK3PXP",
            "qr_b64": "iVBORw0KGgoAAAANSUhEUgAA==",
            "backup_codes": [f"AAAA-BBBB-CCCC-{i:04d}" for i in range(10)],
        }
        defaults.update(kwargs)
        return build_totp_setup_view(**defaults)

    def test_qr_code_data_uri_has_correct_prefix(self):
        """Eliminates template line 257: data:image/png;base64,{{ qr_b64 }} inline assembly."""
        view = self._sample_view(qr_b64="abc123==")
        assert view.qr_code_data_uri == "data:image/png;base64,abc123=="

    def test_qr_code_data_uri_is_complete(self):
        """Template can use {{ view.qr_code_data_uri }} directly in src attribute."""
        view = self._sample_view()
        assert view.qr_code_data_uri.startswith("data:image/png;base64,")

    def test_totp_secret_display_is_raw_secret(self):
        """Eliminates template line 259: {{ totp_secret }} raw variable."""
        view = self._sample_view(totp_secret="MYSECRET1234567890ABCDE")
        assert view.totp_secret_display == "MYSECRET1234567890ABCDE"

    def test_backup_codes_stored_as_tuple(self):
        """Tuples are immutable — no list mutation risk in templates."""
        view = self._sample_view()
        assert isinstance(view.backup_codes, tuple)
        assert len(view.backup_codes) == 10

    def test_backup_codes_formatted_is_newline_separated(self):
        codes = [f"AAAA-BBBB-CCCC-{i:04d}" for i in range(10)]
        view = build_totp_setup_view(totp_secret="SECRET", qr_b64="x", backup_codes=codes)
        lines = view.backup_codes_formatted.split("\n")
        assert len(lines) == 10
        assert lines[0] == codes[0]

    def test_issuer_name_defaults_to_classroom_token_hub(self):
        view = self._sample_view()
        assert view.issuer_name == "Classroom Token Hub"

    def test_issuer_name_can_be_overridden(self):
        view = build_totp_setup_view(
            totp_secret="S", qr_b64="q",
            backup_codes=["X"] * 10,
            issuer_name="My Custom App",
        )
        assert view.issuer_name == "My Custom App"

    def test_all_fields_are_correct_types(self):
        view = self._sample_view()
        assert isinstance(view.qr_code_data_uri, str)
        assert isinstance(view.totp_secret_display, str)
        assert isinstance(view.backup_codes, tuple)
        assert isinstance(view.backup_codes_formatted, str)
        assert isinstance(view.issuer_name, str)

    def test_returns_correct_type(self):
        view = self._sample_view()
        assert isinstance(view, TOTPSetupView)


# ---------------------------------------------------------------------------
# Pattern E: AccountClaimView
# ---------------------------------------------------------------------------

class TestAccountClaimView:
    """Tests for build_account_claim_view()."""

    def test_full_name_assembled_correctly(self):
        view = build_account_claim_view(
            first_name="Alex", last_name="Johnson",
            claim_identifier="CLM-001", remaining_attempts=3, max_attempts=5,
        )
        assert view.student_display_full_name == "Alex Johnson"

    def test_last_initial_extracted(self):
        view = build_account_claim_view(
            first_name="Sam", last_name="Williams",
            claim_identifier="X", remaining_attempts=2, max_attempts=5,
        )
        assert view.student_display_last_initial == "W"

    def test_claim_identifier_preserved(self):
        view = build_account_claim_view(
            first_name="A", last_name="B",
            claim_identifier="CLM-XYZ", remaining_attempts=1, max_attempts=5,
        )
        assert view.claim_identifier == "CLM-XYZ"

    def test_attempts_preserved(self):
        view = build_account_claim_view(
            first_name="A", last_name="B",
            claim_identifier="X", remaining_attempts=2, max_attempts=5,
        )
        assert view.remaining_attempts == 2
        assert view.max_attempts == 5

    def test_empty_name_fields_handled_gracefully(self):
        view = build_account_claim_view(
            first_name="", last_name="",
            claim_identifier="X", remaining_attempts=3, max_attempts=5,
        )
        assert view.student_display_full_name == ""
        assert view.student_display_last_initial == ""

    def test_returns_correct_type(self):
        view = build_account_claim_view(
            first_name="A", last_name="B",
            claim_identifier="X", remaining_attempts=1, max_attempts=3,
        )
        assert isinstance(view, AccountClaimView)


# ---------------------------------------------------------------------------
# Pattern F: AdminClassSelectionView
# ---------------------------------------------------------------------------

class TestAdminClassSelectionView:
    """Tests for build_admin_class_selection_view()."""

    def _sample_classes(self):
        return [
            {"class_id": "uuid-1", "class_identifier": "Period 1", "join_code": "P1ABC", "student_count": 25},
            {"class_id": "uuid-2", "class_identifier": "Period 2", "join_code": "P2DEF", "student_count": 22},
        ]

    def test_has_any_classes_false_when_empty(self):
        view = build_admin_class_selection_view("Teacher", [])
        assert view.has_any_classes is False
        assert len(view.available_classes) == 0

    def test_has_any_classes_true_when_populated(self):
        view = build_admin_class_selection_view("Teacher", self._sample_classes())
        assert view.has_any_classes is True
        assert len(view.available_classes) == 2

    def test_class_options_are_tuple(self):
        """ClassOption list must be a tuple (immutable)."""
        view = build_admin_class_selection_view("Teacher", self._sample_classes())
        assert isinstance(view.available_classes, tuple)

    def test_class_option_fields_populated(self):
        view = build_admin_class_selection_view("Teacher", self._sample_classes())
        first = view.available_classes[0]
        assert first.class_id == "uuid-1"
        assert first.display_name == "Period 1"
        assert first.join_code == "P1ABC"
        assert first.student_count == 25

    def test_current_class_marks_is_current_true(self):
        view = build_admin_class_selection_view(
            "Teacher", self._sample_classes(), current_class_id="uuid-2"
        )
        options = {opt.class_id: opt for opt in view.available_classes}
        assert options["uuid-1"].is_current is False
        assert options["uuid-2"].is_current is True

    def test_no_current_class_all_is_current_false(self):
        view = build_admin_class_selection_view("Teacher", self._sample_classes(), current_class_id=None)
        assert all(not opt.is_current for opt in view.available_classes)

    def test_teacher_display_name_preserved(self):
        view = build_admin_class_selection_view("Dr. Smith", self._sample_classes())
        assert view.teacher_display_name == "Dr. Smith"

    def test_class_option_is_frozen(self):
        view = build_admin_class_selection_view("T", self._sample_classes())
        with pytest.raises((AttributeError, TypeError)):
            view.available_classes[0].display_name = "CHANGED"  # type: ignore[misc]

    def test_returns_correct_type(self):
        view = build_admin_class_selection_view("Teacher", [])
        assert isinstance(view, AdminClassSelectionView)


# ---------------------------------------------------------------------------
# Pattern G: StudentClassSelectionView
# ---------------------------------------------------------------------------

class TestStudentClassSelectionView:
    """Tests for build_student_class_selection_view()."""

    def _sample_classes(self):
        return [
            {"class_id": "uuid-1", "class_identifier": "Period 1", "join_code": "P1", "teacher_name": "Ms. Rivera"},
            {"class_id": "uuid-2", "class_identifier": "Period 3", "join_code": "P3", "teacher_name": "Mr. Chen"},
        ]

    def test_has_any_classes_false_when_empty(self):
        view = build_student_class_selection_view("Alex J.", [])
        assert view.has_any_classes is False

    def test_has_any_classes_true_when_populated(self):
        view = build_student_class_selection_view("Alex J.", self._sample_classes())
        assert view.has_any_classes is True

    def test_class_options_are_tuple(self):
        view = build_student_class_selection_view("Alex J.", self._sample_classes())
        assert isinstance(view.available_classes, tuple)

    def test_teacher_display_name_in_option(self):
        view = build_student_class_selection_view("Alex J.", self._sample_classes())
        assert view.available_classes[0].teacher_display_name == "Ms. Rivera"

    def test_current_class_marked_correctly(self):
        view = build_student_class_selection_view(
            "Alex J.", self._sample_classes(), current_class_id="uuid-1"
        )
        options = {opt.class_id: opt for opt in view.available_classes}
        assert options["uuid-1"].is_current is True
        assert options["uuid-2"].is_current is False

    def test_student_display_name_preserved(self):
        view = build_student_class_selection_view("Jordan M.", self._sample_classes())
        assert view.student_display_name == "Jordan M."

    def test_missing_teacher_name_defaults_to_teacher(self):
        classes = [{"class_id": "uuid-1", "class_identifier": "P1", "join_code": "P1"}]
        view = build_student_class_selection_view("Alex", classes)
        assert view.available_classes[0].teacher_display_name == "Teacher"

    def test_returns_correct_type(self):
        view = build_student_class_selection_view("Alex", [])
        assert isinstance(view, StudentClassSelectionView)


# ---------------------------------------------------------------------------
# Pattern H: No ORM leakage — all fields are primitives
# ---------------------------------------------------------------------------

class TestNoORMLeakage:
    """View models must never contain ORM objects. All values must be primitives."""

    def test_admin_layout_view_contains_only_primitives(self):
        ctx = {"class_identifier": "P1", "join_code": "J1", "class_timezone": "US/Eastern"}
        view = build_admin_layout_context_view("Teacher Name", ctx)
        assert isinstance(view.teacher_display_name, str)
        assert isinstance(view.has_class_context, bool)
        assert isinstance(view.class_timezone, str)
        assert isinstance(view.class_display_name, str)
        assert isinstance(view.class_join_code, str)
        assert isinstance(view.is_maintenance_bypass_active, bool)

    def test_student_layout_view_contains_only_primitives(self):
        meta = SimpleNamespace(
            student_first_name="Alex", student_last_name="J",
            class_identifier="P1", join_code="J1",
        )
        view = build_student_layout_context_view(meta)
        assert isinstance(view.student_display_full_name, str)
        assert isinstance(view.student_display_first_name, str)
        assert isinstance(view.student_display_last_initial, str)
        assert isinstance(view.has_class_context, bool)
        assert isinstance(view.class_display_name, str)
        assert isinstance(view.class_join_code, str)

    def test_totp_view_contains_only_primitives(self):
        view = build_totp_setup_view("SECRET", "base64data", ["CODE"] * 10)
        assert isinstance(view.qr_code_data_uri, str)
        assert isinstance(view.totp_secret_display, str)
        assert isinstance(view.backup_codes, tuple)
        assert all(isinstance(c, str) for c in view.backup_codes)
        assert isinstance(view.backup_codes_formatted, str)
        assert isinstance(view.issuer_name, str)

    def test_admin_class_selection_view_contains_only_primitives(self):
        classes = [{"class_id": "u1", "class_identifier": "P1", "join_code": "J1", "student_count": 20}]
        view = build_admin_class_selection_view("Teacher", classes)
        assert isinstance(view.teacher_display_name, str)
        assert isinstance(view.has_any_classes, bool)
        for opt in view.available_classes:
            assert isinstance(opt.class_id, str)
            assert isinstance(opt.display_name, str)
            assert isinstance(opt.join_code, str)
            assert isinstance(opt.student_count, int)
            assert isinstance(opt.is_current, bool)
