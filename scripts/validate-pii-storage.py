#!/usr/bin/env python3
"""Validate the explicitly permitted PII storage forms in app/models.py."""
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "app" / "models.py"

# Authority: INV-ARC-018 §VI. Keep this finite and explicit. A new field must
# amend the invariant before this allowlist changes.
ALLOWED = {
    ("User", "username_hash"): "hmac",
    ("IdentityProfile", "first_name"): "encrypted",
    ("IdentityProfile", "last_name"): "encrypted",
    ("Seat", "claim_first_name_hash"): "hmac",
    ("Seat", "claim_last_name_hash"): "hmac",
}
# Credential hashes are security material, but are not the PII fields governed
# by the finite identity-display/claim allowlist in INV-ARC-018 §VI.
NON_PII_HASH_FIELDS = {"username_lookup_hash", "pin_hash", "passphrase_hash"}


def _column_fields(cls: ast.ClassDef) -> list[tuple[str, str]]:
    fields = []
    for node in cls.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "Column":
            continue
        storage = "plain"
        if call.args and isinstance(call.args[0], ast.Call):
            inner = call.args[0]
            if isinstance(inner.func, ast.Name) and inner.func.id == "PIIEncryptedType":
                storage = "encrypted"
        if target.id.endswith("_hash") or target.id == "username_hash":
            storage = "hmac"
        fields.append((target.id, storage))
    return fields


def validate(path: Path = MODEL_PATH) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in {"User", "Seat", "IdentityProfile"}:
            continue
        for field, storage in _column_fields(node):
            if field in NON_PII_HASH_FIELDS:
                continue
            expected = ALLOWED.get((node.name, field))
            if expected is None and (field in {"first_name", "last_name", "notes"} or field.endswith("_hash")):
                findings.append(f"{node.name}.{field}: PII field is not permitted by INV-ARC-018 §VI")
            elif expected and storage != expected:
                findings.append(f"{node.name}.{field}: expected {expected} storage, found {storage}")
    return findings


def main() -> int:
    findings = validate()
    if findings:
        print("PII storage violations:")
        print("\n".join(f"  - {finding}" for finding in findings))
        return 1
    print("PII storage allowlist passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
