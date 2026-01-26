# src/body/services/policy_expression_evaluator.py

"""
Policy Expression Evaluator - Safe Boolean Expression Evaluation

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Evaluate policy expressions safely
- No CLI dependencies
- Reusable for governance checks

Extracted from cli/logic/validate.py to separate evaluation logic.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: review_context
# ID: 38a08d04-04d2-4196-bb0b-b95d2a227ae3
@dataclass
# ID: 24950f8a-5412-483a-9af7-e02427769ee7
class ReviewContext:
    """Context for policy expression evaluation."""

    risk_tier: str = "low"
    score: float = 0.0
    touches_critical_paths: bool = False
    checkpoint: bool = False
    canary: bool = False
    approver_quorum: bool = False


# ID: policy_expression_evaluator
# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class PolicyExpressionEvaluator:
    """
    Safely evaluates boolean policy expressions.

    SECURITY: Uses AST validation to ensure only safe operations.
    No arbitrary code execution possible.

    Usage:
        evaluator = PolicyExpressionEvaluator()
        context = {"risk_tier": "high", "checkpoint": True}
        result = evaluator.evaluate("risk_tier == 'high' and checkpoint", context)
    """

    # AST allowlist for safe policy evaluation
    _ALLOWED_NODES: ClassVar[set[type]] = {
        ast.Expression,
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.And,
        ast.Or,
        ast.Not,
        ast.In,
        ast.Eq,
        ast.NotEq,
    }

    # ID: evaluator_evaluate
    # ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
    def evaluate(self, expr: str, context: dict[str, Any]) -> bool:
        """
        Safely evaluate a boolean expression string against a context dictionary.

        SECURITY NOTE: This function uses eval() but is SAFE because:
        1. Input is parsed and validated via AST whitelist
        2. Only safe nodes are permitted (no calls, imports, attribute access)
        3. Builtins are disabled ({"__builtins__": {}})
        4. Only whitelisted context variables are available
        5. Used exclusively for evaluating policy conditions from .intent/

        This is verified safe code execution for constitutional governance.

        Args:
            expr: Boolean expression string
            context: Dictionary of allowed variables

        Returns:
            Evaluation result

        Raises:
            ValueError: If expression contains disallowed operations
        """
        # Normalize boolean literals
        expr = expr.replace(" true", " True").replace(" false", " False")

        # Layer 1: Parse to AST
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {e}") from e

        # Layer 2: AST Validation
        for node in ast.walk(tree):
            if type(node) not in self._ALLOWED_NODES:
                raise ValueError(
                    f"Disallowed node in expression: {type(node).__name__}"
                )

        # Layer 3: Restricted Execution (Sandboxing)
        # SECURITY: Using compile() on validated AST is safer than eval(str)
        # SECURITY: __builtins__ is empty to prevent access to globals
        compiled = compile(tree, "<policy_expr>", "eval")

        # SECURITY: context variables only
        try:
            return bool(eval(compiled, {"__builtins__": {}}, context))
        except Exception as e:
            raise ValueError(f"Expression evaluation failed: {e}") from e

    # ID: evaluator_validate_expression
    # ID: 0d1e2f3a-4b5c-6d7e-8f9a-0b1c2d3e4f5a
    def validate_expression(self, expr: str) -> tuple[bool, str | None]:
        """
        Validate expression without evaluating it.

        Args:
            expr: Expression to validate

        Returns:
            (is_valid, error_message)
        """
        try:
            # Normalize
            expr = expr.replace(" true", " True").replace(" false", " False")

            # Parse
            tree = ast.parse(expr, mode="eval")

            # Validate nodes
            for node in ast.walk(tree):
                if type(node) not in self._ALLOWED_NODES:
                    return (
                        False,
                        f"Disallowed operation: {type(node).__name__}",
                    )

            return True, None
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Validation error: {e}"
