"""Ticket-Log Correlation Pack (TLCP) helpers."""

from __future__ import annotations

import os
import random
import uuid
from datetime import timedelta

import sqlalchemy as sa
from flask import has_request_context, request, current_app

from app.extensions import db
from app.models import ActorRequestTrace, ClassEconomy, Seat
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import utc_now

CORRELATION_VERSION = 1
DEFAULT_TRACE_LIMIT = 20
DEFAULT_TRACE_TTL_DAYS = 7
DEFAULT_ERROR_WINDOW_HOURS = 2
DEFAULT_RECENT_ERROR_MINUTES = 15
DEFAULT_TRACE_FETCH_MULTIPLIER = 4
TTL_CLEANUP_PROBABILITY = 0.01  # ~1% of requests trigger global TTL cleanup
DEFAULT_NOISE_ENDPOINT_PREFIXES = (
    "/static/",
    "/sw.js",
    "/favicon.ico",
    "/api/set-timezone",
)

# TODO: No namespaced authority doc (INV-*, DOM-*, FEAT-*) currently governs
# which endpoints are public vs authenticated. Create an authoritative doc
# (e.g. INV-ARC-0XX_ROUTE_ACCESS_CLASSIFICATION) that defines:
#   1. The classification tiers (public, authenticated, class-scoped)
#   2. The criteria for each tier
#   3. The canonical list of public endpoints and the rationale for each
#   4. The enforcement mechanism (this set + TLCP gating)
# Until then, changes to these sets have no constitutional audit trail.
DEFAULT_PUBLIC_ENDPOINTS = {
    "docs.index",
    "docs.timeline",
    "docs.view_doc",
    "docs.search",
    "admin.login",
    "main.district",
    "main.offline",
    "main.service_worker",
    "main.verify_hall_pass",
    "api.get_tips",
}

# TODO: Same gap — no authoritative doc governs which endpoints bypass
# canonical context resolution. Document alongside the route access
# classification spec above.
DEFAULT_NO_CONTEXT_ENDPOINTS = {
    "admin.onboarding",
    "admin.signup",
    "admin.select_class_context",
    "student.select_class_context",
}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _sanitize_error_message(raw_message: str | None) -> str:
    if not raw_message:
        return ""
    compact = " ".join(str(raw_message).split())
    return compact[:500]


def _error_events_available(bind=None) -> bool:
    """Return True only when the ``error_events`` table physically exists.

    ``error_events`` was dropped by migration 7c3d4e5f6a7b (slated for
    absorption into operational_events, DOM-OPS-001, which is not yet built).
    Both the writer (app/__init__.py) and these readers must guard on the
    table's presence so the correlation surface degrades to "no errors"
    instead of raising when the table is absent. It must NEVER be confused
    with the tamper-evident ``audit_events`` chain, whose schema differs.
    """
    try:
        bind = bind if bind is not None else db.session.get_bind()
        return sa.inspect(bind).has_table("error_events")
    except Exception:
        return False


def _error_event_rows(sql: str, params: dict) -> list:
    """Run a guarded read against ``error_events``; [] when the table is absent."""
    if not _error_events_available():
        return []
    result = db.session.execute(sa.text(sql), params)
    return [dict(row) for row in result.mappings()]


def _noise_endpoint_prefixes() -> tuple[str, ...]:
    raw = os.getenv("TLCP_NOISE_ENDPOINT_PREFIXES")
    if not raw:
        return DEFAULT_NOISE_ENDPOINT_PREFIXES
    prefixes = tuple(part.strip() for part in raw.split(",") if part.strip())
    return prefixes or DEFAULT_NOISE_ENDPOINT_PREFIXES


def _is_noise_endpoint(endpoint: str | None) -> bool:
    if not endpoint:
        return True
    return any(endpoint.startswith(prefix) for prefix in _noise_endpoint_prefixes())


def _is_public_request(endpoint: str | None, path: str | None) -> bool:
    if endpoint in DEFAULT_PUBLIC_ENDPOINTS:
        return True
    if path and any(path.startswith(prefix) for prefix in _noise_endpoint_prefixes()):
        return True
    return False


def _log_invariant_violation(message: str, *, context: CanonicalContext | None = None) -> None:
    extra = {
        "actor_type": "-",
        "actor_public_id": "-",
        "class_id": "-",
        "error_class": "InvariantViolation",
        "correlation_version": CORRELATION_VERSION,
    }
    if context is not None:
        extra.update(
            actor_type=context.actor_role,
            class_id=context.class_id,
        )
    current_app.logger.error(f"TLCP-INVARIANT-VIOLATION: {message}", extra=extra)


