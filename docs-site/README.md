# Docs Site Workspace

This directory hosts the docs site for Classroom Token Hub.

## Why It Exists

The Flask app still owns contextual in-product help, but this Docusaurus workspace is the place for the current student, teacher, and technical guides.

This is not a public site. The intended usage is local development against a dev server. Only the routes listed in `route-map.json` are intentionally handed off from Flask.

## Local Development

Requirements:

- Node.js 20 or newer
- npm or another compatible package manager

Commands:

```bash
cd docs-site
npm install
npm run start
```

## Routing Assumption

The Docusaurus docs plugin is mounted at the site root, but Flask only redirects the subset of routes listed in `route-map.json`.

That lets the migration move incrementally instead of breaking unmigrated docs.

Mapped requests can move from:

```text
/docs/<path>
```

to:

```text
https://docs.example.com/<mapped-path>
```
