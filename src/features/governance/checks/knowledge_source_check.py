# src/features/governance/checks/knowledge_source_check.py
"""
A constitutional audit check to enforce the single source of truth for knowledge.
"""
from __future__ import annotations

from typing import List

from features.governance.checks.base_check import BaseCheck
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity


# ID: 17efaec9-2238-46a9-945e-fa2610882d80
class KnowledgeSourceCheck(BaseCheck):
    """
    Verifies that knowledge_graph.json is not read directly by runtime components,
    except for those explicitly permitted by the knowledge_source_policy.
    """

    # ID: 8dfccaae-a166-4e22-8673-33d0e3b6a784
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check by scanning all source files for forbidden access patterns.
        """
        findings = []
        forbidden_string = "knowledge_graph.json"

        # --- THIS IS THE FIX ---
        # The check now loads its configuration from the constitution via the settings object.
        # It has no hardcoded knowledge of which files are allowed.
        try:
            policy = settings.load(
                "charter.policies.governance.knowledge_source_policy"
            )
            allowed_files = set(policy.get("allowed_access_paths", []))
        except (FileNotFoundError, IOError):
            # Fail safely if the policy is missing
            allowed_files = set()
        # --- END OF FIX ---

        for file_path in self.src_dir.rglob("*.py"):
            file_path_str = str(file_path.relative_to(self.repo_root))

            if file_path_str in allowed_files:
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
                continue

        return findings
