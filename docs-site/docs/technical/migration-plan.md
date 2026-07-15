---
title: Migration Plan
---

The docs platform split has four phases:

1. Foundation: add the external docs workspace and config-driven Flask redirects.
2. Content migration: move public guides and technical pages into Docusaurus collections.
3. In-app simplification: keep only curated contextual help inside Flask.
4. Renderer retirement: stop using Flask as the public markdown site renderer.

The canonical engineering plan for this work lives in:

- `docs/SPECS/V2_DOCS_PLATFORM_SPLIT.md`
