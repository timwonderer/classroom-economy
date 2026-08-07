from __future__ import annotations

from app.extensions import db
from app.models import Announcement
from app.utils.canonical_temporal_resolver import utc_now


def create_class_announcement(
    *,
    user_id: int,
    class_id: str,
    title: str,
    message: str,
    priority: int,
    is_active: bool,
    expires_at,
) -> Announcement:
    announcement = Announcement(
        user_id=user_id,
        class_id=class_id,
        title=title,
        message=message,
        priority=priority,
        is_active=is_active,
        expires_at=expires_at,
    )
    db.session.add(announcement)
    db.session.flush()
    return announcement


def update_class_announcement(
    announcement: Announcement,
    *,
    title: str,
    message: str,
    priority: int,
    is_active: bool,
    expires_at,
) -> Announcement:
    announcement.title = title
    announcement.message = message
    announcement.priority = priority
    announcement.is_active = is_active
    announcement.expires_at = expires_at
    announcement.updated_at = utc_now()
    db.session.flush()
    return announcement


def delete_class_announcement(announcement: Announcement) -> None:
    db.session.delete(announcement)
    db.session.flush()
