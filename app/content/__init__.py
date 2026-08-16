"""Canonical support-content registry.

See app/content/registry.py for the loader and public API. Public entry
points: `help`, `help_long`, `help_text`, `init_content_registry`.
"""

from app.content.registry import (
    ContentEntry,
    RenderedContent,
    ContentKeyError,
    help,
    help_long,
    help_text,
    init_content_registry,
    get_registry,
)

__all__ = [
    "ContentEntry",
    "RenderedContent",
    "ContentKeyError",
    "help",
    "help_long",
    "help_text",
    "init_content_registry",
    "get_registry",
]
