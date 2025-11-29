# src/mind/governance/pattern_validator.py
# ID: pattern-validator-001

"""
Constitutional Pattern Validator.

Validates code against design patterns defined in .intent/charter/patterns/
at generation time (not test time). Part of the constitutional enforcement layer.

Pattern: stateless_transformer
See: .intent/charter/patterns/service_patterns.yaml#stateless_transformer
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import yaml
from shared.logger import getLogger

logger = getLogger(__name__)


@dataclass
# ID: 6e8b1d4f-fd61-4fc5-87f5-2c3701ccad48
class PatternViolation:
    """Represents a pattern violation found during validation."""

    pattern_id: str
    violation_type: str
    message: str
    severity: str = "error"  # error, warning


@dataclass
# ID: 555c90b7-ac59-4f54-9b14-3206ea9d73de
class PatternValidationResult:
    """Result of pattern validation."""

    pattern_id: str
    passed: bool
    violations: list[PatternViolation]

    @property
    # ID: 83d266c7-f437-47b8-a02a-aab70f315610
    def is_approved(self) -> bool:
        """Check if validation passed (no errors)."""
        errors = [v for v in self.violations if v.severity == "error"]
        return len(errors) == 0


# ID: 21952802-dee8-496d-85b3-5334a452e04a
class PatternValidator:
    """
    Validates code against constitutional design patterns.

    This is NOT a test suite. This is constitutional enforcement
    that runs at code generation time to prevent violations.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.patterns_dir = repo_root / ".intent" / "charter" / "patterns"
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> dict:
        """Load pattern specifications from YAML files."""
        patterns = {}

        if not self.patterns_dir.exists():
            logger.warning(f"Patterns directory not found: {self.patterns_dir}")
            return patterns

        for pattern_file in self.patterns_dir.glob("*_patterns.yaml"):
            try:
                with open(pattern_file) as f:
                    data = yaml.safe_load(f)
                    category = data.get("id", pattern_file.stem)
                    patterns[category] = data
                    logger.info(f"Loaded pattern spec: {category}")
            except Exception as e:
                logger.error(f"Failed to load {pattern_file}: {e}")

        return patterns

    # ID: 2d7d8e23-f4cf-49d8-a3c1-500e9b024949
    async def validate(
        self, code: str, pattern_id: str, component_type: str = "command"
    ) -> PatternValidationResult:
        """
        Validate code against specified pattern.

        Args:
            code: The generated code to validate
            pattern_id: Pattern to validate against (e.g., 'inspect_pattern')
            component_type: Type of component ('command', 'service', 'agent', 'workflow')

        Returns:
            PatternValidationResult with violations if any
        """
        violations = []

        try:
            # Parse code into AST
            tree = ast.parse(code)

            # Validate based on pattern type
            if pattern_id.endswith("_pattern") and component_type == "command":
                violations.extend(self._validate_command_pattern(tree, pattern_id))
            elif component_type == "service":
                violations.extend(self._validate_service_pattern(tree, pattern_id))
            elif component_type == "agent":
                violations.extend(self._validate_agent_pattern(tree, pattern_id))

        except SyntaxError as e:
            violations.append(
                PatternViolation(
                    pattern_id=pattern_id,
                    violation_type="syntax_error",
                    message=f"Code has syntax errors: {e}",
                    severity="error",
                )
            )

        passed = len([v for v in violations if v.severity == "error"]) == 0

        return PatternValidationResult(
            pattern_id=pattern_id, passed=passed, violations=violations
        )

    def _validate_command_pattern(
        self, tree: ast.AST, pattern_id: str
    ) -> list[PatternViolation]:
        """Validate command patterns (inspect, action, check, run, manage)."""
        violations = []

        # Find all function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check pattern-specific rules
                if pattern_id == "inspect_pattern":
                    violations.extend(self._check_inspect_pattern(node))
                elif pattern_id == "action_pattern":
                    violations.extend(self._check_action_pattern(node))
                elif pattern_id == "check_pattern":
                    violations.extend(self._check_check_pattern(node))

        return violations

    def _check_inspect_pattern(self, node: ast.FunctionDef) -> list[PatternViolation]:
        """Validate inspect pattern: read-only, no modifications."""
        violations = []

        # Inspect commands must NOT have --write flag
        if self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    pattern_id="inspect_pattern",
                    violation_type="forbidden_parameter",
                    message="Inspect commands must not have --write flag (read-only guarantee)",
                    severity="error",
                )
            )

        # Inspect commands should not have --apply or --force
        if self._has_parameter(node, "apply") or self._has_parameter(node, "force"):
            violations.append(
                PatternViolation(
                    pattern_id="inspect_pattern",
                    violation_type="forbidden_parameter",
                    message="Inspect commands must not modify state",
                    severity="error",
                )
            )

        return violations

    def _check_action_pattern(self, node: ast.FunctionDef) -> list[PatternViolation]:
        """Validate action pattern: dry-run by default, --write to execute."""
        violations = []

        # Action commands MUST have --write flag
        if not self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    pattern_id="action_pattern",
                    violation_type="missing_parameter",
                    message="Action commands must have --write flag for safety",
                    severity="error",
                )
            )
        else:
            # Check default value is False (dry-run by default)
            default = self._get_parameter_default(node, "write")
            if default is True:
                violations.append(
                    PatternViolation(
                        pattern_id="action_pattern",
                        violation_type="unsafe_default",
                        message="Action commands must default to dry-run (write=False)",
                        severity="error",
                    )
                )

        return violations

    def _check_check_pattern(self, node: ast.FunctionDef) -> list[PatternViolation]:
        """Validate check pattern: validation only, no modifications."""
        violations = []

        # Check commands should NOT have --write flag
        if self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    pattern_id="check_pattern",
                    violation_type="forbidden_parameter",
                    message="Check commands must not modify state (validation only)",
                    severity="error",
                )
            )

        return violations

    def _validate_service_pattern(
        self, tree: ast.AST, pattern_id: str
    ) -> list[PatternViolation]:
        """Validate service patterns."""
        violations = []

        # Find class definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if pattern_id == "stateful_service":
                    violations.extend(self._check_stateful_service(node))
                elif pattern_id == "repository_pattern":
                    violations.extend(self._check_repository_pattern(node))

        return violations

    def _check_stateful_service(self, node: ast.ClassDef) -> list[PatternViolation]:
        """Validate stateful service pattern."""
        violations = []

        # Check for __init__ method (should use dependency injection)
        has_init = any(
            isinstance(n, ast.FunctionDef) and n.name == "__init__" for n in node.body
        )

        if not has_init:
            violations.append(
                PatternViolation(
                    pattern_id="stateful_service",
                    violation_type="missing_init",
                    message="Stateful services should have __init__ for dependency injection",
                    severity="warning",
                )
            )

        return violations

    def _check_repository_pattern(self, node: ast.ClassDef) -> list[PatternViolation]:
        """Validate repository pattern."""
        violations = []

        # Repository should have standard CRUD methods
        method_names = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]

        # Check for at least some standard methods
        standard_methods = ["save", "find_by_id", "find_all", "delete"]
        has_standard = any(method in method_names for method in standard_methods)

        if not has_standard:
            violations.append(
                PatternViolation(
                    pattern_id="repository_pattern",
                    violation_type="missing_standard_methods",
                    message="Repository should implement standard data access methods",
                    severity="warning",
                )
            )

        return violations

    def _validate_agent_pattern(
        self, tree: ast.AST, pattern_id: str
    ) -> list[PatternViolation]:
        """Validate agent patterns."""
        violations = []

        # Find class definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if pattern_id == "cognitive_agent":
                    violations.extend(self._check_cognitive_agent(node))

        return violations

    def _check_cognitive_agent(self, node: ast.ClassDef) -> list[PatternViolation]:
        """Validate cognitive agent pattern."""
        violations = []

        # Cognitive agents should have execute method
        method_names = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]

        if "execute" not in method_names:
            violations.append(
                PatternViolation(
                    pattern_id="cognitive_agent",
                    violation_type="missing_execute",
                    message="Cognitive agents should implement execute() method",
                    severity="error",
                )
            )

        return violations

    def _has_parameter(self, node: ast.FunctionDef, param_name: str) -> bool:
        """Check if function has a specific parameter."""
        for arg in node.args.args:
            if arg.arg == param_name:
                return True
        for arg in node.args.kwonlyargs:
            if arg.arg == param_name:
                return True
        return False

    def _get_parameter_default(self, node: ast.FunctionDef, param_name: str) -> any:
        """Get default value for a parameter."""
        # Find parameter index
        param_idx = None
        for i, arg in enumerate(node.args.args):
            if arg.arg == param_name:
                param_idx = i
                break

        if param_idx is None:
            # Check keyword-only args
            for i, arg in enumerate(node.args.kwonlyargs):
                if arg.arg == param_name:
                    if i < len(node.args.kw_defaults):
                        default = node.args.kw_defaults[i]
                        if isinstance(default, ast.Constant):
                            return default.value
            return None

        # Get default value (counted from end)
        defaults_start = len(node.args.args) - len(node.args.defaults)
        default_idx = param_idx - defaults_start

        if default_idx < 0 or default_idx >= len(node.args.defaults):
            return None

        default = node.args.defaults[default_idx]
        if isinstance(default, ast.Constant):
            return default.value

        return None
