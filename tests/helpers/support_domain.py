"""Canonical Support domain test helper.

This module is the Support-domain wrapper layer over the canonical classroom
initializer and the production Support/admin FEAT routes.

Each helper performs one task only:
- provision a canonical teacher or student session for Support tests
- submit a support ticket through the real admin route
- create a class announcement through the real admin route

No helper here fabricates identity or bypasses production services.
"""

from __future__ import annotations

from flask import Flask

from app.feats.base import FEATContext
from app.utils.issue_categories import init_default_categories
from tests.helpers.classroom_initializer import (
    ProvisionedClassroom,
    ProvisionedStudent,
    initialize_as_student,
    initialize_as_teacher,
)


def initialize_support_teacher(classroom_key: str, client, app: Flask) -> ProvisionedClassroom:
    """Provision the canonical Support classroom and establish a teacher session."""
    return initialize_as_teacher(classroom_key, client, app)


def initialize_support_student(
    classroom_key: str,
    client,
    app: Flask,
    student_index: int = 0,
) -> tuple[ProvisionedClassroom, ProvisionedStudent]:
    """Provision the canonical Support classroom and establish a student session."""
    return initialize_as_student(classroom_key, client, app, student_index=student_index)


def submit_support_ticket(
    client,
    *,
    issue_category: str,
    title: str,
    description: str,
    expected_behavior: str | None = None,
    page_url: str | None = None,
):
    """Submit a support ticket through the production admin help-support route."""
    return client.post(
        "/admin/help-support",
        data={
            "issue_category": issue_category,
            "title": title,
            "description": description,
            "expected_behavior": expected_behavior or "",
            "page_url": page_url or "",
        },
        follow_redirects=True,
    )


def create_class_announcement(
    client,
    *,
    title: str,
    message: str,
    priority: str = "normal",
    is_active: bool = True,
    expires_at: str | None = None,
):
    """Create a class announcement through the production admin announcement route."""
    data = {
        "title": title,
        "message": message,
        "priority": priority,
        "is_active": "y" if is_active else "",
    }
    if expires_at is not None:
        data["expires_at"] = expires_at
    return client.post("/admin/announcements/create", data=data, follow_redirects=True)


def seed_support_issue_categories() -> int:
    """Seed the production default issue categories used by Support routes."""
    with FEATContext("FEAT-SUP-001", idempotency_key="support-domain:default-issue-categories"):
        return init_default_categories()
