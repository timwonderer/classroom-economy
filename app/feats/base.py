from __future__ import annotations
import threading
from functools import wraps
from typing import Any, Callable, Optional, Dict, List
import uuid
import logging
import os
from datetime import datetime
from enum import Enum, auto
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy import event
from app.extensions import db

logger = logging.getLogger(__name__)

# Thread-local storage for FEAT context
_feat_context = threading.local()

# Thread-local flag set by audit_service.system_audit_authority().
# Allows the audit infrastructure to flush/commit without a FEAT context.
_system_audit_ctx = threading.local()


def is_system_audit_authority() -> bool:
    """Return True if system_audit_authority context is active in this thread."""
    return getattr(_system_audit_ctx, "active", False)

def generate_correlation_id() -> str:
    """Generate a unique correlation ID for cross-domain tracking."""
    import uuid
    return f"corr_{uuid.uuid4().hex}"

def validate_id_format(value: str, prefix: str) -> bool:
    """Verify that an ID follows the required naming convention."""
    if not value: return False
    return value.startswith(prefix) or value.startswith("bypass_test_")

def correlation_type(corr_id: str) -> str:
    """Classify a correlation ID into its lifecycle category."""
    if not corr_id or corr_id == "NO-CORRELATION": return "unknown"
    if corr_id.startswith("corr_"): return "prod"
    if corr_id.startswith("bypass_test_"): return "test"
    return "unclassified"

def is_feat_active() -> bool:
    """Check if a FEAT context is currently active in the current thread."""
    return getattr(_feat_context, "active_feat", None) is not None

def get_active_feat_name() -> Optional[str]:
    """Return the name of the currently active FEAT."""
    return getattr(_feat_context, "active_feat", None)

def get_correlation_id() -> str:
    """Return the current correlation ID or a placeholder."""
    return getattr(_feat_context, "correlation_id", "NO-CORRELATION")

def is_nested_feat() -> bool:
    """Check if the current FEAT is nested inside another FEAT."""
    return hasattr(_feat_context, "stack") and len(_feat_context.stack) > 0


def _resolve_session(session):
    """Return the underlying SQLAlchemy ``Session`` for transaction introspection.

    ``db.session`` is a ``scoped_session`` proxy, and (in SQLAlchemy 2.0) it does
    NOT proxy ``in_transaction``/``in_nested_transaction``/``get_transaction``.
    Calling the proxy yields the thread-local ``Session``, which does expose them.
    Passing an already-resolved ``Session`` is a no-op.
    """
    if hasattr(session, "get_transaction"):
        return session
    if callable(session):
        try:
            return session()
        except Exception:  # noqa: BLE001
            return session
    return session


def is_discardable_read_autobegin(session) -> bool:
    """Return True only for an incidental read-only autobegin transaction.

    SQLAlchemy opens a transaction implicitly on the first read of a session
    (``origin == AUTOBEGIN``). In request handling this happens in Flask's
    ``before_request`` canonical-context resolution, well before any route body
    runs. If a *top-level* FEAT then opens while that autobegin is live, the FEAT
    takes a ``begin_nested()`` SAVEPOINT instead of a top-level ``begin()`` — and
    releasing a savepoint is NOT a commit, so the FEAT's mutations are silently
    discarded at request teardown (FEAT-ENTRY logged, but never
    FEAT-COMMIT-OWNERSHIP).

    Such an autobegin provably carries no writes: the ``before_flush`` guard in
    this module forbids flushing mutated state outside a verified FEAT context,
    so any un-owned DML would already have raised. Discarding it is therefore
    lossless, and lets the FEAT own a real top-level transaction whose commit
    persists.

    The predicate is deliberately narrow. It returns False — leaving the existing
    ``begin_nested()`` behavior intact — for every state that is NOT an incidental
    read autobegin:

    * pending ORM mutation (``session.new``/``dirty``/``deleted`` non-empty);
    * an explicit ``session.begin()`` boundary (``origin == BEGIN``);
    * an active SAVEPOINT / nested transaction;
    * any state where the transaction origin cannot be positively confirmed.
    """
    session = _resolve_session(session)

    # Pending ORM mutation must never be discarded.
    if session.new or session.dirty or session.deleted:
        return False

    # A flush clears session.new/dirty/deleted, but the emitted INSERT/UPDATE/DELETE
    # still lives in the open transaction as uncommitted DML. The ``before_flush``
    # listener records this on ``session.info`` so a post-flush transaction is never
    # mistaken for a clean read autobegin and silently rolled back.
    if session.info.get("_txn_dml_flushed"):
        return False

    # An active SAVEPOINT is an intentional nested boundary, not a read autobegin.
    if bool(getattr(session, "in_nested_transaction", lambda: False)()):
        return False

    try:
        root = session.get_transaction()
    except Exception:  # noqa: BLE001 — scoped-session states may reject introspection
        return False
    if root is None:
        return False

    origin = getattr(root, "origin", None)
    # Positive confirmation only: discard exclusively when the root transaction
    # was opened implicitly by an autobegin. Anything else (BEGIN, BEGIN_NESTED,
    # SUBTRANSACTION, or an unreadable origin) is preserved.
    return getattr(origin, "name", None) == "AUTOBEGIN"


