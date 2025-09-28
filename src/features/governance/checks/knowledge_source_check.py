# src/features/governance/checks/knowledge_source_check.py
"""
Auditor check to enforce the single source of truth for knowledge.
Verifies that no code directly accesses legacy knowledge artifacts like
knowledge_graph.json, forcing them to use the governed KnowledgeService instead.
"""
# ID: 672e382f-870d-4054-9549-74d436531393
from __future__ import annotations

import ast
from pathlib import Path

from features.governance.checks.base_check import BaseCheck
from services.mind_service import get_mind_service
from shared.models import AuditFinding


# ID: c18f3a3e-4b6e-451e-b873-1f19d9b62f1c
class KnowledgeSourceCheck(BaseCheck):
    """
    Ensures that no code directly accesses forbidden knowledge artifacts.
    """

    # ID: 1e8f2c2e-4b6e-451e-b873-1f19d9b62f1d
    def execute(self) -> list[AuditFinding]:
        findings = []
        forbidden_string = "knowledge_graph.json"

        mind_service = get_mind_service()
        policy = mind_service.load_policy(
            "charter.policies.governance.knowledge_source_policy"
        )
        allowed_paths = policy.get("allowed_access_paths", [])

        # --- START OF FIX ---
        # The method was renamed. This uses the correct, current method on AuditorContext.
        python_files = self.context.get_files_by_extension(".py")
        for file_path in python_files:
        # --- END OF FIX ---
            relative_path = str(file_path.relative_to(self.context.repo_root))

            # This check is allowed to access the file, so we skip it.
            if relative_path in allowed_paths:
                continue

            try:
                content = file_path.read_text("utf-8")
                if forbidden_string in content:
                    # Basic string search passed, now do a more precise AST check
                    # to avoid flagging comments or documentation.
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if (
                            isinstance(node, ast.Constant)
                            and isinstance(node.value, str)
                            and forbidden_string in node.value
                        ):
                            findings.append(
                                self.finding(
                                    check_id="knowledge.source.direct_access",
                                    message=f"Illegal direct access to '{forbidden_string}'. "
                                    "Use the KnowledgeService instead.",
                                    file_path=file_path,
                                    line_number=node.lineno,
                                )
                            )
                            break  # Only report once per file
            except Exception:
                # Ignore files that can't be parsed; other checks will handle syntax errors.
                continue
        return findings