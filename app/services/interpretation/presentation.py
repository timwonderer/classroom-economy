"""ITR-owned presentation objects for a materialized cycle (DOM-ITR-001, INV-ARC-022).

This is the domain-owned *presentation shape* of a completed cycle's interpretation:
it transforms the canonical, frozen ``observations_json`` of an
``interpretation_cycle_record`` into presentation-ready objects a page view model
and template can consume **without knowing anything about JSONB storage or
candidate internals** (no ``candidate_id == "Q3-C2"`` or ``value.kind ==
"coverage_by_type"`` logic ever reaches a template).

Design goal (teacher legibility): a teacher should be able to *interpret* the page,
not re-analyze it. Each section says both what it shows and how to make sense of
it; each number is phrased in plain, contextual language; and where a category
carries several independent signals, each one is named and explained.

Two hard rules:

* **Never recompute.** These builders consume the stored record only. Reviewing
  cycle N shows the interpretation materialized when cycle N closed — a durable
  historical record, not a cache (DOM-ITR-001 §VII/§IX). There is no import of the
  compute layer here.
* **Guiding questions are non-prescriptive presentation content, not history.**
  They are attached here, never frozen into the immutable record. See
  :data:`GUIDING_QUESTION_CONTRACT` and :func:`validate_guiding_question`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

# --------------------------------------------------------------------------- #
# Guiding-question contract (ITR presentation doctrine)                        #
# --------------------------------------------------------------------------- #

GUIDING_QUESTION_CONTRACT = """
A guiding question may invite contextualization, comparison, investigation, and
reflection. It MUST NOT presume causation, characterize an observation as
desirable or undesirable, imply a preferred conclusion, or encode a recommended
intervention. Interpretation describes what was observed; it never prescribes.
""".strip()

# Stems that betray a prescription, a value judgement, or a presumed conclusion —
# the ways a retired prescriptive action-recommendation would try to sneak back
# in. Guiding questions are validated against these so the non-prescriptive
# contract is enforceable, not merely aspirational.
_PRESCRIPTIVE_STEMS: tuple[str, ...] = (
    "should", "recommend", "you ought", "ought to", "need to", "try to",
    "increase", "decrease", "reduce", "raise ", "lower ", "improve", "fix",
    "better", "worse", "too high", "too low", "too few", "too many",
    "problem", "concerning", "healthy", "unhealthy", "good ", "bad ",
    "must ", "make sure", "ensure that", "consider increasing", "consider reducing",
)


def validate_guiding_question(question: str) -> None:
    """Raise ``ValueError`` if ``question`` violates the non-prescriptive contract.

    A lawful guiding question is a genuine question (ends with ``?``) free of
    prescriptive / evaluative stems (:data:`GUIDING_QUESTION_CONTRACT`).
    """
    text = (question or "").strip()
    if not text.endswith("?"):
        raise ValueError(f"guiding question must be a question: {question!r}")
    lowered = text.lower()
    for stem in _PRESCRIPTIVE_STEMS:
        if stem in lowered:
            raise ValueError(
                f"guiding question is prescriptive/evaluative ('{stem.strip()}'): {question!r}"
            )


# --------------------------------------------------------------------------- #
# Presentation dataclasses                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InterpretationCycleSummary:
    """History-row projection of a completed cycle (no ORM, no observations)."""

    payroll_cycle_id: str
    cycle_started_at: datetime
    cycle_completed_at: datetime
    computed_at: datetime


@dataclass(frozen=True)
class ObservationValue:
    """Presentation-ready value: a plain primary ``display`` plus supporting lines."""

    kind: str
    display: str
    supporting: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservationPresentation:
    """One candidate rendered for a teacher — plain labels, no candidate internals."""

    candidate_id: str
    title: str
    summary: str
    applicability: str  # "computed" | "not_applicable"
    value: ObservationValue | None
    supporting_context: tuple[str, ...] = ()
    not_applicable_reason: str | None = None
    guiding_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterpretationSection:
    """A themed group of observations: what it shows, how to read it, and prompts."""

    key: str
    title: str
    summary: str
    how_to_read: str
    observations: tuple[ObservationPresentation, ...]
    guiding_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterpretationCycleView:
    """The full presentation of one completed cycle."""

    cycle: InterpretationCycleSummary
    sections: tuple[InterpretationSection, ...]


# --------------------------------------------------------------------------- #
# Plain-language label maps                                                     #
# --------------------------------------------------------------------------- #

# Maps the deterministic ids used in the frozen payload to teacher-facing words.
_FRIENDLY_LABELS: dict[str, str] = {
    # Obligation outcomes (Q3-C1 categories).
    "satisfied_payment_only": "paid in full",
    "satisfied_waived": "waived",
    "satisfied_mixed": "part paid, part waived",
    "unsatisfied": "unpaid",
    # Income origins (Q5-C1 categories).
    "labor": "attendance-based work",
    "interest": "interest",
    "teacher_admin": "teacher awards & adjustments",
    "system_non_labor": "other system credits",
    "reversal": "refunds & reversals",
    "other": "other sources",
    # Obligation event kinds (Q3-C3 label suffixes).
    "assessment": "charged",
    "payment": "payments",
    "waived": "waivers",
    # Teacher-support counts (Q9 signal).
    "waived_events": "waivers granted",
    "teacher_inflows": "teacher credits",
}


def _friendly(label: str) -> str:
    """Translate a payload id (possibly ``sort_prefix``/``type:kind``) to plain text."""
    text = label
    if "_" in text and text.split("_", 1)[0].isdigit():
        text = text.split("_", 1)[1]
    if ":" in text:
        left, right = text.split(":", 1)
        right_friendly = _FRIENDLY_LABELS.get(right, right.replace("_", " "))
        return f"{left.replace('_', ' ').title()} — {right_friendly}"
    return _FRIENDLY_LABELS.get(text, text.replace("_", " "))


# --------------------------------------------------------------------------- #
# Number formatting                                                            #
# --------------------------------------------------------------------------- #


def _money(decimal_str: str) -> str:
    """A stored 2-dp decimal string rendered as classroom money."""
    return f"${Decimal(decimal_str).quantize(Decimal('0.01'))}"


def _count(decimal_str: str) -> str:
    """A stored decimal rendered as a count — whole numbers lose the ``.00`` tail."""
    dec = Decimal(decimal_str)
    if dec == dec.to_integral_value():
        return str(int(dec))
    return f"{dec.normalize()}"


def _pct(decimal_str: str) -> str:
    return f"{(Decimal(decimal_str) * 100).quantize(Decimal('0.01'))}%"


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    return singular if n == 1 else (plural or singular + "s")


# --------------------------------------------------------------------------- #
# Catalog: candidate + section metadata and curated guiding questions          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _CandidateMeta:
    section: str
    title: str
    summary: str
    unit: str = ""   # "money" | "count" — how the candidate's numbers should read
    noun: str = ""   # e.g. "attendance records" for a count distribution
    guiding_questions: tuple[str, ...] = ()


# Section order + copy. Each carries a "how to read this" so a teacher can
# interpret without re-analyzing.
_SECTIONS: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("participation", "How students participated",
     "Attendance recorded during this completed cycle.",
     "Attendance is what earns pay, so this is the foundation of the whole economy. "
     "Read it as how many of your students were economically active this cycle. A "
     "student with no attendance simply wasn't active — it isn't a judgment about them.",
     ("What might account for the level of participation observed this cycle?",)),
    ("activity", "How students used the economy",
     "Student-initiated activity recorded during this completed cycle.",
     "This is about engagement, not wealth — how much students did with their money "
     "once they had it (spending, transfers, purchases they started). A quiet cycle "
     "looks low and a busy one looks high; it doesn't say whether students are doing "
     "'well.'",
     ("What context might inform how you read the amount of activity this cycle?",)),
    ("obligations", "What happened with obligations",
     "Obligations recorded during this completed cycle.",
     "Obligations are things students owed, like rent. Read this as how those debts "
     "were settled — paid by the student, waived by you, or left unpaid at the end — "
     "and how much money each outcome accounted for.",
     ("What might explain the mix of obligation outcomes observed this cycle?",)),
    ("savings", "Savings",
     "Whether students held and added to savings this cycle.",
     "Two different things live here. 'Students with savings' is whether a student "
     "had any savings at the end, which could be from earlier cycles. 'Added to "
     "savings' is whether they put money in during this cycle. A student can hold "
     "savings without adding any.",
     ("How does the savings behavior this cycle compare with earlier cycles you have reviewed?",)),
    ("income", "Where income came from",
     "Income received during this completed cycle, grouped by source.",
     "This is the mix of where students' money came from — attendance-based work, "
     "teacher awards, refunds, and so on — not the total amount. It answers 'what "
     "kind of income did students get,' e.g. mostly earned versus mostly given.",
     ("What might account for the composition of income observed this cycle?",)),
    ("resources", "Money at the end of the cycle",
     "Balances remaining when this completed cycle ended.",
     "This is money left over at the end, not money earned. It shows the typical "
     "ending balance and how evenly balances were spread. Watch the 'at or below "
     "zero' count — those are students who ended the cycle with nothing or in the "
     "negative.",
     ("What context might inform how you read the spread of resources this cycle?",)),
    ("resilience", "Additional observations",
     "Independent descriptive signals, each reported on its own.",
     "These are independent signals that do not roll up into a score. Each is "
     "described separately below. Treat them as prompts — if one stands out, follow "
     "it into the source records rather than reading a verdict into it.",
     ("Which of these independent signals, if any, would you want to look into further "
      "through the source records?",)),
)

_CANDIDATES: dict[str, _CandidateMeta] = {
    "Q1a-C1": _CandidateMeta("participation", "Students who recorded attendance",
        "How many of your enrolled students logged any attendance this cycle."),
    "Q1a-C2": _CandidateMeta("participation", "Attendance records per student",
        "How attendance was spread across students — a few very active, or evenly.",
        unit="count", noun="attendance records"),
    "Q1b-C1": _CandidateMeta("activity", "Students who started an activity",
        "How many students initiated at least one economic action of their own."),
    "Q2-C1": _CandidateMeta("activity", "How often students used money",
        "How frequently students started transactions, on an average day."),
    "Q2-C2": _CandidateMeta("activity", "Money moved by students",
        "The total value of transactions students started themselves.", unit="money"),
    "Q3-C1": _CandidateMeta("obligations", "How obligations were resolved",
        "For each kind of obligation, the share paid, waived, or left unpaid."),
    "Q3-C2": _CandidateMeta("obligations", "How much was covered",
        "For each kind of obligation, how the money owed was covered.", unit="money"),
    "Q3-C3": _CandidateMeta("obligations", "Obligation events recorded",
        "A raw tally of obligation events, by kind, for transparency."),
    "Q4-C1": _CandidateMeta("savings", "Students with savings",
        "How many students had any savings balance when the cycle ended."),
    "Q4-C2": _CandidateMeta("savings", "Students who added to savings",
        "How many students moved money into savings during this cycle."),
    "Q4-C3": _CandidateMeta("savings", "Money added to savings",
        "The total value students moved into savings this cycle.", unit="money"),
    "Q5-C1": _CandidateMeta("income", "Income by source",
        "Of all the money students received, how much came from each source."),
    "Q5-C2": _CandidateMeta("income", "Income from attendance-based work",
        "The share of students' income that came from working (attendance), "
        "as opposed to awards, refunds, or other credits."),
    "Q6-C1": _CandidateMeta("resources", "Checking balances",
        "What students had left in checking at the end. This is leftover balance, "
        "not total income received.", unit="money"),
    "Q6-C2": _CandidateMeta("resources", "Savings balances",
        "What students had left in savings at the end. This is leftover balance, "
        "not total income received.", unit="money"),
    "Q6-C3": _CandidateMeta("resources", "Total balances",
        "Checking and savings combined, at the end of the cycle.", unit="money"),
    "Q9-C1": _CandidateMeta("resilience", "Independent signals",
        "Several independent signals, each described on its own line below — no "
        "score and no ranking."),
}


# --------------------------------------------------------------------------- #
# Value formatting (stored value dict → ObservationValue)                      #
# --------------------------------------------------------------------------- #


def _format_fraction(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    return ObservationValue(
        kind="fraction",
        display=f"{value['numerator']} of {value['denominator']} students ({_pct(value['value'])})",
    )


def _format_ratio(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    # Q5-C2 labor share: antecedent/consequent are money volumes (cents).
    return ObservationValue(
        kind="ratio",
        display=f"{_pct(value['value'])} of income came from attendance-based work",
        supporting=(
            f"{_money(_dollars(value['antecedent']))} of "
            f"{_money(_dollars(value['consequent']))} in recorded income.",
        ),
    )


def _dollars(cents: int) -> str:
    return f"{(Decimal(int(cents)) / 100).quantize(Decimal('0.01'))}"


def _format_rate(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    # Q2-C1: numerator = student-started transactions; value = per active student/day.
    count = value["numerator"]
    return ObservationValue(
        kind="rate",
        display=f"{count} student-started {_plural(count, 'transaction')} this cycle",
        supporting=(f"That averages about {_count(value['value'])} per active student per day.",),
    )


def _format_amount(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    return ObservationValue(kind="amount", display=_money(value["value"]))


def _format_distribution(
    value: dict[str, Any], *, money: bool, noun: str
) -> ObservationValue:
    num = _money if money else _count
    count = value["count"]
    if money:
        display = f"Half the class ended with {num(value['p50'])} or more"
        supporting = [f"Most students were between {num(value['p25'])} and {num(value['p75'])}."]
    else:
        avg = _count(value["mean"]) if "mean" in value else _count(value["p50"])
        display = f"About {avg} {noun} per student on average"
        supporting = [f"Half the class had {num(value['p50'])} or more {noun}."]
    if "n_at_or_below_zero" in value:
        n = value["n_at_or_below_zero"]
        supporting.append(
            f"{n} {_plural(n, 'student')} ended at or below {num('0.00') if money else '0'}."
        )
    if money and "mean" in value:
        supporting.append(f"Average balance: {num(value['mean'])}.")
    return ObservationValue(kind="distribution", display=display, supporting=tuple(supporting))


def _format_distribution_for_meta(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    return _format_distribution(
        value, money=(meta.unit == "money"), noun=(meta.noun or "records")
    )


def _format_category_fractions(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    lines = [
        f"{_friendly(cat['category'])}: {_pct(cat['value'])} "
        f"({_money(_dollars(cat['numerator']))} of {_money(_dollars(cat['denominator']))} received)"
        for cat in value["categories"]
    ]
    return ObservationValue(
        kind="category_fractions",
        display="Where students' money came from:",
        supporting=tuple(lines),
    )


def _format_category_fractions_by_type(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    by_type = value.get("obligation_types", {})
    if not by_type:
        return ObservationValue(kind="category_fractions_by_type",
                                display="No obligations were recorded this cycle.")
    lines: list[str] = []
    for obligation_type in sorted(by_type):
        cats = by_type[obligation_type].get("categories", [])
        parts = ", ".join(f"{_pct(c['value'])} {_friendly(c['category'])}" for c in cats)
        lines.append(f"{obligation_type.replace('_', ' ').title()}: {parts}")
    return ObservationValue(kind="category_fractions_by_type",
                            display="For each obligation, how it was resolved:",
                            supporting=tuple(lines))


def _format_coverage_by_type(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    by_type = value.get("obligation_types", {})
    if not by_type:
        return ObservationValue(kind="coverage_by_type",
                                display="No obligations were recorded this cycle.")
    lines: list[str] = []
    for obligation_type in sorted(by_type):
        comp = by_type[obligation_type]
        lines.append(
            f"{obligation_type.replace('_', ' ').title()}: "
            f"{_money(_dollars(comp['assessed_cents']))} owed — "
            f"{_money(_dollars(comp['student_paid_cents']))} paid by students, "
            f"{_money(_dollars(comp['waived_cents']))} waived, "
            f"{_money(_dollars(comp['unmet_cents']))} left unpaid."
        )
    return ObservationValue(kind="coverage_by_type",
                            display="For each obligation, how the amount owed was covered:",
                            supporting=tuple(lines))


def _format_counts(value: dict[str, Any], meta: _CandidateMeta) -> ObservationValue:
    lines = [f"{_friendly(it['label'])}: {it['count']}" for it in value["items"]]
    total = value["total"]
    return ObservationValue(kind="counts",
                            display=f"{total} obligation {_plural(total, 'event')} recorded",
                            supporting=tuple(lines))


# Per-signal plain names + how each nested value should read (Q9-C1 signal_set).
_SIGNAL_META: dict[str, dict[str, Any]] = {
    "labor_participation": {"name": "Attendance per student", "money": False, "noun": "attendance records"},
    "obligation_outcomes": {"name": "Obligation outcomes", "money": False, "noun": "obligations"},
    "resource_checking": {"name": "Checking balances", "money": True},
    "resource_savings": {"name": "Savings balances", "money": True},
    "resource_total": {"name": "Total balances", "money": True},
    "teacher_support": {"name": "Teacher support", "money": False, "noun": "events"},
    "persistence": {"name": "Persistence across cycles", "money": False},
}


def _signal_phrase(signal: dict[str, Any]) -> str:
    """A compact plain phrase for one Q9 signal's value."""
    kind = (signal.get("value") or {}).get("kind")
    if kind == "distribution":
        v = signal["value"]
        meta = _SIGNAL_META.get(signal["signal_id"], {})
        if meta.get("money"):
            return f"half the class ended with {_money(v['p50'])} or more"
        noun = meta.get("noun", "records")
        avg = _count(v["mean"]) if "mean" in v else _count(v["p50"])
        return f"about {avg} {noun} per student on average"
    if kind == "counts":
        v = signal["value"]
        parts = ", ".join(f"{it['count']} {_friendly(it['label'])}" for it in v["items"])
        return parts or "none recorded"
    formatted = _format_value(signal.get("value"), None)
    return formatted.display if formatted else "recorded"


