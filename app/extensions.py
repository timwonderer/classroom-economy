"""
Shared Flask extension instances.

Centralized to avoid circular imports. Extensions are initialized
here but configured in create_app().
"""

import os
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
    except RuntimeError:
        return get_remote_address()

# Use memory storage in CI/testing environments, Redis in production
# This prevents Redis connection errors in GitHub Actions
if os.environ.get('RATELIMIT_STORAGE_URI'):
    # Explicitly configured storage URI takes precedence
    storage_uri = os.environ.get('RATELIMIT_STORAGE_URI')
elif os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
    # Use memory storage in CI environments
    storage_uri = 'memory://'
elif os.environ.get('REDIS_URL'):
    # Use Redis URL if provided
    storage_uri = os.environ.get('REDIS_URL')
else:
    # Default to local Redis in production/development
    storage_uri = 'redis://localhost:6379'

limiter = Limiter(
    key_func=get_real_ip_for_limiter,
    default_limits=["500 per day", "200 per hour"],
    storage_uri=storage_uri,
    strategy="fixed-window"
)
