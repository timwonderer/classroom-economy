# MAP-UI-002: Request Context and View Model Pipeline

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| MAP-UI-002 | 0.1 | 2026-07-20 | N/A | Informative |

---

## I. Purpose

This map defines the intended request-to-template pipeline for CTH v2 page rendering.

It separates authority, temporal evaluation, display metadata, and page-specific view data so routes and templates stop rediscovering the same decisions on every page.

---

## II. Scope

This map applies to:

- authenticated Flask page routes
- template context assembly
- shared template metadata
- page-specific view models
- future route decomposition and template rewiring work

This map does not create runtime authority. Authority remains governed by `INV`, `DOM`, and `FEAT` documents.

---

## III. Authority and Inputs

Authority order:

1. `INV-CORE-000_CORE_INVARIANTS.md`
2. `DOM-IDEN-006_CANONICAL_CONTEXT_RESOLUTION.md`
3. `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
4. `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
5. `SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md`
6. `MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`

---

## IV. The Four Questions

Every page-load pipeline must keep these questions separate.

| Layer | Question | Responsibility | Must Not Answer |
|---|---|---|---|
| Canonical Context | What makes you think you can do this? | Runtime authority: `user_id`, `seat_id`, `class_id`, `actor_role` | Display names, page data, time formatting |
| Temporal Context | What time do you think it is? | Temporal authority: UTC now, class timezone, class-local time, class day boundaries | Actor authority, display names, business state |
| Identity Display Context | How are you presented in here? | Shared display metadata derived from canonical identity and class records | Authorization, business logic, page-specific data |
| Page View Model | Which information should you see on this page? | Page-specific data assembled from lawful domain reads and projections | Runtime authority, independent time interpretation, persistence writes |

If a layer starts answering another layer's question, treat it as a design smell.

---

## V. Pipeline

The intended page-load pipeline is:

1. Flask receives request.
2. Auth boundary resolves `CanonicalContext`.
3. Class-scoped routes resolve temporal context for the request or operation.
4. Shared identity display context is assembled from canonical identity/class metadata.
5. Route invokes domain read services or FEAT command paths as required.
6. Page-specific view model is built from lawful reads/projections.
7. Template receives shared context plus exactly one page view model.
8. Browser renders timestamps using the class display timezone supplied by the temporal context.

Conceptual shape:

```text
Request
  -> CanonicalContext
  -> TemporalContext
  -> IdentityDisplayContext
  -> Domain reads / FEAT commands
  -> PageViewModel
  -> Template
```

---

## VI. Canonical Context

Canonical Context answers only:

> What makes you think you can do this?

Canonical Context is the authority object defined by `DOM-IDEN-006`.

It carries:

- `user_id`
- `seat_id`
- `class_id`
- `actor_role`

Rules:

- It is resolved once at the authenticated request boundary.
- It is not reconstructed downstream.
- It does not carry display metadata.
- It does not carry class labels, names, sections, or template navigation state.
- It does not carry temporal interpretation beyond the `class_id` needed by the temporal resolver.

---

## VII. Temporal Context

Temporal Context answers only:

> What time do you think it is?

For class-level evaluations, the answer is class-scoped, not browser-scoped, server-scoped, or user-local.

Expected fields:

- `evaluation_type`: `SLE` or `CLE`
- `reference_time_utc`
- `class_timezone`
- `class_time`
- `class_date`
- `class_day_start_utc`
- `class_day_end_utc`
- `display_timezone`

Rules:

- UTC remains the storage truth.
- Class timezone is the interpretation authority for CLEs.
- Templates and browser JavaScript may render with the supplied display timezone, but must not invent temporal authority.
- Page view models must not perform their own date boundary derivation.
- Routes should pass a single temporal context or explicit display-time fields rather than each page selecting its own timezone convention.

---

## VIII. Identity Display Context

Identity Display Context answers only:

> How are you presented in here?

It is presentation metadata derived from canonical identity and class records. It is not authority.

