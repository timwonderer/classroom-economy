# GitHub Pages Transition Site

This directory is the deployable GitHub Pages source for the Classroom Token Hub v2 transition period.

It intentionally publishes a narrow static surface:

- `index.html` — root entry point that redirects to the transition page.
- `v2transition.html` — the v1 end-of-service / v2 transition page.
- `learnmore.html` — the supporting learn-more page.

The pages must not link back to app-server routes; the production app server is expected to redirect requests back to GitHub Pages during the transition period.
