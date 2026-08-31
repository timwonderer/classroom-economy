"""Interpretation compute composition (slice 8.2b).

Composes the per-candidate compute modules into an ``observations_json`` payload.
This layer performs **composition only** — the candidate math lives in the
per-question modules (``participation``, ``economic_interaction``, and, in later
slices, the remaining source-domain clusters).

Scope discipline (slice 8.2b-1):
* Only Q1a-C1, Q1a-C2, and Q1b-C1 are implemented. The remaining 14 required
  candidates are deliberately absent — this module does NOT stub them and does
  NOT weaken the 17-candidate materialization gate (SPEC-ITR-001 §15.8).
* The payload this returns is therefore a **partial** payload. Its
  serializer-derived ``coverage.complete`` is ``False`` and
  ``observation_contract.validate_for_materialization`` will reject it purely
  because candidate coverage is incomplete. That rejection is the intended
  end-state of this slice, not a defect.
* This is NOT the immutable writer (slice 8.2c). It reads source-domain facts
  and returns a dict; it never persists an ``interpretation_cycle_record``.
"""

from __future__ import annotations

from typing import Any

from app.services.interpretation.economic_interaction import compute_q1b
from app.services.interpretation.observation_contract import (
    REQUIRED_SET_VERSION,
    SCHEMA_VERSION,
    SPEC_REF,
    SPEC_VERSION,
    derive_coverage_complete,
)
from app.services.interpretation.participation import compute_q1a


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