Expected fields may include:

- `actor_role`
- `actor_display_name`
- `seat_public_id`
- `class_id`
- `class_display_name`
- `section`
- `display_timezone`
- `navigation_scope_label`

Rules:

- It must be derived from canonical `User`, `Seat`, `IdentityProfile`, and `ClassEconomy` records.
- It must not expose legacy `Student`, `Admin`, `TeacherBlock`, `student_id`, `teacher_id`, or `join_code` authority assumptions.
- It may expose display aliases such as class labels and sections.
- It must not decide whether an actor may perform an operation.
- It should be reusable across pages so templates stop reading identity/class metadata ad hoc.

---

## IX. Page View Model

The Page View Model answers only:

> Which information should you see on this page?

A view model is page-specific. It is the template contract for one rendered surface.

Examples:

| Page | View Model Responsibility |
|---|---|
| Student dashboard | Current productivity state, projected pay, balances, recent activity, class announcements |
| Student payroll | Payroll history, attendance events, projected pay, payroll statistics |
| Admin payroll | Payroll estimates, payroll run history, manual credit options, settings summaries |
| Admin hall pass | Pending requests, approved queue, out-of-class state, verification link |

Rules:

- The view model must be built from lawful domain reads and projections.
- It must not write state.
- It must not query persistence directly from Jinja.
- It must hide persistence shape from templates.
- It must use canonical identifiers and display-safe metadata.
- It should be stable even if the underlying domain tables change.

---

## X. Template Contract

Templates should receive:

- `context`: shared request/presentation context, or separate `identity_display` and `temporal` objects
- `view`: the page-specific view model
- narrowly scoped helpers already approved as Jinja globals

Templates should not receive raw persistence objects when a display view model is available.

Preferred pattern:

```jinja
{{ identity_display.actor_display_name }}
{{ identity_display.class_display_name }}
{{ temporal.display_timezone }}
{{ view.current_status }}
{{ view.projected_pay }}
```

Avoided pattern:

```jinja
{{ student.full_name }}
{{ student.hall_passes }}
{{ student.tap_events }}
{{ admin.get_display_name() }}
{{ transaction.teacher_id }}
```

---

## XI. Abstraction Justification Test

This pipeline exists for maintainability, not because abstraction is inherently valuable.

Every abstraction must eliminate repeated business decisions, not merely repeated code.

| Layer | Repeated Decision Removed |
|---|---|
| Canonical Context | Who may act, in which class, as which seat |
| Temporal Context | Which time authority and boundary apply |
| Identity Display Context | How actor/class metadata should be presented |
| Page View Model | What page-specific projection the template receives |

Before adding a new shared context or view layer, ask:

> If this abstraction were removed tomorrow, which repeated decision would return?

If the answer is only "some code would be shorter," the abstraction is not justified.

If the answer is "routes would independently decide authority, time, display identity, or page data shape," the abstraction is justified.

---

## XII. Implementation Guidance

Recommended implementation order:

1. Keep `CanonicalContext` strict and authority-only.
2. Implement or finish the request-level temporal context described by `INV-ARC-015`.
3. Introduce a small immutable identity display context for shared template metadata.
4. Build page-specific view model builders only for pages being actively rewired.
5. Migrate templates gradually from raw objects to `identity_display`, `temporal`, and `view`.
6. Add render tests for each migrated page.

Do not introduce global view-model abstractions for pages not yet being rewired.

---

## XIII. Open Questions

1. Should the shared template object be named `identity_display`, `presentation`, or `page_context`?
2. Should browser timestamp rendering be powered by a single shared data attribute contract or by server-rendered formatted strings?
3. Should view model builders live under `app/view_models/` or remain domain-local until route decomposition begins?

---

## XIV. Amendment

Revisions to this map must:

1. update the version number
2. preserve separation between authority, time, display metadata, and page-specific view data
3. remain consistent with `DOM-IDEN-006` and `INV-ARC-015`
