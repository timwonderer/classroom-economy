from __future__ import annotations

from typing import Any, Optional

import sqlalchemy as sa
from flask import current_app, g, has_request_context, request, session

from app.extensions import db

# Severity levels considered surface-worthy for operator error dashboards.
_ERROR_LEVELS = ("ERROR", "CRITICAL")


def record(
    *,
    event_type: str,
    severity: str = "info",
    domain: str,
    route: Optional[str] = None,
    actor_id: Optional[int] = None,
    class_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Record structured operational events in a stable, queryable shape.

    Current storage target is application logs; this keeps routing/alert policies
    outside business logic while preserving explicit fail-closed evidence.
    """
    if not event_type or not domain:
        return

    payload = {
        "event_type": event_type,
        "severity": severity,
        "domain": domain,
        "route": route or (request.path if has_request_context() else None),
        "actor_id": actor_id if actor_id is not None else (
            getattr(getattr(g, 'canonical_context', None), 'user_id', None)
            if has_request_context() else None
        ),
        "class_id": class_id,
        "correlation_id": correlation_id,
        "details": details or {},
    }

    # Keep this as warning-or-info style operational telemetry, not exception noise.
    log_fn = current_app.logger.warning if severity in {"warning", "error", "critical", "security"} else current_app.logger.info
    log_fn("OPERATIONAL_EVENT %s", payload)


def get_recent_error_events(limit: int = 5) -> list[dict[str, Any]]:
    """Read the most recent ERROR/CRITICAL operational events (read-only).

    Returns plain dicts so route/GET handlers never touch db.session directly
    (INV-ARC-007: reads route through the service layer, keeping the read out
    of the request handler and satisfying the policy guardrails).
    """
    rows = db.session.execute(
        sa.text(
            "SELECT id, created_at, level, message, payload "
            "FROM operational_events "
            "WHERE level IN ('ERROR', 'CRITICAL') "
            "ORDER BY created_at DESC, id DESC LIMIT :limit"
        ),
        {"limit": limit},
    ).mappings().all()
    return [dict(row) for row in rows]


def get_error_events() -> list[dict[str, Any]]:
    """Read all ERROR/CRITICAL operational events, newest first (read-only).

    Pagination/slicing is performed by the caller; this returns the full
    ordered result set as plain dicts.
    """
    rows = db.session.execute(
        sa.text(
            "SELECT id, created_at, level, payload "
            "FROM operational_events "
            "WHERE level IN ('ERROR', 'CRITICAL') "
            "ORDER BY created_at DESC, id DESC"
        )
    ).mappings().all()
    return [dict(row) for row in rows]
