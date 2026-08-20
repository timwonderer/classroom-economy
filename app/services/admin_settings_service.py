from __future__ import annotations

from app.extensions import db
from app.models import RentSettings


def create_rent_settings(*, class_id: str) -> RentSettings:
    """Create and flush a canonical rent settings row."""
    settings = RentSettings(class_id=class_id)
    db.session.add(settings)
    db.session.flush()
    return settings
