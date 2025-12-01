"""Utilities for cleaning up demo student sessions."""

from app.models import DemoStudent
from app.utils.demo_sessions import cleanup_demo_student_data


def cleanup_demo_student_records(demo_session: DemoStudent) -> None:
    """Backward-compatible shim around :func:`cleanup_demo_student_data`."""

    cleanup_demo_student_data(demo_session)
