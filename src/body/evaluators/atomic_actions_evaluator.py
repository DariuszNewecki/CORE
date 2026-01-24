# src/body/evaluators/atomic_actions_evaluator.py

"""
Atomic Actions Evaluator - AUDIT Phase Component.
Validates code compliance with the atomic actions pattern.

Constitutional Alignment:
- Phase: AUDIT (Quality assessment and pattern detection)
- Authority: POLICY (Enforces constitutional atomic actions pattern)
- Purpose: Validate atomic action compliance across codebase
- Self-contained: No external checker dependencies

Validation rules (from .intent/charter/patterns/atomic_actions.json):
1. action_must_return_result: Every atomic action MUST return ActionResult
2. result_must_be_structured: ActionResult.data MUST be a dictionary
3. action_must_declare_metadata: Actions must have @atomic_action decorator
4. action_must_declare_impact: Actions should declare their ActionImpact
5. governance_never_bypassed: No action can skip constitutional validation
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: d06f140e-d783-4434-a1fe-555183d03d7d
class AtomicActionViolation:
    """Violation of atomic action pattern contract."""

    file_path: Path
    function_name: str
    rule_id: str
    message: str
    line_number: int | None = None
    severity: str = "error"
    suggested_fix: str | None = None


# ID: 8c95de30-861b-4908-bb93-ab272d4039be
class AtomicActionsEvaluator(Component):
    """
    Evaluates codebase for atomic action pattern compliance.

    This is a fully self-contained V2 Component with no external dependencies.
    All AST analysis and validation logic is internal to this component.

    Checks:
    - @atomic_action decorator presence
    - ActionResult return types
    - Structured metadata declaration (action_id, intent, impact, policies)
    - Return statement validation
    """

    @property
    # ID: b73eba23-e6c1-4eb9-930c-dc033915a148
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    # ID: a9bd8873-8696-4f14-a055-a32ba0ecd956
    async def execute(self, repo_root: Path, **kwargs: Any) -> ComponentResult:
        """
        Execute the atomic actions compliance audit.

        Args:
            repo_root: Repository root

        Returns:
            ComponentResult with compliance metrics and violation details
        """
        start_time = time.time()
        src_dir = repo_root / "src"

        violations: list[AtomicActionViolation] = []
        total_actions = 0
        compliant_actions = 0

        if not src_dir.exists():
            logger.warning("Source directory not found: %s", src_dir)
            return ComponentResult(
                component_id=self.component_id,
                ok=True,
                data={
                    "total_actions": 0,
                    "compliant_actions": 0,
                    "compliance_rate": 100.0,
                    "violations": [],
                },
                phase=self.phase,
                confidence=1.0,
                duration_sec=time.time() - start_time,
            )

        # Scan all Python files in src/
        for py_file in src_dir.rglob("*.py"):
            # Skip private modules (except __init__.py) and test files
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue
            if "test" in str(py_file):
                continue

            file_violations, file_actions = self._check_file(py_file)
            violations.extend(file_violations)
            total_actions += file_actions
            compliant_actions += file_actions - len(
                [v for v in file_violations if v.severity == "error"]
            )

        # Calculate metrics
        compliance_rate = (
            (compliant_actions / total_actions * 100.0) if total_actions > 0 else 100.0
        )
        has_errors = any(v.severity == "error" for v in violations)

        # Convert violations to dicts for ComponentResult
        violation_dicts = [
            {
                "file": str(v.file_path),
                "function": v.function_name,
                "rule": v.rule_id,
                "message": v.message,
                "severity": v.severity,
                "line": v.line_number,
                "suggested_fix": v.suggested_fix,
            }
            for v in violations
        ]

        return ComponentResult(
            component_id=self.component_id,
            ok=not has_errors,
            data={
                "total_actions": total_actions,
                "compliant_actions": compliant_actions,
                "compliance_rate": compliance_rate,
                "violations": violation_dicts,
            },
            phase=self.phase,
            confidence=1.0,
            metadata={
                "has_errors": has_errors,
                "violation_count": len(violations),
            },
            duration_sec=time.time() - start_time,
        )

    def _check_file(self, file_path: Path) -> tuple[list[AtomicActionViolation], int]:
        """
        Check a single file for atomic action pattern compliance.

        Returns:
            Tuple of (violations, action_count)
        """
        violations = []
        action_count = 0

        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
                tree = ast.parse(source)

            # Walk AST looking for async function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef):
                    if self._is_atomic_action_candidate(node):
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
            logger.error("Error checking %s: %s", file_path, e)

        return (violations, action_count)

    def _is_atomic_action_candidate(self, node: ast.AsyncFunctionDef) -> bool:
        """
        Determine if function is an atomic action candidate.

        Candidates are async functions that:
        - End with '_internal' suffix (convention for atomic actions)
        - Have @atomic_action decorator
        - Return ActionResult type annotation
        """
        if node.name.endswith("_internal"):
            return True
        if self._has_atomic_action_decorator(node):
            return True
        if self._returns_action_result(node):
            return True
        return False

    def _has_atomic_action_decorator(self, node: ast.AsyncFunctionDef) -> bool:
        """Check if function has @atomic_action decorator."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "atomic_action":
                return True
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    if decorator.func.id == "atomic_action":
                        return True
        return False

    def _returns_action_result(self, node: ast.AsyncFunctionDef) -> bool:
        """Check if function is annotated to return ActionResult."""
        if not node.returns:
            return False
        if isinstance(node.returns, ast.Name):
            return node.returns.id == "ActionResult"
        if isinstance(node.returns, ast.Subscript):
            if isinstance(node.returns.value, ast.Name):
                return node.returns.value.id == "ActionResult"
        return False

    def _validate_atomic_action(
        self, file_path: Path, node: ast.AsyncFunctionDef, source: str
    ) -> list[AtomicActionViolation]:
        """
        Validate atomic action against constitutional requirements.

        Constitutional rules:
        1. Must have @atomic_action decorator
        2. Must return ActionResult type
        3. ActionResult must have required fields
        4. Should declare ActionImpact
        """
        violations = []

        # Rule 1: Check for decorator
        if not self._has_atomic_action_decorator(node):
            violations.append(
                AtomicActionViolation(
                    file_path=file_path,
                    function_name=node.name,
                    rule_id="action_must_have_decorator",
                    message=f"Atomic action '{node.name}' missing @atomic_action decorator",
                    line_number=node.lineno,
                    severity="error",
                    suggested_fix="Add @atomic_action decorator with action_id, intent, impact, and policies",
                )
            )

        # Rule 2: Check return type
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

        # Rule 3: Validate decorator metadata
        if self._has_atomic_action_decorator(node):
            decorator_violations = self._validate_decorator_metadata(
                file_path, node, source
            )
            violations.extend(decorator_violations)

        # Rule 4: Validate return statements
        result_violations = self._validate_return_statements(file_path, node)
        violations.extend(result_violations)

        return violations

    def _validate_decorator_metadata(
        self, file_path: Path, node: ast.AsyncFunctionDef, source: str
    ) -> list[AtomicActionViolation]:
        """
        Validate @atomic_action decorator has required metadata.

        Required fields (from atomic_actions.yaml):
        - action_id: Unique identifier
        - intent: Clear statement of purpose
        - impact: ActionImpact enum value
        - policies: List of policy IDs this action validates
        """
        violations = []

        # Find the @atomic_action decorator
        decorator = None
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name) and dec.func.id == "atomic_action":
                    decorator = dec
                    break

        if not decorator:
            return violations

        # Extract decorator arguments
        decorator_args = {}
        for keyword in decorator.keywords:
            if isinstance(keyword.value, ast.Constant):
                decorator_args[keyword.arg] = keyword.value.value
            elif isinstance(keyword.value, ast.Attribute):
                decorator_args[keyword.arg] = (
                    f"{keyword.value.value.id}.{keyword.value.attr}"
                )
            elif isinstance(keyword.value, ast.List):
                decorator_args[keyword.arg] = [
                    elt.value
                    for elt in keyword.value.elts
                    if isinstance(elt, ast.Constant)
                ]

        # Check required fields
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
                        message=f"@atomic_action missing required field '{field}': {description}",
                        line_number=node.lineno,
                        severity="error",
                        suggested_fix=f"Add {field}=... to @atomic_action decorator",
                    )
                )

        # Validate action_id format
        if "action_id" in decorator_args:
            action_id = decorator_args["action_id"]
            if not isinstance(action_id, str) or "." not in action_id:
                violations.append(
                    AtomicActionViolation(
                        file_path=file_path,
                        function_name=node.name,
                        rule_id="invalid_action_id_format",
                        message=f"action_id '{action_id}' must use dot notation (e.g., 'fix.ids', 'check.imports')",
                        line_number=node.lineno,
                        severity="warning",
                        suggested_fix="Use category.name format for action_id",
                    )
                )

        return violations

    def _validate_return_statements(
        self, file_path: Path, node: ast.AsyncFunctionDef
    ) -> list[AtomicActionViolation]:
        """
        Validate return statements create valid ActionResult instances.

        Check that:
        - ActionResult() has required fields: action_id, ok, data
        - data is a dictionary literal (not a variable)
        """
        violations = []

        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value:
                if isinstance(child.value, ast.Call):
                    if isinstance(child.value.func, ast.Name):
                        if child.value.func.id == "ActionResult":
                            violations.extend(
                                self._validate_action_result_call(
                                    file_path, node.name, child, child.lineno
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
        """Validate ActionResult(...) constructor call."""
        violations = []
        call = return_node.value

        if not isinstance(call, ast.Call):
            return violations

        # Extract keyword arguments
        result_args = {}
        for keyword in call.keywords:
            result_args[keyword.arg] = keyword.value

        # Check required fields
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

        # Validate data is a dict literal
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
    violations: list[AtomicActionViolation], verbose: bool = False
) -> str:
    """
    Format atomic action violations for display.

    This formatter is kept for backward compatibility with CLI commands.
    """
    if not violations:
        return "✅ All atomic actions follow constitutional pattern!"

    output = []
    output.append("\n❌ Found Atomic Action Violations:\n")

    # Group by file
    by_file: dict[Path, list[AtomicActionViolation]] = {}
    for v in violations:
        by_file.setdefault(v.file_path, []).append(v)

    for file_path, file_violations in sorted(by_file.items()):
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
