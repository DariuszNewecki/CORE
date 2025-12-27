# src/mind/logic/engines/ast_gate/checks/purity_enforcement_check.py

"""
Enforces code purity rules via AST analysis.

Rules enforced:
- purity.stable_id_anchor: Public symbols must have # ID: <uuid> anchors
- purity.forbidden_decorators: No @capability, @meta, @owner decorators
- purity.forbidden_primitives: No eval/exec/compile/__import__ primitives

Ref: .intent/policies/code/purity.json
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from mind.governance.checks.rule_enforcement_check import RuleEnforcementCheck


PURITY_POLICY = Path(".intent/policies/code/purity.json")


# ID: f9e2d7c5-8b4a-6e1f-3d9c-2a7b5e8f4c1d
class PurityEnforcementCheck(RuleEnforcementCheck):
    """
    Enforces purity rules through AST-based constitutional checks.

    These rules are enforced by ast_gate engine with specific check_types.
    The engine handles the actual verification logic.

    Why AST instead of LLM:
    - Deterministic (no model variance)
    - Fast (no API calls)
    - Precise (exact pattern matching)
    - Cacheable (same code = same result)

    Ref: .intent/policies/code/purity.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "purity.stable_id_anchor",
        "purity.forbidden_decorators",
        "purity.forbidden_primitives",
    ]

    policy_file: ClassVar[Path] = PURITY_POLICY

    # These rules are enforced via ast_gate engine dispatch
    # No enforcement_methods needed - engine handles verification
    enforcement_methods: ClassVar[list] = []

    @property
    def _is_concrete_check(self) -> bool:
        return True
