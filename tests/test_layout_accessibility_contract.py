"""Regression checks for the shared navigation accessibility contract."""

from pathlib import Path

from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parent.parent


def _template(name: str) -> BeautifulSoup:
    return BeautifulSoup(
        (REPO_ROOT / "templates" / name).read_text(encoding="utf-8"),
        "html.parser",
    )


def test_standalone_documents_provide_a_main_landmark():
    for page in (REPO_ROOT / "templates").rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        if soup.find("html"):
            main = soup.find("main")
            assert main is not None, f"Standalone document lacks main landmark: {page}"


def test_portal_navigation_has_distinct_landmark_names():
    for name, label in (
        ("layout_admin.html", "Admin portal"),
        ("layout_student.html", "Student portal"),
        ("layout_system_admin.html", "System administration"),
    ):
        soup = _template(name)
        assert soup.find("nav", attrs={"aria-label": label}) is not None


def test_portal_layouts_provide_skip_navigation_to_main_content():
    for name in ("layout_admin.html", "layout_student.html", "layout_system_admin.html"):
        soup = _template(name)
        skip = soup.find("a", href="#main-content")
        assert skip is not None
        assert "Skip to main content" in skip.get_text(" ", strip=True)
        assert soup.find(id="main-content") is not None


def test_mobile_sidebar_script_matches_shell_breakpoint():
    script = (REPO_ROOT / "static" / "js" / "mobile-sidebar-toggle.js").read_text(
        encoding="utf-8"
    )
    assert "window.matchMedia('(max-width: 991.98px)')" in script
    assert "const DESKTOP_BREAKPOINT_PX = 992" in script


def test_mobile_sidebar_hides_closed_controls_from_sequential_focus():
    script = (REPO_ROOT / "static" / "js" / "mobile-sidebar-toggle.js").read_text(
        encoding="utf-8"
    )
    assert "sidebar.setAttribute('inert', '')" in script
    assert "sidebar.removeAttribute('inert')" in script


def test_admin_compact_navigation_exposes_current_page_state():
    soup = _template("layout_admin.html")
    compact_nav = soup.select_one(".mobile-bottom-nav")
    assert compact_nav is not None
    links = compact_nav.find_all("a")
    assert len(links) == 4
    for page in ("dashboard", "attendance", "students", "store"):
        assert f"current_page == '{page}'" in str(compact_nav)
    assert all(link.get("aria-label") for link in links)


def test_public_new_tab_links_announce_context_change():
    for page in (REPO_ROOT / "github-pages").glob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for link in soup.select('a[target="_blank"]'):
            assert "noopener" in link.get("rel", [])
            assert "opens in a new tab" in link.get_text(" ", strip=True).lower(), page