def resolve_actor_context(context: CanonicalContext | None) -> dict | None:
    """Convert canonical request context into correlation logging fields."""
    if not has_request_context():
        return None
    if context is None:
        endpoint = request.endpoint
        if request.endpoint in DEFAULT_NO_CONTEXT_ENDPOINTS:
            return None
        if _is_public_request(endpoint, request.path):
            return None
        _log_invariant_violation("missing canonical context")
        return None

    seat = db.session.get(Seat, context.seat_id)
    if not seat:
        _log_invariant_violation("missing canonical seat", context=context)
        return None

    actor_type = seat.role
    actor_id = context.user_id
    class_id = context.class_id
    actor_public_id = seat.public_id

    endpoint = request.url_rule.rule if request.url_rule and request.url_rule.rule else request.path
    return {
        "actor_type": actor_type,
        "actor_id": actor_id,
        "actor_public_id": actor_public_id,
        "class_id": class_id,
        "endpoint": endpoint,
        "method": request.method,
    }


def persist_request_trace(
    context: dict | None,
    request_id: str | None,
    status_code: int | None,
    *,
    _session=None,
) -> None:
    """Persist request trace rows with bounded retention.

    Pass ``_session`` to use an isolated SQLAlchemy session instead of the
    default request-scoped ``db.session``.  The caller is responsible for
    committing (or rolling back) the provided session.
    """
    if not context or not context.get("actor_public_id"):
        return

    sess = _session if _session is not None else db.session

    trace_limit = _int_env("TLCP_TRACE_LIMIT", DEFAULT_TRACE_LIMIT)
    ttl_days = _int_env("TLCP_TRACE_TTL_DAYS", DEFAULT_TRACE_TTL_DAYS)
    now = utc_now()
    ttl_cutoff = now - timedelta(days=ttl_days)

    request_id = request_id or uuid.uuid4().hex

    trace = ActorRequestTrace(
        actor_type=context.get("actor_type"),
        actor_public_id=context.get("actor_public_id"),
        class_id=context.get("class_id"),
        request_id=request_id,
        method=context.get("method"),
        endpoint=context.get("endpoint"),
        status_code=status_code,
        created_at=now,
    )
    sess.add(trace)
    sess.flush()

    ids_to_keep = (
        sess.query(ActorRequestTrace.id)
        .filter(
            ActorRequestTrace.actor_type == context.get("actor_type"),
            ActorRequestTrace.actor_public_id == context.get("actor_public_id"),
        )
        .order_by(ActorRequestTrace.created_at.desc(), ActorRequestTrace.id.desc())
        .limit(trace_limit)
        .subquery()
    )

    sess.query(ActorRequestTrace).filter(
        ActorRequestTrace.actor_type == context.get("actor_type"),
        ActorRequestTrace.actor_public_id == context.get("actor_public_id"),
        ~ActorRequestTrace.id.in_(sa.select(ids_to_keep.c.id)),
    ).delete(synchronize_session=False)

    # Run global TTL cleanup probabilistically to avoid O(table) contention on every hot-path call.
    if random.random() < TTL_CLEANUP_PROBABILITY:
        sess.query(ActorRequestTrace).filter(
            ActorRequestTrace.created_at < ttl_cutoff
        ).delete(synchronize_session=False)

        # Prune the correlation error log (NOT the tamper-evident audit_events
        # chain). Guarded because error_events may be absent (see
        # _error_events_available); a missing table must be a no-op.
        if _error_events_available(sess.get_bind()):
            sess.execute(
                sa.text("DELETE FROM error_events WHERE created_at < :cutoff"),
                {"cutoff": ttl_cutoff},
            )


def save_error_event(
    *,
    request_id: str | None,
    actor_type: str | None,
    actor_public_id: str | None,
    class_id: str | None,
    endpoint: str | None,
    method: str | None,
    error_class: str,
    error_message: str | None,
) -> None:
    """Persist a short-lived error event for ticket correlation.

    Writes to the ``error_events`` correlation log via guarded raw SQL so the
    schema stays decoupled from any ORM model and the call degrades to a no-op
    when the table is absent (see _error_events_available). This is NOT the
    tamper-evident ``audit_events`` chain.
    """
    if not actor_type or not actor_public_id:
        return
    if not _error_events_available():
        return

    db.session.execute(
        sa.text(
            """
            INSERT INTO error_events
                (request_id, actor_type, actor_public_id, class_id,
                 endpoint, method, error_class, error_message,
                 correlation_version, created_at)
            VALUES
                (:request_id, :actor_type, :actor_public_id, :class_id,
                 :endpoint, :method, :error_class, :error_message,
                 :correlation_version, :created_at)
            """
        ),
        {
            "request_id": request_id,
            "actor_type": actor_type,
            "actor_public_id": actor_public_id,
            "class_id": class_id,
            "endpoint": endpoint,
            "method": method,
            "error_class": error_class,
            "error_message": _sanitize_error_message(error_message),
            "correlation_version": CORRELATION_VERSION,
            "created_at": utc_now(),
        },
    )


