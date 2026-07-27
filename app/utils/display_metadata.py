"""Display-only metadata resolver for canonical request contexts. (Read Specification at SPEC-DISPLAY-001)""" 

from __future__ import annotations

from dataclasses import asdict, dataclass

from flask import session

from app.models import ClassEconomy, IdentityProfile, Seat
from app.services.context_resolver import CanonicalContext


DISPLAY_METADATA_SESSION_KEY = "display_metadata"


@dataclass(frozen=True)
class DisplayMetadata:
    """Display-only facts derived from canonical context.

    This object is never an authority source. Authorization must continue to use
    CanonicalContext; this cache only prevents repeating display-data assembly
    while the canonical context is unchanged.
    """

    context_key: str
    user_id: int | None
    seat_id: int | None
    class_id: str | None
    actor_role: str | None
    join_code: str | None
    class_display_name: str | None
    class_identifier: str | None
    class_timezone: str | None
    section: str | None
    block: str | None
    block_display: str | None
    actor_first_name: str | None
    actor_last_name: str | None
    actor_full_name: str | None
    student_first_name: str | None
    student_last_name: str | None
    student_full_name: str | None
    teacher_first_name: str | None
    teacher_last_name: str | None
    teacher_display_name: str | None
    teacher_note: str | None

    def to_session_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_class_context(self) -> dict[str, object]:
        return {
            "join_code": self.join_code,
            "class_id": self.class_id,
            "class_identifier": self.class_identifier,
            "class_timezone": self.class_timezone,
            "teacher_name": self.teacher_display_name,
            "user_id": self.user_id,
            "block": self.block,
            "section": self.section,
            "block_display": self.block_display,
            "student_full_name": self.student_full_name or "",
        }

    def to_available_class_option(self, *, is_current: bool = True) -> dict[str, object]:
        class_context = self.to_class_context()
        class_context["is_current"] = is_current
        return class_context


def _context_key(ctx: CanonicalContext) -> str:
    return "|".join(
        str(value or "")
        for value in (
            getattr(ctx, "user_id", None),
            getattr(ctx, "seat_id", None),
            getattr(ctx, "class_id", None),
            getattr(ctx, "actor_role", None),
        )
    )


def _profile_for_seat(*, seat_id: int | None, class_id: str | None) -> IdentityProfile | None:
    if not seat_id or not class_id:
        return None
    return IdentityProfile.query.filter_by(seat_id=seat_id, class_id=class_id).first()


def _teacher_profile_for_class(class_row: ClassEconomy | None) -> IdentityProfile | None:
    if class_row is None:
        return None
    teacher_seat = (
        Seat.query
        .filter_by(class_id=class_row.class_id, user_id=class_row.user_id, role="teacher")
        .order_by(Seat.id.asc())
        .first()
    )
    if teacher_seat is None:
        return None
    return _profile_for_seat(seat_id=teacher_seat.id, class_id=class_row.class_id)


def _full_name(profile: IdentityProfile | None) -> str | None:
    if profile is None:
        return None
    first_name = profile.first_name or ""
    last_name = profile.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    return full_name or None


def resolve_display_metadata(ctx: CanonicalContext | None) -> DisplayMetadata | None:
    """Resolve display-only metadata for the current canonical context."""
    if ctx is None or not getattr(ctx, "class_id", None):
        return None

    class_row = ClassEconomy.query.filter_by(class_id=ctx.class_id).first()
    if class_row is None:
        return None

    actor_profile = _profile_for_seat(seat_id=getattr(ctx, "seat_id", None), class_id=ctx.class_id)
    teacher_profile = _teacher_profile_for_class(class_row)
    join_code = class_row.join_code
    class_display_name = class_row.display_name or join_code
    actor_role = getattr(ctx, "actor_role", None)

    student_profile = actor_profile if actor_role == "student" else None
    teacher_display_name = _full_name(teacher_profile) or "Teacher"

    return DisplayMetadata(
        context_key=_context_key(ctx),
        user_id=getattr(ctx, "user_id", None),
        seat_id=getattr(ctx, "seat_id", None),
        class_id=ctx.class_id,
        actor_role=actor_role,
        join_code=join_code,
        class_display_name=class_display_name,
        class_identifier=class_display_name,
        class_timezone=class_row.class_timezone,
        section=class_row.section,
        block=class_row.section,
        block_display=class_display_name,
        actor_first_name=actor_profile.first_name if actor_profile else None,
        actor_last_name=actor_profile.last_name if actor_profile else None,
        actor_full_name=_full_name(actor_profile),
        student_first_name=student_profile.first_name if student_profile else None,
        student_last_name=student_profile.last_name if student_profile else None,
        student_full_name=_full_name(student_profile),
        teacher_first_name=teacher_profile.first_name if teacher_profile else None,
        teacher_last_name=teacher_profile.last_name if teacher_profile else None,
        teacher_display_name=teacher_display_name,
        teacher_note=actor_profile.notes if actor_profile else None,
    )


def get_cached_display_metadata(ctx: CanonicalContext | None) -> DisplayMetadata | None:
    if ctx is None:
        return None
    cached = session.get(DISPLAY_METADATA_SESSION_KEY)
    if not isinstance(cached, dict):
        return None
    if cached.get("context_key") != _context_key(ctx):
        return None
    return DisplayMetadata(**cached)


def set_cached_display_metadata(metadata: DisplayMetadata) -> None:
    session[DISPLAY_METADATA_SESSION_KEY] = metadata.to_session_dict()


def clear_display_metadata_cache() -> None:
    session.pop(DISPLAY_METADATA_SESSION_KEY, None)


def get_or_resolve_display_metadata(ctx: CanonicalContext | None) -> DisplayMetadata | None:
    cached = get_cached_display_metadata(ctx)
    if cached is not None:
        return cached
    metadata = resolve_display_metadata(ctx)
    if metadata is not None:
        set_cached_display_metadata(metadata)
    return metadata
