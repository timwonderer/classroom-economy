from __future__ import annotations

from typing import Any, Optional

from flask import current_app, g, has_request_context, request, session


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
