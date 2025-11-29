"""Helpers for retrieving period/block-scoped settings.

These utilities centralize the logic for selecting the correct settings
record (block-specific first, then global fallback) and for normalizing
period identifiers across the app.
"""

from __future__ import annotations

from typing import Optional, Type

from flask import has_request_context, session

from app.extensions import db


def normalize_block(block_value: Optional[str]) -> Optional[str]:
    """Return a normalized, uppercased block value or ``None`` for blanks."""

    if not block_value:
        return None

    cleaned = block_value.strip().upper()
    return cleaned or None


def get_primary_block_for_student(student) -> Optional[str]:
    """Return the current block for a student, preferring the session value."""

    # Prefer the actively selected block stored in the session
    active_block = normalize_block(session.get("current_period")) if has_request_context() else None
    if active_block:
        return active_block

    # Fall back to the first block listed on the student record
    if student and student.block:
        for block_part in student.block.split(','):
            normalized = normalize_block(block_part)
            if normalized:
                return normalized

    return None


def get_settings_for_block(
    model: Type[db.Model],
    teacher_id: int,
    block: Optional[str],
    create_global: bool = False,
):
    """Return settings scoped to a block with a global fallback.

    Args:
        model: SQLAlchemy model class with ``teacher_id`` and ``block`` columns.
        teacher_id: Current teacher/admin identifier.
        block: Desired block/period identifier (case-insensitive).
        create_global: When ``True``, create a global (``block=None``) record if
            none exists. This is helpful for admin pages that expect at least
            one settings row.

    Returns:
        Instance of ``model`` for the requested block if it exists, otherwise
        the teacher's global settings row. May return ``None`` if nothing is
        found and ``create_global`` is ``False``.
    """

    normalized_block = normalize_block(block)

    if normalized_block:
        scoped_settings = model.query.filter_by(
            teacher_id=teacher_id, block=normalized_block
        ).first()
        if scoped_settings:
            return scoped_settings

    global_settings = model.query.filter_by(teacher_id=teacher_id, block=None).first()
    if global_settings:
        return global_settings

    if create_global:
        global_settings = model(teacher_id=teacher_id, block=None)
        db.session.add(global_settings)
        # Note: caller is responsible for committing the session
        return global_settings

    return None


def get_or_create_settings_for_blocks(
    model: Type[db.Model],
    teacher_id: int,
    target_blocks: list,
):
    """Get or create settings records for a list of blocks.

    This is a helper for admin routes that need to apply settings to multiple
    blocks at once (e.g., when "apply to all blocks" is checked).

    Args:
        model: SQLAlchemy model class with ``teacher_id`` and ``block`` columns.
        teacher_id: Current teacher/admin identifier.
        target_blocks: List of block values to get or create settings for.
            May contain ``None`` for global settings.

    Yields:
        Tuple[model, bool]: A tuple of (settings_record, is_new) where:
            - settings_record: Instance of ``model`` for the block
            - is_new: True if the record was just created, False if it existed
        The caller is responsible for updating the settings and committing the session.
    """
    for block_value in target_blocks:
        settings_record = model.query.filter_by(
            teacher_id=teacher_id,
            block=block_value
        ).first()

        is_new = False
        if not settings_record:
            settings_record = model(teacher_id=teacher_id, block=block_value)
            db.session.add(settings_record)
            is_new = True

        yield settings_record, is_new
