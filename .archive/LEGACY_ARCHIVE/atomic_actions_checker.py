# src/body/cli/logic/atomic_actions_checker.py

"""
Constitutional checker for atomic actions pattern compliance.

Validates that all atomic actions in CORE follow the universal contract
defined in .intent/charter/patterns/atomic_actions.json

Validation rules (from constitutional pattern):
1. action_must_return_result: Every atomic action MUST return ActionResult
2. result_must_be_structured: ActionResult.data MUST be a dictionary
3. action_must_declare_metadata: Actions must have @atomic_action decorator
4. action_must_declare_impact: Actions should declare their ActionImpact
5. governance_never_bypassed: No action can skip constitutional validation
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

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


@dataclass
# ID: 196f33b6-63ec-4f1f-90d7-1ee0bbca85b2
class AtomicActionCheckResult:
    """Results from atomic action pattern checking."""

    total_actions: int
    compliant_actions: int
    violations: list[AtomicActionViolation]

    @property
    # ID: cdd70707-6399-4303-9954-e81e848b577a
    def compliance_rate(self) -> float:
        """Calculate compliance percentage."""
        if self.total_actions == 0:
            return 100.0
        return self.compliant_actions / self.total_actions * 100.0

    @property
    # ID: a6aed230-51c5-45e4-a1a9-d7454b8fd695
    def has_errors(self) -> bool:
        """Check if any error-level violations exist."""
        return any(v.severity == "error" for v in self.violations)


# ID: dc1fd1d6-683c-421f-b9fb-39a85772c389
class AtomicActionsChecker:
    """
    Validates code compliance with atomic actions pattern.

    Constitutional enforcement of:
    - ActionResult return types
    - @atomic_action decorator presence
    - ActionImpact declarations
    - Structured data contracts
    """

    def __init__(self, repo_root: Path):
        """Initialize checker with repository root."""
        self.repo_root = repo_root
        self.src_dir = repo_root / "src"

    # ID: d5b8dc17-dbdd-4b84-acc1-da52a274ed48
    def check_all(self) -> AtomicActionCheckResult:
        """
        Check all atomic actions in the codebase.

        Returns:
            AtomicActionCheckResult with violations and statistics
        """
        violations = []
        total_actions = 0
        compliant_actions = 0
        if not self.src_dir.exists():
            logger.warning("Source directory not found: %s", self.src_dir)
            return AtomicActionCheckResult(
                total_actions=0, compliant_actions=0, violations=[]
            )
        for py_file in self.src_dir.rglob("*.py"):
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
        return AtomicActionCheckResult(
            total_actions=total_actions,
            compliant_actions=compliant_actions,
            violations=violations,
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
            logger.error("Error checking {file_path}: %s", e)
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
            decorator_violations = self._validate_decorator_metadata(
                file_path, node, source
            )
            violations.extend(decorator_violations)
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
        decorator = None
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name) and dec.func.id == "atomic_action":
                    decorator = dec
                    break
        if not decorator:
            return violations
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
        result_args = {}
        for keyword in call.keywords:
            result_args[keyword.arg] = keyword.value
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
    violations: list[AtomicActionViolation], verbose: bool = False
) -> str:
    """Format atomic action violations for display."""
    if not violations:
        return "✅ All atomic actions follow constitutional pattern!"
    lines = [f"\n❌ Found {len(violations)} atomic action pattern violations:\n"]
    by_file: dict[Path, list[AtomicActionViolation]] = {}
    for v in violations:
        by_file.setdefault(v.file_path, []).append(v)
    for file_path, file_violations in sorted(by_file.items()):
        rel_path = (
            file_path.relative_to(Path.cwd())
            if Path.cwd() in file_path.parents
            else file_path
        )
        lines.append(f"\n📄 {rel_path}:")
        for v in file_violations:
            severity_icon = {"error": "❌", "warning": "⚠️", "info": "i"}[v.severity]
            lines.append(f"  {severity_icon} {v.function_name}:")
            lines.append(f"      Rule: {v.rule_id}")
            lines.append(f"      {v.message}")
            if verbose:
                if v.line_number:
                    lines.append(f"      Line: {v.line_number}")
                if v.suggested_fix:
                    lines.append(f"      Fix: {v.suggested_fix}")
    return "\n".join(lines)
