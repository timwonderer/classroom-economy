"""Rendered axe-core smoke audits for the public application surface.

This audit drives a real browser against a RUNNING dev server, so it has three
environment prerequisites: the Playwright package, a Chromium build, and a
server listening on ``BASE_URL``. It is not part of the accessibility CI gate
(``.github/workflows/accessibility-gate.yml`` runs ``tests/test_accessibility.py``),
so in an ordinary suite run the server is normally absent.

All three prerequisites are therefore treated alike and skip rather than fail.
Previously the first two skipped and the third raised ``ERR_CONNECTION_REFUSED``,
which put a permanent red in every full-suite run — noise that makes a real
regression harder to see. A skip says "not audited here"; a failure should be
reserved for "audited, and the page has a violation".

To actually run it: ``flask run`` in another shell, then invoke pytest.
"""

import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None


REPO_ROOT = Path(__file__).resolve().parent.parent
AXE_SOURCE = (REPO_ROOT / "tests" / "assets" / "axe-core.min.js").read_text(encoding="utf-8")
BASE_URL = "http://127.0.0.1:5000"
PUBLIC_ROUTES = [
    "/",
    "/gh/landing.html",
    "/gh/learnmore.html",
    "/gh/district.html",
    "/gh/privacy.html",
    "/gh/terms.html",
    "/gh/v2progress.html",
]


def _server_is_listening(base_url: str, timeout: float = 0.5) -> bool:
    parsed = urlparse(base_url)
    try:
        with socket.create_connection(
            (parsed.hostname, parsed.port or 80), timeout=timeout
        ):
            return True
    except OSError:
        return False


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_public_pages_have_no_axe_violations():
    """Audit every unauthenticated public page against the local dev server."""
    if not _server_is_listening(BASE_URL):
        pytest.skip(
            f"No dev server listening on {BASE_URL}; start one with `flask run` "
            "to run the rendered axe audit"
        )

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            page = browser.new_page()
            for route in PUBLIC_ROUTES:
                response = page.goto(f"{BASE_URL}{route}", wait_until="networkidle")
                assert response is not None and response.ok, f"Could not load {route}"
                page.add_script_tag(content=AXE_SOURCE)
                result = page.evaluate("""async () => {
                    return await axe.run(document, {
                        runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}
                    });
                }""")
                assert not result["violations"], f"axe violations on {route}: {result['violations']}"
