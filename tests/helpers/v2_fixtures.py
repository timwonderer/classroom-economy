"""V2 Canonical test fixture helpers.
These replace legacy Admin(username=...) and SystemAdmin(username=...) constructors
with properly hashed credential fields.
"""
from app.utils.auth_username import build_hashed_username_fields

def make_admin(username: str, totp_secret: str, **kwargs):
    """Create a properly hashed Admin fixture (V2 canonical form)."""
    from app.models import Admin, User, UserRole
    from app.extensions import db
    from app.utils.encryption import encrypt_totp
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    
    # Allow kwargs to override defaults (useful for tests that provide their own salt/hashes)
    params = {
        "username_hash": username_hash,
        "username_lookup_hash": username_lookup_hash,
        "salt": salt,
        "totp_secret": totp_secret,
        "public_id": username,
    }
    params.update(kwargs)
    admin = Admin(**params)
    canonical_user = db.session.query(User).filter_by(username_lookup_hash=username_lookup_hash).first()
    if canonical_user is None:
        canonical_user = User(
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
            user_role=UserRole.TEACHER,
            totp_secret_encrypted=encrypt_totp(totp_secret),
            has_completed_setup=True,
        )
        db.session.add(canonical_user)
        db.session.flush()
    admin.user_id = canonical_user.id
    return admin

def make_sysadmin(username: str, totp_secret: str, **kwargs):
    """Create a properly hashed SystemAdmin fixture (V2 canonical form)."""
    from app.models import SystemAdmin
    from app.models import User, UserRole
    from app.extensions import db
    from app.utils.encryption import encrypt_totp
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    
    params = {
        "username_hash": username_hash,
        "username_lookup_hash": username_lookup_hash,
        "salt": salt,
        "totp_secret": totp_secret
    }
    params.update(kwargs)
    sysadmin = SystemAdmin(**params)
    canonical_user = db.session.query(User).filter_by(username_lookup_hash=username_lookup_hash).first()
    if canonical_user is None:
        canonical_user = User(
            username_hash=username_hash,
            username_lookup_hash=username_lookup_hash,
            user_role=UserRole.SYSADMIN,
            totp_secret_encrypted=encrypt_totp(totp_secret),
            has_completed_setup=True,
        )
        db.session.add(canonical_user)
        db.session.flush()
    sysadmin.user_id = canonical_user.id
    return sysadmin
