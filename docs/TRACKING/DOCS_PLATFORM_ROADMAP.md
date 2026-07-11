# Documentation Platform Roadmap

**Status:** Planned
**Created:** 2026-06-14
**Branch:** docs/cleanup-and-organization

---

## Context

The `codex/v2.0` branch is now the default branch. The v2 documentation reorganization (completed 2026-06-14) promoted all v2 canonical docs to top-level directories under `docs/` and archived v1 content to `docs/archive/`. This roadmap covers the remaining documentation work.

---

## Phase 1: Port v1 Docs to v2 Standard

**Goal:** Review archived v1 documentation and migrate still-relevant content into the v2 namespace system.

### Scope
- Review `docs/archive/v1-development/` for content that remains relevant to v2
- Review `docs/LOGS/AUDITS/` for entries that should be promoted or updated
- Migrate relevant content using v2 namespace prefixes (ARC, DOM, FEAT, SOP, SEC, LOG)
- Content that is purely historical stays in `docs/archive/` or `docs/LOGS/`

### Acceptance Criteria
- [ ] Every file in `docs/archive/v1-development/` has been triaged (keep in archive, promote, or delete)
- [ ] Promoted content follows the SOP-DOC-000 documentation standard
- [ ] No orphan references to archived content from active docs

---

## Phase 2: Upgrade v1 User Guides to v2

**Goal:** Rewrite user-facing documentation for the v2 architecture, UX, and terminology.

### Scope
- Review archived guides in `docs/archive/v1-user-guides/`
- Rewrite for v2:
  - **Teacher Manual** — updated for seat-based identity, class_id scoping, FEAT execution model
  - **Student Guide** — updated for v2 student portal UX
  - **Economy Guide** — aligned with DOM-ECON domain specs
  - **Sysadmin Manual** — updated for v2 admin capabilities
- Align terminology with v2 domain model (seat, class_id, join_code as alias, FEAT-driven mutations)

### Acceptance Criteria
- [ ] All four core guides rewritten for v2
- [ ] Terminology consistent with v2 domain specs (authority language only from the canonical identity model)
- [ ] Guides placed in canonical location (may be Docusaurus source, see Phase 3)

---

## Phase 3: Rebuild Documentation Sites

Two separate platforms, each serving a different audience and use case.

### A. Docusaurus Public Site

**Purpose:** External-facing documentation for users, developers, and educators.
**URL:** `classroomtokenhub.com/docs` or `docs.classroomtokenhub.com`

Four content areas:

1. **Main Documentation**
   - Project overview and getting started
   - Architecture and design decisions
   - Installation and self-hosting

2. **In-Depth Guide**
   - Detailed feature documentation for teachers and students
   - Economy design and configuration
   - Best practices for classroom economy management

3. **Feature Guide**
   - Per-feature reference pages (attendance, payroll, rent, store, hall pass, insurance, etc.)
   - Configuration options and examples
   - Screenshots and workflows

4. **Developer Blog**
   - Release notes and version history
   - Technical decision records
   - Migration guides and upgrade paths
   - v2 architecture deep dives

#### Acceptance Criteria
- [ ] Docusaurus site scaffolded and deployable
- [ ] All four content areas populated with initial content
- [ ] Deployed to production URL
- [ ] CI pipeline for docs builds

### B. In-App Custom Doc Site

**Purpose:** Context-sensitive, role-specific help served from within the Flask application.
**Route:** `/docs/` (existing route in `app/routes/docs.py`)

Features:

1. **Role-Specific Content**
   - Teacher help pages tailored to teacher workflows
   - Student help pages tailored to student workflows
   - Sysadmin help pages tailored to admin operations

2. **Context-Sensitive Help**
   - Contextual help for the page the user is currently viewing
   - Quick-reference tooltips and inline guidance

3. **Diagnostics Interface**
   - Troubleshooting guides organized by problem category
   - Based on content from `docs/archive/v1-user-guides/diagnostics/` (ported to v2)
   - Interactive diagnostic flows where applicable

#### Acceptance Criteria
- [ ] In-app docs route serves role-appropriate content
- [ ] Diagnostics guides ported from v1 and updated for v2 UX
- [ ] Context-sensitive help available on key pages
- [ ] Content loads without external dependencies (fully self-contained)

---

## Dependencies

- Phase 1 is independent and can start immediately
- Phase 2 depends on Phase 1 (need to know what v1 content is worth porting)
- Phase 3A (Docusaurus) can start in parallel with Phase 2
- Phase 3B (in-app docs) depends on Phase 2 completion (needs the rewritten guides)