def test_responsive_shell_breakpoints_keep_toggle_available_on_tablets():
    css = (REPO_ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
    mobile_block = css[css.index("/* ─── Mobile Layout ─── */") :]
    assert "@media (max-width: 991.98px)" in mobile_block
    assert "@media (min-width: 992px)" in mobile_block


def test_authenticated_layouts_hide_decorative_material_symbols_from_accessibility_tree():
    for name in ("layout_admin.html", "layout_student.html", "layout_system_admin.html"):
        html = (REPO_ROOT / "templates" / name).read_text(encoding="utf-8")
        assert "querySelectorAll('.material-symbols-outlined')" in html
        assert "setAttribute('aria-hidden', 'true')" in html


def test_sortable_tables_have_keyboard_and_sort_state_support():
    js = (REPO_ROOT / "static" / "js" / "sortable-table.js").read_text(encoding="utf-8")
    assert "header.tabIndex = 0" in js
    assert 'setAttribute("aria-sort", "none")' in js
    assert 'event.key !== "Enter"' in js
    assert 'event.key !== " "' in js


def test_attendance_pagination_uses_named_keyboard_actions():
    html = (REPO_ROOT / "templates" / "admin_attendance_log.html").read_text(encoding="utf-8")
    assert 'aria-label="Previous page"' in html
    assert 'aria-label="Next page"' in html
    assert 'aria-label="Page ${i}"' in html
    assert 'type="button" class="page-link"' in html


def test_inherited_feature_templates_have_no_duplicate_static_ids():
    for page in (REPO_ROOT / "templates").rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        if "{% extends" not in html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        ids = [element["id"] for element in soup.find_all(id=True)]
        duplicates = {value for value in ids if ids.count(value) > 1}
        assert not duplicates, f"{page} contains duplicate static IDs: {duplicates}"


def test_all_template_form_controls_have_a_source_label_or_aria_name():
    ignored = {"admin_nav.html", "_class_setup_fields.html"}
    for page in (REPO_ROOT / "templates").rglob("*.html"):
        if page.name in ignored or "components/" in page.as_posix() or "macros/" in page.as_posix():
            continue
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for control in soup.find_all(["input", "select", "textarea"]):
            if control.get("type") in {"hidden", "submit", "button", "image"}:
                continue
            control_id = control.get("id")
            has_label = bool(control_id and soup.find("label", attrs={"for": control_id}))
            has_label = has_label or bool(control.find_parent("label"))
            has_label = has_label or bool(control.get("aria-label") or control.get("aria-labelledby"))
            assert has_label, f"{page} contains an unlabeled form control: {control}"


def test_standalone_error_and_offline_surfaces_hide_decorative_icons():
    pages = [*REPO_ROOT.glob("templates/error_*.html"), REPO_ROOT / "templates" / "offline.html"]
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert "aria-hidden=\"true\"" in html or "aria-hidden', 'true'" in html, page
    offline = (REPO_ROOT / "templates" / "offline.html").read_text(encoding="utf-8")
    assert 'href="#offline-main"' in offline
    assert '<main id="offline-main">' in offline


def test_teacher_dashboard_uses_standard_html_for_metric_help():
    html = (REPO_ROOT / "templates" / "admin_dashboard.html").read_text(encoding="utf-8")
    assert "<subtitle" not in html
    assert "</subtitle>" not in html


def test_student_transfer_chart_has_a_textual_data_equivalent():
    html = (REPO_ROOT / "templates" / "student_transfer.html").read_text(encoding="utf-8")
    assert 'id="savingsProjectionChart"' in html
    assert 'aria-hidden="true"' in html
    assert 'id="savingsProjectionData"' in html
    assert "Projected savings balance by month" in html


def test_shared_runtime_hides_icons_inserted_after_initial_render():
    js = (REPO_ROOT / "static" / "js" / "app-core.js").read_text(encoding="utf-8")
    assert "MutationObserver" in js
    assert "addedNodes" in js
    assert "hideDecorativeIcons(node)" in js


def test_student_issue_character_counters_announce_updates_politely():
    html = (REPO_ROOT / "templates" / "student_submit_issue.html").read_text(encoding="utf-8")
    assert 'id="explanation-counter" aria-live="polite"' in html
    assert 'id="expected-outcome-counter" aria-live="polite"' in html


def test_templates_and_client_scripts_do_not_use_blocking_alerts():
    roots = [REPO_ROOT / "templates", REPO_ROOT / "github-pages", REPO_ROOT / "static" / "js"]
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".html", ".js"}:
                continue
            source = path.read_text(encoding="utf-8")
            assert "alert(" not in source, f"Blocking alert remains in {path}"


def test_admin_dropdown_triggers_describe_their_controlled_links():
    soup = _template("layout_admin.html")
    for trigger in soup.select("button[aria-controls]"):
        controlled_id = trigger["aria-controls"]
        controlled = soup.find(id=controlled_id)
        assert controlled is not None, f"Missing controlled element: {controlled_id}"
        assert trigger.get("aria-expanded") in {
            "true",
            "false",
            "{{ 'true' if classroom_open else 'false' }}",
            "{{ 'true' if economy_open else 'false' }}",
            "{{ 'true' if bills_open else 'false' }}",
            "{{ 'true' if class_tools_open else 'false' }}",
            "{{ 'true' if settings_open else 'false' }}",
        }


def test_admin_dashboard_exposes_current_location_to_assistive_technology():
    soup = _template("layout_admin.html")
    dashboard = soup.find("a", href="{{ url_for('admin.dashboard') }}")
    assert dashboard is not None
    assert 'aria-current="page"' in str(dashboard)


