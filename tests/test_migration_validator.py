"""The migration idempotency gate must fail on real defects and only on those.

`scripts/validate-migrations.py` is auxiliary evidence for the CI-PERSIST
invariant family, so a false positive blocks every migration-touching PR and a
false negative lets a non-idempotent migration reach deployment. Both directions
are covered here.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_migrations", ROOT / "scripts" / "validate-migrations.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def _check(tmp_path, source):
    path = tmp_path / "0001_example.py"
    path.write_text(source, encoding="utf-8")
    return [error for error in validator.check_idempotency(path) if error.startswith("❌")]


def test_unguarded_add_column_is_still_an_error(tmp_path):
    errors = _check(tmp_path, """
def upgrade():
    op.add_column('issues', sa.Column('class_label', sa.String(255)))
""")
    assert len(errors) == 1
    assert "Unguarded add_column()" in errors[0]


def test_add_column_nested_in_an_existence_check_passes(tmp_path):
    assert _check(tmp_path, """
def upgrade():
    if not column_exists('issues', 'class_label'):
        op.add_column('issues', sa.Column('class_label', sa.String(255)))
""") == []


def test_add_column_after_a_returning_guard_clause_passes(tmp_path):
    """The early-return guard is equivalent protection to an enclosing block."""
    assert _check(tmp_path, """
def upgrade():
    if column_exists('issues', 'class_label'):
        print("already applied")
        return
    op.add_column('issues', sa.Column('class_label', sa.String(255)))
""") == []


def test_a_guard_clause_that_does_not_return_protects_nothing(tmp_path):
    """Falling through an `if` leaves the following statement unconditional."""
    errors = _check(tmp_path, """
def upgrade():
    if column_exists('issues', 'class_label'):
        print("already applied")
    op.add_column('issues', sa.Column('class_label', sa.String(255)))
""")
    assert len(errors) == 1


def test_a_guard_clause_does_not_leak_into_a_later_function(tmp_path):
    errors = _check(tmp_path, """
def upgrade():
    if column_exists('issues', 'class_label'):
        return
    op.add_column('issues', sa.Column('class_label', sa.String(255)))


def downgrade():
    op.add_column('issues', sa.Column('resurrected', sa.String(255)))
""")
    assert len(errors) == 1
    assert "Unguarded add_column()" in errors[0]


@pytest.mark.parametrize("name", [
    "a1c4e7d92f30_issues_class_label_submission_freeze.py",
    "e6f7a8b9c0d1_canonicalize_ledger_persistence.py",
])
def test_committed_guard_clause_migrations_are_accepted(name):
    """Regression: these two used the early-return form and were falsely flagged."""
    path = ROOT / "migrations" / "versions" / name
    errors = [e for e in validator.check_idempotency(path) if e.startswith("❌")]
    assert errors == []
