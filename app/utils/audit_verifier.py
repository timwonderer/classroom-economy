"""Audit Chain Verifier — Phase 5 implementation.

Provides:
  verify_chain(chain_scope, limit)       — Walk a chain and validate HMAC continuity
  verify_row_lineage(table_name, pk, m)  — Spot-check a single row's payload digest
  run_full_invariant_check()             — Nightly sweep across all active chains

These functions only READ from the DB. They never write.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.extensions import db
from app.utils.canonical_temporal_resolver import utc_now

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protected fields per table — must match the fields passed to audit_protected()
# at write time. Missing a field here → false INVALID; extra field here → false
# INVALID too. Keep in sync with the canonical Ledger write services.
# ---------------------------------------------------------------------------

PROTECTED_FIELDS_BY_TABLE: dict[str, list[str]] = {
    # Keep both names during the Wave 5 table rename transition.
    "transaction": [
        "amount", "account_type", "type", "status",
        "class_id", "seat_id", "description", "correlation_id",
    ],
    "ledger_transaction": [
        "amount", "account_type", "type", "status",
        "class_id", "seat_id", "description", "correlation_id",
    ],
}


# ---------------------------------------------------------------------------
# Result types (re-exported from audit_service for convenience)
# ---------------------------------------------------------------------------

from datetime import timezone as _UTC

from app.services.audit_service import (
    LineageState,
    VerificationResult,
    RowVerificationResult,
    _compute_event_hash,
    _compute_payload_digest,
    _SIGNING_KEY,
)


def _utc_isoformat(dt) -> str:
    """Return an ISO-8601 string normalized to UTC ("+00:00" suffix).

    The emit path computes event_hash using `now_utc.isoformat()` where
    now_utc is always UTC (from the centralized `utc_now()` helper). SQLAlchemy may
    return stored datetimes in the local session timezone. Normalizing here
    ensures the verifier recomputes the same string used at emit time.
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC.utc)
    else:
        dt = dt.astimezone(_UTC.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Internal helper: rebuild actor_context_json from AuditEvent fields
# ---------------------------------------------------------------------------

def _rebuild_actor_context_json(event) -> str:
    ctx = {
        "actor_type": event.actor_type,
        "actor_id_hash": event.actor_id_hash,
        "feat_id": event.feat_id,
        "correlation_id": event.correlation_id,
    }
    return json.dumps(ctx, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------

def verify_chain(chain_scope: str, limit: int = 500) -> VerificationResult:
    """Walk the chain for chain_scope and verify HMAC and hash continuity.

    Steps:
    1. Load events ordered by sequence_number (up to limit).
    2. Recompute each event's event_hash from stored fields.
    3. Verify that previous_hash on event N equals event_hash of event N-1.
    4. Verify no sequence gaps.

    Returns VerificationResult with state VERIFIED, INVALID, or DEGRADED.
    """
    from app.models import AuditEvent, ChainHead  # late import

    try:
        head = ChainHead.query.filter_by(chain_scope=chain_scope).first()
        if head is None:
            return VerificationResult(
                chain_scope=chain_scope,
                state=LineageState.DEGRADED,
                event_count=0,
                failure_type="MISSING_CHAIN_HEAD",
                first_bad_sequence=None,
                last_good_hash=None,
                detail=f"No ChainHead row found for scope '{chain_scope}'",
            )

        events = (
            AuditEvent.query
            .filter_by(chain_scope=chain_scope)
            .order_by(AuditEvent.sequence_number.asc())
            .limit(limit)
            .all()
        )

        if not events:
            return VerificationResult(
                chain_scope=chain_scope,
                state=LineageState.VERIFIED,
                event_count=0,
                failure_type=None,
                first_bad_sequence=None,
                last_good_hash="genesis",
                detail="Chain is empty (no events yet)",
            )

        previous_hash = "genesis"
        last_good_hash = "genesis"
        expected_sequence = 1

        for event in events:
            # Sequence gap check
            if event.sequence_number != expected_sequence:
                return VerificationResult(
                    chain_scope=chain_scope,
                    state=LineageState.INVALID,
                    event_count=expected_sequence - 1,
                    failure_type="SEQUENCE_GAP",
                    first_bad_sequence=expected_sequence,
                    last_good_hash=last_good_hash,
                    detail=(
                        f"Expected sequence {expected_sequence}, "
                        f"found {event.sequence_number}"
                    ),
                )

            # previous_hash continuity check
            if event.previous_hash != previous_hash:
                return VerificationResult(
                    chain_scope=chain_scope,
                    state=LineageState.INVALID,
                    event_count=expected_sequence - 1,
                    failure_type="BAD_HASH",
                    first_bad_sequence=event.sequence_number,
                    last_good_hash=last_good_hash,
                    detail=(
                        f"Hash chain broken at sequence {event.sequence_number}: "
                        f"expected previous_hash={previous_hash!r}, "
                        f"stored={event.previous_hash!r}"
                    ),
                )

            # HMAC recomputation — normalize to UTC so isoformat matches emit path
            created_at_str = _utc_isoformat(event.created_at_utc)
            actor_context_json = _rebuild_actor_context_json(event)
            expected_hash = _compute_event_hash(
                _SIGNING_KEY,
                previous_hash,
                chain_scope,
                event.sequence_number,
                event.table_name,
                event.row_pk,
                event.operation,
                actor_context_json,
                event.payload_digest,
                created_at_str,
            )
            if expected_hash != event.event_hash:
                return VerificationResult(
                    chain_scope=chain_scope,
                    state=LineageState.INVALID,
                    event_count=expected_sequence - 1,
                    failure_type="BAD_HMAC",
                    first_bad_sequence=event.sequence_number,
                    last_good_hash=last_good_hash,
                    detail=f"HMAC mismatch at sequence {event.sequence_number}",
                )

            previous_hash = event.event_hash
            last_good_hash = event.event_hash
            expected_sequence += 1

        return VerificationResult(
            chain_scope=chain_scope,
            state=LineageState.VERIFIED,
            event_count=len(events),
            failure_type=None,
            first_bad_sequence=None,
            last_good_hash=last_good_hash,
            detail=f"Verified {len(events)} event(s) (limit={limit})",
        )

    except Exception as exc:
        logger.exception("Chain verification failed for scope %s", chain_scope)
        return VerificationResult(
            chain_scope=chain_scope,
            state=LineageState.DEGRADED,
            event_count=0,
            failure_type="VERIFIER_ERROR",
            first_bad_sequence=None,
            last_good_hash=None,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Row-level lineage verification
# ---------------------------------------------------------------------------

def verify_row_lineage(
    table_name: str,
    row_pk: str | int,
    model_instance,
) -> RowVerificationResult:
    """Verify that a row's current field values match its linked AuditEvent.

    Lineage state:
    - UNVERIFIED: lineage_event_id is NULL — pre-rollout row, NOT an incident.
    - INVALID: payload_digest mismatch — row was mutated outside a lawful path.
    - VERIFIED: current field values hash to the stored payload_digest.
    - DEGRADED: unexpected error during verification (infrastructure failure).
    """
    from app.models import AuditEvent  # late import

    row_pk_str = str(row_pk)

    lineage_event_id = getattr(model_instance, "lineage_event_id", None)
    if lineage_event_id is None:
        return RowVerificationResult(
            table_name=table_name,
            row_pk=row_pk_str,
            state=LineageState.UNVERIFIED,
            lineage_event_id=None,
            failure_type=None,
            detail="Row predates lineage rollout — UNVERIFIED is expected, not an incident",
        )

    try:
        event = AuditEvent.query.get(lineage_event_id)
        if event is None:
            return RowVerificationResult(
                table_name=table_name,
                row_pk=row_pk_str,
                state=LineageState.INVALID,
                lineage_event_id=lineage_event_id,
                failure_type="MISSING_EVENT",
                detail=f"AuditEvent id={lineage_event_id} not found — deleted or never created",
            )

        protected_fields = PROTECTED_FIELDS_BY_TABLE.get(table_name)
        if protected_fields is None:
            return RowVerificationResult(
                table_name=table_name,
                row_pk=row_pk_str,
                state=LineageState.DEGRADED,
                lineage_event_id=lineage_event_id,
                failure_type="UNKNOWN_TABLE",
                detail=f"No protected field definition for table '{table_name}'",
            )

        current_values = {
            f: getattr(model_instance, f, None)
            for f in protected_fields
        }
        current_digest = _compute_payload_digest(
            event.table_name,
            event.row_pk,
            event.operation,
            event.class_id,
            current_values,
        )

        if current_digest != event.payload_digest:
            return RowVerificationResult(
                table_name=table_name,
                row_pk=row_pk_str,
                state=LineageState.INVALID,
                lineage_event_id=lineage_event_id,
                failure_type="PAYLOAD_MISMATCH",
                detail=(
                    f"Payload digest mismatch for {table_name}:{row_pk_str} — "
                    f"row may have been mutated outside the canonical write path"
                ),
            )

        return RowVerificationResult(
            table_name=table_name,
            row_pk=row_pk_str,
            state=LineageState.VERIFIED,
            lineage_event_id=lineage_event_id,
            failure_type=None,
            detail=None,
        )

    except Exception as exc:
        logger.exception(
            "Row lineage verification failed for %s:%s", table_name, row_pk_str
        )
        return RowVerificationResult(
            table_name=table_name,
            row_pk=row_pk_str,
            state=LineageState.DEGRADED,
            lineage_event_id=lineage_event_id,
            failure_type="VERIFIER_ERROR",
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Full invariant check (called by nightly scheduled job)
# ---------------------------------------------------------------------------

def run_full_invariant_check() -> list[VerificationResult]:
    """Sweep all active class chains and the system chain.

    Returns one VerificationResult per chain scope. Callers should check
    any result with state != VERIFIED and record the failure details.
    """
    from app.models import ChainHead

    results: list[VerificationResult] = []

    try:
        scopes = [row.chain_scope for row in ChainHead.query.all()]
    except Exception as exc:
        logger.exception("Failed to load chain scopes for invariant check")
        return [
            VerificationResult(
                chain_scope="(all)",
                state=LineageState.DEGRADED,
                event_count=0,
                failure_type="SCOPE_LOAD_ERROR",
                first_bad_sequence=None,
                last_good_hash=None,
                detail=str(exc),
            )
        ]

    for scope in scopes:
        result = verify_chain(scope, limit=1000)
        results.append(result)
        if result.state != LineageState.VERIFIED:
            logger.error(
                "Audit chain INVALID for scope=%s: type=%s seq=%s detail=%s",
                scope, result.failure_type, result.first_bad_sequence, result.detail,
            )

    return results


# ---------------------------------------------------------------------------
# Verifier output recorder (called by scheduled job after invariant check)
# ---------------------------------------------------------------------------

def record_integrity_verification(results: list[VerificationResult]) -> None:
    """Record verifier output without writing to a removed status table."""
    failed = [
        {"scope": r.chain_scope, "type": r.failure_type, "detail": r.detail}
        for r in results
        if r.state != LineageState.VERIFIED
    ]
    if failed:
        logger.warning("Invariant check failures: %s", json.dumps(failed))