def test_documentation_timeline_disclosures_have_keyboard_contract():
    soup = BeautifulSoup(
        (REPO_ROOT / "templates" / "docs" / "timeline.html").read_text(encoding="utf-8"),
        "html.parser",
    )
    headers = soup.select(".tl-card-header")
    assert headers
    # The script promotes legacy div headers at runtime; retain an explicit
    # keyboard handler on the already-compliant first entry as a source guard.
    assert all(header.get("onclick") or header.get("role") == "button" for header in headers)
    assert "header.click()" in soup.get_text() or "header.click();" in str(soup)
    assert len(headers) > 1
    assert "querySelectorAll('.tl-card-header')" in str(soup)
    assert "aria-expanded" in str(soup)


def test_public_pages_load_an_icon_font_under_both_hosts():
    """The public pages must render icons from BOTH hosts that serve them.

    These files are served twice, under opposite constraints:

    * Published to GitHub Pages, where the artifact is ``github-pages/`` alone
      (see ``.github/workflows/github-pages-transition.yml``). A relative
      ``../static/`` path cannot resolve there, so the source must name a CDN.
    * Served by the application at ``/gh/<page>`` so a certification run stays
      on one origin. There the application's CSP applies and blocks that CDN,
      which would drop every Material Symbols glyph and re-expose ligature
      names as visible text. ``github_pages_asset`` therefore rewrites the
      stylesheet link back to the same-origin font on the way out.

    This test owns the published half. The app-served half is pinned by
    ``tests/dom/platform/test_security_headers.py``. An earlier version of this
    test asserted the CDN was absent from the source, which encoded a
    single-host assumption and made the correct published markup look broken.
    """
    pages = sorted((REPO_ROOT / "github-pages").glob("*.html"))
    assert pages, "No public pages found to check"

    icon_pages = []
    for page in pages:
        html = page.read_text(encoding="utf-8")
        # Keyed on actual icon USE, not on a filename allow-list: a page that
        # grows its first icon inherits the requirement automatically.
        if "material-symbols" in html:
            icon_pages.append(page.name)
            assert "Material+Symbols+Outlined" in html, (
                f"{page.name} uses icons but loads no icon font, so every glyph "
                "would render as its ligature name"
            )
        # Relative to the Pages artifact root, so it survives publication.
        assert "../static/" not in html, (
            f"{page.name} points outside the published artifact and would 404"
        )

    assert icon_pages, "No public page uses icons; this contract checks nothing"

    # The same-origin font the app-served copy is rewritten to must keep
    # ligatures on, or the rewrite trades one broken host for the other.
    fonts_css = (REPO_ROOT / "static" / "css" / "fonts.css").read_text(encoding="utf-8")
    assert "font-feature-settings: 'liga';" in fonts_css


def test_template_images_have_nonempty_alternative_text():
    for page in list((REPO_ROOT / "templates").rglob("*.html")) + list((REPO_ROOT / "github-pages").glob("*.html")):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for image in soup.find_all("img"):
            assert image.get("alt", "").strip(), f"Image without alternative text in {page}"


