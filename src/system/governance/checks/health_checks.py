# src/system/governance/checks/health_checks.py
"""
Audits codebase health by measuring cognitive complexity, nesting depth, line length, and detecting statistical outliers in file size.
"""

from __future__ import annotations

import ast
import statistics

from radon.visitors import ComplexityVisitor

from system.governance.models import AuditFinding, AuditSeverity


# CAPABILITY: audit.check.codebase_health
class HealthChecks:
    """Container for codebase health constitutional checks."""

    # CAPABILITY: system.health_check.initialize
    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context
        self.health_policy = self.context.load_config(
            self.context.intent_dir / "policies" / "code_health_policy.yaml"
        )

    # CAPABILITY: audit.check.logical_lines_of_code
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

        # --- Policy Thresholds from the Constitution ---
        rules = self.health_policy.get("rules", {})
        max_complexity = rules.get("max_cognitive_complexity", 15)
        max_nesting = rules.get("max_nesting_depth", 4)
        max_line_len_config = rules.get("max_line_length", {})
        max_lines = max_line_len_config.get("limit", 100)
        line_len_enforcement = max_line_len_config.get("enforcement", "soft")
        std_dev_threshold = rules.get("outlier_standard_deviations", 2.0)

        file_llocs = {}
        all_violations = []

        # --- Analysis Phase ---
        for symbol in self.context.symbols_list:
            file_path_str = symbol.get("file")
            if not file_path_str or not file_path_str.endswith(".py"):
                continue

            file_path = self.context.repo_root / file_path_str
            if file_path in file_llocs:  # Analyze each file only once
                continue

            try:
                source_code = file_path.read_text(encoding="utf-8")
                file_llocs[file_path] = self._get_logical_lines_of_code(source_code)
                tree = ast.parse(source_code)

                # 1. Check Cognitive Complexity
                visitor = ComplexityVisitor.from_ast(tree)
                for func in visitor.functions:
                    if func.cognitive_complexity > max_complexity:
                        msg = f"Function '{func.name}' has Cognitive Complexity of {func.cognitive_complexity} (limit: {max_complexity})."
                        all_violations.append(
                            AuditFinding(
                                AuditSeverity.WARNING, msg, check_name, file_path_str
                            )
                        )

                # 2. Check Nesting Depth
                for func in visitor.functions:
                    if func.max_nesting_depth > max_nesting:
                        msg = f"Function '{func.name}' has nesting depth of {func.max_nesting_depth} (limit: {max_nesting})."
                        all_violations.append(
                            AuditFinding(
                                AuditSeverity.WARNING, msg, check_name, file_path_str
                            )
                        )

                # 3. Check Line Length
                for i, line in enumerate(source_code.splitlines(), 1):
                    if len(line) > max_lines:
                        severity = (
                            AuditSeverity.WARNING
                            if line_len_enforcement == "soft"
                            else AuditSeverity.ERROR
                        )
                        msg = f"Line {i} exceeds max length of {max_lines} characters."
                        all_violations.append(
                            AuditFinding(severity, msg, check_name, file_path_str)
                        )

            except Exception:
                continue

        # --- Statistical Outlier Detection Phase ---
        if len(file_llocs) >= 3:
            lloc_values = list(file_llocs.values())
            average_lloc = statistics.mean(lloc_values)
            std_dev = statistics.stdev(lloc_values)
            outlier_threshold = average_lloc + (std_dev_threshold * std_dev)

            for path, lloc in file_llocs.items():
                if lloc > outlier_threshold:
                    # --- THIS IS THE CORRECTED MESSAGE FORMAT ---
                    msg = f"Possible complexity outlier ({lloc} LLOC vs. AVG of {average_lloc:.0f}). This may violate 'separation_of_concerns'."
                    all_violations.append(
                        AuditFinding(
                            AuditSeverity.WARNING,
                            msg,
                            check_name,
                            str(path.relative_to(self.context.repo_root)),
                        )
                    )

        # --- Reporting Phase ---
        if not all_violations:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "Codebase complexity and atomicity are within healthy limits.",
                    check_name,
                )
            )
        else:
            findings.extend(all_violations)

        return findings
