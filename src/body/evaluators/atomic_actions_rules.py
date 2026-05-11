# src/body/evaluators/atomic_actions_rules.py
"""Atomic action contract — data shape, AST predicates, and validation rules.

This module answers: "what does it mean to be a well-formed atomic action?"

It owns:
- AtomicActionViolation — the violation record produced by rule functions
  and consumed by both the orchestrator (AtomicActionsEvaluator) and the
  formatter (atomic_actions_format.format_atomic_action_violations).
- AST predicates — pure inspection functions that identify whether an
  AsyncFunctionDef looks like an atomic action.
- Rule functions — produce violations when the @atomic_action decorator
  or the returned ActionResult is malformed.

LAYER: body/evaluators — read-only AST inspection only. No filesystem
writes, no DB access, no Will-layer imports. Functions are module-level
and take all inputs explicitly; no instance state.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
# ID: 6f296fc1-4fc3-4da3-b38d-b712ab452667
class AtomicActionViolation:
    """Violation of atomic action pattern contract."""

    file_path: Path
    function_name: str
    rule_id: str
    message: str
    line_number: int | None = None
    severity: str = "error"
    suggested_fix: str | None = None


# ID: c61f81e9-5e68-47f7-af7f-8899ab5c6045
def is_atomic_action_candidate(node: ast.AsyncFunctionDef) -> bool:
    """Return True if the function looks like it intends to be an atomic action.

    A candidate is any async function whose name ends with '_internal',
    or that carries an @atomic_action decorator (bare or called), or
    whose return type annotation is ActionResult.
    """
    if node.name.endswith("_internal"):
        return True
    if _has_atomic_action_decorator(node):
        return True
    if _returns_action_result(node):
        return True
    return False


def _has_atomic_action_decorator(node: ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "atomic_action":
            return True
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
            if decorator.func.id == "atomic_action":
                return True
    return False


def _returns_action_result(node: ast.AsyncFunctionDef) -> bool:
    if not node.returns:
        return False
    if isinstance(node.returns, ast.Name):
        return node.returns.id == "ActionResult"
    if isinstance(node.returns, ast.Subscript) and isinstance(
        node.returns.value, ast.Name
    ):
        return node.returns.value.id == "ActionResult"
    return False


# ID: 0266bc9f-720b-402d-baac-637bc425543a
def validate_atomic_action(
    file_path: Path,
    node: ast.AsyncFunctionDef,
    source: str,
) -> list[AtomicActionViolation]:
    """Run all contract checks on a single atomic-action candidate.

    Returns the combined list of violations across three sub-checks:
      1. @atomic_action decorator presence + required metadata fields.
      2. ActionResult return-type annotation presence.
      3. Each `return ActionResult(...)` statement carries required fields
         and uses a dict literal for `data`.
    """
    violations: list[AtomicActionViolation] = []

    if not _has_atomic_action_decorator(node):
        violations.append(
            AtomicActionViolation(
                file_path=file_path,
                function_name=node.name,
                rule_id="action_must_have_decorator",
                message=f"Atomic action '{node.name}' missing @atomic_action decorator",
                line_number=node.lineno,
                severity="error",
                suggested_fix=(
                    "Add @atomic_action decorator with action_id, intent, impact, and policies"
                ),
            )
        )

    if not _returns_action_result(node):
        violations.append(
            AtomicActionViolation(
                file_path=file_path,
                function_name=node.name,
                rule_id="action_must_return_result",
                message=f"Atomic action '{node.name}' must return ActionResult",
                line_number=node.lineno,
                severity="error",
                suggested_fix="Add '-> ActionResult' return type annotation",
            )
        )

    if _has_atomic_action_decorator(node):
        violations.extend(_validate_decorator_metadata(file_path, node, source))

    violations.extend(_validate_return_statements(file_path, node))
    return violations


def _validate_decorator_metadata(
    file_path: Path,
    node: ast.AsyncFunctionDef,
    source: str,
) -> list[AtomicActionViolation]:
    violations: list[AtomicActionViolation] = []
    decorator: ast.Call | None = None

    for dec in node.decorator_list:
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Name)
            and dec.func.id == "atomic_action"
        ):
            decorator = dec
            break

    if not decorator:
        return violations

    decorator_args: dict[str, Any] = {}

    for keyword in decorator.keywords:
        if isinstance(keyword.value, ast.Constant):
            decorator_args[keyword.arg] = keyword.value.value
        elif isinstance(keyword.value, ast.Attribute):
            # Example: ActionImpact.LOW
            base = keyword.value.value
            if isinstance(base, ast.Name):
                decorator_args[keyword.arg] = f"{base.id}.{keyword.value.attr}"
        elif isinstance(keyword.value, ast.List):
            decorator_args[keyword.arg] = [
                elt.value for elt in keyword.value.elts if isinstance(elt, ast.Constant)
            ]

    required_fields = {
        "action_id": "Unique identifier for this action",
        "intent": "Clear statement of purpose",
        "impact": "ActionImpact classification",
        "policies": "List of constitutional policies validated",
    }

    for field, description in required_fields.items():
        if field not in decorator_args:
            violations.append(
                AtomicActionViolation(
                    file_path=file_path,
                    function_name=node.name,
                    rule_id="decorator_missing_required_field",
                    message=(
                        f"@atomic_action missing required field '{field}': {description}"
                    ),
                    line_number=node.lineno,
                    severity="error",
                    suggested_fix=f"Add {field}=... to @atomic_action decorator",
                )
            )

    if "action_id" in decorator_args:
        action_id = decorator_args["action_id"]
        if not isinstance(action_id, str) or "." not in action_id:
            violations.append(
                AtomicActionViolation(
                    file_path=file_path,
                    function_name=node.name,
                    rule_id="invalid_action_id_format",
                    message=f"action_id '{action_id}' must use dot notation",
                    line_number=node.lineno,
                    severity="warning",
                    suggested_fix="Use category.name format for action_id",
                )
            )

    return violations


def _validate_return_statements(
    file_path: Path,
    node: ast.AsyncFunctionDef,
) -> list[AtomicActionViolation]:
    violations: list[AtomicActionViolation] = []

    for child in ast.walk(node):
        if (
            isinstance(child, ast.Return)
            and child.value
            and isinstance(child.value, ast.Call)
        ):
            call = child.value
            if isinstance(call.func, ast.Name) and call.func.id == "ActionResult":
                violations.extend(
                    _validate_action_result_call(
                        file_path,
                        node.name,
                        child,
                        child.lineno,
                    )
                )

    return violations


def _validate_action_result_call(
    file_path: Path,
    function_name: str,
    return_node: ast.Return,
    line_number: int,
) -> list[AtomicActionViolation]:
    violations: list[AtomicActionViolation] = []

    call = return_node.value
    if not isinstance(call, ast.Call):
        return violations

    result_args: dict[str, ast.AST] = {k.arg: k.value for k in call.keywords if k.arg}

    required_fields = ["action_id", "ok", "data"]
    for field in required_fields:
        if field not in result_args:
            violations.append(
                AtomicActionViolation(
                    file_path=file_path,
                    function_name=function_name,
                    rule_id="result_missing_required_field",
                    message=f"ActionResult missing required field '{field}'",
                    line_number=line_number,
                    severity="error",
                    suggested_fix=f"Add {field}=... to ActionResult constructor",
                )
            )

    if "data" in result_args:
        data_value = result_args["data"]
        if not isinstance(data_value, ast.Dict):
            violations.append(
                AtomicActionViolation(
                    file_path=file_path,
                    function_name=function_name,
                    rule_id="result_must_be_structured",
                    message="ActionResult.data must be a dictionary literal",
                    line_number=line_number,
                    severity="warning",
                    suggested_fix="Use data={...} with explicit key-value pairs",
                )
            )

    return violations
