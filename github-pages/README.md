# GitHub Pages Transition Site

This directory is the deployable GitHub Pages source for the Classroom Token Hub v2 transition period.

It intentionally publishes a narrow static surface:

- `index.html` — root entry point that redirects to the landing page.
- `landing.html` — the v2 landing page with sign-in entry points.
- `learnmore.html` — the supporting learn-more page.

The pages must not link back to app-server routes; the production app server is expected to redirect requests back to GitHub Pages during the transition period.
