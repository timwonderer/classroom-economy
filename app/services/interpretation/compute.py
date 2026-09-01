"""Interpretation compute composition (slice 8.2b).

Composes the per-candidate compute modules into an ``observations_json`` payload.
This layer performs **composition only** — the candidate math lives in the
per-question modules (``participation``, ``economic_interaction``, and, in later
slices, the remaining source-domain clusters).

Scope discipline (slice 8.2b-5):
* All 17 required candidates are implemented (Q1a, Q1b, Q2, Q3, Q4, Q5, Q6, Q9).
  The compute core is now contract-complete: over a lawful cycle window it
  produces a payload whose serializer-derived ``coverage.complete`` is ``True``
  and which ``validate_for_materialization`` accepts. This module still does NOT
  persist anything — writing an immutable ``interpretation_cycle_record`` is the
  separate slice 8.2c boundary (materialization writer, ``reference_configuration``
  capture, idempotency, fail-closed persistence).
* The payload this returns is therefore still a **partial** payload. Its
  serializer-derived ``coverage.complete`` is ``False`` and
  ``observation_contract.validate_for_materialization`` will reject it purely
  because candidate coverage is incomplete. That rejection is the intended
  end-state of this slice, not a defect.
* This is NOT the immutable writer (slice 8.2c). It reads source-domain facts
  and returns a dict; it never persists an ``interpretation_cycle_record``.
"""

from __future__ import annotations

from typing import Any

from app.services.interpretation.economic_activity import compute_q2
from app.services.interpretation.economic_interaction import compute_q1b
from app.services.interpretation.income_composition import compute_q5
from app.services.interpretation.obligation_observation import compute_q3
from app.services.interpretation.observation_contract import (
    REQUIRED_SET_VERSION,
    SCHEMA_VERSION,
    SPEC_REF,
    SPEC_VERSION,
    derive_coverage_complete,
)
from app.services.interpretation.participation import compute_q1a
from app.services.interpretation.resilience_observation import compute_q9
from app.services.interpretation.resource_distribution import compute_q6
from app.services.interpretation.savings_behavior import compute_q4


def compute_partial_observations(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute the currently-implemented observation entries for a cycle window.

    Returns the entries sorted ascending by ``candidate_id`` (SPEC-ITR-001
    §15.9). As additional slices land, their candidate modules are composed
    here; the sort keeps the output deterministic regardless of composition
    order.
    """
    entries: list[dict[str, Any]] = []
    entries.extend(compute_q1a(class_id, window_start, window_end))
    entries.extend(compute_q1b(class_id, window_start, window_end))
    entries.extend(compute_q2(class_id, window_start, window_end))
    entries.extend(compute_q3(class_id, window_start, window_end))
    entries.extend(compute_q4(class_id, window_start, window_end))
    entries.extend(compute_q5(class_id, window_start, window_end))
    entries.extend(compute_q6(class_id, window_start, window_end))
    entries.extend(compute_q9(class_id, window_start, window_end))
    entries.sort(key=lambda entry: entry["candidate_id"])
    return entries


def build_observations_payload(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap observation entries in the §15 envelope.

    ``coverage.complete`` is serializer-derived (SPEC-ITR-001 §15.8): it is set
    from :func:`derive_coverage_complete`, never asserted by compute. ``coverage``
    stays lean — no compute-supplied ``candidates_present``/``candidates_missing``
    lists (the validator rejects those, §15.4).
    """
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "spec": {"ref": SPEC_REF, "version": SPEC_VERSION},
        "coverage": {"required_set_version": REQUIRED_SET_VERSION},
        "observations": observations,
    }
    payload["coverage"]["complete"] = derive_coverage_complete(payload)
    return payload


def compute_partial_payload(class_id: str, window_start, window_end) -> dict[str, Any]:
    """Convenience: compute implemented candidates and wrap them in the envelope.

    The result is a partial payload (see module docstring) — a faithful
    computation of the implemented candidates that the materialization gate will
    correctly reject as incomplete until all 17 candidates are computed.
    """
    return build_observations_payload(
        compute_partial_observations(class_id, window_start, window_end)
    )
