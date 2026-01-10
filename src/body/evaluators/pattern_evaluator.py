# src/body/evaluators/pattern_evaluator.py
# ID: 85bcca66-0390-4eaf-96e4-079b626c5b5e

"""
Pattern Evaluator - AUDIT Phase Component.
Validates code against constitutional design patterns (inspect, action, check).

Self-contained evaluator with no external checker dependencies.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path
from typing import Any

import yaml

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.config import settings
from shared.logger import getLogger
from shared.models.pattern_graph import PatternViolation


logger = getLogger(__name__)
_NO_DEFAULT = object()


# ID: a0631e53-9a66-45db-a96c-9823ece79763
class PatternEvaluator(Component):
    """
    Evaluates codebase for design pattern compliance.

    Checks:
    - Command patterns (inspect vs action)
    - Service patterns
    - Agent patterns

    Self-contained implementation with pattern loading and checking logic.
    """

    @property
    # ID: d164ccc9-f4a1-4fba-9ac1-d4bada7e49df
    def phase(self) -> ComponentPhase:
        return ComponentPhase.AUDIT

    # ID: 52fb3e23-ac1b-4bd9-a49d-abb3b750a15a
    async def execute(
        self, category: str = "all", repo_root: Path | None = None, **kwargs: Any
    ) -> ComponentResult:
        """
        Execute the pattern audit.
        """
        start_time = time.time()
        root = repo_root or settings.REPO_PATH

        # Load patterns from .intent/charter/patterns/
        patterns = self._load_patterns(root)

        # Run checks based on requested category
        if category == "all":
            violations = self._check_all(root, patterns)
        else:
            violations = self._check_category(root, patterns, category)

        # Calculate metrics
        total = max(len(violations), 1)  # Avoid division by zero
        compliant = total - len([v for v in violations if v.severity == "error"])
        compliance_rate = (compliant / total * 100.0) if total > 0 else 100.0
        passed = len([v for v in violations if v.severity == "error"]) == 0

        # Convert violations to dicts for ComponentResult
        violation_dicts = [
            {
                "file": v.file_path or "unknown",
                "component": v.component_name or "unknown",
                "pattern": v.expected_pattern,
                "type": v.violation_type,
                "message": v.message,
                "severity": v.severity,
                "line": v.line_number,
            }
            for v in violations
        ]

        duration = time.time() - start_time

        return ComponentResult(
            component_id=self.component_id,
            ok=passed,
            data={
                "total": total,
                "compliant": compliant,
                "compliance_rate": compliance_rate,
                "violations": violation_dicts,
            },
            phase=self.phase,
            confidence=1.0,
            metadata={"category": category, "violation_count": len(violation_dicts)},
            duration_sec=duration,
        )

    def _load_patterns(self, repo_root: Path) -> dict[str, dict]:
        """Load all pattern specifications from .intent/charter/patterns/"""
        patterns = {}
        patterns_dir = repo_root / ".intent" / "charter" / "patterns"

        if not patterns_dir.exists():
            logger.warning("Patterns directory not found: %s", patterns_dir)
            return patterns

        for pattern_file in patterns_dir.glob("*_patterns.yaml"):
            try:
                with open(pattern_file) as f:
                    data = yaml.safe_load(f)
                    category = data.get("id", pattern_file.stem)
                    patterns[category] = data
                    logger.debug("Loaded pattern spec: %s", category)
            except Exception as e:
                logger.error("Failed to load %s: %s", pattern_file, e)

        return patterns

    def _check_all(self, repo_root: Path, patterns: dict) -> list[PatternViolation]:
        """Check all code for pattern compliance."""
        violations = []
        violations.extend(self._check_commands(repo_root))
        violations.extend(self._check_services(repo_root))
        violations.extend(self._check_agents(repo_root))
        violations.extend(self._check_workflows(repo_root))
        return violations

    def _check_category(
        self, repo_root: Path, patterns: dict, category: str
    ) -> list[PatternViolation]:
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
        return checker(repo_root)

    def _check_commands(self, repo_root: Path) -> list[PatternViolation]:
        """Check CLI commands against command patterns."""
        violations = []
        commands_dir = repo_root / "src" / "body" / "cli" / "commands"
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
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
                tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    pattern_declared = self._get_declared_pattern(node)
                    if pattern_declared and pattern_declared.startswith("inspect"):
                        violations.extend(
                            self._validate_inspect_pattern(file_path, node)
                        )
                    elif pattern_declared and pattern_declared.startswith("action"):
                        violations.extend(
                            self._validate_action_pattern(file_path, node)
                        )
                    elif pattern_declared and pattern_declared.startswith("check"):
                        violations.extend(self._validate_check_pattern(file_path, node))

        except Exception as e:
            logger.debug("Could not parse %s: %s", file_path, e)

        return violations

    def _get_declared_pattern(self, node: ast.FunctionDef) -> str | None:
        """Extract pattern declaration from docstring."""
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
        """Validate inspect pattern requirements."""
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
        return violations

    def _validate_action_pattern(
        self, file_path: Path, node: ast.FunctionDef
    ) -> list[PatternViolation]:
        """Validate action pattern requirements."""
        violations = []
        has_write = self._has_parameter(node, "write")
        if not has_write:
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="action_pattern",
                    violation_type="missing_parameter",
                    message="Action commands must have 'write' parameter",
                    line_number=node.lineno,
                    severity="error",
                )
            )
        else:
            # Check write defaults to False
            default = self._get_parameter_default(node, "write")
            if default is not False and default is not _NO_DEFAULT:
                violations.append(
                    PatternViolation(
                        file_path=str(file_path),
                        component_name=node.name,
                        pattern_id="action_pattern",
                        violation_type="unsafe_default",
                        message="Action 'write' parameter must default to False",
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
        if self._has_parameter(node, "write") or self._has_parameter(node, "apply"):
            violations.append(
                PatternViolation(
                    file_path=str(file_path),
                    component_name=node.name,
                    pattern_id="check_pattern",
                    violation_type="forbidden_parameter",
                    message="Check commands must not modify state (no write flag)",
                    line_number=node.lineno,
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

    def _get_parameter_default(self, node: ast.FunctionDef, param_name: str) -> Any:
        """Get default value for a parameter."""
        # Check positional args
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

        # Check keyword-only args
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

    def _check_services(self, repo_root: Path) -> list[PatternViolation]:
        """Check service patterns (not implemented yet)."""
        return []

    def _check_agents(self, repo_root: Path) -> list[PatternViolation]:
        """Check agent patterns (not implemented yet)."""
        return []

    def _check_workflows(self, repo_root: Path) -> list[PatternViolation]:
        """Check workflow patterns (not implemented yet)."""
        return []


# ID: 8065de9c-3e1e-4a0a-9f49-2eca7633613f
def format_violations(violations: list[PatternViolation], verbose: bool = False) -> str:
    """
    Format pattern violations for display.

    This formatter is kept for backward compatibility with CLI commands.
    """
    if not violations:
        return "✅ No pattern violations found!"

    output = []
    output.append("\n❌ Found Pattern Violations:\n")

    # Group by file
    by_file: dict[str, list[PatternViolation]] = {}
    for v in violations:
        file_path = v.file_path or "unknown"
        by_file.setdefault(file_path, []).append(v)

    for file_path, file_violations in sorted(by_file.items()):
        output.append(f"\n📄 {file_path}")

        for v in file_violations:
            severity_marker = "🔴" if v.severity == "error" else "🟡"
            component = v.component_name or "unknown"
            line = v.line_number or "?"
            output.append(f"  {severity_marker} {component} (line {line})")
            output.append(f"     Pattern: {v.expected_pattern}")
            output.append(f"     Type: {v.violation_type}")
            output.append(f"     {v.message}")

            if verbose:
                output.append("")

    return "\n".join(output)


# ID: 9610eb12-b215-4902-85a7-9215e29f2de3
def load_patterns_dict(repo_root: Path) -> dict[str, dict]:
    """
    Load pattern specifications for external use (e.g., list command).

    Returns dict mapping category -> pattern spec data.
    """
    patterns = {}
    patterns_dir = repo_root / ".intent" / "charter" / "patterns"

    if not patterns_dir.exists():
        logger.warning("Patterns directory not found: %s", patterns_dir)
        return patterns

    for pattern_file in patterns_dir.glob("*_patterns.yaml"):
        try:
            with open(pattern_file) as f:
                data = yaml.safe_load(f)
                category = data.get("id", pattern_file.stem)
                patterns[category] = data
        except Exception as e:
            logger.error("Failed to load %s: %s", pattern_file, e)

    return patterns
