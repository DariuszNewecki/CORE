# src/mind/logic/engines/ast_gate/checks/prompt_model_checks.py
"""
AST checks for AI Prompt Governance constitutional enforcement.

Detects direct calls to make_request_async() or make_request() that bypass
the PromptModel governed surface.

CONSTITUTIONAL ALIGNMENT:
- Enforces: ai.prompt.model_required
- Authority: .intent/rules/ai/prompt_governance.json
- All AI invocations MUST route through PromptModel.invoke().
"""

from __future__ import annotations

import ast
from typing import Any

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: pm-checks-001
# ID: cd452337-4e1a-48a4-97e6-b47599a5496a
class PromptModelChecks:
    """
    Enforces PromptModel usage as the sole governed surface for AI invocations.

    Detects direct calls to make_request_async() or make_request() anywhere
    in the codebase — these are only permitted inside the PromptModel
    implementation and LLMClient itself (excluded via scope in mapping).
    """

    @staticmethod
    # ID: pm-checks-002
    # ID: e9d22c46-36ea-4ca8-bd72-d58e787c4068
    def check_prompt_model_required(
        tree: ast.AST,
        params: dict[str, Any],
    ) -> list[str]:
        """
        Detect direct calls to forbidden LLM invocation methods.

        Walks the entire module AST and flags any call whose method name
        matches the configured forbidden_calls list. The PromptModel
        implementation and LLMClient are excluded via scope in the
        enforcement mapping — not here. This check is intentionally
        scope-unaware: it flags ALL occurrences and lets the mapping
        decide what to exclude.

        Args:
            tree: Parsed AST of the source file.
            params: Enforcement params from the mapping YAML.
                    Expected key: 'forbidden_calls' (list[str]).

        Returns:
            List of violation strings (empty = compliant).
        """
        forbidden: set[str] = set(params.get("forbidden_calls", []))
        if not forbidden:
            return []

        violations: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            # Resolve the full dotted name of the call target
            name = ASTHelpers.full_attr_name(node.func)
            if name is None:
                continue

            # Match on the final method name component only.
            # e.g. "writer_client.make_request_async" -> "make_request_async"
            method_name = name.split(".")[-1]

            if method_name in forbidden:
                line = getattr(node, "lineno", "?")
                violations.append(
                    f"Line {line}: direct call to '{method_name}()' detected. "
                    f"Use PromptModel.invoke() instead. "
                    f"[ai.prompt.model_required]"
                )

        return violations
