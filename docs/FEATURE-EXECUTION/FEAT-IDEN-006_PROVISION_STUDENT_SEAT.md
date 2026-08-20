# FEAT-IDEN-006 — Provision Student Seat in Existing Class

## Contract

Student roster upload/paste-grid provisioning is an IDENTITY operation. It
creates an unclaimed student `Seat` and its `IdentityProfile` inside an
already-created class. Class creation is a separate CLASS operation.

The FEAT requires canonical teacher context scoped to the existing class and
explicit `correlation_id` and `idempotency_key` metadata. It validates teacher
ownership and class scope before the atomic seat/profile mutation.

## Boundary

Routes may collect roster input and resolve the existing `class_id`, but they
must not create seats or profiles inline. `FEAT-CLASS-002` owns class-boundary
modification; `FEAT-IDEN-006` owns identity seat provisioning.

Authority: DOM-IDEN-007, DOM-CLASS-001, SOP-DEV-002.
