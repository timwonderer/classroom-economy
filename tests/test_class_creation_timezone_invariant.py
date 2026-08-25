"""Slice 1 — required-timezone class-creation invariant.

A class is never born timezone-less. These tests prove:
  - the pure canonicalizer rejects blank/missing and validates IANA;
  - the canonical create_class() service persists the confirmed zone exactly,
    canonicalizes an explicit UTC selection to 'Etc/UTC', and fails closed on a
    blank value without creating any partial Class/Seat/economic lineage;
  - the latent FEAT-CLASS-001 constructor enforces the same invariant;
  - both live creation surfaces (signup + authenticated add-class) refuse to
    create a class when the timezone is missing.

Scope: creation-time enforcement only. This slice does NOT make the DB column
NOT NULL and does NOT change the temporal resolver's legacy None -> UTC fallback.
"""

from __future__ import annotations

import pytest

from app.extensions import db
from app.feats.base import FEATContext
from app.models import ClassEconomy, EconomicEngine, IdentityProfile, Seat
from app.services.classroom_setup import (
    canonicalize_class_timezone,
    create_class,
    create_teacher,
)
from app.services.context_resolver import CanonicalContext
from app.utils.join_code import generate_join_code
from tests.helpers.canonical_classroom import provision_classroom


# ---------------------------------------------------------------------------
# Pure canonicalizer
# ---------------------------------------------------------------------------


class TestCanonicalizeClassTimezone:

    @pytest.mark.parametrize("bad", [None, "", "   ", "\t"])
    def test_blank_or_missing_fails_closed(self, bad):
        with pytest.raises(ValueError):
            canonicalize_class_timezone(bad)

    def test_explicit_utc_alias_normalized(self):
        assert canonicalize_class_timezone("UTC") == "Etc/UTC"

    def test_etc_utc_passes_through(self):
        assert canonicalize_class_timezone("Etc/UTC") == "Etc/UTC"

    def test_non_utc_iana_zone_preserved_exactly(self):
        assert canonicalize_class_timezone("America/New_York") == "America/New_York"

    def test_surrounding_whitespace_trimmed(self):
        assert canonicalize_class_timezone("  America/Chicago  ") == "America/Chicago"

    def test_invalid_name_rejected(self):
        with pytest.raises(ValueError):
            canonicalize_class_timezone("Not/AZone")


# ---------------------------------------------------------------------------
# create_class() service boundary
# ---------------------------------------------------------------------------


class TestCreateClassServiceInvariant:

    def _make_teacher(self):
        # create_teacher/create_class mutate through the identity FEAT boundary.
        with FEATContext("FEAT-IDEN-001", idempotency_key="tz-invariant:teacher"):
            teacher = create_teacher("tz_invariant_teacher")
        return teacher

    def test_non_utc_zone_persists_exactly(self, app):
        with app.app_context():
            teacher = self._make_teacher()
            with FEATContext("FEAT-IDEN-001", idempotency_key="tz-invariant:class-ny"):
                economy = create_class(
                    teacher.id,
                    join_code=generate_join_code(),
                    display_name="Econ",
                    class_timezone="America/New_York",
                )
            assert economy.class_timezone == "America/New_York"

    def test_explicit_utc_persists_as_etc_utc(self, app):
        with app.app_context():
            teacher = self._make_teacher()
            with FEATContext("FEAT-IDEN-001", idempotency_key="tz-invariant:class-utc"):
                economy = create_class(
                    teacher.id,
                    join_code=generate_join_code(),
                    display_name="Econ",
                    class_timezone="UTC",
                )
            assert economy.class_timezone == "Etc/UTC"

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_blank_timezone_raises_and_creates_no_lineage(self, app, blank):
        with app.app_context():
            teacher = self._make_teacher()

            classes_before = ClassEconomy.query.count()
            seats_before = Seat.query.count()
            profiles_before = IdentityProfile.query.count()
            engines_before = EconomicEngine.query.count()

            with pytest.raises(ValueError):
                with FEATContext("FEAT-IDEN-001", idempotency_key="tz-invariant:blank"):
                    create_class(
                        teacher.id,
                        join_code=generate_join_code(),
                        display_name="Econ",
                        class_timezone=blank,
                        teacher_first_name="Ms.",
                        teacher_last_name="Ayala",
                    )
            db.session.rollback()

            # Fail-closed: no partial Class/Seat/profile/economic-engine lineage.
            assert ClassEconomy.query.count() == classes_before
            assert Seat.query.count() == seats_before
            assert IdentityProfile.query.count() == profiles_before
            assert EconomicEngine.query.count() == engines_before


