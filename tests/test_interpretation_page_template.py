"""Slice 8.4c — Interpretation page template (pure, accessible ITR consumer).

The template renders the seven ITR sections from the page view model, observation
first / context second / question third, with non-prescriptive guiding questions
in collapsed disclosures. Acceptance:

* the rendered page passes the canonical accessibility audit (one h1, named
  controls, labeled selects, no duplicate ids);
* observations render value + supporting + explanation; not_applicable reads
  intentionally (reason, not a dash/0/empty);
* guiding questions appear as collapsed <details> "Questions to consider", never
  as verdicts;
* empty history renders the awaiting-first-cycle state with no "generate" cue;
* the template is a pure consumer — no candidate_id / value.kind branching.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from bs4 import BeautifulSoup

from app.extensions import db
from app.feats.base import FEATContext
from app.models import InterpretationCycleRecord
from app.utils.canonical_temporal_resolver import utc_now
from tests.helpers.classroom_initializer import initialize_as_teacher
from tests.test_accessibility import _audit_html_accessibility

_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "admin_analytics_dashboard.html"
_REF = {"schema_version": 1, "economic_engine": {}, "policy": {}}


def _dist(**extra):
    return {"kind": "distribution", "count": 4, "p10": "0.00", "p25": "0.00",
            "p50": "10.00", "p75": "20.00", "p90": "30.00", "iqr": "20.00", **extra}


def _one_per_section():
    return [
        {"candidate_id": "Q1a-C1", "applicability": "computed",
         "value": {"kind": "fraction", "numerator": 15, "denominator": 22, "value": "0.6818"}},
        {"candidate_id": "Q2-C2", "applicability": "computed",
         "value": {"kind": "amount", "value": "42.00", "unit": "tokens"}},
        {"candidate_id": "Q3-C3", "applicability": "computed",
         "value": {"kind": "counts", "items": [{"label": "RENT:payment", "count": 3}], "total": 3}},
        {"candidate_id": "Q4-C1", "applicability": "not_applicable",
         "not_applicable_reason": {"feature": "savings", "state": "disabled"}, "value": None},
        {"candidate_id": "Q5-C2", "applicability": "computed",
         "value": {"kind": "ratio", "antecedent": 2000, "consequent": 3500, "value": "0.5714"}},
        {"candidate_id": "Q6-C1", "applicability": "computed", "value": _dist(n_at_or_below_zero=1)},
        {"candidate_id": "Q9-C1", "applicability": "computed",
         "value": {"kind": "signal_set", "signals": [
             {"signal_id": "persistence", "applicability": "not_applicable", "value": None}]}},
    ]


def _put_record(cid, cycle_id, observations):
    now = utc_now()
    with FEATContext("FEAT-PROD-004", idempotency_key=f"rec:{cid}:{cycle_id}"):
        db.session.add(InterpretationCycleRecord(
            class_id=cid, payroll_cycle_id=cycle_id,
            cycle_started_at=now - timedelta(hours=1), cycle_completed_at=now, computed_at=now,
            reference_configuration=_REF,
            observations_json={"schema_version": 1, "observations": observations}))
        db.session.flush()


def test_template_is_a_pure_consumer():
    import re

    # Strip Jinja comments so prose describing the rule can't trigger the check;
    # only the rendered template CODE must be free of candidate-internal branching
    # (INV-ARC-022 — 8.4a already translated those into presentation objects).
    code = re.sub(r"\{#.*?#\}", "", _TEMPLATE.read_text(), flags=re.DOTALL)
    assert "candidate_id" not in code
    assert ".kind" not in code


def test_rendered_page_is_accessible_and_renders_sections(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    _put_record(classroom.class_id, "cycle-render", _one_per_section())

    response = client.get("/admin/interpretation/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    _audit_html_accessibility(html)  # one h1, named controls, labeled selects, no dup ids

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".interpretation-page")
    assert region is not None
    text = region.get_text(" ", strip=True)

    # All seven themed sections render.
    for title in ("How students participated", "How students used the economy",
                  "What happened with obligations", "Savings", "Where income came from",
                  "Money at the end of the cycle", "Additional observations"):
        assert title in text, title

    # Observation value renders (participation 15 of 22).
    assert "15 of 22 students (68.18%)" in text

    # not_applicable reads intentionally — reason, not a dash/0/empty.
    assert "Not applicable this cycle. Savings is disabled for this class this cycle." in text

    # Guiding questions are collapsed <details> disclosures, visually modest.
    details = region.select("details.itr-questions")
    assert details, "guiding-question disclosures missing"
    assert all(d.find("summary") for d in details)
    assert any("Questions to consider" in d.get_text() for d in details)
    # Collapsed by default (not forced open).
    assert all(not d.has_attr("open") for d in details)

    # The cycle selector is a labeled, accessible control.
    assert region.select_one('label[for="itr-cycle-select"]') is not None
    assert region.select_one('select#itr-cycle-select') is not None


def test_empty_history_state_has_no_generate_cue(client):
    app = client.application
    initialize_as_teacher("chemistry_p1", client, app)  # no cycle records

    response = client.get("/admin/interpretation/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    _audit_html_accessibility(html)

    region = BeautifulSoup(html, "html.parser").select_one(".interpretation-page")
    text = region.get_text(" ", strip=True)
    assert "No completed interpretation yet" in text
    assert "after the first payroll cycle is completed" in text
    # No on-demand "generate analytics" mental model, no reflection panel.
    assert "generate" not in text.lower()
    assert "Questions to consider" not in text
