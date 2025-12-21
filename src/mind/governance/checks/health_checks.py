# src/mind/governance/checks/health_checks.py
"""
Audits codebase health for complexity, atomicity, and line length violations.
Enforces 'code_standards' rules regarding module size and complexity.
"""

from __future__ import annotations

import ast
import statistics
from pathlib import Path
from typing import ClassVar


# External dependency: radon
try:
    from radon.visitors import ComplexityVisitor

    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 51dd8f1d-eda6-40e2-9c64-530ce6c290a6
class HealthChecks(BaseCheck):
    """
    Enforces complexity and size limits defined in code_standards.yaml.
    """

    # Explicitly link to the specific rules in code_standards.yaml
    policy_rule_ids: ClassVar[list[str]] = [
        "code_standards.max_file_lines",
        "code_standards.max_function_lines",
        # "complexity.max_cognitive_complexity" # Implicit in health_standards
    ]

    def __init__(self, context):
        super().__init__(context)
        # Load configuration (Reference Data) from policy
        code_standards = self.context.policies.get("code_standards", {})
        self.health_config = code_standards.get("health_standards", {})

        if not RADON_AVAILABLE:
            logger.warning(
                "HealthChecks: 'radon' library not installed. Complexity checks will be skipped."
            )

    # ID: 64bffe32-e6fd-4fd1-a235-aaf764363076
    def execute(self) -> list[AuditFinding]:
        """Measures code complexity and atomicity against defined policies."""
        file_line_counts = {}
        all_violations = []

        # Use src_dir to scan all python files in the body/features/services
        for file_path in self.src_dir.rglob("*.py"):
            # Skip tests for complexity checks unless specified otherwise
            if "tests/" in str(file_path):
                continue

            logical_lines, violations = self._analyze_python_file(file_path)

            if logical_lines > 0:
                file_line_counts[file_path] = logical_lines

            all_violations.extend(violations)

        # Check for outliers (Statistical Health)
        all_violations.extend(self._find_file_size_outliers(file_line_counts))

        return all_violations

    def _analyze_python_file(self, file_path: Path) -> tuple[int, list[AuditFinding]]:
        """Analyze a single Python file for health violations."""
        findings = []
        try:
            source_code = file_path.read_text(encoding="utf-8")
            logical_lines = self._count_logical_lines(source_code)
            rel_path = str(file_path.relative_to(self.repo_root))

            # 1. Check Module Length
            # Rule: code_standards.max_file_lines (Enforcement: ERROR)
            max_lloc = self.health_config.get("max_module_lloc", 300)
            if logical_lines > max_lloc:
                findings.append(
                    AuditFinding(
                        check_id="code_standards.max_file_lines",
                        severity=AuditSeverity.ERROR,  # Constitution says ERROR
                        message=f"Module length {logical_lines} exceeds limit of {max_lloc}.",
                        file_path=rel_path,
                        context={"current": logical_lines, "limit": max_lloc},
                    )
                )

            # 2. Check Complexity & Function Length (Requires Radon)
            if RADON_AVAILABLE:
                syntax_tree = ast.parse(source_code)
                complexity_visitor = ComplexityVisitor.from_ast(syntax_tree)
                findings.extend(
                    self._check_function_metrics(complexity_visitor, rel_path)
                )

            return logical_lines, findings

        except SyntaxError:
            # File is not valid Python
            return 0, [
                AuditFinding(
                    check_id="code_quality.syntax_error",
                    severity=AuditSeverity.ERROR,
                    message="Syntax Error: Unable to parse file for health checks.",
                    file_path=str(file_path.relative_to(self.repo_root)),
                )
            ]
        except Exception as e:
            logger.debug("Health check failed for %s: %s", file_path, e)
            return 0, []

    def _count_logical_lines(self, source_code: str) -> int:
        """Counts lines excluding comments and blanks."""
        return sum(
            1
            for line in source_code.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    def _check_function_metrics(
        self,
        visitor: ComplexityVisitor,
        file_path_str: str,
    ) -> list[AuditFinding]:
        violations = []
        max_complexity = self.health_config.get("max_cognitive_complexity", 15)
        # Rule: code_standards.max_function_lines (Enforcement: WARN)
        max_func_lloc = self.health_config.get("max_function_lloc", 80)

        for function in visitor.functions:
            # Complexity Check
            if function.cognitive_complexity > max_complexity:
                violations.append(
                    AuditFinding(
                        check_id="complexity.max_cognitive_complexity",
                        severity=AuditSeverity.WARNING,
                        message=(
                            f"Function '{function.name}' complexity is {function.cognitive_complexity} "
                            f"(limit: {max_complexity}). Breakdown suggestions possible."
                        ),
                        file_path=file_path_str,
                        line_number=function.lineno,
                    )
                )

            # Function Length Check
            if function.lloc > max_func_lloc:
                violations.append(
                    AuditFinding(
                        check_id="code_standards.max_function_lines",
                        severity=AuditSeverity.WARNING,  # Constitution says WARN
                        message=f"Function '{function.name}' length {function.lloc} exceeds limit of {max_func_lloc}.",
                        file_path=file_path_str,
                        line_number=function.lineno,
                    )
                )
        return violations

    def _find_file_size_outliers(self, file_line_counts: dict) -> list[AuditFinding]:
        """Identifies files that are statistical outliers in size."""
        if len(file_line_counts) < 3:
            return []

        violations = []
        line_count_values = list(file_line_counts.values())
        average_lines = statistics.mean(line_count_values)

        try:
            standard_deviation = statistics.stdev(line_count_values)
        except statistics.StatisticsError:
            return []

        stdev_multiplier = self.health_config.get("outlier_standard_deviations", 2.0)
        outlier_threshold = average_lines + (stdev_multiplier * standard_deviation)

        for file_path, line_count in file_line_counts.items():
            if line_count > outlier_threshold:
                violations.append(
                    AuditFinding(
                        check_id="code_quality.health.module_outlier",
                        severity=AuditSeverity.WARNING,
                        message=(
                            f"Module size outlier ({line_count} lines). "
                            f"System Avg: {average_lines:.0f} lines. Threshold: {outlier_threshold:.0f}."
                        ),
                        file_path=str(file_path.relative_to(self.repo_root)),
                    )
                )
        return violations
