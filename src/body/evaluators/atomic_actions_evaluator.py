# src/body/evaluators/atomic_actions_evaluator.py
# ID: 8c95de30-861b-4908-bb93-ab272d4039be
"""Atomic Actions Evaluator - AUDIT Phase Component.

Validates code compliance with the atomic actions pattern.

Constitutional Alignment:
- Phase: AUDIT (Quality assessment and pattern detection)
- Authority: POLICY (Enforces constitutional atomic actions pattern)
- Purpose: Validate atomic action compliance across codebase
- Self-contained: No external checker dependencies

PURIFIED (V2.7.4)
- Removed Will-layer 'DecisionTracer' to satisfy architecture.layers.no_body_to_will.
- Preserves 100% of original AST analysis and validation logic.
- Rationale is now returned in metadata for Will-layer consumption.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.component_primitive import ComponentResult
from shared.logger import getLogger

from .base_evaluator import BaseEvaluator


logger = getLogger(__name__)


# ID: d06f140e-d783-4434-a1fe-555183d03d7d
@dataclass
# ID: d8aa3d3e-47bf-4cf6-82f0-4732f899dfc8
class AtomicActionViolation:
    """Violation of atomic action pattern contract."""

    file_path: Path
    function_name: str
    rule_id: str
    message: str
    line_number: int | None = None
    severity: str = "error"
    suggested_fix: str | None = None


# ID: 54c63404-6a42-4ec3-9b88-8a039d52d7ec
class AtomicActionsEvaluator(BaseEvaluator):
    """Evaluate codebase for atomic action pattern compliance.

    This is a fully self-contained V2 component with no external dependencies.
    All AST analysis and validation logic is internal to this component.
    """

    # ID: a9bd8873-8696-4f14-a055-a32ba0ecd956
    async def execute(self, repo_root: Path, **kwargs: Any) -> ComponentResult:
        """Execute the atomic actions compliance audit."""
        start_time = time.time()
        src_dir = repo_root / "src"

        violations: list[AtomicActionViolation] = []
        total_actions = 0

        if not src_dir.exists():
            logger.warning("Source directory not found: %s", src_dir)
            return await self._create_result(
                ok=True,
                data={
                    "total_actions": 0,
                    "compliant_actions": 0,
                    "compliance_rate": 100.0,
                    "violations": [],
                },
                confidence=1.0,
                duration=0.0,
                rationale="Source directory missing; no actions audited.",
            )

        # 1) Sensation: scan all Python files in src/
        for py_file in src_dir.rglob("*.py"):
            # Skip private modules (except __init__.py) and test files
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue
            if "test" in str(py_file):
                continue

            file_violations, file_actions = self._check_file(py_file)
            violations.extend(file_violations)
            total_actions += file_actions

        # 2) Analysis: calculate metrics
        compliant_actions = total_actions - len(
            [v for v in violations if v.severity == "error"]
        )
        compliance_rate = (
            (compliant_actions / total_actions * 100.0) if total_actions > 0 else 100.0
        )
        has_errors = any(v.severity == "error" for v in violations)

        # 3) Decision tracing: preserved logic, moved to metadata
        rationale = (
            f"Audited {total_actions} actions. Compliance: {compliance_rate:.1f}%"
        )

        violation_dicts = [
            {
                "file": str(
                    v.file_path.relative_to(repo_root)
                    if v.file_path.is_absolute()
                    else v.file_path
                ),
                "function": v.function_name,
                "rule": v.rule_id,
                "message": v.message,
                "severity": v.severity,
                "line": v.line_number,
                "suggested_fix": v.suggested_fix,
            }
            for v in violations
        ]

        return await self._create_result(
            ok=not has_errors,
            data={
                "total_actions": total_actions,
                "compliant_actions": compliant_actions,
                "compliance_rate": compliance_rate,
                "violations": violation_dicts,
            },
            confidence=1.0,
            duration=time.time() - start_time,
            rationale=rationale,
        )

    # =========================================================================
    # THE CORE LOGIC (Restored with 100% Fidelity)
    # =========================================================================

    def _check_file(self, file_path: Path) -> tuple[list[AtomicActionViolation], int]:
        """Check a single file for atomic action pattern compliance."""
        violations: list[AtomicActionViolation] = []
        action_count = 0

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(
                    node, ast.AsyncFunctionDef
                ) and self._is_atomic_action_candidate(node):
                    action_count += 1
                    violations.extend(
                        self._validate_atomic_action(file_path, node, source)
                    )

        except SyntaxError as e:
            violations.append(
                AtomicActionViolation(
                    file_path=file_path,
                    function_name="<parse_error>",
                    rule_id="syntax_error",
                    message=f"Syntax error: {e}",
                    severity="error",
                )
            )
        except Exception as e:
            logger.error("Error checking %s: %s", file_path, e, exc_info=True)

        return (violations, action_count)

    def _is_atomic_action_candidate(self, node: ast.AsyncFunctionDef) -> bool:
        if node.name.endswith("_internal"):
            return True
        if self._has_atomic_action_decorator(node):
            return True
        if self._returns_action_result(node):
            return True
        return False

    def _has_atomic_action_decorator(self, node: ast.AsyncFunctionDef) -> bool:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "atomic_action":
                return True
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if decorator.func.id == "atomic_action":
                    return True
        return False

    def _returns_action_result(self, node: ast.AsyncFunctionDef) -> bool:
        if not node.returns:
            return False
        if isinstance(node.returns, ast.Name):
            return node.returns.id == "ActionResult"
        if isinstance(node.returns, ast.Subscript) and isinstance(
            node.returns.value, ast.Name
        ):
            return node.returns.value.id == "ActionResult"
        return False

    def _validate_atomic_action(
        self,
        file_path: Path,
        node: ast.AsyncFunctionDef,
        source: str,
    ) -> list[AtomicActionViolation]:
        violations: list[AtomicActionViolation] = []

        if not self._has_atomic_action_decorator(node):
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

        if not self._returns_action_result(node):
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

        if self._has_atomic_action_decorator(node):
            violations.extend(
                self._validate_decorator_metadata(file_path, node, source)
            )

        violations.extend(self._validate_return_statements(file_path, node))
        return violations

    def _validate_decorator_metadata(
        self,
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
                    elt.value
                    for elt in keyword.value.elts
                    if isinstance(elt, ast.Constant)
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
        self,
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
                        self._validate_action_result_call(
                            file_path,
                            node.name,
                            child,
                            child.lineno,
                        )
                    )

        return violations

    def _validate_action_result_call(
        self,
        file_path: Path,
        function_name: str,
        return_node: ast.Return,
        line_number: int,
    ) -> list[AtomicActionViolation]:
        violations: list[AtomicActionViolation] = []

        call = return_node.value
        if not isinstance(call, ast.Call):
            return violations

        result_args: dict[str, ast.AST] = {
            k.arg: k.value for k in call.keywords if k.arg
        }

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


# ID: 88cd5c3d-aece-498a-935f-df133086a948
def format_atomic_action_violations(
    violations: list[AtomicActionViolation],
    verbose: bool = False,
) -> str:
    """Format atomic action violations for display."""
    if not violations:
        return "✅ All atomic actions follow constitutional pattern!"

    output: list[str] = ["\n❌ Found Atomic Action Violations:\n"]

    by_file: dict[Path, list[AtomicActionViolation]] = {}
    for v in violations:
        by_file.setdefault(v.file_path, []).append(v)

    for file_path, file_violations in sorted(by_file.items(), key=lambda x: str(x[0])):
        output.append(f"\n📄 {file_path}")
        for v in file_violations:
            severity_marker = "🔴" if v.severity == "error" else "🟡"
            output.append(
                f"  {severity_marker} {v.function_name} (line {v.line_number or '?'})"
            )
            output.append(f"     Rule: {v.rule_id}")
            output.append(f"     {v.message}")
            if verbose and v.suggested_fix:
                output.append(f"     💡 Fix: {v.suggested_fix}")

    return "\n".join(output)
