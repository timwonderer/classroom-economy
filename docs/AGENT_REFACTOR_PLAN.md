# Classroom Token Hub Refactor Plan for Agents

**Purpose:** Provide AI agents with a compatibility-safe roadmap to modularize the existing `app.py` monolith. This plan is intended for implementation in stages to reduce risk, maintain backward compatibility, and improve maintainability.

## Intentions
- Preserve the current WSGI entrypoint (`app:app`) and external imports while progressively restructuring internals.
- Reduce `app.py` complexity by extracting cohesive modules (extensions, models, auth utilities, routes, and helpers).
- Align new modules with clear responsibilities to simplify testing, code reviews, and future feature work.
- Keep configuration, security, and user-facing behavior identical during the refactor.

## Proposed Structure
- `app/__init__.py`: Application factory (`create_app`) handling config load, extension init, blueprint registration, logging, CSRF, and Jinja filters. Root `app.py` should import this and expose `app = create_app()`.
- `app/extensions.py`: Shared extension instances (SQLAlchemy `db`, Migrate, CSRF, login manager if introduced later). Centralizes initialization to avoid circular imports.
- `app/models.py`: All SQLAlchemy models currently in `app.py`, preserving table names, relationships, and custom types.
- `app/auth.py`: Session helpers and decorators (`login_required`, `admin_required`, `system_admin_required`), maintaining existing flash/redirect behavior and timeouts.
- `app/routes/`: Blueprints separated by audience (`student.py`, `admin.py`, `system_admin.py`) with identical URLs and endpoint names. Shared business logic can move into `app/services/` as needed.
- `app/utils/`: Reusable helpers (PII encryption type, URL safety checks, datetime formatting, Jinja filters, logging helpers) extracted from `app.py`.
- Transitional exports: Root `app.py` should re-export commonly imported symbols (e.g., `db`, `Student`) until callers are updated.

## Staged Execution Plan
1. **Bootstrap core package**: Add `app/__init__.py` with `create_app()` and `app/extensions.py`. Wire `app.py` to use the factory while preserving `app = create_app()`.
2. **Move models**: Extract all models into `app/models.py` using shared `db`; update Alembic import path if needed. Temporarily re-export models from `app.py`.
3. **Extract auth utilities**: Relocate session helpers and decorators to `app/auth.py`; update route imports; re-export in `app.py` for compatibility.
4. **Blueprint routes**: Split routes into audience-specific blueprints under `app/routes/` and register them in `create_app()`. Keep URLs, endpoint names, and templates unchanged.
5. **Centralize utilities**: Move helpers into `app/utils/` modules and register filters/helpers through `create_app()`.
6. **Cleanup**: Remove transitional re-exports after dependent modules are updated and tests confirm parity.

## Compatibility Safeguards
- Maintain `app = create_app()` in root `app.py` for Gunicorn/Flask CLI.
- Keep environment variable handling, logging format, CSRF settings, session configuration, and template filters identical.
- Avoid schema changes; model moves should not alter metadata or defaults.
- Preserve route rules, endpoint names, flash messages, and redirects.
- Document any temporary compatibility shims and remove them only after dependent code migrates.

## Expected Outcomes
- **Maintainability:** Smaller, focused modules with clearer responsibilities and easier onboarding for new contributors.
- **Testability:** Reduced cross-module coupling enables targeted unit tests for auth, services, and utilities.
- **Safety:** Staged rollout with transitional exports minimizes breakage and eases code review.
- **Scalability:** Blueprinted routes and centralized extensions simplify future additions (multi-tenancy, new services).

## Notes for Agents
- Update `TODO.md` after each stage to record progress and remaining steps.
- Validate behavior parity after each stage (URLs, templates, session handling, and logging).
- Keep documentation in sync (e.g., `README.md`, `MIGRATION_GUIDE.md`) when entrypoints or initialization flows change.
