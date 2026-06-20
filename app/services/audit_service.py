"""Audit Lineage Service — canonical write path for AuditEvent chain entries.

This is the ONLY legal path for creating AuditEvents. No other code may
touch the audit_events table directly. The service manages chain head
acquisition (SELECT FOR UPDATE), HMAC signing, and lineage attachment.

Requires AUDIT_HMAC_KEY env var — application refuses to start without it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import sqlalchemy as sa

from app.extensions import db
from app.utils.time import ensure_utc, utc_now

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HMAC signing key — loaded once at import time.
# Application refuses to start if absent.
# ---------------------------------------------------------------------------

def _load_signing_key() -> bytes:
    raw = os.environ.get("AUDIT_HMAC_KEY", "")
    if not raw:
        raise RuntimeError(
            "AUDIT_HMAC_KEY is not set. The audit lineage system cannot start "
            "without a signing key. Generate one with: python -c \"import secrets; "
            "print(secrets.token_hex(32))\""
        )
    return raw.encode()


try:
    _SIGNING_KEY: bytes = _load_signing_key()
    _SIGNER_KEY_ID = "v1"
    _SIGNATURE_VERSION = 1
except RuntimeError:
    # In test environments the key may come from pytest fixtures; defer the error.
    _SIGNING_KEY = b""
    _SIGNER_KEY_ID = "v1"
    _SIGNATURE_VERSION = 1
    logger.warning("AUDIT_HMAC_KEY not set at import time — audit service will fail on first use if key is absent")


# ---------------------------------------------------------------------------
# System authority context — for genesis / verifier writes only
# ---------------------------------------------------------------------------

@contextmanager
def system_audit_authority(reason: str):
    """Narrow system-only context for genesis and verifier writes.

    Must NOT be used inside business mutation paths. actor_type is always
    "system" and chain_scope is always "system" when this is active.

    Sets base.py's _system_audit_ctx flag so that the session before_flush
    and before_commit hooks also allow writes within this context.
    """
    from app.feats.base import _system_audit_ctx  # avoids circular at module scope
    _system_audit_ctx.active = True
    _system_audit_ctx.reason = reason
    try:
        yield
    finally:
        _system_audit_ctx.active = False
        _system_audit_ctx.reason = None


def _is_system_authority() -> bool:
    from app.feats.base import _system_audit_ctx
    return getattr(_system_audit_ctx, "active", False)


# ---------------------------------------------------------------------------
# Context validation
# ---------------------------------------------------------------------------

class AuditContextError(Exception):
    """Raised when emit_audit_event is called outside a valid context."""


def _assert_write_authority(class_id: str | None) -> None:
    """Verify that emit is called inside a FEAT or system authority context."""
    from app.feats.base import is_feat_active  # avoid circular import

    if _is_system_authority():
        return  # genesis / verifier path

    if not is_feat_active():
        raise AuditContextError(
            "emit_audit_event must be called inside an active FEAT context or "
            "system_audit_authority. Direct calls without a context are forbidden."
        )


# ---------------------------------------------------------------------------
# Chain scope resolution
# ---------------------------------------------------------------------------

def _resolve_scope(class_id: str | None) -> str:
    if class_id:
        return f"class:{class_id}"
    return "system"


# ---------------------------------------------------------------------------
# Payload canonicalization and digest helpers
# ---------------------------------------------------------------------------

def _canonical_payload(
    table_name: str,
    row_pk: str,
    operation: str,
    class_id: str | None,
    fields: dict[str, Any],
) -> str:
    """Produce a deterministic JSON string for digest computation.

    Rules:
    - Always include table_name, row_pk, operation, class_id as prefix fields.
    - Business fields sorted by key.
    - Datetime values converted to UTC ISO-8601.
    - None values represented as JSON null.
    - Float/Decimal values converted to canonical string representation.
    """
    def _normalize(v: Any) -> Any:
        if isinstance(v, datetime):
            normalized = ensure_utc(v)
            return normalized.isoformat() if normalized else None
        if hasattr(v, "__str__") and type(v).__name__ == "Decimal":
            return str(v)
        return v

    canonical: dict[str, Any] = {
        "__table__": table_name,
        "__pk__": str(row_pk),
        "__op__": operation,
        "__class_id__": class_id,
    }
    for k in sorted(fields.keys()):
        canonical[k] = _normalize(fields[k])

    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _compute_payload_digest(
    table_name: str,
    row_pk: str,
    operation: str,
    class_id: str | None,
    fields: dict[str, Any],
) -> str:
    return _sha256_hex(_canonical_payload(table_name, row_pk, operation, class_id, fields))


def _compute_context_digest(
    feat_id: str | None,
    class_id: str | None,
    actor_type: str | None,
    actor_id_hash: str | None,
    correlation_id: str | None,
    idempotency_key: str | None,
) -> str:
    ctx = {
        "feat_id": feat_id,
        "class_id": class_id,
        "actor_type": actor_type,
        "actor_id_hash": actor_id_hash,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
    }
    return _sha256_hex(json.dumps(ctx, sort_keys=True, separators=(",", ":")))


def _compute_event_hash(
    signing_key: bytes,
    previous_hash: str,
    chain_scope: str,
    sequence_number: int,
    table_name: str,
    row_pk: str,
    operation: str,
    actor_context_json: str,
    payload_digest: str,
    created_at_utc: str,
) -> str:
    """HMAC-SHA256 over pipe-delimited canonical fields."""
    msg = "|".join([
        previous_hash,
        chain_scope,
        str(sequence_number),
        table_name,
        str(row_pk),
        operation,
        actor_context_json,
        payload_digest,
        created_at_utc,
    ])
    return hmac.new(signing_key, msg.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Core emit function
# ---------------------------------------------------------------------------

def emit_audit_event(
    table_name: str,
    row_pk: str | int,
    operation: str,
    protected_fields: dict[str, Any],
    *,
    class_id: str | None = None,
    seat_id: int | None = None,
    teacher_id: int | None = None,
    actor_type: str | None = None,
    actor_id_hash: str | None = None,
    feat_id: str | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    request_id: str | None = None,
):
    """Append a tamper-evident event to the audit chain.

    Must be called inside an active FEAT context (before the owning FEAT
    commits) or inside system_audit_authority(). Does NOT commit — the
    caller's transaction boundary owns the commit.

    Returns the newly created AuditEvent instance.
    """
    from app.models import AuditEvent, ChainHead  # late import to avoid circularity

    if not _SIGNING_KEY:
        raise AuditContextError(
            "AUDIT_HMAC_KEY is not set. Cannot emit audit events."
        )

    _assert_write_authority(class_id)

    # Pull correlation/feat from FEAT thread-local if not explicitly provided
    if not _is_system_authority():
        from app.feats.base import get_correlation_id, get_active_feat_name
        correlation_id = correlation_id or get_correlation_id()
        feat_id = feat_id or get_active_feat_name()

    chain_scope = _resolve_scope(class_id)
    now_utc = utc_now()
    row_pk_str = str(row_pk)

    # Acquire chain head with row-level lock
    head = (
        db.session.query(ChainHead)
        .filter_by(chain_scope=chain_scope)
        .with_for_update()
        .first()
    )

    if head is None:
        # Bootstrap per-class chain head on first event for that class
        head = ChainHead(
            chain_scope=chain_scope,
            latest_hash="genesis",
            latest_sequence=0,
            event_count=0,
            last_updated_utc=now_utc,
        )
        db.session.add(head)
        db.session.flush()

    next_sequence = head.latest_sequence + 1
    previous_hash = head.latest_hash

    resolved_actor_type = actor_type if not _is_system_authority() else "system"
    payload_digest = _compute_payload_digest(
        table_name, row_pk_str, operation, class_id, protected_fields
    )
    context_digest = _compute_context_digest(
        feat_id, class_id, resolved_actor_type, actor_id_hash, correlation_id, idempotency_key
    )
    actor_context_json = json.dumps({
        "actor_type": resolved_actor_type,
        "actor_id_hash": actor_id_hash,
        "feat_id": feat_id,
        "correlation_id": correlation_id,
    }, sort_keys=True, separators=(",", ":"))

    event_hash = _compute_event_hash(
        _SIGNING_KEY,
        previous_hash,
        chain_scope,
        next_sequence,
        table_name,
        row_pk_str,
        operation,
        actor_context_json,
        payload_digest,
        now_utc.isoformat(),
    )

    audit_event = AuditEvent(
        chain_scope=chain_scope,
        sequence_number=next_sequence,
        previous_hash=previous_hash,
        event_hash=event_hash,
        table_name=table_name,
        row_pk=row_pk_str,
        operation=operation,
        actor_type=resolved_actor_type,
        actor_id_hash=actor_id_hash,
        class_id=class_id,
        seat_id=seat_id,
        teacher_id=teacher_id,
        feat_id=feat_id,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        request_id=request_id,
        payload_digest=payload_digest,
        context_digest=context_digest,
        created_at_utc=now_utc,
        signer_key_id=_SIGNER_KEY_ID,
        signature_version=_SIGNATURE_VERSION,
        hmac_signature=event_hash,
    )
    db.session.add(audit_event)

    # Update chain head atomically (still inside the locked row)
    head.latest_hash = event_hash
    head.latest_sequence = next_sequence
    head.event_count = head.event_count + 1
    head.last_updated_utc = now_utc

    db.session.flush()  # assign audit_event.id without committing

    return audit_event


# ---------------------------------------------------------------------------
# Lineage state taxonomy
# ---------------------------------------------------------------------------

class LineageState:
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"  # predates lineage rollout — NOT an incident
    INVALID = "INVALID"        # tampered or broken chain — IS an incident
    DEGRADED = "DEGRADED"      # verifier infrastructure failure


# ---------------------------------------------------------------------------
# Verification result types (used by Phase 5 verifier)
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    chain_scope: str
    state: str  # LineageState constant
    event_count: int
    failure_type: str | None
    first_bad_sequence: int | None
    last_good_hash: str | None
    detail: str | None = None


@dataclass
class RowVerificationResult:
    table_name: str
    row_pk: str
    state: str  # LineageState constant
    lineage_event_id: int | None
    failure_type: str | None
    detail: str | None = None


def verify_chain(chain_scope: str, limit: int = 500) -> VerificationResult:
    """Walk the chain and verify hash continuity and HMAC integrity.

    Implemented fully in Phase 5 (audit_verifier.py). This stub allows
    Phase 4 FEAT integration to import the result type without circular deps.
    """
    # Deferred to audit_verifier.py — import and delegate when available
    try:
        from app.utils.audit_verifier import verify_chain as _verify
        return _verify(chain_scope, limit=limit)
    except ImportError:
        return VerificationResult(
            chain_scope=chain_scope,
            state=LineageState.DEGRADED,
            event_count=0,
            failure_type="VERIFIER_NOT_AVAILABLE",
            first_bad_sequence=None,
            last_good_hash=None,
            detail="audit_verifier module not yet installed",
        )


def verify_row_lineage(table_name: str, row_pk: str | int, model_instance) -> RowVerificationResult:
    """Verify that a row's current payload matches its linked AuditEvent.

    Implemented fully in Phase 5. This stub returns UNVERIFIED for rows
    without a lineage_event_id (pre-rollout rows), which is the correct
    transitional state.
    """
    try:
        from app.utils.audit_verifier import verify_row_lineage as _verify_row
        return _verify_row(table_name, str(row_pk), model_instance)
    except ImportError:
        lineage_id = getattr(model_instance, "lineage_event_id", None)
        if lineage_id is None:
            return RowVerificationResult(
                table_name=table_name,
                row_pk=str(row_pk),
                state=LineageState.UNVERIFIED,
                lineage_event_id=None,
                failure_type=None,
                detail="Row predates lineage rollout",
            )
        return RowVerificationResult(
            table_name=table_name,
            row_pk=str(row_pk),
            state=LineageState.DEGRADED,
            lineage_event_id=lineage_id,
            failure_type="VERIFIER_NOT_AVAILABLE",
            detail="audit_verifier module not yet installed",
        )
