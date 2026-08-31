"""Interpretation Domain (DOM-ITR-001) services.

This package is the compliant home for Interpretation-Domain logic. It is
deliberately kept separate from ``app/services/analytics`` and
``app/utils/analytics_engine.py``, which are documented-noncompliant runtime
surfaces per ``DOM-ITR-001`` §XIII.b and MUST NOT be persisted into an immutable
``interpretation_cycle_record``.
"""
