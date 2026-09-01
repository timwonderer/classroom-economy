"""ITR-owned presentation objects for a materialized cycle (DOM-ITR-001, INV-ARC-022).

This is the domain-owned *presentation shape* of a completed cycle's interpretation:
it transforms the canonical, frozen ``observations_json`` of an
``interpretation_cycle_record`` into presentation-ready objects a page view model
and template can consume **without knowing anything about JSONB storage or
candidate internals** (no ``candidate_id == "Q3-C2"`` or ``value.kind ==
"coverage_by_type"`` logic ever reaches a template).

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

from dataclasses import dataclass, field
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
# the ways ``suggested_action`` would try to sneak back in. Guiding questions are
# validated against these so the non-prescriptive contract is enforceable, not
# merely aspirational.
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
    """A themed group of observations with its own guiding questions."""

    key: str
    title: str
    summary: str
    observations: tuple[ObservationPresentation, ...]
    guiding_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterpretationCycleView:
    """The full presentation of one completed cycle."""

    cycle: InterpretationCycleSummary
    sections: tuple[InterpretationSection, ...]


# --------------------------------------------------------------------------- #
# Catalog: candidate + section metadata and curated guiding questions          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _CandidateMeta:
    section: str
    title: str
    summary: str
    guiding_questions: tuple[str, ...] = ()


# Section order and copy. Sections group the 17 candidates thematically.
_SECTIONS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("participation", "Labor participation",
     "How many students took part in the classroom labor economy this cycle.",
     ("What might account for the level of participation observed this cycle?",)),
    ("activity", "Economic activity",
     "How much student-initiated economic interaction and movement occurred.",
     ("What context might inform how you read the amount of activity this cycle?",)),
    ("obligations", "Obligations",
     "How assessed obligations were resolved this cycle, by count and by amount.",
     ("What might explain the mix of obligation outcomes observed this cycle?",)),
    ("savings", "Savings behavior",
     "Whether students held and contributed to savings this cycle.",
     ("How does the savings behavior this cycle compare with earlier cycles you have reviewed?",)),
    ("income", "Income composition",
     "Where observed student income came from, by origin category.",
     ("What might account for the composition of income observed this cycle?",)),
    ("resources", "Resource distribution",
     "How economic resources were distributed across the class at cycle end.",
     ("What context might inform how you read the spread of resources this cycle?",)),
    ("resilience", "Resilience signals",
     "Independent descriptive signals relevant to students' economic participation.",
     ("Which of these independent signals, if any, would you want to look into further "
      "through the source records?",)),
)

_CANDIDATES: dict[str, _CandidateMeta] = {
    "Q1a-C1": _CandidateMeta("participation", "Labor-participation share",
        "The share of enrolled students who took part in labor this cycle."),
    "Q1a-C2": _CandidateMeta("participation", "Participation-count distribution",
        "How participation counts are distributed across students."),
    "Q1b-C1": _CandidateMeta("activity", "Student-initiated economic interaction",
        "The share of students who initiated an economic interaction this cycle."),
    "Q2-C1": _CandidateMeta("activity", "Student-initiated transaction frequency",
        "How often students initiated transactions, per active student per day."),
    "Q2-C2": _CandidateMeta("activity", "Student-initiated monetary volume",
        "The total monetary volume of student-initiated transactions."),
    "Q3-C1": _CandidateMeta("obligations", "Obligation satisfaction (by count)",
        "How obligations were resolved this cycle, by count, per obligation type."),
    "Q3-C2": _CandidateMeta("obligations", "Obligation coverage (by amount)",
        "How assessed obligation dollars were covered, per obligation type."),
    "Q3-C3": _CandidateMeta("obligations", "Obligation event counts",
        "Raw counts of obligation events this cycle, per type and kind."),
    "Q4-C1": _CandidateMeta("savings", "Savings-holding share",
        "The share of students holding any savings at cycle end."),
    "Q4-C2": _CandidateMeta("savings", "Savings-contribution share",
        "The share of students who contributed to savings this cycle."),
    "Q4-C3": _CandidateMeta("savings", "Savings-contribution volume",
        "The total volume of student savings contributions this cycle."),
    "Q5-C1": _CandidateMeta("income", "Income composition",
        "The share of observed income from each origin category."),
    "Q5-C2": _CandidateMeta("income", "Labor share of income",
        "The share of observed income that originated from labor."),
    "Q6-C1": _CandidateMeta("resources", "Checking distribution",
        "How checking balances were distributed across the class at cycle end."),
    "Q6-C2": _CandidateMeta("resources", "Savings distribution",
        "How savings balances were distributed across the class at cycle end."),
    "Q6-C3": _CandidateMeta("resources", "Total-resource distribution",
        "How total resources were distributed across the class at cycle end."),
    "Q9-C1": _CandidateMeta("resilience", "Resilience observation set",
        "A set of independent descriptive signals, reported without a composite verdict."),
}


# --------------------------------------------------------------------------- #
# Value formatting (stored value dict → ObservationValue)                      #
# --------------------------------------------------------------------------- #


def _pct(decimal_str: str) -> str:
    return f"{(Decimal(decimal_str) * 100).quantize(Decimal('0.01'))}%"


def _cents(cents: int) -> str:
    return f"{(Decimal(int(cents)) / 100).quantize(Decimal('0.01'))}"


def _humanize_label(label: str) -> str:
    # Category / outcome ids are prefixed for deterministic sorting (e.g.
    # "1_satisfied_payment_only"); strip a leading numeric sort key and spacing.
    text = label
    if "_" in text and text.split("_", 1)[0].isdigit():
        text = text.split("_", 1)[1]
    return text.replace("_", " ")


def _format_fraction(value: dict[str, Any]) -> ObservationValue:
    return ObservationValue(
        kind="fraction",
        display=f"{_pct(value['value'])} ({value['numerator']} of {value['denominator']})",
    )


def _format_ratio(value: dict[str, Any]) -> ObservationValue:
    return ObservationValue(
        kind="ratio",
        display=f"{_pct(value['value'])} ({value['antecedent']} of {value['consequent']})",
    )


def _format_rate(value: dict[str, Any]) -> ObservationValue:
    unit = _humanize_label(value.get("unit", ""))
    return ObservationValue(
        kind="rate",
        display=f"{value['value']} {unit}".strip(),
        supporting=(f"{value['numerator']} over {value['denominator']}",),
    )


def _format_amount(value: dict[str, Any]) -> ObservationValue:
    return ObservationValue(kind="amount", display=f"{value['value']} {value.get('unit', '')}".strip())


def _format_distribution(value: dict[str, Any]) -> ObservationValue:
    supporting = [
        f"p10 {value['p10']} · p25 {value['p25']} · p75 {value['p75']} · p90 {value['p90']}",
        f"interquartile range {value['iqr']}",
    ]
    if "mean" in value:
        supporting.append(f"mean {value['mean']}")
    if "n_at_or_below_zero" in value:
        supporting.append(f"{value['n_at_or_below_zero']} at or below zero")
    return ObservationValue(
        kind="distribution",
        display=f"median {value['p50']} across {value['count']} students",
        supporting=tuple(supporting),
    )


def _format_category_fractions(value: dict[str, Any]) -> ObservationValue:
    lines = [
        f"{_humanize_label(cat['category'])}: {_pct(cat['value'])} "
        f"({cat['numerator']} of {cat['denominator']})"
        for cat in value["categories"]
    ]
    return ObservationValue(kind="category_fractions", display="by category", supporting=tuple(lines))


def _format_category_fractions_by_type(value: dict[str, Any]) -> ObservationValue:
    by_type = value.get("obligation_types", {})
    if not by_type:
        return ObservationValue(kind="category_fractions_by_type",
                                display="no obligations this cycle")
    lines: list[str] = []
    for obligation_type in sorted(by_type):
        cats = by_type[obligation_type].get("categories", [])
        parts = ", ".join(
            f"{_humanize_label(c['category'])} {_pct(c['value'])}" for c in cats
        )
        lines.append(f"{_humanize_label(obligation_type)}: {parts}")
    return ObservationValue(kind="category_fractions_by_type",
                            display="by obligation type", supporting=tuple(lines))


def _format_coverage_by_type(value: dict[str, Any]) -> ObservationValue:
    by_type = value.get("obligation_types", {})
    if not by_type:
        return ObservationValue(kind="coverage_by_type", display="no obligations this cycle")
    lines: list[str] = []
    for obligation_type in sorted(by_type):
        comp = by_type[obligation_type]
        lines.append(
            f"{_humanize_label(obligation_type)}: assessed {_cents(comp['assessed_cents'])}, "
            f"student-paid {_cents(comp['student_paid_cents'])}, "
            f"waived {_cents(comp['waived_cents'])}, unmet {_cents(comp['unmet_cents'])}"
        )
    return ObservationValue(kind="coverage_by_type", display="by obligation type",
                            supporting=tuple(lines))


def _format_counts(value: dict[str, Any]) -> ObservationValue:
    lines = [f"{_humanize_label(it['label'])}: {it['count']}" for it in value["items"]]
    return ObservationValue(kind="counts", display=f"{value['total']} events",
                            supporting=tuple(lines))


def _format_signal_set(value: dict[str, Any]) -> ObservationValue:
    lines: list[str] = []
    for signal in value["signals"]:
        name = _humanize_label(signal["signal_id"])
        if signal.get("applicability") == "not_applicable":
            lines.append(f"{name}: not applicable")
        else:
            nested = _format_value(signal.get("value") or {})
            lines.append(f"{name}: {nested.display}" if nested else f"{name}: —")
    return ObservationValue(kind="signal_set",
                            display=f"{len(value['signals'])} independent signals",
                            supporting=tuple(lines))


_FORMATTERS = {
    "fraction": _format_fraction,
    "ratio": _format_ratio,
    "rate": _format_rate,
    "amount": _format_amount,
    "distribution": _format_distribution,
    "category_fractions": _format_category_fractions,
    "category_fractions_by_type": _format_category_fractions_by_type,
    "coverage_by_type": _format_coverage_by_type,
    "counts": _format_counts,
    "signal_set": _format_signal_set,
}


def _format_value(value: dict[str, Any] | None) -> ObservationValue | None:
    if not value or "kind" not in value:
        return None
    formatter = _FORMATTERS.get(value["kind"])
    if formatter is None:
        return ObservationValue(kind=value["kind"], display="—")
    return formatter(value)


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
        value=_format_value(entry.get("value")),
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
    for key, title, section_summary, section_questions in _SECTIONS:
        members = tuple(
            by_candidate[cid]
            for cid, meta in _CANDIDATES.items()
            if meta.section == key and cid in by_candidate
        )
        if not members:
            continue
        sections.append(InterpretationSection(
            key=key, title=title, summary=section_summary,
            observations=members, guiding_questions=section_questions,
        ))
    return InterpretationCycleView(cycle=summary, sections=tuple(sections))
