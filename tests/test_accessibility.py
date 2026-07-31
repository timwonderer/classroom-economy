"""
Accessibility smoke tests for rendered public and auth pages.

The test scope is intentionally narrow: it audits the exact rendered HTML for
the template(s) or static GitHub Pages files listed in
ACCESSIBILITY_TEMPLATE_PATHS.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from flask import render_template

from app import app as flask_app


REPO_ROOT = Path(__file__).resolve().parent.parent
GITHUB_PAGES_DIR = REPO_ROOT / "github-pages"


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


def _render_static_github_page(template_path: Path) -> str:
    return template_path.read_text(encoding="utf-8")


def _render_route(client, route: str) -> str:
    response = client.get(route)
    assert response.status_code == 200, f"Route {route} did not return 200."
    return response.get_data(as_text=True)


def _render_direct(template_name: str, **context) -> str:
    with flask_app.test_request_context("/"):
        return render_template(template_name, **context)


class _DummyField:
    def __init__(self, tag_name: str = "input", field_type: str | None = "text"):
        self.tag_name = tag_name
        self.field_type = field_type

    def __call__(self, **attrs):
        rendered_attrs = []
        if self.tag_name == "input" and self.field_type:
            rendered_attrs.append(f'type="{self.field_type}"')
        for key, value in attrs.items():
            rendered_attrs.append(f'{key.replace("_", "-")}="{value}"')
        if self.tag_name == "input":
            return f"<input {' '.join(rendered_attrs)} />"
        return f"<{self.tag_name} {' '.join(rendered_attrs)}></{self.tag_name}>"


class _DummyForm:
    def __init__(self, **fields):
        self._fields = fields

    def hidden_tag(self):
        return ""

    def __getattr__(self, item):
        if item in self._fields:
            return self._fields[item]
        raise AttributeError(item)


def _render_page(template_path: Path, client) -> str:
    name = template_path.name

    github_pages_map = {
        "privacy.html": GITHUB_PAGES_DIR / "privacy.html",
        "district.html": GITHUB_PAGES_DIR / "district.html",
        "terms.html": GITHUB_PAGES_DIR / "terms.html",
    }
    if template_path in github_pages_map.values():
        return _render_static_github_page(template_path)

    route_map = {
        "templates/admin_login.html": lambda: _render_route(client, "/admin/login"),
        "templates/admin_recovery_saved.html": lambda: _render_direct(
            "admin_recovery_saved.html",
            codes_saved=2,
            resume_pin="123456",
            recovery_request=SimpleNamespace(expires_at=SimpleNamespace(strftime=lambda fmt: "July 31, 2026 at 12:00 PM")),
        ),
        "templates/admin_reset_credentials.html": lambda: _render_direct(
            "admin_reset_credentials.html",
            show_qr=False,
            saved_codes=[],
            saved_username="",
            form=SimpleNamespace(csrf_token=""),
        ),
        "templates/admin_resume_credentials.html": lambda: _render_route(client, "/admin/resume-credentials"),
        "templates/admin_signup.html": lambda: _render_route(client, "/admin/signup"),
        "templates/error_400.html": lambda: _render_direct("error_400.html", error_message="Example request error."),
        "templates/error_500.html": lambda: _render_direct("error_500.html", error_id="ERR-TEST-500"),
        "templates/system_admin_login.html": lambda: _render_route(client, "/sysadmin/login"),
        "templates/system_admin_logs.html": lambda: _render_direct(
            "system_admin_logs.html",
            logs=[{"message": "Test log entry", "timestamp": "2026-07-31 00:00:00"}],
            current_page=1,
            total_pages=1,
            total_logs=1,
        ),
        "templates/student_login.html": lambda: _render_route(client, "/student/login"),
        "templates/student_account_claim.html": lambda: _render_route(client, "/student/claim-account"),
        "templates/student_create_username.html": lambda: _render_direct(
            "student_create_username.html",
            theme_prompt="creative word",
            form=_DummyForm(
                hidden_tag=lambda: "",
                write_in_word=_DummyField(),
                submit=_DummyField("button", None),
            ),
        ),
        "templates/student_pin_setup.html": lambda: _render_direct(
            "student_pin_setup.html",
            username="student1234",
            form=_DummyForm(
                hidden_tag=lambda: "",
                pin=_DummyField(),
                passphrase=_DummyField(),
                submit=_DummyField("button", None),
            ),
        ),
        "templates/maintenance.html": lambda: _render_direct(
            "maintenance.html",
            badge_icon="construction",
            badge_text="Scheduled Maintenance",
            title="Scheduled Maintenance",
            subtitle="We're performing scheduled maintenance to keep Classroom Economy running smoothly.",
        ),
    }

    key = str(template_path)
    if key in route_map:
        return route_map[key]()

    if template_path.suffix == ".html" and template_path.parent.name == "github-pages":
        return _render_static_github_page(template_path)

    if name == "base.html" or name.startswith("layout_"):
        pytest.skip("Layout shell templates are not standalone pages; audit rendered pages instead.")

    html = template_path.read_text(encoding="utf-8")
    if "{% extends" in html:
        pytest.skip("Template is a fragment rendered via a parent layout; audit the final page instead.")
    return html


@pytest.mark.parametrize("template_path", _template_paths())
def test_template_accessibility_smoke(template_path: Path):
    with flask_app.test_client() as client:
        html = _render_page(template_path, client)
    _audit_html_accessibility(html)
