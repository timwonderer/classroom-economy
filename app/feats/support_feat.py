from __future__ import annotations
from app.extensions import db
from app.models import Issue
from app.feats.base import requires_feat_context
from app.utils.issue_helpers import update_issue_status
from app.utils.canonical_temporal_resolver import utc_now

@requires_feat_context("FEAT-SUP-001")
def execute_close_issue(
    issue: Issue,
    resolution_summary: str,
    teacher_public_id: str | None
) -> None:
    if issue.teacher_notes:
        issue.teacher_notes = f"{issue.teacher_notes}\n\nClosure Summary: {resolution_summary}"
    else:
        issue.teacher_notes = resolution_summary
    issue.closed_at = utc_now()
    issue.closed_by_type = 'teacher'
    update_issue_status(issue, Issue.STATUS_CLOSED, 'teacher', teacher_public_id, notes=resolution_summary)