def _is_top_level_autobegin(session) -> bool:
    """True when the session's live root transaction is a top-level AUTOBEGIN.

    Unlike ``is_discardable_read_autobegin`` this makes no claim about whether the
    autobegin is clean — it only confirms the transaction origin is AUTOBEGIN and
    that no savepoint is currently active. A top-level FEAT uses this to recognise
    an autobegin that already carries pending/flushed writes so it can ADOPT and
    commit that transaction rather than nest a savepoint under it (which would
    never commit the underlying writes).
    """
    session = _resolve_session(session)
    if bool(getattr(session, "in_nested_transaction", lambda: False)()):
        return False
    try:
        root = session.get_transaction()
    except Exception:  # noqa: BLE001
        return False
    if root is None:
        return False
    origin = getattr(root, "origin", None)
    return getattr(origin, "name", None) == "AUTOBEGIN"

class GuardReason(Enum):
    """Central registry of standard guard failure reasons."""
    INSUFFICIENT_FUNDS = auto()
    RENT_DELINQUENT = auto()
    FEATURE_DISABLED = auto()
    ENTITLEMENT_REQUIRED = auto()
    QUOTA_EXCEEDED = auto()
    UNAUTHORIZED_ACTOR = auto()
    INVALID_CONTEXT = auto()
    IDEMPOTENCY_CONFLICT = auto()
    SYSTEM_MAINTENANCE = auto()
    LEGACY_VIOLATION = auto() # Used for temporary wrapping of old code
    MAINTENANCE_MODE = auto()

def guard_ok(): 
    """Return a successful guard response."""
    return {"allowed": True, "reason": None}

def guard_block(reason: GuardReason): 
    """Return a blocked guard response with reason."""
    return {"allowed": False, "reason": reason}

class FEATContextError(Exception):
    """Raised when a mutation is attempted outside a FEAT context."""
    pass


class InvariantViolation(Exception):
    """Raised when runtime state violates a canonical architectural invariant."""
    pass

