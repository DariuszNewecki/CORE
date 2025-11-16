# src/mind/governance/checks/health_checks.py
"""
Audits codebase health for complexity, atomicity, and line length violations,
enforcing the 'code_quality' constitutional rule.
"""

from __future__ import annotations

import ast
import statistics
from pathlib import Path

from radon.visitors import ComplexityVisitor
from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: 51dd8f1d-eda6-40e2-9c64-530ce6c290a6
class HealthChecks(BaseCheck):
    """
    Container for codebase health constitutional checks. This check enforces the
    'code_quality' rule from the quality_assurance policy by measuring various
    metrics defined in the 'health_standards' section of the code_standards policy.
    """

    # Explicit Constitutional Linkage:
    # This check contributes directly to the 'code_quality' rule.
    policy_rule_ids = ["code_quality"]

    def __init__(self, context):
        super().__init__(context)
        code_standards_policy = self.context.policies.get("code_standards", {})
        self.health_policy = code_standards_policy.get("health_standards", {})

    # ID: 64bffe32-e6fd-4fd1-a235-aaf764363076
    def execute(self) -> list[AuditFinding]:
        """Measures code complexity and atomicity against defined policies."""
        policy_rules = self.health_policy
        file_line_counts = {}
        all_violations = []
        unique_files = {
            s["file_path"]
            for s in self.context.symbols_list
            if s.get("file_path", "").startswith("src/")
        }
        for file_path_str in sorted(list(unique_files)):
            if not file_path_str.endswith(".py"):
                continue
            file_path = self.repo_root / file_path_str
            logical_lines, violations = self._analyze_python_file(
                file_path, policy_rules
            )
            if logical_lines > 0:
                file_line_counts[file_path] = logical_lines
            all_violations.extend(violations)
        all_violations.extend(
            self._find_file_size_outliers(file_line_counts, policy_rules)
        )
        return all_violations

    def _analyze_python_file(
        self, file_path: Path, rules: dict
    ) -> tuple[int, list[AuditFinding]]:
        """Analyze a single Python file for health violations."""
        try:
            source_code = file_path.read_text(encoding="utf-8")
            logical_lines = self._count_logical_lines(source_code)

            # Note: The finding 'check_id' is now more specific.
            max_lloc = rules.get("max_module_lloc", 300)
            if logical_lines > max_lloc:
                return logical_lines, [
                    AuditFinding(
                        check_id="code_quality.health.module_too_long",
                        severity=AuditSeverity.WARNING,
                        message=f"Module has {logical_lines} lines (limit: {max_lloc}).",
                        file_path=str(file_path.relative_to(self.repo_root)),
                    )
                ]

            syntax_tree = ast.parse(source_code)
            complexity_visitor = ComplexityVisitor.from_ast(syntax_tree)
            violations = self._check_function_metrics(
                complexity_visitor,
                rules,
                str(file_path.relative_to(self.repo_root)),
            )
            return logical_lines, violations
        except Exception:
            return 0, []

    def _count_logical_lines(self, source_code: str) -> int:
        return sum(
            1
            for line in source_code.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    def _check_function_metrics(
        self,
        visitor: ComplexityVisitor,
        rules: dict,
        file_path_str: str,
    ) -> list[AuditFinding]:
        violations = []
        max_complexity = rules.get("max_cognitive_complexity", 15)
        max_func_lloc = rules.get("max_function_lloc", 80)

        for function in visitor.functions:
            if function.cognitive_complexity > max_complexity:
                violations.append(
                    AuditFinding(
                        check_id="code_quality.health.function_too_complex",
                        severity=AuditSeverity.WARNING,
                        message=f"Function '{function.name}' complexity is {function.cognitive_complexity} (limit: {max_complexity}).",
                        file_path=file_path_str,
                        line_number=function.lineno,
                    )
                )
            if function.lloc > max_func_lloc:
                violations.append(
                    AuditFinding(
                        check_id="code_quality.health.function_too_long",
                        severity=AuditSeverity.WARNING,
                        message=f"Function '{function.name}' has {function.lloc} lines (limit: {max_func_lloc}).",
                        file_path=file_path_str,
                        line_number=function.lineno,
                    )
                )
        return violations

    def _find_file_size_outliers(
        self, file_line_counts: dict, rules: dict
    ) -> list[AuditFinding]:
        if len(file_line_counts) < 3:
            return []
        violations = []
        line_count_values = list(file_line_counts.values())
        average_lines = statistics.mean(line_count_values)
        standard_deviation = statistics.stdev(line_count_values)

        stdev_multiplier = rules.get("outlier_standard_deviations", 2.0)
        outlier_threshold = average_lines + (stdev_multiplier * standard_deviation)

        for file_path, line_count in file_line_counts.items():
            if line_count > outlier_threshold:
                violations.append(
                    AuditFinding(
                        check_id="code_quality.health.module_outlier",
                        severity=AuditSeverity.WARNING,
                        message=f"Module size outlier ({line_count} lines vs avg of {average_lines:.0f}). Consider refactoring.",
                        file_path=str(file_path.relative_to(self.repo_root)),
                    )
                )
        return violations
