"""Canonical Identity domain test helpers.

This module contains Identity-domain operations that are exercised by tests
and implemented through production FEAT routes.
"""

from __future__ import annotations

from typing import Any

from flask.testing import FlaskClient


def admin_generate_recovery_code(client: FlaskClient, seat_id: int):
    return client.post(f"/recovery/admin/generate-code/{seat_id}", follow_redirects=False)


def student_login(client: FlaskClient, *, username: str, pin: str, follow_redirects: bool = False):
    return client.post("/student/login", data={"username": username, "pin": pin}, follow_redirects=follow_redirects)


def student_get_dashboard(client: FlaskClient, *, follow_redirects: bool = False):
    return client.get("/student/dashboard", follow_redirects=follow_redirects)


def student_login_next(
    client: FlaskClient,
    *,
    username: str,
    pin: str,
    next_path: str,
    follow_redirects: bool = False,
):
    return client.post(
        f"/student/login?next={next_path}",
        data={"username": username, "pin": pin},
        follow_redirects=follow_redirects,
    )


def student_lookup_recovery_code(client: FlaskClient, reset_code: str, *, follow_redirects: bool = True):
    return client.post("/recovery/lookup", data={"reset_code": reset_code}, follow_redirects=follow_redirects)


def student_create_username(client: FlaskClient, write_in_word: str, *, follow_redirects: bool = True):
    return client.post(
        "/student/create-username",
        data={"write_in_word": write_in_word},
        follow_redirects=follow_redirects,
    )


def student_setup_pin_passphrase(
    client: FlaskClient,
    *,
    pin: str,
    confirm_pin: str,
    passphrase: str,
    confirm_passphrase: str,
    follow_redirects: bool = True,
):
    return client.post(
        "/student/setup-pin-passphrase",
        data={
            "pin": pin,
            "confirm_pin": confirm_pin,
            "passphrase": passphrase,
            "confirm_passphrase": confirm_passphrase,
        },
        follow_redirects=follow_redirects,
    )


def student_switch_class(client: FlaskClient, class_id: str):
    return client.post(f"/student/switch-class/{class_id}")


def admin_set_current_class(client: FlaskClient, class_id: str):
    return client.post("/admin/current-class", json={"class_id": class_id})


def admin_passkey_register_start(client: FlaskClient):
    return client.post("/admin/passkey/register/start", json={})


def admin_passkey_auth_finish(client: FlaskClient, *, token: str):
    return client.post("/admin/passkey/auth/finish", json={"token": token})


def sysadmin_passkey_auth_finish(client: FlaskClient, *, token: str):
    return client.post("/sysadmin/passkey/auth/finish", json={"token": token})


def admin_delete_join_code(client: FlaskClient, join_code: str, confirm_join_code: str | None = None):
    payload: dict[str, Any] = {"join_code": join_code}
    if confirm_join_code is not None:
        payload["confirm_join_code"] = confirm_join_code
    return client.post("/admin/join-code/delete", json=payload)


def admin_add_individual_student(
    client: FlaskClient,
    *,
    first_name: str,
    last_name: str,
    dob: str,
    block_select: str,
    follow_redirects: bool = False,
):
    return client.post(
        "/admin/student/add-individual",
        data={
            "first_name": first_name,
            "last_name": last_name,
            "dob": dob,
            "block_select": block_select,
        },
        follow_redirects=follow_redirects,
    )


def admin_edit_student(
    client: FlaskClient,
    *,
    seat_id: int,
    first_name: str,
    last_name: str,
    blocks: list[str],
    follow_redirects: bool = False,
):
    return client.post(
        "/admin/student/edit",
        data={
            "seat_id": seat_id,
            "first_name": first_name,
            "last_name": last_name,
            "blocks": blocks,
        },
        follow_redirects=follow_redirects,
    )


def admin_enforce_daily_limits(client: FlaskClient):
    return client.post("/admin/enforce-daily-limits")


def admin_get_students(client: FlaskClient):
    return client.get("/admin/students")


def admin_get_store(client: FlaskClient, *, block: str | None = None):
    path = "/admin/store" if block is None else f"/admin/store?block={block}"
    return client.get(path)


def admin_create_store_item(client: FlaskClient, *, data: dict[str, Any] | None = None, follow_redirects: bool = False):
    return client.post("/admin/store", data=data or {}, follow_redirects=follow_redirects)


def admin_update_payroll_settings(client: FlaskClient, *, data: dict[str, Any] | None = None, follow_redirects: bool = False):
    return client.post("/admin/payroll/settings", data=data or {}, follow_redirects=follow_redirects)


def admin_get_banking(client: FlaskClient, *, block: str | None = None):
    path = "/admin/banking" if block is None else f"/admin/banking?block={block}"
    return client.get(path)


def admin_get_transactions(client: FlaskClient, *, block: str | None = None, follow_redirects: bool = False):
    path = "/admin/transactions" if block is None else f"/admin/transactions?block={block}"
    return client.get(path, follow_redirects=follow_redirects)


def admin_get_attendance_log(client: FlaskClient, *, follow_redirects: bool = False):
    return client.get("/admin/attendance-log", follow_redirects=follow_redirects)


def api_get_attendance_history(client: FlaskClient):
    return client.get("/api/attendance/history")


def student_help_support(client: FlaskClient, *, follow_redirects: bool = True):
    return client.get("/student/help-support", follow_redirects=follow_redirects)