# Canonical FEAT Registry
FEAT_REGISTRY = {
    "FEAT-BYPASS-LEGACY": {"domain": "Test", "blast_radius": "LOW", "desc": "Legacy fixture bypass"},
    "FEAT-LED-000": {"domain": "Ledger", "blast_radius": "HIGH", "desc": "Canonical Monetary Resolution"},
    "FEAT-LED-001": {"domain": "Ledger", "blast_radius": "HIGH", "desc": "Overdraft Fee Application"},
    "FEAT-LED-002": {"domain": "Ledger", "blast_radius": "HIGH", "desc": "Void Transaction"},
    "FEAT-LED-003": {"domain": "Ledger", "blast_radius": "HIGH", "desc": "Settlement Sweep"},
    "FEAT-LED-004": {"domain": "Ledger", "blast_radius": "HIGH", "desc": "Payroll Execution"},
    "FEAT-IDEN-001": {"domain": "Identity", "blast_radius": "LOW", "desc": "Unauthenticated Student Seat Claim"},
    "FEAT-IDEN-002": {"domain": "Identity", "blast_radius": "HIGH", "desc": "Student Credential Setup"},
    "FEAT-IDEN-003": {"domain": "Identity", "blast_radius": "MED", "desc": "Teacher Reset Code Generation"},
    "FEAT-IDEN-004": {"domain": "Identity", "blast_radius": "HIGH", "desc": "Student Recovery Code Validation"},
    "FEAT-IDEN-005": {"domain": "Identity", "blast_radius": "MED", "desc": "Authenticated Class Binding"},
    "FEAT-IDEN-006": {"domain": "Identity", "blast_radius": "MED", "desc": "Provision Student Seat in Existing Class"},
    "FEAT-STOR-001": {"domain": "Store", "blast_radius": "MED", "desc": "Store Purchase and Entitlement Grant"},
    "FEAT-STOR-002": {"domain": "Store", "blast_radius": "MED", "desc": "Entitlement Terminal Lifecycle"},
    "FEAT-STOR-003": {"domain": "Store", "blast_radius": "MED", "desc": "Insurance Claim Lifecycle"},
    # Bridge aliases — retired FEAT codes kept until all call-sites are migrated
    "FEAT-STOR-004": {"domain": "Store", "blast_radius": "MED", "desc": "[RETIRED → FEAT-STOR-001] Rent Perk Purchase"},
    "FEAT-STOR-005": {"domain": "Store", "blast_radius": "LOW", "desc": "[RETIRED → FEAT-STOR-002] Redeem Item"},
    "FEAT-STOR-006": {"domain": "Store", "blast_radius": "MED", "desc": "[RETIRED → FEAT-STOR-002] Redemption Disposition"},
    "FEAT-ENT-001": {"domain": "Store", "blast_radius": "MED", "desc": "[RETIRED → FEAT-STOR-001] Hall Pass Entitlement Adjustment"},
    "FEAT-PROD-001": {"domain": "Productivity", "blast_radius": "MED", "desc": "Record Attendance Session"},
    "FEAT-PROD-002": {"domain": "Productivity", "blast_radius": "MED", "desc": "Record Hall Pass Log"},
    "FEAT-PROD-003": {"domain": "Productivity", "blast_radius": "HIGH", "desc": "Record Payroll Event"},
    "FEAT-CLASS-001": {"domain": "Class Configuration", "blast_radius": "HIGH", "desc": "Create class boundary"},
    "FEAT-CLASS-002": {"domain": "Class Configuration", "blast_radius": "MED", "desc": "Modify existing class boundary"},
    "FEAT-CLASS-004": {"domain": "Class Configuration", "blast_radius": "MED", "desc": "Feature enablement"},
    "FEAT-CLASS-005": {"domain": "Class Configuration", "blast_radius": "HIGH", "desc": "Economic engine evolution"},
    "FEAT-SETTINGS-001": {"domain": "Class Configuration", "blast_radius": "MED", "desc": "Class Settings Update"},
    "FEAT-ITR-001": {"domain": "Interpretation", "blast_radius": "LOW", "desc": "Compute Interpretation Snapshot"},
    "FEAT-ADMN-001": {"domain": "Logistics", "blast_radius": "LOW", "desc": "Bulk administration"},
    "FEAT-OBL-001": {"domain": "Obligations", "blast_radius": "MED", "desc": "Rent Payment"},
    "FEAT-OBL-002": {"domain": "Obligations", "blast_radius": "MED", "desc": "Scheduled Rent Cycle"},
    "FEAT-OBL-003": {"domain": "Obligations", "blast_radius": "MED", "desc": "Scheduled Insurance Cycle"},
    "FEAT-OPS-001": {"domain": "Operations", "blast_radius": "MED", "desc": "Maintenance/Cleanup Operations"},
    "FEAT-SUP-001": {"domain": "Support", "blast_radius": "LOW", "desc": "Issue Submission and Category Setup"},
}

