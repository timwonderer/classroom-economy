"""Attendance-domain test helper surface.

This module contains only Attendance-domain operations backed by production FEAT
routes. It does not provision classrooms or establish sessions.
"""

from __future__ import annotations

def tap_in_student(client, *, pin: str):
    """Tap a student in via the production /api/tap FEAT route."""
    response = client.post(
        "/api/tap",
        json={
            "action": "tap_in",
            "pin": pin,
        },
    )
    return response


def tap_out_student(client, *, pin: str):
    """Tap a student out via the production /api/tap FEAT route."""
    response = client.post(
        "/api/tap",
        json={
            "action": "tap_out",
            "pin": pin,
        },
    )
    return response


def set_student_tap_enabled(client, *, seat_id: int, tap_enabled: bool):
    """Set tap_enabled for one seat through the production admin FEAT route."""
    return client.post(
        "/api/admin/student/tap-settings",
        json={
            "seat_id": seat_id,
            "tap_enabled": tap_enabled,
        },
    )


def set_block_tap_settings(client, *, tap_enabled: bool, class_id: str):
    """Set tap_enabled for an entire class through the production admin FEAT route."""
    payload = {"tap_enabled": tap_enabled, "class_id": class_id}
    return client.post("/api/admin/block-tap-settings", json=payload)


def get_block_tap_settings(client, *, class_id: str):
    """Read block tap settings through the production admin FEAT route."""
    return client.get(f"/api/admin/block-tap-settings?class_id={class_id}")


def checkout_hall_pass(client, *, pass_id: int):
    """Checkout a hall pass through the production FEAT route."""
    return client.post("/api/hall-pass/checkout", json={"pass_id": pass_id}, headers={"X-CSRFToken": "test"})


def checkin_hall_pass(client, *, pass_id: int):
    """Check in a hall pass through the production FEAT route."""
    return client.post("/api/hall-pass/checkin", json={"pass_id": pass_id}, headers={"X-CSRFToken": "test"})


def approve_hall_pass(client, *, pass_id: int):
    """Approve a hall pass through the production FEAT route."""
    return client.post(f"/api/hall-pass/{pass_id}/approve", headers={"X-CSRFToken": "test"})


def cancel_hall_pass(client, *, pass_id: int):
    """Cancel a hall pass through the production FEAT route."""
    return client.post(f"/api/hall-pass/cancel/{pass_id}", headers={"X-CSRFToken": "test"})


def rotate_hall_pass_verify_token(client):
    """Rotate the teacher hall-pass verification token through the production FEAT route."""
    return client.post("/api/hall-pass/verify-token/rotate")


def get_attendance_history(client):
    """Fetch attendance history through the production FEAT route."""
    return client.get("/api/attendance/history")


def get_hall_pass_history(client):
    """Fetch hall-pass history through the production FEAT route."""
    return client.get("/api/hall-pass/history")


def get_hall_pass_available_types(client, *, class_id: str | None = None, teacher_public_id: str | None = None):
    """Fetch available hall-pass types through the production FEAT route."""
    query = []
    if class_id is not None:
        query.append(f"class_id={class_id}")
    if teacher_public_id is not None:
        query.append(f"teacher_public_id={teacher_public_id}")
    suffix = f"?{'&'.join(query)}" if query else ""
    return client.get(f"/api/hall-pass/available-types{suffix}")