def _format_signal_set(value: dict[str, Any], meta: _CandidateMeta | None) -> ObservationValue:
    lines: list[str] = []
    for signal in value["signals"]:
        name = _SIGNAL_META.get(signal["signal_id"], {}).get(
            "name", _friendly(signal["signal_id"])
        )
        if signal.get("applicability") == "not_applicable":
            if signal["signal_id"] == "persistence":
                lines.append(f"{name}: not available yet (needs a prior completed cycle).")
            else:
                lines.append(f"{name}: not applicable this cycle.")
        else:
            lines.append(f"{name}: {_signal_phrase(signal)}.")
    n = len(value["signals"])
    return ObservationValue(
        kind="signal_set",
        display=f"{n} independent {_plural(n, 'signal')}, each shown separately:",
        supporting=tuple(lines),
    )


_FORMATTERS = {
    "fraction": _format_fraction,
    "ratio": _format_ratio,
    "rate": _format_rate,
    "amount": _format_amount,
    "distribution": _format_distribution_for_meta,
    "category_fractions": _format_category_fractions,
    "category_fractions_by_type": _format_category_fractions_by_type,
    "coverage_by_type": _format_coverage_by_type,
    "counts": _format_counts,
    "signal_set": _format_signal_set,
}


def _format_value(value: dict[str, Any] | None, meta: _CandidateMeta | None) -> ObservationValue | None:
    if not value or "kind" not in value:
        return None
    formatter = _FORMATTERS.get(value["kind"])
    if formatter is None:
        return ObservationValue(kind=value["kind"], display="—")
    return formatter(value, meta)