class FEATContext:
    """
    Context manager to track active Feature Execution (FEAT) units.
    Ensures all state mutations are attributed to a compliant orchestrator.
    """
    def __init__(self, feat_name: str, correlation_id: str = None, idempotency_key: str = None):
        if feat_name not in FEAT_REGISTRY:
            # Allow test FEATs only in non-production environments
            is_test_env = os.environ.get("FLASK_ENV") in ["testing", "development"]
            is_test_feat = feat_name.startswith("FEAT-TEST-") or feat_name in ["OUTER", "INNER"]
            if not (is_test_env and is_test_feat):
                raise FEATContextError(f"FATAL: FEAT code {feat_name} is not in the canonical registry.")
            
            # Temporary meta for test FEATs
            self.meta = {"domain": "Test", "blast_radius": "LOW", "desc": "Temporary Test FEAT"}
        else:
            self.meta = FEAT_REGISTRY[feat_name]
        
        self.feat_name = feat_name
        
        # NESTING GUARD: If context exists, it MUST share the same correlation ID (Re-entry safe)
        active_corr = getattr(_feat_context, "correlation_id", None)
        if active_corr and correlation_id and active_corr != correlation_id:
            raise FEATContextError(
                f"FATAL: Illegal nested FEAT context detected. "
                f"Current={active_corr}, Attempted={correlation_id}. "
                "Atomicity violation: different correlation IDs in one thread."
            )
        # Re-entry optimization: if same-ID nesting, we don't need to re-validate everything
        self.is_reentry = (active_corr == (correlation_id or active_corr) and active_corr is not None)
            
        self.correlation_id = correlation_id or active_corr or generate_correlation_id()
        self.idempotency_key = idempotency_key
        
        # 1. Format Discipline: Enforce corr_ prefix (Exempt bypass IDs)
        if not (validate_id_format(self.correlation_id, "corr_") or self.correlation_id.startswith("bypass_test_")):
             self.correlation_id = f"corr_{self.correlation_id}"

        # 1.1 Inverse Reject: Do not allow test IDs in production mode
        if self.correlation_id.startswith("bypass_test_") and os.environ.get("FLASK_ENV") == "production":
             raise FEATContextError(f"FATAL: Test correlation ID '{self.correlation_id}' detected in PRODUCTION environment. This is strictly prohibited.")

        # 2. Idempotency Format Discipline (Warning level for structured keys)
        if self.idempotency_key and ":" not in self.idempotency_key:
             logger.warning(f"FEAT-FORMAT-WARNING: Unstructured idempotency key '{self.idempotency_key}' in {feat_name}. Recommended: <feat>:<op>:<uuid>")

        # MANDATORY ID GUARD: Tier 1 (HIGH blast radius) MUST have idempotency_key
        # EXCEPTION: Allow missing idempotency if we are nested inside an explicit test bypass.
        is_bypass_parent = hasattr(_feat_context, "stack") and any(s["name"] == "FEAT-BYPASS-LEGACY" for s in _feat_context.stack)
        is_active_bypass = getattr(_feat_context, "active_feat", None) == "FEAT-BYPASS-LEGACY"
        
        if self.meta["blast_radius"] == "HIGH" and not self.idempotency_key and not (is_bypass_parent or is_active_bypass):
            msg = f"MANDATORY ID MISSING: HIGH blast radius FEAT {feat_name} requires an idempotency_key."
            if os.environ.get("FLASK_ENV") != "production":
                raise FEATContextError(f"FATAL: {msg}")
            else:
                logger.error(f"FEAT-INTEGRITY-FATAL: {msg}")
        elif not self.idempotency_key:
            logger.warning(f"FEAT-INTEGRITY-WARNING: FEAT {feat_name} (Blast={self.meta['blast_radius']}) missing idempotency_key.")

        self.commit_count = 0
        self.flush_count = 0
        self._owns_transaction = False
        self._transaction_ctx = None
        self._adopted_transaction = False

    def __enter__(self):
        if not hasattr(_feat_context, "stack"):
            _feat_context.stack = []
        elif getattr(_feat_context, "active_feat", None) is None and _feat_context.stack:
            # A previous FEAT may have leaked stack state if teardown was interrupted.
            # Clear it when starting a fresh top-level FEAT so the new context owns a clean boundary.
            _feat_context.stack = []
        
        # Track nested FEATs
        active = getattr(_feat_context, "active_feat", None)
        if active:
            _feat_context.stack.append({
                "name": active,
                "correlation_id": getattr(_feat_context, "correlation_id", None),
                "commit_count": getattr(_feat_context, "commit_count", 0),
                "flush_count": getattr(_feat_context, "flush_count", 0)
            })
        
        _feat_context.active_feat = self.feat_name
        _feat_context.correlation_id = self.correlation_id
        _feat_context.idempotency_key = self.idempotency_key
        _feat_context.commit_count = 0
        _feat_context.flush_count = 0
        
        # Bind context to the current session for cross-layer verification
        db.session.info["feat_context_active"] = True
        db.session.info["active_correlation_id"] = self.correlation_id
        db.session.info["feat_orchestrator_commit"] = False

        # FEAT is the transaction boundary: top-level FEAT owns exactly one DB transaction.
        self._owns_transaction = not is_nested_feat()
        if self._owns_transaction:
            _sess = _resolve_session(db.session)
            session_has_txn = bool(getattr(_sess, "in_transaction", lambda: False)())
            if not session_has_txn:
                # Fresh session: the FEAT owns a real top-level begin().
                self._transaction_ctx = db.session.begin()
                self._transaction_ctx.__enter__()
            elif is_discardable_read_autobegin(db.session):
                # Incidental read-only autobegin (clean: no pending mutation, no
                # flushed DML, not a savepoint, not an explicit BEGIN). Discard it so
                # the FEAT owns a real begin() whose commit persists — rather than a
                # begin_nested() savepoint whose release is not a commit and would
                # silently drop the FEAT's writes.
                db.session.rollback()
                self._transaction_ctx = db.session.begin()
                self._transaction_ctx.__enter__()
            elif _is_top_level_autobegin(_sess):
                # An autobegin that already carries pending/flushed writes made before
                # this FEAT opened. It must NOT be discarded (that would lose the
                # writes) and must NOT be buried under a savepoint (releasing the
                # savepoint would never commit the underlying autobegin, also losing
                # the writes). Instead the top-level FEAT ADOPTS the autobegin as its
                # owned transaction and commits it on exit, folding those pending
                # writes into the FEAT's single atomic top-level commit.
                self._transaction_ctx = _sess.get_transaction()
                self._adopted_transaction = True
            else:
                # An explicit non-FEAT BEGIN or an already-active SAVEPOINT: preserve
                # that outer boundary and layer a savepoint on top of it.
                try:
                    self._transaction_ctx = db.session.begin_nested()
                except InvalidRequestError:
                    self._transaction_ctx = db.session.begin_nested()
                self._transaction_ctx.__enter__()

        self.log_event("FEAT-ENTRY", {
            "feat": self.feat_name,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key or "NONE",
        })
        return self

    def log_event(self, event_type: str, data: dict):
        """Standardized structured logger for FEAT events."""
        msg = f"{event_type}: " + " | ".join(f"{k}={v}" for k, v in data.items())
        logger.info(msg)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Commit on success / rollback on failure for the whole FEAT transaction.
        txn_error = None
        try:
            if self._owns_transaction and self._transaction_ctx is not None:
                # Allow the single orchestrator commit path triggered by session.begin().__exit__.
                db.session.info["feat_orchestrator_commit"] = True
                self._transaction_ctx.__exit__(exc_type, exc_val, exc_tb)
        except Exception as exc:  # noqa: BLE001
            txn_error = exc
        finally:
            if hasattr(_feat_context, "stack") and _feat_context.stack:
                prev = _feat_context.stack.pop()
                _feat_context.active_feat = prev["name"]
                _feat_context.correlation_id = prev["correlation_id"]
                _feat_context.commit_count = prev["commit_count"]
                _feat_context.flush_count = prev["flush_count"]
                db.session.info["active_correlation_id"] = prev["correlation_id"]
            else:
                _feat_context.active_feat = None
                _feat_context.correlation_id = None
                _feat_context.commit_count = 0
                _feat_context.flush_count = 0
                db.session.info["feat_context_active"] = False
                db.session.info["active_correlation_id"] = None
                if hasattr(_feat_context, "stack"):
                    _feat_context.stack = []

            db.session.info["feat_orchestrator_commit"] = False

        if txn_error is not None:
            raise txn_error

