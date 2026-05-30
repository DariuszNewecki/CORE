"""Unit tests for ``current_capability()`` per ADR-079 D2.

The accessor is a thin read of ``_executor_token`` — its job is to give the
chokepoint a stable surface to consume without introducing a parallel
ContextVar. Tests pin both that contract (token-out = accessor-in) and the
nested-frame semantics that paper §7 and ADR-079 D2 rely on.
"""

from __future__ import annotations

from shared.governance_token import authorize_execution, current_capability


def test_returns_none_outside_authorize_execution() -> None:
    """No frame active → None (the §7 'no provenance' case)."""
    assert current_capability() is None


def test_returns_action_id_inside_authorize_execution() -> None:
    """Active frame's action_id is what the accessor returns."""
    with authorize_execution("fix.format"):
        assert current_capability() == "fix.format"


def test_nested_frames_report_innermost() -> None:
    """Nested authorize_execution → innermost wins (dispatcher → dispatched)."""
    with authorize_execution("action.execute"):
        assert current_capability() == "action.execute"
        with authorize_execution("fix.format"):
            assert current_capability() == "fix.format"
        assert current_capability() == "action.execute"


def test_reset_restores_prior_state() -> None:
    """Exiting a frame restores the prior token (or None at the root)."""
    assert current_capability() is None
    with authorize_execution("fix.format"):
        pass
    assert current_capability() is None
