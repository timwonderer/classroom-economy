from __future__ import annotations

import ast
from pathlib import Path

import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_pii_storage", ROOT / "scripts" / "validate-pii-storage.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_current_model_is_evaluated_against_finite_allowlist():
    findings = MODULE.validate()
    assert any("IdentityProfile.notes" in finding for finding in findings)


def test_unknown_hash_field_is_rejected(tmp_path):
    source = """
class Seat:
    unknown_hash = db.Column(db.String(128), nullable=True)
"""
    path = tmp_path / "models.py"
    path.write_text(source, encoding="utf-8")
    findings = MODULE.validate(path)
    assert findings == ["Seat.unknown_hash: PII field is not permitted by INV-ARC-018 §VI"]