def has_recent_error_for_actor(
    actor_type: str,
    actor_public_id: str,
    recent_minutes: int | None = None,
) -> bool:
    """Return True when the actor has a recent error event.

    Degrades to False when the ``error_events`` table is absent.
    """
    minutes = recent_minutes or _int_env("TLCP_RECENT_ERROR_MINUTES", DEFAULT_RECENT_ERROR_MINUTES)
    cutoff = utc_now() - timedelta(minutes=minutes)
    rows = _error_event_rows(
        """
        SELECT id FROM error_events
        WHERE actor_type = :actor_type
          AND actor_public_id = :actor_public_id
          AND created_at >= :cutoff
        LIMIT 1
        """,
        {
            "actor_type": actor_type,
            "actor_public_id": actor_public_id,
            "cutoff": cutoff,
        },
    )
    return bool(rows)


def create_ticket_correlation_pack(
    *,
    issue_id: int,
    actor_type: str,
    actor_public_id: str,
    class_id: str | None,
    ticket_created_at,
    include_recent_error: bool = True,
) -> dict:
    """Create immutable correlation snapshot for a ticket."""
    trace_limit = _int_env("TLCP_TRACE_LIMIT", DEFAULT_TRACE_LIMIT)
    ttl_days = _int_env("TLCP_TRACE_TTL_DAYS", DEFAULT_TRACE_TTL_DAYS)
    error_window_hours = _int_env("TLCP_ERROR_WINDOW_HOURS", DEFAULT_ERROR_WINDOW_HOURS)

    fetch_limit = trace_limit * _int_env("TLCP_TRACE_FETCH_MULTIPLIER", DEFAULT_TRACE_FETCH_MULTIPLIER)
    trace_rows = (
        ActorRequestTrace.query.filter_by(
            actor_type=actor_type,
            actor_public_id=actor_public_id,
        )
        .order_by(ActorRequestTrace.created_at.desc(), ActorRequestTrace.id.desc())
        .limit(fetch_limit)
        .all()
    )

    prioritized = [row for row in trace_rows if not _is_noise_endpoint(row.endpoint)]
    noisy = [row for row in trace_rows if _is_noise_endpoint(row.endpoint)]
    ranked_rows = (prioritized + noisy)[:trace_limit]

    request_trace_json = [
        {
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "method": row.method,
            "endpoint": row.endpoint,
            "request_id": row.request_id,
            "status_code": row.status_code,
            "class_id": row.class_id,
        }
        for row in ranked_rows
    ]

    error_window_start = ticket_created_at - timedelta(hours=error_window_hours)
    error_rows = (
        _error_event_rows(
            """
            SELECT request_id, endpoint, method, error_class, error_message,
                   class_id, created_at
            FROM error_events
            WHERE actor_type = :actor_type
              AND actor_public_id = :actor_public_id
              AND created_at >= :window_start
              AND created_at <= :ticket_created_at
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """,
            {
                "actor_type": actor_type,
                "actor_public_id": actor_public_id,
                "window_start": error_window_start,
                "ticket_created_at": ticket_created_at,
                "limit": trace_limit,
            },
        )
        if include_recent_error
        else []
    )

    if include_recent_error and not error_rows:
        ttl_cutoff = ticket_created_at - timedelta(days=ttl_days)
        error_rows = _error_event_rows(
            """
            SELECT request_id, endpoint, method, error_class, error_message,
                   class_id, created_at
            FROM error_events
            WHERE actor_type = :actor_type
              AND actor_public_id = :actor_public_id
              AND created_at >= :ttl_cutoff
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            {
                "actor_type": actor_type,
                "actor_public_id": actor_public_id,
                "ttl_cutoff": ttl_cutoff,
            },
        )

    def _iso(value):
        return value.isoformat() if value is not None and hasattr(value, "isoformat") else value

    error_refs_json = [
        {
            "timestamp": _iso(row.get("created_at")),
            "endpoint": row.get("endpoint"),
            "request_id": row.get("request_id"),
            "error_class": row.get("error_class"),
            "error_message": row.get("error_message"),
            "method": row.get("method"),
            "class_id": row.get("class_id"),
        }
        for row in error_rows
    ]

    return {
        "issue_id": issue_id,
        "correlation_version": CORRELATION_VERSION,
        "actor_type": actor_type,
        "actor_public_id": actor_public_id,
        "class_id": class_id,
        "request_trace_json": request_trace_json,
        "error_refs_json": error_refs_json,
        "created_at": utc_now(),
    }
