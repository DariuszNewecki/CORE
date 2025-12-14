# src/mind/governance/checks/limited_legacy_access_check.py
"""
Enforces knowledge.limited_legacy_access.
Restricts code access to deprecated knowledge artifacts (legacy YAML files).
Only constitutionally whitelisted tools may reference these files.
"""

from __future__ import annotations

import ast

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# The specific artifacts that should not be accessed by general code
LEGACY_ARTIFACTS = {
    "cli_registry.yaml",
    "resource_manifest.yaml",
    "cognitive_roles.yaml",
}


# ID: 1572122b-d11a-4ed4-89d7-678b92779480
class LimitedLegacyAccessCheck(BaseCheck):
    """
    Scans for string references to legacy knowledge artifacts.
    Enforces that only specific governance/migration tools can touch these files.
    Ref: standard_data_governance (knowledge_integrity)
    """

    policy_rule_ids = ["knowledge.limited_legacy_access"]

    def __init__(self, context):
        super().__init__(context)
        # Load Whitelist from Constitution
        data_policy = self.context.policies.get("data_governance", {})
        knowledge_rules = data_policy.get("knowledge_integrity", [])

        self.allowed_paths = set()

        # Find the specific rule config
        for rule in knowledge_rules:
            if rule.get("id") == "knowledge.limited_legacy_access":
                self.allowed_paths = set(rule.get("allowed_access_paths", []))
                break

    # ID: 90fab030-8d3e-443a-9d8e-93abae8fc2e2
    def execute(self) -> list[AuditFinding]:
        findings = []

        for file_path in self.src_dir.rglob("*.py"):
            # 1. Check Whitelist
            rel_path = str(file_path.relative_to(self.repo_root)).replace("\\", "/")
            if rel_path in self.allowed_paths:
                continue

            # 2. Scan for Forbidden References
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    # We look for String Literals that contain the legacy filenames
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        for artifact in LEGACY_ARTIFACTS:
                            if artifact in node.value:
                                findings.append(
                                    AuditFinding(
                                        check_id="knowledge.limited_legacy_access",
                                        severity=AuditSeverity.ERROR,
                                        message=(
                                            f"Forbidden reference to legacy artifact '{artifact}'. "
                                            "Access is restricted to whitelisted system tools. "
                                            "Use the Database (SSOT) instead."
                                        ),
                                        file_path=rel_path,
                                        line_number=node.lineno,
                                        context={"artifact": artifact},
                                    )
                                )
            except Exception as e:
                logger.debug("Failed to scan %s for legacy access: %s", file_path, e)

        return findings
