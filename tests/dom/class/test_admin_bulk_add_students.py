"""Tests for the paste-based bulk student provisioning endpoint."""

from __future__ import annotations

import json

from app.extensions import db
from app.models import IdentityProfile, Seat
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize_as_teacher


def _post_bulk(client, students):
    return client.post(
        "/admin/students/bulk-add",
        data=json.dumps({"students": students}),
        content_type="application/json",
    )


def _get_student_seats(class_id):
    return (
        Seat.query
        .filter_by(class_id=class_id, role="student")
        .all()
    )


def _get_profile(seat):
    return IdentityProfile.query.filter_by(seat_id=seat.id).first()


class TestBulkAddHappyPath:

    def test_creates_three_unique_students(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        students = [
            {"first_name": "Alice", "last_name": "Smith", "notes": ""},
            {"first_name": "Bob", "last_name": "Jones", "notes": "Section A"},
            {"first_name": "Carol", "last_name": "Lee", "notes": None},
        ]
        resp = _post_bulk(client, students)
        data = resp.get_json()

        assert resp.status_code == 200
        assert data["status"] == "success"
        assert data["created"] == 3
        assert data["join_code"]

        seats = _get_student_seats(cr.class_id)
        created_names = set()
        for seat in seats:
            profile = _get_profile(seat)
            if profile:
                created_names.add((profile.first_name, profile.last_name))
        assert ("Alice", "Smith") in created_names
        assert ("Bob", "Jones") in created_names
        assert ("Carol", "Lee") in created_names

    def test_claim_hashes_set(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        _post_bulk(client, [{"first_name": "Dana", "last_name": "Park"}])

        seat = Seat.query.filter_by(class_id=cr.class_id, role="student").first()
        assert seat is not None
        assert seat.claim_first_name_hash is not None
        assert seat.claim_last_name_hash is not None
        assert seat.roster_fingerprint is not None


class TestTwoColumnPaste:

    def test_notes_omitted(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "Eve", "last_name": "Brown"},
            {"first_name": "Frank", "last_name": "Green"},
        ])
        data = resp.get_json()
        assert data["created"] == 2

        seats = _get_student_seats(cr.class_id)
        for seat in seats:
            profile = _get_profile(seat)
            if profile and profile.first_name in ("Eve", "Frank"):
                assert profile.notes is None


class TestThreeColumnPaste:

    def test_notes_stored(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        _post_bulk(client, [
            {"first_name": "Grace", "last_name": "Kim", "notes": "Transfer student"},
        ])

        seats = _get_student_seats(cr.class_id)
        grace_profile = None
        for seat in seats:
            p = _get_profile(seat)
            if p and p.first_name == "Grace" and p.last_name == "Kim":
                grace_profile = p
                break
        assert grace_profile is not None
        assert grace_profile.notes == "Transfer student"


class TestBlankRowHandling:

    def test_blank_rows_ignored(self, client, app):
        initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "Valid", "last_name": "Student"},
            {"first_name": "", "last_name": ""},
            {"first_name": "  ", "last_name": "  "},
            {"first_name": "Another", "last_name": "Student"},
        ])
        data = resp.get_json()
        assert data["created"] == 2
        assert not data["errors"]


class TestRequiredFieldValidation:

    def test_missing_first_name_error(self, client, app):
        initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "", "last_name": "Smith"},
        ])
        data = resp.get_json()
        assert resp.status_code == 400
        assert any("First name" in e["message"] for e in data["errors"])

    def test_missing_last_name_error(self, client, app):
        initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "Jane", "last_name": ""},
        ])
        data = resp.get_json()
        assert resp.status_code == 400
        assert any("Last name" in e["message"] for e in data["errors"])


class TestBatchLocalDuplicateDetection:

    def test_both_duplicates_get_dedupe_code(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "Juan", "last_name": "Garcia"},
            {"first_name": "Juan", "last_name": "Garcia"},
        ])
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["created"] == 2

        seats = _get_student_seats(cr.class_id)
        juan_seats = [s for s in seats if _get_profile(s) and _get_profile(s).first_name == "Juan"]
        assert len(juan_seats) == 2
        codes = [s.dedupe_code for s in juan_seats]
        assert all(c is not None for c in codes)
        assert codes[0] != codes[1]

    def test_duplicate_warning_not_blocking(self, client, app):
        initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "Juan", "last_name": "Garcia"},
            {"first_name": "Juan", "last_name": "Garcia"},
        ])
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["created"] == 2
        assert not data["errors"]

    def test_differentiated_names_no_collision(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "Juan Carlos", "last_name": "Garcia"},
            {"first_name": "Juan", "last_name": "Garcia"},
        ])
        data = resp.get_json()
        assert data["created"] == 2

        seats = _get_student_seats(cr.class_id)
        for seat in seats:
            assert seat.dedupe_code is None

    def test_three_way_collision(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [
            {"first_name": "Alex", "last_name": "Kim"},
            {"first_name": "Alex", "last_name": "Kim"},
            {"first_name": "Alex", "last_name": "Kim"},
        ])
        data = resp.get_json()
        assert data["created"] == 3

        seats = _get_student_seats(cr.class_id)
        alex_seats = [s for s in seats if _get_profile(s) and _get_profile(s).first_name == "Alex"]
        assert len(alex_seats) == 3
        codes = [s.dedupe_code for s in alex_seats]
        assert all(c is not None for c in codes)
        assert len(set(codes)) == 3


class TestNoExistingRosterLookup:

    def test_does_not_skip_existing_name(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)

        # Pre-create a seat with same name via the canonical provisioning path
        from app.services.classroom_setup import create_roster_student_seat
        from app.hash_utils import hash_username_lookup

        with FEATContext("FEAT-IDEN-001", idempotency_key="test:pre-create:existing"):
            create_roster_student_seat(
                class_id=cr.class_id,
                first_name="Existing",
                last_name="Student",
                claim_first_name_hash=hash_username_lookup("existing"),
                claim_last_name_hash=hash_username_lookup("student"),
                roster_fingerprint=hash_username_lookup(f"{cr.class_id}|existing|student"),
            )

        existing_count_before = len(_get_student_seats(cr.class_id))

        resp = _post_bulk(client, [
            {"first_name": "Existing", "last_name": "Student"},
        ])
        data = resp.get_json()
        assert data["created"] == 1

        assert len(_get_student_seats(cr.class_id)) == existing_count_before + 1


class TestClassScoping:

    def test_seats_use_context_class_id(self, client, app):
        cr = initialize_as_teacher("chemistry_p1", client, app)
        _post_bulk(client, [{"first_name": "Test", "last_name": "Scoped"}])

        seat = Seat.query.filter_by(role="student").order_by(Seat.id.desc()).first()
        assert seat.class_id == cr.class_id


class TestSanitization:

    def test_html_stripped_from_names(self, client, app):
        initialize_as_teacher("chemistry_p1", client, app)
        _post_bulk(client, [
            {"first_name": "<b>Jane</b>", "last_name": "<script>alert(1)</script>Smith"},
        ])

        seat = Seat.query.filter_by(role="student").order_by(Seat.id.desc()).first()
        profile = _get_profile(seat)
        assert "<" not in profile.first_name
        assert "<" not in profile.last_name


class TestEmptyBatch:

    def test_empty_array_rejected(self, client, app):
        initialize_as_teacher("chemistry_p1", client, app)
        resp = _post_bulk(client, [])
        assert resp.status_code == 400

    def test_no_students_key_rejected(self, client, app):
        initialize_as_teacher("chemistry_p1", client, app)
        resp = client.post(
            "/admin/students/bulk-add",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
