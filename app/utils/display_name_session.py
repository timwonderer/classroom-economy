"""Session-scoped cache helpers for decrypted display names."""

from __future__ import annotations

from flask import session


ADMIN_DISPLAY_NAME_KEY = "admin_display_name"
ADMIN_DISPLAY_NAME_ID_KEY = "admin_display_name_teacher_user_id"
TEACHER_DISPLAY_NAME_CACHE_KEY = "teacher_display_name_cache"


def set_admin_display_name_cache(*, teacher_user_id: int, display_name: str) -> None:
    session[ADMIN_DISPLAY_NAME_ID_KEY] = teacher_user_id
    session[ADMIN_DISPLAY_NAME_KEY] = display_name


def get_admin_display_name_cache(*, teacher_user_id: int) -> str | None:
    if session.get(ADMIN_DISPLAY_NAME_ID_KEY) != teacher_user_id:
        return None
    return session.get(ADMIN_DISPLAY_NAME_KEY)


def clear_admin_display_name_cache() -> None:
    session.pop(ADMIN_DISPLAY_NAME_ID_KEY, None)
    session.pop(ADMIN_DISPLAY_NAME_KEY, None)


def get_teacher_display_name_cache() -> dict[str, str]:
    cache = session.get(TEACHER_DISPLAY_NAME_CACHE_KEY)
    if isinstance(cache, dict):
        return cache
    return {}


def upsert_teacher_display_name_cache(entries: dict[str, str]) -> None:
    cache = get_teacher_display_name_cache()
    cache.update(entries)
    session[TEACHER_DISPLAY_NAME_CACHE_KEY] = cache


def clear_teacher_display_name_cache() -> None:
    session.pop(TEACHER_DISPLAY_NAME_CACHE_KEY, None)
