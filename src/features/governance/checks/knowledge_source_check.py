# src/features/governance/checks/knowledge_source_check.py
"""
A constitutional audit check to enforce the single source of truth for knowledge.
This check ensures that no component reads the legacy knowledge_graph.json file
directly, forcing them to use the KnowledgeService instead.
"""
from __future__ import annotations

from typing import List

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 4ecc31b1-7bc6-48ae-9933-f062f73c82cf
class KnowledgeSourceCheck(BaseCheck):
    """
    Verifies that knowledge_graph.json is not read directly by runtime components.
    """

    # ID: 49b73ea2-7298-4272-9493-2b5d01cab77c
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check by scanning all source files for forbidden access patterns.
        """
        findings = []
        forbidden_string = "knowledge_graph.json"
        allowed_file = "src/features/introspection/knowledge_graph_service.py"

        for file_path in self.src_dir.rglob("*.py"):
            file_path_str = str(file_path.relative_to(self.repo_root))

            if file_path_str == allowed_file:
                continue

            try:
                content = file_path.read_text("utf-8")
                if forbidden_string in content:
                    findings.append(
                        AuditFinding(
                            check_id="knowledge.source.direct_access",
                            severity=AuditSeverity.ERROR,
                            message=f"Illegal direct access to '{forbidden_string}'. Use the KnowledgeService instead.",
                            file_path=file_path_str,
                        )
                    )
            except Exception:
                continue  # Ignore files that can't be read

        return findings
