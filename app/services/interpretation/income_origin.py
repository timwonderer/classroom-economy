"""Income-origin provenance classifier (SPEC-ITR-001 §10.2).

The shared primitive underneath Q5. It assigns each inbound Ledger row to exactly
one of six economically-meaningful origin categories using a **deterministic
precedence order**, so the same inflow can never land in two categories and
"other / unclassified" is only ever reached *after* every canonical provenance
check has failed (§10.2 category 6).

Design constraints enforced here:

* **Source-domain precedence (INV-ITR-016).** Labor is corroborated against the
  authoritative ``PayrollEvent`` surface (a ``correlation_id`` in the labor set),
  not by trusting a Ledger row's ``feat_code`` to look payroll-ish.
* **Structural reversal detection first (INV-LED-003).** A row with
  ``original_transaction_id`` set is a reversal/refund regardless of what else it
  resembles, so it is checked before any economic-origin heuristic.
* **No ``Transaction.type`` (INV-ITR-015).** Classification keys only on
  mechanism, account type, ``feat_code``, ``correlation_id``, and the reversal
  linkage — never the free-text ledger ``type``.
* **"Other" is a lawful floor, not a chute.** It is the final fallback only; the
  precedence chain above it is exhaustive of the canonical provenance signals.

Weak-surface note (§10.4): interest accrual currently has no dedicated event
model and no canonical interest FEAT code, so :data:`INTEREST_ACCRUAL_FEAT_CODES`
is intentionally empty. Under today's provenance an interest inflow therefore
does NOT match category 2; a ``mechanism=system`` interest credit falls through
to category 4 (system-originated non-labor), and a ``mechanism=self`` interest
credit falls through to category 6 (other/unclassified). That is the honest,
documented outcome — not a defect — and the predicate is retained so category 2
lights up automatically once a dedicated interest FEAT exists.
"""

from __future__ import annotations

from typing import Iterable

# --- Category identifiers (SPEC-ITR-001 §10.2) -----------------------------
#
# Numeric prefixes make the six-category vector sort deterministically by the
# ``category`` label required by the ``category_fractions`` value shape (§15.9),
# while preserving the §10.2 category numbering.
CATEGORY_LABOR = "1_labor"
CATEGORY_INTEREST = "2_interest"
CATEGORY_TEACHER_ADMIN = "3_teacher_admin"
CATEGORY_SYSTEM_NON_LABOR = "4_system_non_labor"
CATEGORY_REVERSAL = "5_reversal"
CATEGORY_OTHER = "6_other"

# The full, ordered vocabulary. Every income-composition observation reports all
# six categories (a zero share is still a lawful, self-describing observation).
INCOME_ORIGIN_CATEGORIES: tuple[str, ...] = (
    CATEGORY_LABOR,
    CATEGORY_INTEREST,
    CATEGORY_TEACHER_ADMIN,
    CATEGORY_SYSTEM_NON_LABOR,
    CATEGORY_REVERSAL,
    CATEGORY_OTHER,
)

# Ledger mechanism string values (normalized by the read surface).
_MECHANISM_TEACHER = "teacher"
_MECHANISM_SYSTEM = "system"

# §10.2 category 3 — teacher/admin FEATs that inject credits directly.
TEACHER_ADMIN_FEAT_CODES: frozenset[str] = frozenset(
    {
        "FEAT-ADMN-001",           # Bulk administration / admin adjustment
        "FEAT-ADMIN-ADJUSTMENT",   # Named admin-adjustment FEAT (SPEC alias)
    }
)

# §10.2 category 2 — interest accrual FEATs. Empty today (see module docstring
# and §10.4): no canonical interest FEAT exists, so this category is dormant.
INTEREST_ACCRUAL_FEAT_CODES: frozenset[str] = frozenset()


def classify_income_origin(
    row,
    *,
    labor_correlation_ids: frozenset[str],
    manual_credit_correlation_ids: frozenset[str],
) -> str:
    """Return the single §10.2 origin category id for one inbound ledger ``row``.

    ``row`` is any object exposing ``original_transaction_id``, ``correlation_id``,
    ``mechanism`` (lowercase string), ``account_type``, and ``feat_code`` — e.g. a
    :class:`~app.services.ledger_service.InboundLedgerRow`. The precedence order
    below is exhaustive over the canonical provenance signals and is applied
    top-to-bottom; the first match wins.
    """
    # 1. Reversal / refund — structural, wins over any economic heuristic
    #    (INV-LED-003, §10.2 category 5).
    if row.original_transaction_id is not None:
        return CATEGORY_REVERSAL

    correlation_id = row.correlation_id
    mechanism = row.mechanism

    # 2. Labor-derived — corroborated by the authoritative PayrollEvent surface
    #    (INV-ITR-016, §10.2 category 1). Excludes manual_credit/reversal because
    #    the labor set only carries payroll_event_type='payroll' correlations.
    if correlation_id is not None and correlation_id in labor_correlation_ids:
        return CATEGORY_LABOR

    # 3. Teacher/admin-injected — payroll manual_credit corroboration OR a direct
    #    teacher-mechanism admin-adjustment FEAT (§10.2 category 3).
    if correlation_id is not None and correlation_id in manual_credit_correlation_ids:
        return CATEGORY_TEACHER_ADMIN
    if mechanism == _MECHANISM_TEACHER and row.feat_code in TEACHER_ADMIN_FEAT_CODES:
        return CATEGORY_TEACHER_ADMIN

    # 4. Interest / passive — savings + system mechanism + interest-accrual FEAT
    #    (§10.2 category 2). Dormant under current provenance (§10.4); retained so
    #    it activates automatically once a canonical interest FEAT exists.
    if (
        mechanism == _MECHANISM_SYSTEM
        and row.account_type == "savings"
        and row.feat_code in INTEREST_ACCRUAL_FEAT_CODES
    ):
        return CATEGORY_INTEREST

    # 5. System-originated non-labor — any remaining system-mechanism credit that
    #    is neither interest nor payroll (§10.2 category 4).
    if mechanism == _MECHANISM_SYSTEM:
        return CATEGORY_SYSTEM_NON_LABOR

    # 6. Other / unclassified — lawful floor, only after 1–5 fail (§10.2 category 6).
    return CATEGORY_OTHER


def aggregate_income_by_category(
    rows: Iterable,
    *,
    labor_correlation_ids: frozenset[str],
    manual_credit_correlation_ids: frozenset[str],
) -> dict[str, int]:
    """Sum inbound ``amount_cents`` per §10.2 origin category.

    Returns a dict keyed by every id in :data:`INCOME_ORIGIN_CATEGORIES` (each
    present, possibly zero) so the resulting composition is complete and
    self-describing regardless of which categories were observed.
    """
    totals: dict[str, int] = {category: 0 for category in INCOME_ORIGIN_CATEGORIES}
    for row in rows:
        category = classify_income_origin(
            row,
            labor_correlation_ids=labor_correlation_ids,
            manual_credit_correlation_ids=manual_credit_correlation_ids,
        )
        totals[category] += int(row.amount_cents or 0)
    return totals