# --------------------------------------------------------------------------- #
# Humanizing applicability / qualifiers                                        #
# --------------------------------------------------------------------------- #


def _humanize_not_applicable(reason: dict[str, Any] | None) -> str | None:
    if not isinstance(reason, dict):
        return None
    if reason.get("feature") == "savings":
        return "Savings is disabled for this class this cycle."
    if reason.get("input") == "prior_completed_cycle_records":
        return "No prior completed cycle is available yet."
    return "Not applicable this cycle."


def _qualifier_lines(qualifiers: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(qualifiers, dict):
        return ()
    basis = qualifiers.get("basis_note")
    if isinstance(basis, dict) and basis.get("code") == "checking_only_savings_disabled":
        return ("Reported on a checking-only basis (savings excluded).",)
    return ()


# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #


def _build_observation(entry: dict[str, Any]) -> ObservationPresentation | None:
    candidate_id = entry.get("candidate_id")
    meta = _CANDIDATES.get(candidate_id)
    if meta is None:
        return None  # unknown candidate — not presented
    applicability = entry.get("applicability", "computed")
    if applicability == "not_applicable":
        return ObservationPresentation(
            candidate_id=candidate_id,
            title=meta.title,
            summary=meta.summary,
            applicability="not_applicable",
            value=None,
            not_applicable_reason=_humanize_not_applicable(entry.get("not_applicable_reason")),
            guiding_questions=meta.guiding_questions,
        )
    return ObservationPresentation(
        candidate_id=candidate_id,
        title=meta.title,
        summary=meta.summary,
        applicability="computed",
        value=_format_value(entry.get("value"), meta),
        supporting_context=_qualifier_lines(entry.get("qualifiers")),
        guiding_questions=meta.guiding_questions,
    )


def build_cycle_view(summary: InterpretationCycleSummary, observations_json: dict[str, Any]) -> InterpretationCycleView:
    """Assemble the presentation of one cycle from its **stored** ``observations_json``.

    Pure transform — reads only the frozen payload, never the compute layer.
    Observations are grouped into the fixed themed sections; a section with no
    present observations is omitted.
    """
    by_candidate: dict[str, ObservationPresentation] = {}
    for entry in (observations_json or {}).get("observations", []):
        presentation = _build_observation(entry)
        if presentation is not None:
            by_candidate[presentation.candidate_id] = presentation

    sections: list[InterpretationSection] = []
    for key, title, section_summary, how_to_read, section_questions in _SECTIONS:
        members = tuple(
            by_candidate[cid]
            for cid, meta in _CANDIDATES.items()
            if meta.section == key and cid in by_candidate
        )
        if not members:
            continue
        sections.append(InterpretationSection(
            key=key, title=title, summary=section_summary, how_to_read=how_to_read,
            observations=members, guiding_questions=section_questions,
        ))
    return InterpretationCycleView(cycle=summary, sections=tuple(sections))
