"""Tests for TestGenAcceptanceCheck (ADR-140 Amendment 2026-07-14, later; #791, #800).

The check fires when a file constructs CompositeAcceptanceCondition([...]) for
the test-generation acceptance loop without including PytestAcceptanceCondition
among its conditions — the exact drift that produced #791.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mind.logic.engines.ast_gate.checks.test_gen_acceptance_check import (
    TestGenAcceptanceCheck,
)


def _check(code: str, path: str = "src/will/agents/test_gen_cognitive_delegate.py") -> list[str]:
    tree = ast.parse(code)
    return TestGenAcceptanceCheck.check(tree, Path(path))


# ID: 1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d
def test_composite_including_pytest_gate_passes() -> None:
    code = (
        "acceptance = CompositeAcceptanceCondition(\n"
        "    [\n"
        "        IntentGuardAcceptanceCondition(repo_root=r, target_path=t),\n"
        "        PytestAcceptanceCondition(executor=e, source_file=s, "
        "target_path=t, base_content=b, file_service=f),\n"
        "    ]\n"
        ")\n"
    )
    assert _check(code) == []


# ID: 2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e
def test_composite_missing_pytest_gate_flags() -> None:
    """The exact #791 drift shape: composite reverted to a static-only gate."""
    code = (
        "acceptance = CompositeAcceptanceCondition(\n"
        "    [IntentGuardAcceptanceCondition(repo_root=r, target_path=t)]\n"
        ")\n"
    )
    findings = _check(code)
    assert len(findings) == 1
    assert "PytestAcceptanceCondition" in findings[0]
    assert "ADR-135 D6" in findings[0]


# ID: 3c4d5e6f-7a8b-4c9d-0e1f-2a3b4c5d6e7f
def test_empty_composite_flags() -> None:
    code = "acceptance = CompositeAcceptanceCondition([])\n"
    findings = _check(code)
    assert len(findings) == 1


# ID: 4d5e6f7a-8b9c-4d0e-1f2a-3b4c5d6e7f8a
def test_no_composite_construction_is_out_of_scope() -> None:
    """A file that builds no composite at all is not this check's target —
    it guards against drift in an existing wiring point, not the wiring
    point's presence.
    """
    code = "acceptance = IntentGuardAcceptanceCondition(repo_root=r, target_path=t)\n"
    assert _check(code) == []


# ID: 5e6f7a8b-9c0d-4e1f-2a3b-4c5d6e7f8a9b
def test_pytest_gate_via_attribute_call_is_recognized() -> None:
    """PytestAcceptanceCondition referenced via a module-qualified attribute
    call (e.g. conditions.PytestAcceptanceCondition(...)) is still detected —
    the check matches on the call's final attribute name, not just bare Name.
    """
    code = (
        "acceptance = CompositeAcceptanceCondition(\n"
        "    [\n"
        "        conditions.IntentGuardAcceptanceCondition(repo_root=r, target_path=t),\n"
        "        conditions.PytestAcceptanceCondition(executor=e, source_file=s, "
        "target_path=t, base_content=b, file_service=f),\n"
        "    ]\n"
        ")\n"
    )
    assert _check(code) == []


# ID: 6f7a8b9c-0d1e-4f2a-3b4c-5d6e7f8a9b0c
def test_multiple_composites_each_checked_independently() -> None:
    code = (
        "good = CompositeAcceptanceCondition(\n"
        "    [IntentGuardAcceptanceCondition(repo_root=r, target_path=t), "
        "PytestAcceptanceCondition(executor=e, source_file=s, target_path=t, "
        "base_content=b, file_service=f)]\n"
        ")\n"
        "bad = CompositeAcceptanceCondition(\n"
        "    [IntentGuardAcceptanceCondition(repo_root=r, target_path=t)]\n"
        ")\n"
    )
    findings = _check(code)
    assert len(findings) == 1


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
