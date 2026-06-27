# GitHub Pages Setup Instructions

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-007| 1.1 | 2026-03-08 | 1.0 |Normative|

This document explains how to configure and maintain the GitHub Pages site for Classroom Token Hub.

---

## I. Purpose

TBD
## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Quick Setup

1. **Enable GitHub Pages**
   - Repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main`
   - Folder: `/docs`
   - Save

2. **Wait for deployment**
   - GitHub will build and deploy automatically
   - Available at: `https://[username].github.io/[repository-name]/`

---

## VI. Landing Pages

GitHub Pages serves static HTML:

- `docs/index.html` (sign-in hub)
- `docs/about.html` (marketing and feature overview)
- `docs/style.css` (shared styles)

Markdown documentation is **not** served publicly.

---

## VII. Customizing Content

### Update Version Banner

In `about.html`, update the release banner text to match the latest release.

### Update Features and Screenshots

- Add new screenshots to `docs/`
- Update the screenshots section in `about.html` to reference the new assets

### Update Links

Check all sign-in and docs links in both `index.html` and `about.html`:

- Student: `https://app.classroomtokenhub.com/student/login`
- Teacher: `https://app.classroomtokenhub.com/admin/login`
- System Admin: `https://app.classroomtokenhub.com/sysadmin/login`
- Docs: `https://app.classroomtokenhub.com/docs`

---

## VIII. Local Preview

```bash
cd docs
python3 -m http.server 8000
```

Visit: `http://localhost:8000`

---

## IX. Troubleshooting

### Site not updating
- Clear browser cache
- Confirm Pages settings point to `/docs` on `main`
- Wait a few minutes for GitHub to rebuild

### Images not loading
- Verify file names and case sensitivity
- Ensure paths are relative to `index.html` or `about.html`

---

**Last Updated:** 2026-02-09
## X. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