# ---------------------------------------------------------------------------
# Latent FEAT-CLASS-001 constructor (point 5)
# ---------------------------------------------------------------------------


class TestCreateClassBoundaryFeatInvariant:

    def _teacher_ctx(self, classroom) -> CanonicalContext:
        return CanonicalContext(
            user_id=classroom.teacher_user_id,
            class_id=classroom.class_id,
            seat_id=classroom.teacher_seat_id,
            actor_role="teacher",
        )

    def test_blank_timezone_rejected(self, app):
        from app.feats.class_configuration import execute_create_class_boundary

        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            db.session.commit()

            result = execute_create_class_boundary(
                canonical_context=self._teacher_ctx(classroom),
                class_name="Second Class",
                timezone="",
                idempotency_key="feat:class:create:tz-blank",
            )
            assert result.success is False
            assert result.error_code == "INVALID_TIMEZONE"

    def test_explicit_utc_persists_as_etc_utc(self, app):
        from app.feats.class_configuration import execute_create_class_boundary

        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            db.session.commit()

            result = execute_create_class_boundary(
                canonical_context=self._teacher_ctx(classroom),
                class_name="Second Class",
                timezone="UTC",
                idempotency_key="feat:class:create:tz-utc",
            )
            assert result.success is True
            created = db.session.get(ClassEconomy, result.class_id)
            assert created.class_timezone == "Etc/UTC"

    def test_non_utc_zone_persists_exactly(self, app):
        from app.feats.class_configuration import execute_create_class_boundary

        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            db.session.commit()

            result = execute_create_class_boundary(
                canonical_context=self._teacher_ctx(classroom),
                class_name="Second Class",
                timezone="America/Denver",
                idempotency_key="feat:class:create:tz-denver",
            )
            assert result.success is True
            created = db.session.get(ClassEconomy, result.class_id)
            assert created.class_timezone == "America/Denver"


# ---------------------------------------------------------------------------
# Live creation surfaces refuse timezone-less classes
# ---------------------------------------------------------------------------


class TestCreationSurfacesRequireTimezone:

    def test_signup_step1_rejects_missing_timezone(self, app, client):
        """Signup step 1 must not stage a class without a timezone."""
        with app.app_context():
            classes_before = ClassEconomy.query.count()

        # No class_timezone in the POST body — step 1 should not advance.
        resp = client.post(
            "/admin/signup",
            data={
                "signup_step": "class_setup",
                "class_display_name": "Chemistry",
                "first_name": "Ms.",
                "last_name": "Ayala",
                "tos_agreed": "true",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            # No class row created (staging never completed).
            assert ClassEconomy.query.count() == classes_before

    def test_authenticated_add_class_rejects_missing_timezone(self, app, client):
        """Authenticated add-class must reject a blank timezone and create nothing."""
        from tests.helpers.classroom_initializer import initialize_as_teacher

        # initialize_as_teacher manages its own app context + live teacher session.
        initialize_as_teacher("chemistry_p1", client, app)
        with app.app_context():
            classes_before = ClassEconomy.query.count()

        resp = client.post(
            "/admin/create-class",
            data={
                "class_display_name": "New Class",
                "first_name": "Ms.",
                "last_name": "Ayala",
                # class_timezone deliberately omitted
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

        with app.app_context():
            assert ClassEconomy.query.count() == classes_before
