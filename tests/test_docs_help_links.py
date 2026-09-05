"""The in-app help links must resolve to real documentation.

The layouts pick a doc path from `help_doc_map` keyed on `current_page` with a
fallback to `request.endpoint`. A typo in either the map key or the doc path
renders a Guide button that 404s, and nothing else in the suite would notice.
"""

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from tests.helpers.classroom_initializer import (
    initialize_as_student,
    initialize_as_teacher,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"

# Deliberately a small sample. The contract these prove is that the layout
# resolves `help_doc_map` into a working link at all; `test_help_doc_map_targets_exist`
# is what covers every entry. Balance-bearing pages are excluded because they
# depend on ledger state the fixture does not build.
TEACHER_PAGES = [
    "/admin/attendance-log",
    "/admin/store",
    "/admin/hall-pass",
]

STUDENT_PAGES = [
    "/student/payroll",
]


def _doc_paths_in_layout(layout: str) -> list[str]:
    """Every value declared in the layout's `help_doc_map`."""
    source = (REPO_ROOT / "templates" / layout).read_text(encoding="utf-8")
    start = source.index("help_doc_map = {")
    end = source.index("}", start)
    block = source[start:end]
    return [
        line.split(":", 1)[1].strip().strip(",").strip("'\"")
        for line in block.splitlines()
        if ":" in line and ("'" in line or '"' in line)
    ]


def _doc_file_exists(doc_path: str) -> bool:
    base = DOCS_ROOT / doc_path
    return any(
        candidate.is_file()
        for candidate in (
            base.with_suffix(".md"),
            base / "index.md",
            base / "README.md",
        )
    )


@pytest.mark.parametrize("layout", ["layout_admin.html", "layout_student.html"])
def test_help_doc_map_targets_exist(layout):
    missing = [p for p in _doc_paths_in_layout(layout) if not _doc_file_exists(p)]
    assert not missing, f"{layout} help_doc_map points at missing docs: {missing}"


# `url_for('docs.view_doc', doc_path=...)` and the help macros both take a bare
# doc path, so a typo renders a 404 that only shows up by clicking it.
_DOC_REFERENCE = re.compile(
    r"""(?:doc_path=|doc_url\(|help_link\(|help_icon\()\s*['"]([^'"]+)['"]"""
)


def test_every_template_doc_reference_resolves():
    missing = {}
    for template in (REPO_ROOT / "templates").rglob("*.html"):
        for ref in _DOC_REFERENCE.findall(template.read_text(encoding="utf-8")):
            path = ref.split("#", 1)[0]
            if not _doc_file_exists(path):
                missing.setdefault(template.name, set()).add(path)
    assert not missing, f"templates reference missing docs: {missing}"


def _assert_help_links_resolve(client, url):
    page = client.get(url)
    assert page.status_code == 200, f"{url} returned {page.status_code}"

    soup = BeautifulSoup(page.data, "html.parser")
    # The help macros interpolate a nested macro call, so hrefs arrive padded
    # with the surrounding template whitespace.
    hrefs = {
        a["href"].strip()
        for a in soup.find_all("a", href=True)
        if a["href"].strip().startswith("/docs/")
    }
    assert hrefs, f"{url} rendered no help links"

    for href in sorted(hrefs):
        response = client.get(href)
        assert response.status_code < 400, (
            f"help link {href} on {url} returned {response.status_code}"
        )


@pytest.mark.parametrize("url", TEACHER_PAGES)
def test_teacher_help_links_resolve(client, app, url):
    initialize_as_teacher("chemistry_p1", client, app)
    _assert_help_links_resolve(client, url)


@pytest.mark.parametrize("url", STUDENT_PAGES)
def test_student_help_links_resolve(client, app, url):
    initialize_as_student("chemistry_p1", client, app)
    _assert_help_links_resolve(client, url)