def increment_commit_count():
    """Track number of commits in current FEAT and tripwire multiple commits."""
    if is_feat_active():
        name = get_active_feat_name()
        meta = FEAT_REGISTRY.get(name, {"blast_radius": "LOW"})
        
        _feat_context.commit_count = getattr(_feat_context, "commit_count", 0) + 1
        
        if _feat_context.commit_count == 1:
            logger.info(
                f"FEAT-COMMIT-OWNERSHIP: {name} | First commit owned by {name} | "
                f"Correlation={get_correlation_id()}"
            )

        if _feat_context.commit_count > 1:
            msg = (
                f"FEAT-INTEGRITY-WARNING: MULTIPLE-COMMIT-ATTEMPT in {name}. "
                f"Count={_feat_context.commit_count}. Correlation={get_correlation_id()}"
            )
            
            if meta["blast_radius"] == "HIGH":
                if os.environ.get("FLASK_ENV") != "production":
                    raise FEATContextError(f"FATAL: {msg} (HIGH blast radius violation blocked in dev/test)")
                else:
                    logger.error(f"FEAT-INTEGRITY-FATAL: {msg}")
            else:
                logger.warning(msg)

def increment_flush_count():
    """Track number of flushes and warn about complexity creep."""
    if is_feat_active():
        _feat_context.flush_count = getattr(_feat_context, "flush_count", 0) + 1
        if _feat_context.flush_count > 5:
             logger.warning(
                 f"FEAT-FLUSH-COMPLEXITY: {get_active_feat_name()} has triggered {_feat_context.flush_count} flushes. "
                 "Consider simplifying or batching mutations."
             )