def test_shared_styles_respect_reduced_motion_preferences():
    css = (REPO_ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition-duration: 0.01ms !important" in css
    assert "scroll-behavior: auto !important" in css


def test_shared_styles_preserve_controls_in_forced_colors_mode():
    css = (REPO_ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
    assert "@media (forced-colors: active)" in css
    assert "border: 1px solid ButtonText" in css
    assert "outline: 3px solid Highlight !important" in css


def test_every_public_page_has_title_single_h1_and_main_landmark():
    public_pages = REPO_ROOT / "github-pages"
    pages = sorted(public_pages.glob("*.html"))
    assert pages
    for page in pages:
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        assert soup.title and soup.title.get_text(strip=True), page
        assert len(soup.find_all("h1")) == 1, page
        assert soup.find("main") is not None, page


def test_public_relative_links_resolve_to_checked_in_pages():
    public_pages = REPO_ROOT / "github-pages"
    for page in public_pages.glob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith(("http://", "https://", "mailto:", "#", "/")):
                continue
            target = (page.parent / href.split("#", 1)[0]).resolve()
            assert target.exists(), f"{page} contains a broken relative link: {href}"


def test_new_tab_links_declare_safe_relationship():
    for page in (REPO_ROOT / "templates").rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for link in soup.select('a[target="_blank"]'):
            assert "noopener" in link.get("rel", []), f"Unsafe new-tab link in {page}"


def test_template_buttons_declare_native_type():
    """Prevent non-submit controls from accidentally submitting surrounding forms."""
    for root in (REPO_ROOT / "templates", REPO_ROOT / "github-pages"):
        for page in root.rglob("*.html"):
            soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
            for button in soup.find_all("button"):
                assert button.get("type") in {"button", "submit", "reset"}, (
                    f"Button without explicit native type in {page}: "
                    f"{button.get_text(' ', strip=True)[:60]}"
                )


def test_template_new_tab_links_announce_context_change():
    for page in (REPO_ROOT / "templates").rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for link in soup.select('a[target="_blank"]'):
            assert "opens in a new tab" in link.get_text(" ", strip=True).lower(), page


def test_student_bulk_operations_use_button_semantics():
    soup = _template("admin_students.html")
    bulk_actions = soup.select("#bulkActionsDropdown-current-class + ul .dropdown-item")
    assert len(bulk_actions) == 4
    assert all(item.name == "button" for item in bulk_actions)
    assert all(item.get("type") == "button" for item in bulk_actions)


def test_student_store_keeps_action_feedback_in_page_accessible_region():
    soup = _template("student_shop.html")
    page_feedback = soup.find(id="storePageFeedback")
    assert page_feedback is not None
    assert page_feedback.get("role") == "status"
    assert page_feedback.get("aria-live") == "polite"
    script = str(soup)
    assert "announceStorePage(data.message || 'Purchase completed.')" in script
    assert "announceStorePage(data.message || 'Item use completed.')" in script


def test_student_store_tabs_expose_selection_and_panel_relationships():
    soup = _template("student_shop.html")
    for tab in soup.select("[role='tab']"):
        panel_id = tab.get("aria-controls")
        assert panel_id
        panel = soup.find(id=panel_id)
        assert panel is not None
        assert tab.get("aria-selected") in {"true", "false"}


def test_hall_pass_setup_dynamic_limits_and_toggle_are_named():
    script = (REPO_ROOT / "templates" / "hall_pass_setup.html").read_text(encoding="utf-8")
    assert 'aria-label="Enable ${passTypeName} hall pass type"' in script
    assert 'aria-label="${passTypeName} queue limit"' in script
    assert 'aria-label="${passTypeName} simultaneous limit"' in script


def test_template_modals_have_explicit_title_relationships():
    for page in (REPO_ROOT / "templates").rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for modal in soup.select(".modal"):
            labelledby = modal.get("aria-labelledby")
            assert labelledby, f"Modal {modal.get('id')} in {page} has no accessible title relationship"
            assert soup.find(id=labelledby), f"Modal {modal.get('id')} in {page} references missing title {labelledby}"


def test_template_tab_panels_have_explicit_tab_relationships():
    for page in (REPO_ROOT / "templates").rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for panel in soup.select('[role="tabpanel"]'):
            labelledby = panel.get("aria-labelledby")
            assert labelledby, f"Tab panel {panel.get('id')} in {page} has no controlling tab"
            tab = soup.find(id=labelledby)
            assert tab is not None, f"Tab panel {panel.get('id')} in {page} references missing tab {labelledby}"
            assert tab.get("role") == "tab"


def test_student_pin_strength_feedback_is_announced_politely():
    soup = _template("student_pin_setup.html")
    feedback = soup.find(id="strength-feedback")
    assert feedback is not None
    assert feedback.get("role") == "status"
    assert feedback.get("aria-live") == "polite"


def test_student_management_bulk_submit_feedback_is_focusable_and_live():
    soup = _template("admin_students.html")
    feedback = soup.find(id="submit-result")
    assert feedback is not None
    assert feedback.get("role") == "status"
    assert feedback.get("aria-live") == "polite"
    assert feedback.get("tabindex") == "-1"
    script = str(soup)
    assert script.count("resultEl.focus()") >= 3
