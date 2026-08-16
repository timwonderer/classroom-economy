"""Canonical support-content registry.

Loads YAML microcopy and Markdown long-form panels once at app boot and
exposes them through a small, presentation-independent API.

Design invariants:

- **Content IDs are presentation-independent.** A key like
  `admin.rent.grace_period` may render as a tooltip today, a panel
  tomorrow, or a full support page later. The *kind* (tooltip / hint /
  panel / alert / …) is metadata on the entry, not encoded in the ID.

- **Trust boundary is explicit.** `help_long()` returns a
  `RenderedContent` object. Only its `.html` attribute unwraps to a
  trusted `Markup` — because that HTML came from a Markdown source
  that the registry itself sanitized against a documented allowlist.
  Templates that write `{{ obj }}` see the raw source text, HTML-escaped
  by Jinja like any other value. A stray `{% autoescape false %}` on
  `.body` cannot promote arbitrary strings to trusted markup.

- **Missing keys are structurally exceptional.** A CI validator
  (see `scripts/validate_content_keys.py`) makes any referenced
  key-that-does-not-exist a build failure. Runtime fallback exists
  only as a last-line safety net — in dev/test it is loud and
  visible; in prod it is logged and quiet.

- **Interpolation** uses `str.format(**kwargs)`. Missing placeholders
  raise in dev/test and log-and-strip in prod (same policy as missing
  keys).
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bleach
import markdown as md
import yaml
from markupsafe import Markup, escape

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

# Closed set of content kinds. Encodes rendering + missing-key policy.
# VISIBLE kinds surface a `[missing: key]` marker in dev and a controlled
# fallback in prod. INVISIBLE kinds (aria / placeholder) fall back to an
# empty string in prod so we do not paint UI garbage into inputs.
KINDS_VISIBLE = frozenset({
    "tooltip", "hint", "panel", "alert", "empty", "flash",
    "warning", "title", "body", "modal",
})
KINDS_INVISIBLE = frozenset({"aria", "placeholder"})
KINDS_LONG = frozenset({"panel", "body", "modal"})  # kinds parsed as Markdown
ALL_KINDS = KINDS_VISIBLE | KINDS_INVISIBLE


# Sanitizer allowlist for Markdown-rendered HTML. Tight by default; we
# add elements deliberately when a real content need appears.
_ALLOWED_TAGS = frozenset({
    "p", "br", "hr",
    "strong", "em", "code", "kbd",
    "ul", "ol", "li",
    "h3", "h4", "h5", "h6",  # h1/h2 reserved for page structure
    "blockquote", "pre",
    "a", "span",
})
_ALLOWED_ATTRS = {
    "a": ["href", "title", "rel"],
    "span": ["class"],
}
_ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})


@dataclass(frozen=True)
class ContentEntry:
    """One entry in the registry."""
    id: str
    kind: str
    body: str  # Raw source text (YAML string, or Markdown source for long kinds)
    source: str  # File path for diagnostics / CI


@dataclass(frozen=True)
class RenderedContent:
    """Trusted rendered content, produced by the registry.

    `.html` is the sanitized, trusted `Markup`. `.text` is the raw
    Markdown source, escaped. Templates that want the styled panel
    must reach for `.html` explicitly — that explicit reach is the
    trust boundary.
    """
    id: str
    kind: str
    html: Markup
    text: str


class ContentKeyError(KeyError):
    """Raised when a key is missing in strict (dev/test) mode."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass
class _Registry:
    entries: dict[str, ContentEntry] = field(default_factory=dict)
    strict: bool = True  # Loud missing-key behavior (dev/test)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, key: str) -> ContentEntry | None:
        return self.entries.get(key)


_registry: _Registry | None = None


def get_registry() -> _Registry:
    if _registry is None:
        raise RuntimeError(
            "Content registry not initialized. Call init_content_registry(app) "
            "during app factory setup before serving requests."
        )
    return _registry


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


_KEY_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*)+$")


def _validate_key(key: str, source: str) -> None:
    if not _KEY_RE.match(key):
        raise ValueError(
            f"Invalid content key {key!r} in {source}: keys must be dotted "
            f"lowercase segments (e.g. 'admin.rent.grace_period')"
        )


