"""V2 Canonical test fixture helpers.
These replace legacy Admin(username=...) and SystemAdmin(username=...) constructors
with properly hashed credential fields.
"""
from app.utils.auth_username import build_hashed_username_fields

def make_admin(username: str, totp_secret: str, **kwargs):
    """Create a properly hashed Admin fixture (V2 canonical form)."""
    from app.models import Admin
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
    return Admin(**params)

def make_sysadmin(username: str, totp_secret: str, **kwargs):
    """Create a properly hashed SystemAdmin fixture (V2 canonical form)."""
    from app.models import SystemAdmin
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    
    params = {
        "username_hash": username_hash,
        "username_lookup_hash": username_lookup_hash,
        "salt": salt,
        "totp_secret": totp_secret
    }
    params.update(kwargs)
    return SystemAdmin(**params)
