# src/mind/governance/pattern_validator.py
"""
Constitutional Pattern Validator.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml
from shared.logger import getLogger

# Import shared models
from shared.models.pattern_graph import PatternValidationResult, PatternViolation

logger = getLogger(__name__)

_NO_DEFAULT = object()


# ID: 7f13c397-c10f-4b3e-bb09-19e4357f8a95
class PatternValidator:
    """
    Validates code against constitutional design patterns.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.patterns_dir = repo_root / ".intent" / "charter" / "patterns"
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> dict:
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

    # ID: 52ab1565-5e61-4a61-a0eb-c4785cde6372
    async def validate(
        self, code: str, pattern_id: str, component_type: str = "command"
    ) -> PatternValidationResult:
        violations = []
        try:
            tree = ast.parse(code)
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
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if pattern_id == "inspect_pattern":
                    violations.extend(self._check_inspect_pattern(node))
                elif pattern_id == "action_pattern":
                    violations.extend(self._check_action_pattern(node))
                elif pattern_id == "check_pattern":
                    violations.extend(self._check_check_pattern(node))
        return violations

    def _check_inspect_pattern(self, node: ast.FunctionDef) -> list[PatternViolation]:
        violations = []
        if self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    pattern_id="inspect_pattern",
                    violation_type="forbidden_parameter",
                    message="Inspect commands must not have --write flag (read-only guarantee)",
                    severity="error",
                )
            )
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
        violations = []
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
        violations = []
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
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if pattern_id == "stateful_service":
                    violations.extend(self._check_stateful_service(node))
                elif pattern_id == "repository_pattern":
                    violations.extend(self._check_repository_pattern(node))
        return violations

    def _check_stateful_service(self, node: ast.ClassDef) -> list[PatternViolation]:
        violations = []
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
        violations = []
        method_names = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
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
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if pattern_id == "cognitive_agent":
                    violations.extend(self._check_cognitive_agent(node))
        return violations

    def _check_cognitive_agent(self, node: ast.ClassDef) -> list[PatternViolation]:
        violations = []
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
        for arg in node.args.args:
            if arg.arg == param_name:
                return True
        for arg in node.args.kwonlyargs:
            if arg.arg == param_name:
                return True
        return False

    def _get_parameter_default(self, node: ast.FunctionDef, param_name: str) -> any:
        param_idx = None
        for i, arg in enumerate(node.args.args):
            if arg.arg == param_name:
                param_idx = i
                break
        if param_idx is None:
            for i, arg in enumerate(node.args.kwonlyargs):
                if arg.arg == param_name:
                    if i < len(node.args.kw_defaults):
                        default = node.args.kw_defaults[i]
                        if isinstance(default, ast.Constant):
                            return default.value
            return None
        defaults_start = len(node.args.args) - len(node.args.defaults)
        default_idx = param_idx - defaults_start
        if default_idx < 0 or default_idx >= len(node.args.defaults):
            return None
        default = node.args.defaults[default_idx]
        if isinstance(default, ast.Constant):
            return default.value
        return None