def _load_yaml_file(path: Path) -> dict[str, dict[str, Any]]:
    """Load a YAML file whose top-level is `{ key: { kind: str, body: str } }`."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping, got {type(data).__name__}")
    return data


def _iter_yaml_entries(
    yaml_dir: Path,
) -> list[ContentEntry]:
    entries: list[ContentEntry] = []
    if not yaml_dir.is_dir():
        return entries
    for yml in sorted(yaml_dir.glob("*.yaml")):
        raw = _load_yaml_file(yml)
        source = str(yml.relative_to(yaml_dir.parent.parent)) if yaml_dir.parent.parent in yml.parents else str(yml)
        for key, spec in raw.items():
            _validate_key(key, source)
            if not isinstance(spec, dict) or "kind" not in spec or "body" not in spec:
                raise ValueError(
                    f"{source}: entry {key!r} must have 'kind' and 'body' fields"
                )
            kind = spec["kind"]
            body = spec["body"]
            if kind not in ALL_KINDS:
                raise ValueError(f"{source}: entry {key!r} has unknown kind {kind!r}")
            if not isinstance(body, str):
                raise ValueError(f"{source}: entry {key!r} body must be a string")
            entries.append(ContentEntry(id=key, kind=kind, body=body, source=source))
    return entries


def _iter_markdown_entries(md_root: Path) -> list[ContentEntry]:
    """Walk `md_root` recursively. Each `.md` file's key is its relative
    path with `/` → `.` and no extension. Kind is read from a frontmatter
    line `<!-- kind: panel -->` at the top of the file; default is `panel`.
    """
    entries: list[ContentEntry] = []
    if not md_root.is_dir():
        return entries
    for path in sorted(md_root.rglob("*.md")):
        rel = path.relative_to(md_root)
        key = str(rel.with_suffix("")).replace(os.sep, ".")
        source = str(path.relative_to(md_root.parent.parent)) if md_root.parent.parent in path.parents else str(path)
        _validate_key(key, source)
        body = path.read_text(encoding="utf-8")
        kind = "panel"
        first_line = body.split("\n", 1)[0].strip()
        m = re.match(r"<!--\s*kind:\s*([a-z]+)\s*-->", first_line)
        if m:
            kind = m.group(1)
            body = body.split("\n", 1)[1] if "\n" in body else ""
        if kind not in KINDS_LONG:
            raise ValueError(
                f"{source}: Markdown files may only declare a long kind "
                f"({sorted(KINDS_LONG)}); got {kind!r}"
            )
        entries.append(ContentEntry(id=key, kind=kind, body=body, source=source))
    return entries


def _build_registry(content_root: Path, *, strict: bool) -> _Registry:
    yaml_dir = content_root / "help"
    md_root = content_root / "help" / "long"
    entries: list[ContentEntry] = []
    entries.extend(_iter_yaml_entries(yaml_dir))
    entries.extend(_iter_markdown_entries(md_root))

    # Duplicate detection — the same key may not be declared twice, regardless
    # of source. Duplicates are a configuration error, not a merge policy.
    seen: dict[str, str] = {}
    for e in entries:
        if e.id in seen:
            raise ValueError(
                f"Duplicate content key {e.id!r}: declared in {seen[e.id]} "
                f"and {e.source}"
            )
        seen[e.id] = e.source

    return _Registry(entries={e.id: e for e in entries}, strict=strict)


def init_content_registry(app) -> _Registry:
    """Initialize the registry from `content/help/` under the app root.

    Called once from the app factory. In dev/test the registry is strict:
    missing keys and format errors raise. In prod it is lenient: missing
    keys log and fall back to a controlled string; CI is the mechanism
    that ensures they never reach prod in the first place.
    """
    global _registry
    content_root = Path(app.root_path).parent / "content"
    strict = app.config.get("TESTING", False) or app.debug or app.env == "development" \
        if hasattr(app, "env") else (app.config.get("TESTING", False) or app.debug)
    with _lock:
        _registry = _build_registry(content_root, strict=strict)
    return _registry


_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_markdown(source: str) -> Markup:
    """Render Markdown → sanitized HTML. Sanitizer allowlist is tight."""
    raw_html = md.markdown(source, extensions=["extra", "sane_lists"])
    cleaned = bleach.clean(
        raw_html,
        tags=list(_ALLOWED_TAGS),
        attributes=_ALLOWED_ATTRS,
        protocols=list(_ALLOWED_PROTOCOLS),
        strip=True,
    )
    return Markup(cleaned)


def _interpolate(body: str, key: str, kind: str, kwargs: dict[str, Any]) -> str:
    """Apply `str.format(**kwargs)`.

    Interpolation mismatches are a caller bug (data-shape mismatch, not
    a copy authoring issue). In strict mode we raise; in prod we log
    and strip unresolved `{placeholders}` rather than paint a stack
    trace into a tooltip.
    """
    if not kwargs and "{" not in body:
        return body
    try:
        return body.format(**kwargs)
    except (KeyError, IndexError) as exc:
        reg = get_registry()
        if reg.strict:
            raise ContentKeyError(
                f"Missing interpolation value for {key!r} ({kind}): {exc}"
            ) from exc
        logger.error(
            "content-registry: interpolation failed for %s (%s): %s", key, kind, exc
        )
        return re.sub(r"\{[^{}]*\}", "", body)


def _missing(key: str, kind_hint: str) -> str:
    """Missing-key body.

    - dev/test (strict): visible `[missing: key]` marker so the gap is
      obvious in the UI without breaking the page. CI is the mechanism
      that keeps missing keys out of prod in the first place.
    - prod: structured error log + controlled fallback. Visible kinds
      render "Help text unavailable."; invisible kinds (aria /
      placeholder) render an empty string so we don't paint UI garbage
      into inputs.
    """
    reg = get_registry()
    if reg.strict:
        logger.warning("content-registry: unknown key %r (hint=%s)", key, kind_hint)
        return f"[missing: {key}]"
    logger.error("content-registry: unknown key %r (hint=%s)", key, kind_hint)
    if kind_hint in KINDS_INVISIBLE:
        return ""
    return "Help text unavailable."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def help(key: str, **kwargs: Any) -> Markup:  # noqa: A001 — Jinja idiom
    """Return short, HTML-escaped microcopy as a `Markup` string.

    For tooltips, hints, placeholders, empty states, aria labels,
    inline alerts, and any other short content. Kwargs interpolate
    via `str.format`. The returned value is *escaped* — safe to place
    in any HTML context.
    """
    reg = get_registry()
    entry = reg.get(key)
    if entry is None:
        return Markup(escape(_missing(key, kind_hint="hint")))
    if entry.kind in KINDS_LONG:
        raise ValueError(
            f"help({key!r}) is a long-form ({entry.kind}); call help_long() instead"
        )
    body = _interpolate(entry.body, key, entry.kind, kwargs)
    return Markup(escape(body))


def help_long(key: str, **kwargs: Any) -> RenderedContent:
    """Return a `RenderedContent` for a long-form Markdown panel.

    Templates render `{{ panel.html }}` to emit trusted HTML. Only the
    `.html` attribute unwraps to trusted `Markup`. Interpolation happens
    on the Markdown *source* before rendering, so `{{ balance }}`-style
    placeholders can appear inside prose.
    """
    reg = get_registry()
    entry = reg.get(key)
    if entry is None:
        fallback = _missing(key, kind_hint="panel")
        return RenderedContent(
            id=key,
            kind="panel",
            html=Markup(f"<p>{escape(fallback)}</p>"),
            text=fallback,
        )
    if entry.kind not in KINDS_LONG:
        raise ValueError(
            f"help_long({key!r}) is a short-form ({entry.kind}); call help() instead"
        )
    interpolated = _interpolate(entry.body, key, entry.kind, kwargs)
    return RenderedContent(
        id=key,
        kind=entry.kind,
        html=_render_markdown(interpolated),
        text=interpolated,
    )


def help_text(key: str, **kwargs: Any) -> str:
    """Return the raw text body of an entry — for Python callers.

    Use for flash messages, log lines, email bodies. No HTML rendering,
    no escaping. Long-form kinds return the raw Markdown source.
    """
    reg = get_registry()
    entry = reg.get(key)
    if entry is None:
        return _missing(key, kind_hint="flash")
    return _interpolate(entry.body, key, entry.kind, kwargs)
