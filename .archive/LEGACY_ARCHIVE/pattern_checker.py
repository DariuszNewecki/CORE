# src/body/cli/logic/pattern_checker.py

"""
Pattern compliance checker for CORE.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger
from shared.models.pattern_graph import PatternValidationResult as PatternCheckResult
from shared.models.pattern_graph import PatternViolation


logger = getLogger(__name__)
_NO_DEFAULT = object()


# ID: 8836a382-38c3-47af-b38c-852a54cd5674
class PatternChecker:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.patterns_dir = repo_root / ".intent" / "charter" / "patterns"
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> dict[str, dict]:
        """Load all pattern specifications."""
        patterns = {}
        if not self.patterns_dir.exists():
            logger.warning("Patterns directory not found: %s", self.patterns_dir)
            return patterns
        for pattern_file in self.patterns_dir.glob("*_patterns.yaml"):
            try:
                with open(pattern_file) as f:
                    data = yaml.safe_load(f)
                    category = data.get("id", pattern_file.stem)
                    patterns[category] = data
                    logger.info("Loaded pattern spec: %s", category)
            except Exception as e:
                logger.error("Failed to load {pattern_file}: %s", e)
        return patterns

    # ID: daa3364f-46d1-42c0-918b-f9ff5574e667
    def check_all(self) -> PatternCheckResult:
        """
        Check all code for pattern compliance.
        """
        violations = []
        violations.extend(self._check_commands())
        violations.extend(self._check_services())
        violations.extend(self._check_agents())
        violations.extend(self._check_workflows())
        total = len(violations) + sum(1 for v in violations if v.severity != "error")
        compliant = total - len([v for v in violations if v.severity == "error"])
        return PatternCheckResult(
            pattern_id="all",
            passed=compliant == total,
            violations=violations,
            total_components=total,
            compliant=compliant,
        )

    # ID: ec0edf76-e1bd-4b57-89d2-159c745188e4
    def check_category(self, category: str) -> list[PatternViolation]:
        """Check specific pattern category."""
        checkers = {
            "commands": self._check_commands,
            "services": self._check_services,
            "agents": self._check_agents,
            "workflows": self._check_workflows,
        }
        checker = checkers.get(category)
        if not checker:
            logger.error("Unknown category: %s", category)
            return []
        return checker()

    def _check_commands(self) -> list[PatternViolation]:
        """Check CLI commands against command patterns."""
        violations = []
        commands_dir = self.repo_root / "src" / "body" / "cli" / "commands"
        if not commands_dir.exists():
            return violations
        for py_file in commands_dir.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            violations.extend(self._check_command_file(py_file))
        return violations

    def _check_command_file(self, file_path: Path) -> list[PatternViolation]:
        """Check a single command file."""
        violations = []
        try:
            with open(file_path) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if self._is_cli_command(node):
                        violations.extend(
                            self._validate_command_pattern(file_path, node)
                        )
        except SyntaxError as e:
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=file_path.stem,
                    pattern_id="command_pattern",
                    violation_type="syntax_error",
                    message=f"Syntax error: {e}",
                    severity="error",
                )
            )
        return violations

    def _is_cli_command(self, node: ast.FunctionDef) -> bool:
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    if decorator.func.attr in ["command", "group"]:
                        return True
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr in ["command", "group"]:
                    return True
        return False

    def _validate_command_pattern(
        self, file_path: Path, node: ast.FunctionDef
    ) -> list[PatternViolation]:
        violations = []
        pattern_declared = self._get_declared_pattern(node)
        if not pattern_declared:
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="any_command_pattern",
                    violation_type="missing_declaration",
                    message=f"Command '{node.name}' missing pattern declaration in docstring",
                    line_number=node.lineno,
                    severity="warning",
                )
            )
            return violations
        if pattern_declared.startswith("inspect"):
            violations.extend(self._validate_inspect_pattern(file_path, node))
        elif pattern_declared.startswith("action"):
            violations.extend(self._validate_action_pattern(file_path, node))
        elif pattern_declared.startswith("check"):
            violations.extend(self._validate_check_pattern(file_path, node))
        return violations

    def _get_declared_pattern(self, node: ast.FunctionDef) -> str | None:
        docstring = ast.get_docstring(node)
        if not docstring:
            return None
        for line in docstring.split("\n"):
            line = line.strip()
            if line.startswith("Pattern:"):
                return line.split(":", 1)[1].strip()
        return None

    def _validate_inspect_pattern(
        self, file_path: Path, node: ast.FunctionDef
    ) -> list[PatternViolation]:
        violations = []
        if self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="inspect_pattern",
                    violation_type="forbidden_parameter",
                    message="Inspect commands must not have --write flag (read-only)",
                    line_number=node.lineno,
                    severity="error",
                )
            )
        if not node.name.startswith("inspect_") and "inspect" not in str(file_path):
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="inspect_pattern",
                    violation_type="naming_convention",
                    message=f"Inspect command '{node.name}' should start with 'inspect_'",
                    line_number=node.lineno,
                    severity="warning",
                )
            )
        return violations

    def _validate_action_pattern(
        self, file_path: Path, node: ast.FunctionDef
    ) -> list[PatternViolation]:
        violations = []
        has_write = self._has_parameter(node, "write")
        if not has_write:
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="action_pattern",
                    violation_type="missing_parameter",
                    message="Action commands must have --write parameter",
                    line_number=node.lineno,
                    severity="error",
                )
            )
            return violations
        default_val = self._get_parameter_default(node, "write")
        if default_val is _NO_DEFAULT:
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="action_pattern",
                    violation_type="unsafe_signature",
                    message="Parameter 'write' MUST have a default value",
                    line_number=node.lineno,
                    severity="error",
                )
            )
        elif default_val is not False:
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="action_pattern",
                    violation_type="unsafe_default",
                    message=f"Parameter 'write' default MUST be False (found: {default_val})",
                    line_number=node.lineno,
                    severity="error",
                )
            )
        return violations

    def _validate_check_pattern(
        self, file_path: Path, node: ast.FunctionDef
    ) -> list[PatternViolation]:
        violations = []
        if self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="check_pattern",
                    violation_type="forbidden_parameter",
                    message="Check commands must not modify state (no --write flag)",
                    line_number=node.lineno,
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

    def _get_parameter_default(self, node: ast.FunctionDef, param_name: str) -> Any:
        param_idx = None
        for i, arg in enumerate(node.args.args):
            if arg.arg == param_name:
                param_idx = i
                break
        if param_idx is not None:
            defaults_count = len(node.args.defaults)
            args_count = len(node.args.args)
            default_idx = param_idx - (args_count - defaults_count)
            if default_idx < 0:
                return _NO_DEFAULT
            default_node = node.args.defaults[default_idx]
            if isinstance(default_node, ast.Constant):
                return default_node.value
            return f"<{type(default_node).__name__}>"
        kw_param_idx = None
        for i, arg in enumerate(node.args.kwonlyargs):
            if arg.arg == param_name:
                kw_param_idx = i
                break
        if kw_param_idx is not None:
            default_node = node.args.kw_defaults[kw_param_idx]
            if default_node is None:
                return _NO_DEFAULT
            if isinstance(default_node, ast.Constant):
                return default_node.value
            return f"<{type(default_node).__name__}>"
        return None

    def _check_services(self) -> list[PatternViolation]:
        return []

    def _check_agents(self) -> list[PatternViolation]:
        return []

    def _check_workflows(self) -> list[PatternViolation]:
        return []


# ID: 8065de9c-3e1e-4a0a-9f49-2eca7633613f
def format_violations(violations: list[PatternViolation], verbose: bool = False) -> str:
    if not violations:
        return "✅ No pattern violations found!"
    lines = [f"\n❌ Found {len(violations)} pattern violations:\n"]
    sorted_violations = sorted(violations, key=lambda v: str(v.file_path))
    by_file: dict[str, list[PatternViolation]] = {}
    for v in sorted_violations:
        path = str(v.file_path) if v.file_path else "unknown"
        by_file.setdefault(path, []).append(v)
    for file_path, file_violations in by_file.items():
        lines.append(f"\n📄 {file_path}:")
        for v in file_violations:
            severity_icon = {"error": "❌", "warning": "⚠️", "info": "i"}.get(
                v.severity, "i"
            )
            lines.append(f"  {severity_icon} {v.component_name} ({v.pattern_id}):")
            lines.append(f"      {v.message}")
            if verbose and v.line_number:
                lines.append(f"      Line {v.line_number}")
    return "\n".join(lines)
