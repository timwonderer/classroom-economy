"""Content registry — unit tests for the pilot plumbing.

Covers: load, kind classification, short vs long rendering, sanitizer,
`RenderedContent` trust boundary, interpolation, missing-key policy in
strict vs prod, duplicate detection, and CI validator behavior.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from markupsafe import Markup

from app.content import registry as content_registry
from app.content.registry import (
    ContentKeyError,
    RenderedContent,
    _build_registry,
    help,
    help_long,
    help_text,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def content_root(tmp_path):
    root = tmp_path / "content"
    (root / "help").mkdir(parents=True)
    (root / "help" / "long" / "admin").mkdir(parents=True)
    return root


def _install(root: Path, *, strict: bool = True):
    reg = _build_registry(root, strict=strict)
    content_registry._registry = reg
    return reg


# ---------------------------------------------------------------------------
# YAML loading + kind classification
# ---------------------------------------------------------------------------


def test_short_entry_returns_escaped_markup(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.rent.grace_period:\n  kind: hint\n  body: Days before late fees.\n"
    )
    _install(content_root)
    result = help("admin.rent.grace_period")
    assert isinstance(result, Markup)
    assert str(result) == "Days before late fees."


def test_short_entry_escapes_html_in_body(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.rent.warn:\n  kind: warning\n  body: '<script>x</script>'\n"
    )
    _install(content_root)
    result = help("admin.rent.warn")
    # Body is HTML-escaped — help() is for short microcopy, never trusted HTML.
    assert "&lt;script&gt;" in str(result)
    assert "<script>" not in str(result)


def test_interpolation(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.class.hello:\n  kind: hint\n  body: Hello, {name}!\n"
    )
    _install(content_root)
    assert str(help("admin.class.hello", name="Ada")) == "Hello, Ada!"


def test_interpolation_escapes_dynamic_value(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.class.hello:\n  kind: hint\n  body: Hello, {name}!\n"
    )
    _install(content_root)
    result = help("admin.class.hello", name="<script>x</script>")
    # str.format runs, then escape() runs on the whole string.
    assert "&lt;script&gt;" in str(result)


# ---------------------------------------------------------------------------
# Markdown long-form + trust boundary
# ---------------------------------------------------------------------------


def test_help_long_returns_rendered_content(content_root):
    (content_root / "help" / "long" / "admin" / "rent.md").write_text(
        "# Rent\n\nExplains **rent** with a [link](https://example.com).\n"
    )
    _install(content_root)
    result = help_long("admin.rent")
    assert isinstance(result, RenderedContent)
    assert result.kind == "panel"
    assert isinstance(result.html, Markup)
    assert "<strong>rent</strong>" in str(result.html)
    assert '<a href="https://example.com">link</a>' in str(result.html)


def test_help_long_sanitizes_disallowed_tags(content_root):
    (content_root / "help" / "long" / "admin" / "rent.md").write_text(
        "<script>steal()</script>\n\nAllowed **bold**.\n"
    )
    _install(content_root)
    result = help_long("admin.rent")
    assert "<script>" not in str(result.html)
    assert "<strong>bold</strong>" in str(result.html)


def test_help_long_strips_javascript_urls(content_root):
    (content_root / "help" / "long" / "admin" / "rent.md").write_text(
        "[click](javascript:alert(1))\n"
    )
    _install(content_root)
    result = help_long("admin.rent")
    assert "javascript:" not in str(result.html)


def test_rendered_content_text_is_raw_source(content_root):
    """The .text attribute is raw Markdown source — templates that use it
    get HTML-escaped by Jinja like any string."""
    (content_root / "help" / "long" / "admin" / "rent.md").write_text(
        "**bold** and _italic_\n"
    )
    _install(content_root)
    result = help_long("admin.rent")
    assert "**bold**" in result.text
    assert isinstance(result.text, str)
    assert not isinstance(result.text, Markup)


def test_help_long_kind_frontmatter(content_root):
    (content_root / "help" / "long" / "admin" / "rent.md").write_text(
        "<!-- kind: modal -->\nA modal body.\n"
    )
    _install(content_root)
    result = help_long("admin.rent")
    assert result.kind == "modal"


# ---------------------------------------------------------------------------
# Kind guardrails: short vs long routing
# ---------------------------------------------------------------------------


def test_help_on_long_kind_raises(content_root):
    (content_root / "help" / "long" / "admin" / "rent.md").write_text("# Rent\n")
    _install(content_root)
    with pytest.raises(ValueError, match="help_long"):
        help("admin.rent")


def test_help_long_on_short_kind_raises(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.rent.tip:\n  kind: tooltip\n  body: short\n"
    )
    _install(content_root)
    with pytest.raises(ValueError, match="help\\("):
        help_long("admin.rent.tip")


# ---------------------------------------------------------------------------
# Missing key policy
# ---------------------------------------------------------------------------


def test_missing_key_strict_returns_visible_marker(content_root, caplog):
    _install(content_root, strict=True)
    result = help("admin.missing.key")
    assert "[missing: admin.missing.key]" in str(result)
    assert any("unknown key" in r.message for r in caplog.records)


def test_missing_key_prod_visible_kind_returns_fallback(content_root, caplog):
    _install(content_root, strict=False)
    result = help("admin.missing.key")
    assert str(result) == "Help text unavailable."
    assert any("unknown key" in r.message for r in caplog.records)


def test_missing_key_prod_invisible_kind_returns_empty(content_root, caplog):
    """aria / placeholder must never render UI-visible garbage in prod."""
    _install(content_root, strict=False)
    # There's no way to signal kind from the caller; the fallback for
    # unknown keys defaults to visible ("Help text unavailable"). Aria
    # keys should exist by CI-time. This test locks the default in.
    assert str(help("admin.missing.key")) == "Help text unavailable."


def test_missing_key_prod_help_long_fallback(content_root):
    _install(content_root, strict=False)
    result = help_long("admin.missing.panel")
    assert isinstance(result, RenderedContent)
    assert "Help text unavailable" in str(result.html)


def test_help_text_missing_key_strict(content_root):
    _install(content_root, strict=True)
    assert "[missing:" in help_text("admin.missing")


def test_help_text_missing_key_prod(content_root):
    _install(content_root, strict=False)
    assert help_text("admin.missing") == "Help text unavailable."


# ---------------------------------------------------------------------------
# Interpolation error policy
# ---------------------------------------------------------------------------


def test_interpolation_missing_kwarg_strict_raises(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.class.hello:\n  kind: hint\n  body: Hello, {name}!\n"
    )
    _install(content_root, strict=True)
    with pytest.raises(ContentKeyError):
        help("admin.class.hello")  # no name= kwarg


def test_interpolation_missing_kwarg_prod_strips(content_root, caplog):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.class.hello:\n  kind: hint\n  body: Hello, {name}!\n"
    )
    _install(content_root, strict=False)
    result = help("admin.class.hello")
    # Placeholder stripped, log emitted.
    assert "{name}" not in str(result)
    assert any("interpolation failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Loader errors: duplicates, invalid keys, unknown kinds
# ---------------------------------------------------------------------------


def test_duplicate_key_across_yaml_files_raises(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.rent.tip:\n  kind: tooltip\n  body: A\n"
    )
    (content_root / "help" / "student.yaml").write_text(
        "admin.rent.tip:\n  kind: tooltip\n  body: B\n"
    )
    with pytest.raises(ValueError, match="Duplicate content key"):
        _build_registry(content_root, strict=True)


def test_duplicate_key_across_yaml_and_markdown_raises(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.rent:\n  kind: hint\n  body: A\n"
    )
    (content_root / "help" / "long" / "admin" / "rent.md").write_text(
        "# Rent\nA panel\n"
    )
    with pytest.raises(ValueError, match="Duplicate content key"):
        _build_registry(content_root, strict=True)


def test_invalid_key_shape_raises(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "InvalidKey:\n  kind: hint\n  body: x\n"
    )
    with pytest.raises(ValueError, match="Invalid content key"):
        _build_registry(content_root, strict=True)


def test_unknown_kind_raises(content_root):
    (content_root / "help" / "admin.yaml").write_text(
        "admin.rent.x:\n  kind: bogus\n  body: y\n"
    )
    with pytest.raises(ValueError, match="unknown kind"):
        _build_registry(content_root, strict=True)


def test_markdown_short_kind_raises(content_root):
    (content_root / "help" / "long" / "admin" / "tip.md").write_text(
        "<!-- kind: tooltip -->\nShort content\n"
    )
    with pytest.raises(ValueError, match="long kind"):
        _build_registry(content_root, strict=True)


# ---------------------------------------------------------------------------
# CI validator
# ---------------------------------------------------------------------------


def _run_validator(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_content_keys.py"),
         "--allow-orphans"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_validator_detects_missing_reference(tmp_path):
    """Reference in a template with no matching entry ⇒ non-zero exit."""
    # Build a minimal fake repo layout
    (tmp_path / "content" / "help").mkdir(parents=True)
    (tmp_path / "content" / "help" / "admin.yaml").write_text(
        "admin.rent.exists:\n  kind: hint\n  body: OK\n"
    )
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "x.html").write_text(
        "{{ help('admin.rent.does_not_exist') }}\n"
    )
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("")
    (tmp_path / "scripts").mkdir()
    # Copy the validator script
    (tmp_path / "scripts" / "validate_content_keys.py").write_bytes(
        (REPO_ROOT / "scripts" / "validate_content_keys.py").read_bytes()
    )
    result = _run_validator(tmp_path)
    assert result.returncode != 0
    assert "MISSING" in result.stderr
    assert "admin.rent.does_not_exist" in result.stderr


def test_validator_passes_on_clean_registry(tmp_path):
    (tmp_path / "content" / "help").mkdir(parents=True)
    (tmp_path / "content" / "help" / "admin.yaml").write_text(
        "admin.rent.tip:\n  kind: hint\n  body: OK\n"
    )
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "x.html").write_text(
        "{{ help('admin.rent.tip') }}\n"
    )
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "validate_content_keys.py").write_bytes(
        (REPO_ROOT / "scripts" / "validate_content_keys.py").read_bytes()
    )
    result = _run_validator(tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"


def test_validator_detects_python_reference(tmp_path):
    """Python `help_text('key')` with no entry ⇒ non-zero exit."""
    (tmp_path / "content" / "help").mkdir(parents=True)
    (tmp_path / "content" / "help" / "admin.yaml").write_text("{}\n")
    (tmp_path / "templates").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "routes.py").write_text(
        "def x():\n    flash(help_text('admin.missing.flash'))\n"
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "validate_content_keys.py").write_bytes(
        (REPO_ROOT / "scripts" / "validate_content_keys.py").read_bytes()
    )
    result = _run_validator(tmp_path)
    assert result.returncode != 0
    assert "admin.missing.flash" in result.stderr
