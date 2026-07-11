"""V2 canonical test fixture helpers.

Tests create identity through the production service layer.
No Admin objects, no bridge patterns.
"""

from app.services.classroom_setup import create_teacher as _svc_create_teacher
from app.feats.base import FEATContext
from app.extensions import db
from app.models import User, UserRole


def make_teacher(username: str, totp_secret: str | None = None) -> User:
    """Create a canonical V2 teacher (User with role=TEACHER).

    Delegates to app/services/classroom_setup.create_teacher().
    Flushes but does NOT commit — caller owns the transaction.
    """
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"make_teacher:{username}"):
        return _svc_create_teacher(username, totp_secret=totp_secret)


def make_sysadmin(username: str, totp_secret: str | None = None) -> User:
    """Create a canonical V2 sysadmin (User with role=SYSADMIN).

    Flushes but does NOT commit.
    """
    from app.utils.auth_username import build_hashed_username_fields
    from app.utils.encryption import normalize_totp_for_storage

    _salt, u_hash, u_lookup = build_hashed_username_fields(username)
    sysadmin = User(
        user_role=UserRole.SYSADMIN,
        username_hash=u_hash,
        username_lookup_hash=u_lookup,
        totp_secret_encrypted=normalize_totp_for_storage(totp_secret) if totp_secret else None,
    )
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"make_sysadmin:{username}"):
        db.session.add(sysadmin)
        db.session.flush()
    return sysadmin


# ---------------------------------------------------------------------------
# Backward-compat shim — tests importing make_admin get make_teacher.
# Remove once all call sites are migrated.
# ---------------------------------------------------------------------------
def make_admin(username: str, totp_secret: str | None = None, **_ignored) -> User:
    """Deprecated: use make_teacher(). Returns canonical User (role=TEACHER)."""
    return make_teacher(username, totp_secret=totp_secret)