def check_dirty_session(session, action: str):
    """
    Check if the session has un-flushed changes without an active FEAT.
    Emits a warning for early detection of illegal mutations.
    """
    if not is_feat_active():
        # Check if there's any dirty state
        if session.new or session.dirty or session.deleted:
            logger.warning(
                f"FEAT-INTEGRITY-WARNING: Model {action} attempted outside of FEAT context. "
                f"Session currently has: New={len(session.new)}, Dirty={len(session.dirty)}, Deleted={len(session.deleted)}. "
                "This state will be BLOCKED at flush/commit time."
            )

class FEATBypass:
    """
    Test-only escape hatch for legacy fixtures while the v2 migration is in flight.
    """

    def __init__(self, correlation_id: str | None = None):
        self.correlation_id = correlation_id or f"bypass_test_{uuid.uuid4().hex}"
        self._ctx: FEATContext | None = None

    def __enter__(self):
        if os.environ.get("FLASK_ENV") == "production":
            raise FEATContextError(
                f"FATAL: Test correlation ID '{self.correlation_id}' detected in PRODUCTION environment. "
                "This is strictly prohibited in PRODUCTION."
            )

        active_feat = get_active_feat_name()
        if active_feat:
            if active_feat == "FEAT-BYPASS-LEGACY":
                # Reuse active bypass correlation for safe re-entry across nested fixture helpers.
                self.correlation_id = get_correlation_id()
            else:
                raise FEATContextError(
                    f"FATAL: FEATBypass cannot enter while non-bypass FEAT '{active_feat}' is active."
                )

        logger.warning("FEAT-INTEGRITY-WARNING: FEATBypass active. Execution integrity is currently unmanaged.")
        self._ctx = FEATContext("FEAT-BYPASS-LEGACY", correlation_id=self.correlation_id)
        return self._ctx.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._ctx is None:
            return False
        return self._ctx.__exit__(exc_type, exc_val, exc_tb)

def audit_protected(
    table_name: str,
    row,
    operation: str,
    fields: list[str],
    *,
    actor_type: str | None = None,
    actor_id_hash: str | None = None,
) -> None:
    """Emit an AuditEvent for a protected row write and attach lineage fields.

    Must be called after db.session.flush() (so row.id is populated) and
    before the owning FEAT commits. Does nothing if AUDIT_HMAC_KEY is absent
    (dev/test without the key configured — CI enforces the key in production).
    """
    try:
        from app.services.audit_service import emit_audit_event, AuditContextError
    except ImportError:
        logger.warning("audit_service not available — audit lineage skipped")
        return

    try:
        event = emit_audit_event(
            table_name=table_name,
            row_pk=str(row.id),
            operation=operation,
            protected_fields={f: getattr(row, f, None) for f in fields},
            class_id=getattr(row, "class_id", None),
            seat_id=getattr(row, "seat_id", None),
            user_id=getattr(row, "user_id", None),
            actor_type=actor_type,
            actor_id_hash=actor_id_hash,
        )
        if hasattr(row, "lineage_event_id"):
            row.lineage_event_id = event.id
            row.lineage_token = event.hmac_signature
            row.lineage_version = event.signature_version
    except AuditContextError as exc:
        logger.error(f"AUDIT-LINEAGE-FAILURE: {exc}")
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"AUDIT-LINEAGE-ERROR: unexpected error emitting audit event for {table_name}:{getattr(row, 'id', '?')} — {exc}")
        raise


