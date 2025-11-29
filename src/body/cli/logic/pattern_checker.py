# src/body/cli/logic/pattern_checker.py

"""
Pattern compliance checker for CORE.

This module validates that code follows declared design patterns
from .intent/charter/patterns/*.yaml

Pattern: check_pattern
See: .intent/charter/patterns/command_patterns.yaml#check_pattern
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import yaml
from shared.logger import getLogger

logger = getLogger(__name__)


@dataclass
# ID: 08cd068a-2fdb-49bf-a6d7-b1db393daf11
class PatternViolation:
    """Represents a pattern compliance violation."""

    file_path: Path
    component_name: str
    expected_pattern: str
    violation_type: str
    message: str
    line_number: int | None = None
    severity: str = "error"  # error, warning, info


@dataclass
# ID: 6a47e7a6-8e82-4e25-94e2-cccef4059d61
class PatternCheckResult:
    """Results from pattern compliance check."""

    total_components: int
    compliant: int
    violations: list[PatternViolation]

    @property
    # ID: ba13910f-d785-4d3b-b353-dd1fb8e5c28b
    def compliance_rate(self) -> float:
        """Calculate compliance percentage."""
        if self.total_components == 0:
            return 100.0
        return (self.compliant / self.total_components) * 100


# ID: 994f01e4-16e5-4976-b411-3aec46216ede
class PatternChecker:
    """
    Validates code compliance with CORE design patterns.

    Reads pattern specifications from .intent/charter/patterns/
    and checks implementation against requirements.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.patterns_dir = repo_root / ".intent" / "charter" / "patterns"
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> dict[str, dict]:
        """Load all pattern specifications."""
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

    # ID: 5aa6e0e2-e189-4e40-b196-2bcc4a563c92
    def check_all(self) -> PatternCheckResult:
        """
        Check all code for pattern compliance.

        Returns:
            PatternCheckResult with violations and statistics
        """
        violations = []

        # Check CLI commands
        violations.extend(self._check_commands())

        # Check services
        violations.extend(self._check_services())

        # Check agents
        violations.extend(self._check_agents())

        # Check workflows (Makefile)
        violations.extend(self._check_workflows())

        total = len(violations) + sum(1 for v in violations if v.severity != "error")
        compliant = total - len([v for v in violations if v.severity == "error"])

        return PatternCheckResult(
            total_components=total, compliant=compliant, violations=violations
        )

    # ID: ab3d6fdc-a904-44c3-ac78-7e71889fbce9
    def check_category(self, category: str) -> list[PatternViolation]:
        """
        Check specific pattern category.

        Args:
            category: One of 'commands', 'services', 'agents', 'workflows'
        """
        checkers = {
            "commands": self._check_commands,
            "services": self._check_services,
            "agents": self._check_agents,
            "workflows": self._check_workflows,
        }

        checker = checkers.get(category)
        if not checker:
            logger.error(f"Unknown category: {category}")
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

            # Find all function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if it's a CLI command (has @click decorator or similar)
                    if self._is_cli_command(node):
                        violations.extend(
                            self._validate_command_pattern(file_path, node)
                        )

        except SyntaxError as e:
            violations.append(
                PatternViolation(
                    file_path=file_path,
                    component_name=file_path.stem,
                    expected_pattern="command_pattern",
                    violation_type="syntax_error",
                    message=f"Syntax error: {e}",
                    severity="error",
                )
            )

        return violations

    def _is_cli_command(self, node: ast.FunctionDef) -> bool:
        """Check if function is a CLI command."""
        # Look for decorators like @click.command, @app.command, etc.
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
        """Validate command follows appropriate pattern."""
        violations = []

        # Check for pattern declaration in docstring
        pattern_declared = self._get_declared_pattern(node)
        if not pattern_declared:
            violations.append(
                PatternViolation(
                    file_path=file_path,
                    component_name=node.name,
                    expected_pattern="any_command_pattern",
                    violation_type="missing_declaration",
                    message=f"Command '{node.name}' missing pattern declaration in docstring",
                    line_number=node.lineno,
                    severity="warning",
                )
            )
            return violations

        # Validate against declared pattern
        if pattern_declared.startswith("inspect"):
            violations.extend(self._validate_inspect_pattern(file_path, node))
        elif pattern_declared.startswith("action"):
            violations.extend(self._validate_action_pattern(file_path, node))
        elif pattern_declared.startswith("check"):
            violations.extend(self._validate_check_pattern(file_path, node))

        return violations

    def _get_declared_pattern(self, node: ast.FunctionDef) -> str | None:
        """Extract pattern declaration from docstring."""
        docstring = ast.get_docstring(node)
        if not docstring:
            return None

        # Look for "Pattern: pattern_name" in docstring
        for line in docstring.split("\n"):
            line = line.strip()
            if line.startswith("Pattern:"):
                return line.split(":", 1)[1].strip()

        return None

    def _validate_inspect_pattern(
        self, file_path: Path, node: ast.FunctionDef
    ) -> list[PatternViolation]:
        """Validate inspect pattern requirements."""
        violations = []

        # Inspect commands should NOT have --write flag
        if self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    file_path=file_path,
                    component_name=node.name,
                    expected_pattern="inspect_pattern",
                    violation_type="forbidden_parameter",
                    message="Inspect commands must not have --write flag (read-only)",
                    line_number=node.lineno,
                    severity="error",
                )
            )

        # Should have appropriate naming (starts with 'inspect_' or is in inspect module)
        if not node.name.startswith("inspect_") and "inspect" not in str(file_path):
            violations.append(
                PatternViolation(
                    file_path=file_path,
                    component_name=node.name,
                    expected_pattern="inspect_pattern",
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
        """Validate action pattern requirements."""
        violations = []

        # Action commands MUST have --write flag (or --dry-run)
        has_write = self._has_parameter(node, "write")
        has_dry_run = self._has_parameter(node, "dry_run")

        if not has_write and not has_dry_run:
            violations.append(
                PatternViolation(
                    file_path=file_path,
                    component_name=node.name,
                    expected_pattern="action_pattern",
                    violation_type="missing_parameter",
                    message="Action commands must have --write or --dry-run flag",
                    line_number=node.lineno,
                    severity="error",
                )
            )

        # Check default value is False (dry-run by default)
        if has_write:
            default = self._get_parameter_default(node, "write")
            if default is True:
                violations.append(
                    PatternViolation(
                        file_path=file_path,
                        component_name=node.name,
                        expected_pattern="action_pattern",
                        violation_type="unsafe_default",
                        message="Action commands must default to dry-run (write=False)",
                        line_number=node.lineno,
                        severity="error",
                    )
                )

        return violations

    def _validate_check_pattern(
        self, file_path: Path, node: ast.FunctionDef
    ) -> list[PatternViolation]:
        """Validate check pattern requirements."""
        violations = []

        # Check commands should NOT have --write flag
        if self._has_parameter(node, "write"):
            violations.append(
                PatternViolation(
                    file_path=file_path,
                    component_name=node.name,
                    expected_pattern="check_pattern",
                    violation_type="forbidden_parameter",
                    message="Check commands must not modify state (no --write flag)",
                    line_number=node.lineno,
                    severity="error",
                )
            )

        # Should return exit code (check for sys.exit or return statement)
        # This requires more sophisticated analysis - skip for now

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

    def _check_services(self) -> list[PatternViolation]:
        """Check services against service patterns."""
        # TODO: Implement service pattern checking
        return []

    def _check_agents(self) -> list[PatternViolation]:
        """Check agents against agent patterns."""
        # TODO: Implement agent pattern checking
        return []

    def _check_workflows(self) -> list[PatternViolation]:
        """Check workflows against workflow patterns."""
        # TODO: Implement workflow pattern checking
        return []


# ID: a5eef7d2-bcef-4ee6-8d86-90bc311b37e6
def format_violations(violations: list[PatternViolation], verbose: bool = False) -> str:
    """Format violations for display."""
    if not violations:
        return "✅ No pattern violations found!"

    lines = [f"\n❌ Found {len(violations)} pattern violations:\n"]

    # Group by file
    by_file: dict[Path, list[PatternViolation]] = {}
    for v in violations:
        by_file.setdefault(v.file_path, []).append(v)

    for file_path, file_violations in sorted(by_file.items()):
        lines.append(f"\n📄 {file_path}:")
        for v in file_violations:
            severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[v.severity]
            lines.append(
                f"  {severity_icon} {v.component_name} ({v.expected_pattern}):"
            )
            lines.append(f"      {v.message}")
            if verbose and v.line_number:
                lines.append(f"      Line {v.line_number}")

    return "\n".join(lines)
