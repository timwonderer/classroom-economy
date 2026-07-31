"""
Template-scoped accessibility smoke tests.

This suite intentionally stays narrow while the UI is under active refactor.
It checks only the template files passed in via ACCESSIBILITY_TEMPLATE_PATHS,
so CI validates the exact template(s) touched by a PR instead of pretending to
cover the whole app.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from bs4 import BeautifulSoup


def _template_paths() -> list[Path]:
    raw = os.environ.get("ACCESSIBILITY_TEMPLATE_PATHS", "").strip()
    if not raw:
        return []
    return [Path(item) for item in raw.splitlines() if item.strip()]


def _audit_html_accessibility(html_content: str) -> None:
    soup = BeautifulSoup(html_content, "html.parser")

    title_tag = soup.find("title")
    assert title_tag is not None, "Page is missing a <title> element."
    assert title_tag.get_text(strip=True), "<title> element is empty."

    for img in soup.find_all("img"):
        assert img.has_attr("alt"), f"Image missing alt attribute: {img}"

    for a in soup.find_all("a"):
        if not a.has_attr("href") and not a.has_attr("role"):
            continue
        has_name = bool(
            a.get_text(strip=True)
            or a.has_attr("aria-label")
            or a.has_attr("aria-labelledby")
            or a.has_attr("title")
            or a.find("img", alt=lambda x: x and len(x.strip()) > 0)
        )
        assert has_name, f"Link missing accessible name: {a}"

    for button in soup.find_all("button"):
        has_name = bool(
            button.get_text(strip=True)
            or button.has_attr("aria-label")
            or button.has_attr("aria-labelledby")
            or button.has_attr("title")
            or button.find("img", alt=lambda x: x and len(x.strip()) > 0)
        )
        assert has_name, f"Button missing accessible name: {button}"

    for control_type in ["input", "select", "textarea"]:
        for control in soup.find_all(control_type):
            if control.get("type") in ["hidden", "submit", "button", "image"]:
                continue

            control_id = control.get("id")
            has_label = False

            if control_id and soup.find("label", attrs={"for": control_id}):
                has_label = True

            if not has_label:
                parent = control.parent
                while parent:
                    if parent.name == "label":
                        has_label = True
                        break
                    parent = parent.parent

            if not has_label and (control.has_attr("aria-label") or control.has_attr("aria-labelledby")):
                has_label = True

            assert has_label, f"Form control <{control_type}> missing label or ARIA identifier: {control}"

    ids = [el.get("id") for el in soup.find_all(id=True)]
    duplicates = {value for value in ids if ids.count(value) > 1}
    assert not duplicates, f"Duplicate ID attributes found on page: {duplicates}"

    headings = [int(el.name[1]) for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    assert headings.count(1) == 1, "Page must have exactly one <h1>."


@pytest.mark.parametrize("template_path", _template_paths())
def test_template_accessibility_smoke(template_path: Path):
    html = template_path.read_text(encoding="utf-8")
    if "{% extends" in html:
        pytest.skip("Template is a fragment rendered via a parent layout; audit the final page instead.")
    _audit_html_accessibility(html)
