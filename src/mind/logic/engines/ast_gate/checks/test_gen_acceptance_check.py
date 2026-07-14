# src/mind/logic/engines/ast_gate/checks/test_gen_acceptance_check.py

"""
TestGenAcceptanceCheck — drift-guard for ADR-135 D6 / ADR-140 Amendment 2026-07-14
(later), decision 8 (#791, #800).

Detects the specific drift that produced #791: the test-generation acceptance
loop silently reverting to a static-only gate (IntentGuardAcceptanceCondition
alone) after the runtime pytest gate (PytestAcceptanceCondition) is removed or
never wired into the CompositeAcceptanceCondition passed to
PromptModelIterativeAgent.generate().

Static-verification ceiling (named explicitly per #801): this is an AST check.
It proves PytestAcceptanceCondition is *referenced* inside a
CompositeAcceptanceCondition([...]) construction in the scoped file — it
cannot prove evaluate() actually executes on every real invocation, or that a
rejection is honored rather than silently swallowed by some future edit that
keeps this static shape intact while defeating its intent. It catches
wholesale removal/replacement of the runtime gate (the failure mode that
actually happened), not a subtler in-place neutering of it.
"""

from __future__ import annotations

import ast
from pathlib import Path


_COMPOSITE_NAME = "CompositeAcceptanceCondition"
_PYTEST_GATE_NAME = "PytestAcceptanceCondition"


# ID: 6f3e8b2a-7c1d-4e9a-b5f6-2a1c9d8e4b70
class TestGenAcceptanceCheck:
    """Detect a test-generation acceptance composite missing the pytest gate."""

    @classmethod
    # ID: 9d2c5a1e-3f7b-4c8a-9e6d-1b4f7a2c8e93
    def check(cls, tree: ast.AST, file_path: Path) -> list[str]:
        """Return violations if the file builds an acceptance composite
        without including PytestAcceptanceCondition among its conditions.

        No violation is raised if the file constructs no composite at all —
        that is out of scope for this check (it targets drift in an existing
        wiring point, not the presence of the wiring point itself).
        """
        composite_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and cls._call_name(node) == _COMPOSITE_NAME
        ]

        violations: list[str] = []
        for call in composite_calls:
            if not cls._includes_pytest_gate(call):
                line = getattr(call, "lineno", "?")
                violations.append(
                    f"{file_path}:{line} - {_COMPOSITE_NAME}(...) does not include "
                    f"{_PYTEST_GATE_NAME} among its conditions. ADR-135 D6's "
                    f"10/10 recovery-rate evidence is conditioned on a runtime "
                    f"execution signal inside the acceptance loop, not a "
                    f"static-only gate (ADR-140 Amendment 2026-07-14, later; #791)."
                )
        return violations

    @staticmethod
    def _call_name(node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    @classmethod
    def _includes_pytest_gate(cls, composite_call: ast.Call) -> bool:
        if not composite_call.args:
            return False
        first_arg = composite_call.args[0]
        if not isinstance(first_arg, ast.List):
            return False
        return any(
            isinstance(elt, ast.Call) and cls._call_name(elt) == _PYTEST_GATE_NAME
            for elt in first_arg.elts
        )
