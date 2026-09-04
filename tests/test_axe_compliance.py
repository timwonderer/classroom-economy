"""Rendered axe-core smoke audits for the public application surface."""

from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment-dependent dependency
    sync_playwright = None


REPO_ROOT = Path(__file__).resolve().parent.parent
AXE_SOURCE = (REPO_ROOT / "tests" / "assets" / "axe-core.min.js").read_text(encoding="utf-8")
PUBLIC_ROUTES = [
    "/",
    "/gh/landing.html",
    "/gh/learnmore.html",
    "/gh/district.html",
    "/gh/privacy.html",
    "/gh/terms.html",
    "/gh/v2progress.html",
]


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_public_pages_have_no_axe_violations():
    """Audit every unauthenticated public page against the local dev server."""
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            page = browser.new_page()
            for route in PUBLIC_ROUTES:
                response = page.goto(f"http://127.0.0.1:5000{route}", wait_until="networkidle")
                assert response is not None and response.ok, f"Could not load {route}"
                page.add_script_tag(content=AXE_SOURCE)
                result = page.evaluate("""async () => {
                    return await axe.run(document, {
                        runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}
                    });
                }""")
                assert not result["violations"], f"axe violations on {route}: {result['violations']}"
