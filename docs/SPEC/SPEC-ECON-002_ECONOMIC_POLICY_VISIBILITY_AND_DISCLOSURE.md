# SPEC-ECON-002: Economic Policy Visibility and Disclosure

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| SPEC-ECON-002 | 2.0 | 2026-05-20 | none | Constitutional |

# I. Purpose

This specification defines constitutional visibility and disclosure requirements for economic policy state within Classroom Token Hub (CTH).

This specification establishes:
- future economic law disclosure requirements,
- future policy visibility requirements,
- student-facing economic transparency requirements,
- teacher-facing governance visibility requirements,
- operational-domain disclosure responsibilities.

Economic policy visibility is treated as constitutional economic legitimacy infrastructure rather than optional UI behavior.

---

# II. Scope

This specification governs:
- active policy visibility,
- future policy visibility,
- student-facing economic disclosure,
- teacher-facing economic disclosure,
- future pricing disclosure,
- future premium disclosure,
- activation intent disclosure,
- operational-domain policy visibility requirements.

This specification applies to:
- rent policy,
- insurance policy,
- banking policy,
- payroll policy,
- future economy-governed operational domains.

---

# III. Governing Authority

This specification is subordinate to:
- INV-CORE-000
- DOM-CLASS-001
- DOM-CLASS-002
- DOM-CLASS-003
- DOM-ITR-001
- INV-ARC-015

This specification derives its policy visibility authority from `DOM-CLASS-003`, which derives from `DOM-CLASS-002` and `DOM-CLASS-001`.

This specification is authoritative over:
- economic policy disclosure requirements,
- future economic law visibility,
- future economic impact visibility.

---

# IV. Constitutional Visibility Principles

## ECON-VIS-001 — Future Economic Law Must Be Visible

Pending economic policy versions are considered publicly announced future economic law.

Future economic state MUST NOT remain hidden from:
- affected students,
- teachers,
- operational domains.

Hidden future economic obligations are constitutionally prohibited.

---

## ECON-VIS-002 — Economic Systems Must Be Explainable

Students and teachers MUST be able to determine:
- current economic law,
- future economic law,
- effective activation intent,
- expected future obligations,
- future pricing impact.

Economic governance MUST remain operationally understandable.

---

## ECON-VIS-003 — Operational Domains Must Surface Relevant Future Policy

Operational domains consuming economic policy MUST expose relevant pending future economic state.

Examples:
- rent domain surfaces future rent,
- insurance domain surfaces future premiums,
- banking domain surfaces future APY.

Operational domains MUST NOT conceal pending policy changes relevant to affected users.

---

## ECON-VIS-004 — Visibility Must Be Contextual

Future economic state SHOULD appear through:
- relevant operational surfaces,
- policy detail pages,
- overview dashboards,
- student-facing obligation views.

Visibility MUST remain contextually discoverable.

---

# V. Teacher Visibility Requirements

Teachers MUST be able to view:
- current policy state,
- pending policy versions,
- activation intent,
- superseded policy changes,
- cancelled policy changes,
- future economic impact.

Teachers MUST be able to:
- cancel pending policy versions,
- apply pending policy versions immediately,
- navigate to affected operational domains.

---

# VI. Student Visibility Requirements

Affected students MUST be able to view:
- future recurring obligations,
- future premiums,
- future pricing changes,
- activation timing intent,
- future economic impact.

Students MUST NOT experience hidden future economic changes without prior visibility.

---

# VII. Pending Policy Disclosure Requirements

Pending policy versions MUST display:

| Field | Requirement |
|---|---|
| Current value | required |
| Future value | required |
| Activation intent | required |
| Affected domain | required |
| Policy status | required |

---

# VIII. Operational Domain Requirements

## 1. Rent Domain

Pending rent policy changes MUST appear:
- above rent overview surfaces,
- inside student rent obligation surfaces,
- inside teacher rent management surfaces.

Displayed information MUST include:
- current rent,
- future rent,
- activation timing intent.

Example:

```
Current Rent:          $1,000
Pending Next-Cycle Rent: $1,200  (Effective: next rent cycle)
```


---

## 2. Insurance Domain

Pending insurance policy changes MUST appear:
- beside active policy listings,
- inside student insurance policy detail pages,
- inside teacher insurance management surfaces.

Displayed information MUST include:
- current premium,
- future premium,
- activation timing intent.

Example:

```
Current Premium:          $150
Pending Renewal Premium:  $180  (Effective: next renewal boundary)
```


---

## 3. Banking Domain

Pending banking policy changes MUST appear:
- within savings/APY informational surfaces,
- within teacher banking configuration surfaces.

Displayed information MUST include:
- current APY,
- future APY,
- activation timing intent.

---

# IX. Policy State Visibility

Teachers MUST be able to distinguish:
- pending policy versions,
- applied policy versions,
- superseded policy changes,
- cancelled policy changes,
- failed policy changes.

Superseded and cancelled policy changes MUST remain historically visible.

---

# X. Disclosure Constraints

The system SHALL NOT:
- conceal pending economic obligations,
- silently replace future policy,
- hide superseded economic changes,
- present future economic state ambiguously,
- expose operational timing internals beyond constitutional activation intent.

---

# XI. Relationship to DOM-ITR

DOM-ITR governs:
- interpretive presentation,
- readability,
- explanation systems.

This specification governs:
- constitutional disclosure obligations,
- required future-law visibility,
- mandatory economic transparency.

---

# XII. Relationship to FEAT Layer

FEAT layer:
- orchestrates execution,
- coordinates activation,
- manages policy application operations.

This specification governs:
- what MUST remain visible,
- what disclosures are constitutionally required.

---

# XIII. Relationship to Operational Domains

Operational domains:
- consume active policy,
- surface pending future policy,
- provide contextual disclosure surfaces.

Operational domains MUST NOT:
- conceal relevant pending policy,
- independently suppress future-law visibility.

---

# XIV. Architectural Outcome

This specification establishes:
- visible future economic law,
- transparent economic governance,
- explainable economic evolution,
- student-visible future obligations,
- teacher-visible governance state,
- contextual operational disclosure.

Economic policy therefore behaves as publicly visible constitutional law rather than hidden backend configuration state.

