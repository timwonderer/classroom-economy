# FEAT-DES-001: Unified Design System Reference

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|FEAT-DES-001| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose

This document provides a unified design system reference for the Classroom Token Hub.

## II. Scope

All CSS tokens, HTML component structures, layout patterns, and visual semantics across all user roles. Source of Truth: `static/css/tokens.css`.

## III. Authority Level

Normative (FEAT Tier). Subordinate to INV-CORE-000.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Philosophy

Classroom Token Hub uses a **semantic, role-based token system** to maintain consistency across three distinct user roles (Teacher, Student, Sysadmin) while sharing a single codebase.

### 1. Core Principles

1.  **Context-Aware Roles** — The same HTML/CSS renders differently based on the user's role:
    -   **Teacher (Advisor Green)**: Professional, authoritative, warm (Teal/Gold).
    -   **Student (Steward Blue)**: Trustworthy, calm, focused (Slate Blue/Bronze).
    -   **System Admin (Guardian Gray)**: Neutral, technical, high-contrast (Gray/Gold).

2.  **Semantic Over Hardcoded** — **NEVER** use hex codes in templates.
    -   ❌ `background-color: #1a4d47`
    -   ✅ `background-color: var(--primary)`

3.  **Minimal & Flat** — The design relies on spacing, typography, and subtle borders rather than heavy shadows or gradients.
    -   **Radius**: Small (4px) for data density, Medium (6px) for interactivity.
    -   **Shadows**: Subtle lift only for overlays/modals.

## VI. Token Architecture

The system is defined in `static/css/tokens.css` and is split into two layers:

### 1. Base Layer (Shared)
Variables available globally, regardless of role.

| Category | Tokens | Usage |
|---|---|---|
| **Typography** | `--font-family` | Inter (default system backup) |
| **Radius** | `--radius-xs` (2px)<br>`--radius-sm` (4px)<br>`--radius-md` (6px)<br>`--radius-lg` (8px)<br>`--radius-pill` (999px) | `sm` for cards/inputs<br>`md` for buttons<br>`lg` for modals |
| **Shadows** | `--shadow-sm`<br>`--shadow-md`<br>`--shadow-lg` | Depth and hierarchy |
| **Neutrals** | `--neutral-50` to `--neutral-900` | Warm-tinted grayscale.<br>`--neutral-100` is the default page background. |
| **Surfaces** | `--background`<br>`--surface`<br>`--border-color` | Role-agnostic structural colors. |

### 2. Theme Layer (Role-Specific)
These tokens change values depending on the active body class (`student-shell`, `sysadmin-shell`, or default teacher).

| Token | Description | Teacher Value | Student Value | Sysadmin Value |
|---|---|---|---|---|
| `--primary` | Main brand color | Teal (`#1a4d47`) | Slate Blue (`#2F4F7F`) | Dark Gray (`#303030`) |
| `--primary-hover` | Darker interaction state | Dark Teal | Dark Slate | Black |
| `--primary-subtle` | Very light tint for backgrounds | Pale Teal | Pale Blue | Pale Gray |
| `--secondary` | Accent color | Gold (`#d3af37`) | Bronze (`#ac8255`) | Gold (`#D4A857`) |
| `--secondary-text` | Text color on secondary bg | Dark (`#171717`) | White (`#ffffff`) | Dark (`#171717`) |

## VII. Semantic Usage Rules

### 1. Backgrounds
Use `bg-*-subtle` utilities for containers, alerts, and sections. **DO NOT use opacity hacks.**

| Use Case | Correct Class | Incorrect (Legacy) |
|---|---|---|
| **Page Background** | `var(--background)` | `#f5f5f3` or `bg-light` |
| **Card Header** | `bg-surface` | `bg-white` |
| **Success Alert** | `bg-success-subtle` | `bg-success bg-opacity-10` |
| **Info Box** | `bg-info-subtle` | `bg-info bg-opacity-10` |
| **Primary Container** | `bg-primary` | `style="background-color: {{ theme_color }}"` |

### 2. Text
Use Bootstrap semantic classes, which are now overridden to use our tokens.

| Use Case | Class |
|---|---|
| **Primary Actions** | `text-primary` (Adapts to role) |
| **Standard Text** | `text-body` or `var(--text-primary)` |
| **Muted/Meta** | `text-muted` or `var(--text-secondary)` |
| **Deep Success** | `text-success` (Darker, accessible green) |

### 3. Buttons
Use standard Bootstrap buttons. We have overridden them to match the active theme.

```html
<!-- Primary Action (Teal/Blue/Gray) -->
<button class="btn btn-primary">Save</button>

<!-- Secondary/Cancel (Gray) -->
<button class="btn btn-secondary">Cancel</button>

<!-- Destructive (Red) -->
<button class="btn btn-danger">Delete</button>
```

### 4. Borders
Use `border` utility (uses `--border-color` / `--neutral-200`).
For colored borders, use semantic utilities: `border-primary`, `border-danger`.

## VIII. Anti-Patterns (Examples of What NOT to Do)

### 1. Hardcoded Colors
```html
<!-- BAD: Hardcoded hex -->
<div style="background-color: #1a4d47; color: white;">...</div>

<!-- GOOD: Semantic tokens -->
<div class="bg-primary text-white">...</div>
```

### 2. Bootstrap Opacity Hacks
```html
<!-- BAD: Relies on Bootstrap's default opacity which is inconsistent across themes -->
<div class="bg-success bg-opacity-25">...</div>

<!-- GOOD: Use the calculated subtle token -->
<div class="bg-success-subtle">...</div>
```

### 3. Role-Specific Logic in Templates
```html
<!-- BAD: Changing class based on role manually -->
{% if role == 'student' %}
  <div class="bg-blue-800">...</div>
{% else %}
  <div class="bg-teal-900">...</div>
{% endif %}

<!-- GOOD: Let the CSS tokens handle it -->
<div class="bg-primary">...</div>
```

## IX. Component Guide

### 1. Cards
Always use `card` with `shadow-sm` and `border-0`.
```html
<div class="card border-0 shadow-sm mb-4">
    <div class="card-header bg-white py-3">
        <h5 class="mb-0 fw-bold text-primary">Card Title</h5>
    </div>
    <div class="card-body">
        Content...
    </div>
</div>
```

### 2. Tables
Use `table` with `align-middle`.
```html
<table class="table align-middle">
    <thead class="text-secondary text-uppercase fs-7">
        <tr>...</tr>
    </thead>
    <tbody>...</tbody>
</table>
```

### 3. Icons
ALWAYS use **Material Symbols Outlined**.
```html
<!-- GOOD -->
<span class="material-symbols-outlined">settings</span>

<!-- BAD -->
<i class="bi bi-gear"></i>
<i class="fa fa-cog"></i>
```

## X. Adding New Tokens
If you need a new constant value (e.g., a specific chart color), add it to `tokens.css`.

1.  Is it shared? Add to `:root` (Base).
2.  Is it theme-dependent? Add to the theme blocks (`.student-shell`, etc.).
3.  **Naming Convention**: `--{category}-{property}-{modifier}` (e.g., `--chart-primary-fill`).

## XI. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
