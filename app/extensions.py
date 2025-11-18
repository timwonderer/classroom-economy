"""
Shared Flask extension instances.

Centralized to avoid circular imports. Extensions are initialized
here but configured in create_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect

# Initialize extensions (without binding to an app yet)
db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
