"""
Shared Flask extension instances.

Centralized to avoid circular imports. Extensions are initialized
here but configured in create_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from apscheduler.schedulers.background import BackgroundScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions (without binding to an app yet)
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
scheduler = BackgroundScheduler()

# Initialize rate limiter
# Uses Cloudflare-aware IP detection for accurate rate limiting
def get_real_ip_for_limiter():
    """Get real IP for rate limiting, handling Cloudflare proxy."""
    try:
        from flask import request
        # Check Cloudflare header first
        real_ip = request.headers.get('CF-Connecting-IP')
        if real_ip:
            return real_ip
        # Fallback to X-Forwarded-For
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        # Final fallback to remote_addr
        return request.remote_addr
    except:
        return get_remote_address()

limiter = Limiter(
    key_func=get_real_ip_for_limiter,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)
