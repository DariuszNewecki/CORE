# src/system/governance/checks/health_checks.py
"""Auditor checks for codebase health, complexity, and atomicity."""

import ast
import statistics

from radon.visitors import ComplexityVisitor
from system.governance.models import AuditFinding, AuditSeverity


class HealthChecks:
    """Container for codebase health constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context
        self.health_policy = self.context.load_config(
            self.context.intent_dir / "policies" / "code_health_policy.yaml"
        )

    def _get_logical_lines_of_code(self, source_code: str) -> int:
        """Calculates the Logical Lines of Code (LLOC), ignoring comments and blank lines."""
        return len(
            [
                line
                for line in source_code.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        )

    # CAPABILITY: audit.check.codebase_health
    def check_codebase_health(self) -> list[AuditFinding]:
        """Measures code complexity and atomicity against defined policies."""
        findings = []
        check_name = "Codebase Health & Atomicity"

        # --- Policy Thresholds ---
        max_complexity = self.health_policy.get("rules", {}).get(
            "max_cognitive_complexity", 15
        )
        std_dev_threshold = self.health_policy.get("rules", {}).get(
            "outlier_standard_deviations", 2.0
        )

        file_llocs = {}
        complexity_violations = []

        # --- Analysis Phase ---
        for symbol in self.context.symbols_list:
            file_path_str = symbol.get("file")
            if not file_path_str or not file_path_str.endswith(".py"):
                continue

            file_path = self.context.repo_root / file_path_str
            if file_path not in file_llocs:  # Analyze each file only once
                try:
                    source_code = file_path.read_text(encoding="utf-8")
                    file_llocs[file_path] = self._get_logical_lines_of_code(source_code)

                    # Analyze complexity for all functions in the file
                    tree = ast.parse(source_code)
                    visitor = ComplexityVisitor.from_ast(tree)
                    for func in visitor.functions:
                        if func.cognitive_complexity > max_complexity:
                            msg = (
                                f"Function '{func.name}' in '{file_path_str}' has a Cognitive "
                                f"Complexity of {func.cognitive_complexity}, exceeding the policy limit of {max_complexity}."
                            )
                            complexity_violations.append(
                                AuditFinding(AuditSeverity.WARNING, msg, check_name)
                            )
                except Exception:
                    continue  # Skip files that can't be parsed

        # --- Statistical Outlier Detection Phase ---
        if len(file_llocs) < 3:  # Need enough data for meaningful stats
            return complexity_violations  # Return any complexity issues found

        lloc_values = list(file_llocs.values())
        average_lloc = statistics.mean(lloc_values)
        std_dev = statistics.stdev(lloc_values)
        outlier_threshold = average_lloc + (std_dev_threshold * std_dev)

        outlier_findings = []
        for path, lloc in file_llocs.items():
            if lloc > outlier_threshold:
                msg = (
                    f"File '{path.relative_to(self.context.repo_root)}' is a complexity outlier "
                    f"({lloc} LLOC vs. project average of {average_lloc:.0f}). "
                    "This may violate the 'separation_of_concerns' principle."
                )
                outlier_findings.append(
                    AuditFinding(AuditSeverity.WARNING, msg, check_name)
                )

        # --- Reporting Phase ---
        if not complexity_violations and not outlier_findings:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "Codebase complexity and atomicity are within healthy limits.",
                    check_name,
                )
            )
        else:
            findings.extend(complexity_violations)
            findings.extend(outlier_findings)

        return findings
