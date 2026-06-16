# tests/shared/infrastructure/intent/test_remediation_guidance.py

"""Tests for load_remediation_guidance (ADR-109 #653 context-bundle source).

Best-effort, read-only projection of auto_remediation.yaml: returns the
human-readable {description, status, confidence} for a rule id, or None when
the rule has no entry / the input is empty. Never raises on a missing rule.
"""

from __future__ import annotations

from shared.infrastructure.intent.remediation_guidance import (
    load_remediation_guidance,
)


def test_none_rule_short_circuits_without_file_read():
    """A falsy rule id returns None immediately (no map read)."""
    assert load_remediation_guidance(None) is None
    assert load_remediation_guidance("") is None


def test_unknown_rule_returns_none():
    """A rule absent from the remediation map returns None, not an error."""
    assert load_remediation_guidance("definitely.not.a.real.rule.xyz") is None


def test_known_rule_returns_guidance_projection():
    """A mapped rule returns the guidance projection with the expected keys."""
    out = load_remediation_guidance("style.import_order")
    assert out is not None
    assert set(out) == {"description", "status", "confidence"}
    assert out["description"]  # non-empty guidance text
