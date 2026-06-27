# V2 Docs Platform Split

Status: partially complete

## Goal

Split the repository's documentation concerns into two separate delivery paths:

- an external static docs/blog site powered by Docusaurus
- a thin in-app help layer inside Flask for authenticated contextual guidance

This removes the need for Flask to act as the long-term public markdown site renderer while preserving session-aware help entry points inside the product.

## Problem Statement

The current `/docs` subsystem mixes two jobs:

- public or developer-facing documentation publishing
- authenticated, role-aware, in-app product help

That coupling has created avoidable fragility:

- markdown rendering behavior is implemented and patched in application code
- docs navigation is hardcoded in templates instead of derived from content structure
- search scans the docs tree at request time
- help entry points and public docs publishing share the same route layer

## Target Architecture

### External Docs Site

- Lives in `docs-site/`
- Built with Docusaurus
- Owns public docs, technical reference publishing, and blog/release storytelling
- Deploys independently as a static site

### Flask In-App Help

- Keeps contextual "Guide" and "Full Guide" entry points from authenticated screens
- Can continue rendering local markdown during migration
- Must be able to hand public unauthenticated traffic off to the external docs site
- Should eventually shrink to a curated help router, not a general-purpose docs engine

## Phase Plan

### Phase 1: Foundation

- Add `docs-site/` Docusaurus workspace
- Add `EXTERNAL_DOCS_BASE_URL` support in Flask
- Centralize docs URL generation so templates do not hardcode `/docs/...`
- Redirect unauthenticated `/docs` traffic to the external docs site when configured

### Phase 2: Information Architecture Migration

- Define external route taxonomy that mirrors the current docs paths where practical
- Move public-facing user guides and technical docs into Docusaurus collections
- Introduce blog/release posts sourced from current changelog or release logs

### Phase 3: In-App Help Simplification

- Replace broad markdown browsing inside Flask with curated help landing pages
- Limit in-app help to task-oriented content actually needed in product flows
- Remove Flask-owned search for public docs

### Phase 4: Renderer Retirement

- Deprecate the Flask markdown site renderer for public traffic
- Keep only the minimum compatibility surface necessary for authenticated help

## Routing Contract

During migration:

- authenticated teacher, student, and sysadmin sessions continue using in-app docs links by default
- unauthenticated `/docs` requests redirect to `EXTERNAL_DOCS_BASE_URL` only for explicitly migrated routes
- contextual help links must be generated through one shared helper, not raw `url_for('docs.view_doc', ...)`
- the migrated public-route subset is defined in `docs-site/route-map.json` and shared by Flask plus the Docusaurus site
- the Docusaurus site is currently a local preview surface only; v2 docs remain non-canonical until the rework is complete

This contract lets the external site ship incrementally without breaking product help affordances. The Flask-side `EXTERNAL_DOCS_BASE_URL` and shared route-map plumbing exist, but the external docs split is still not fully complete.

## External Site Requirements

- Preserve as many existing relative docs paths as practical to reduce redirect churn
- Support docs plus blog from the same site
- Keep route ownership explicit and versionable in repo
- Be independently deployable from Flask

## Open Migration Decisions

- Which subsets of `docs/` remain in Flask permanently, if any
- Whether release notes live as Docusaurus blog posts, docs pages, or both
- Whether internal-only engineering docs should stay private or partially publish externally
- How much of the current docs path taxonomy should be preserved versus rationalized