def requires_feat_context(feat_name: str):
    """
    Decorator to ensure a function is executed within a FEAT context.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            correlation_id = kwargs.get("correlation_id")
            idempotency_key = kwargs.get("idempotency_key")
            with FEATContext(feat_name, correlation_id=correlation_id, idempotency_key=idempotency_key):
                return f(*args, **kwargs)
        return decorated_function
    return decorator

def init_feat_enforcement(app):
    """
    Initialize technical enforcement of the FEAT Constitutional Directive.
    """
    if getattr(db, "_feat_enforcement_initialized", False):
        return
    db._feat_enforcement_initialized = True
    
    @event.listens_for(db.session, "after_attach")
    def monitor_session_attach(session, instance):
        check_dirty_session(session, "ATTACH")

    @event.listens_for(db.session, "before_flush")
    def enforce_feat_context_on_flush(session, flush_context, instances):
        """
        Prevents session flushes (SQL emission) outside a FEAT context.
        """
        # Record that this transaction now carries flushed DML. Once a flush emits
        # INSERT/UPDATE/DELETE, session.new/dirty/deleted are cleared, so those
        # collections can no longer distinguish "clean read autobegin" from
        # "transaction with uncommitted writes". is_discardable_read_autobegin()
        # consults this flag so it never rolls back a transaction that has already
        # persisted pending DML (e.g. a caller that flushed before opening a FEAT).
        if session.new or session.dirty or session.deleted:
            session.info["_txn_dml_flushed"] = True

        is_bypass = get_active_feat_name() == "FEAT-BYPASS-LEGACY"
        if is_bypass or is_system_audit_authority():
            pass  # allowed paths
        elif not is_feat_active() or not session.info.get("feat_context_active"):
            if session.new or session.dirty or session.deleted:
                raise FEATContextError(
                    "MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH): "
                    "Attempted to flush mutated state outside of a verified FEAT context. "
                    f"is_feat_active={is_feat_active()}, session.info={session.info.get('feat_context_active')}. "
                    f"New={len(session.new)}, Dirty={len(session.dirty)}, Deleted={len(session.deleted)}."
                )
        
        increment_flush_count()

    @event.listens_for(db.session, "before_commit")
    def enforce_feat_context_on_commit(session):
        """
        Prevents commits outside a FEAT context, even if flush has not executed yet.
        """
        is_bypass = get_active_feat_name() == "FEAT-BYPASS-LEGACY"
        if is_bypass or is_system_audit_authority():
            pass  # allowed paths
        elif not is_feat_active() or not session.info.get("feat_context_active"):
            if session.new or session.dirty or session.deleted:
                raise FEATContextError(
                    "MANDATORY FEAT CONSTITUTIONAL VIOLATION (COMMIT): "
                    "Attempted to commit mutated state outside of a verified FEAT context. "
                    f"is_feat_active={is_feat_active()}, session.info={session.info.get('feat_context_active')}. "
                    f"New={len(session.new)}, Dirty={len(session.dirty)}, Deleted={len(session.deleted)}."
                )
        # Hard atomicity rule: only FEAT orchestrator may commit.
        # Savepoints (nested transactions) do not count as top-level commits.
        if (
            not is_bypass
            and not is_system_audit_authority()
            and is_feat_active()
            and session.info.get("feat_context_active")
            and not session.info.get("feat_orchestrator_commit")
            and not session.in_nested_transaction()
        ):
            raise FEATContextError(
                "MANDATORY FEAT ATOMICITY VIOLATION (COMMIT): "
                "Direct commit attempted from inside FEAT execution. "
                "Only FEAT orchestrator transaction boundary may commit."
            )

        # Savepoint releases (begin_nested) also emit before_commit but are NOT
        # top-level commits. The multiple-commit tripwire must only count real
        # orchestrator commits; otherwise any FEAT that legitimately uses a
        # savepoint internally (e.g. race-safe row creation in settle_balances)
        # would false-trip on HIGH blast-radius FEATs. This mirrors the
        # atomicity rule above, which already exempts nested transactions.
        if not session.in_nested_transaction():
            increment_commit_count()

    @event.listens_for(db.session, "after_commit")
    def clear_dml_flag_after_commit(session):
        """Reset the flushed-DML marker once the transaction is durably committed.

        The flag lives on ``session.info`` (which outlives individual
        transactions), so it must be cleared at each transaction boundary or a
        stale value would suppress a later legitimate read-autobegin discard.
        """
        session.info.pop("_txn_dml_flushed", None)

    @event.listens_for(db.session, "after_rollback")
    def clear_dml_flag_after_rollback(session):
        """Reset the flushed-DML marker when the transaction is rolled back."""
        session.info.pop("_txn_dml_flushed", None)
