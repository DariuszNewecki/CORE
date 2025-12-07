# src/mind/governance/checks/knowledge_source_check.py
"""
Compares DB single-source-of-truth tables with their (legacy) YAML exports,
enforcing the database SSOT rules from the data_governance policy.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck

# Import our new engine
from mind.governance.checks.knowledge_differ import KnowledgeDiffer
from services.database.session_manager import get_session
from shared.models import AuditFinding, AuditSeverity


# The configuration remains part of the check, as it's specific to this audit.
TABLE_CONFIGS = {
    "cli_registry": {
        "rule_id": "db.cli_registry_in_db",
        "yaml_paths": [".intent/mind/knowledge/cli_registry.yaml"],
        "table": "core.cli_commands",
        "yaml_key": "commands",
        "primary_key": "name",
    },
    "resource_manifest": {
        "rule_id": "db.llm_resources_in_db",
        "yaml_paths": [".intent/mind/knowledge/resource_manifest.yaml"],
        "table": "core.llm_resources",
        "yaml_key": "llm_resources",
        "primary_key": "name",
    },
    "cognitive_roles": {
        "rule_id": "db.cognitive_roles_in_db",
        "yaml_paths": [".intent/mind/knowledge/cognitive_roles.yaml"],
        "table": "core.cognitive_roles",
        "yaml_key": "cognitive_roles",
        "primary_key": "role",
    },
}


# ID: 81d6e8ed-a6f6-444c-acda-9064896c5111
class KnowledgeSourceCheck(BaseCheck):
    """
    Ensures the database is the Single Source of Truth by detecting drift
    or the presence of legacy YAML knowledge files.
    """

    # Fulfills the contract from BaseCheck.
    policy_rule_ids = [
        "db.ssot_for_operational_data",
        "db.cli_registry_in_db",
        "db.llm_resources_in_db",
        "db.cognitive_roles_in_db",
    ]

    # No __init__ needed, we'll create the differ inside execute.

    # ID: b846d3ab-5762-4bc8-9dfc-f3fa060da29c
    async def execute(self) -> list[AuditFinding]:
        """
        Executes the SSOT check by using the KnowledgeDiffer to compare
        each configured artifact and generating findings for any drift.
        """
        findings: list[AuditFinding] = []
        async with get_session() as session:
            differ = KnowledgeDiffer(session, self.repo_root)
            for config in TABLE_CONFIGS.values():
                result = await differ.compare(config)
                if result["status"] == "failed":
                    findings.extend(self._create_findings_from_result(result, config))
        return findings

    def _create_findings_from_result(
        self, result: dict, config: dict
    ) -> list[AuditFinding]:
        """Translates a diff result into a list of AuditFinding objects."""
        findings = []
        diff = result.get("diff", {})
        rule_id = config["rule_id"]
        yaml_path = str(result["yaml_path"].relative_to(self.repo_root))

        if diff.get("missing_in_db"):
            keys = ", ".join(diff["missing_in_db"])
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"SSOT Violation: Entries exist in legacy file '{yaml_path}' but are missing from the database: {keys}",
                    file_path=yaml_path,
                )
            )

        if diff.get("mismatched"):
            keys = ", ".join([m["key"] for m in diff["mismatched"]])
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"SSOT Violation: Entries in legacy file '{yaml_path}' are out of sync with the database: {keys}",
                    file_path=yaml_path,
                    context={"mismatches": diff["mismatched"]},
                )
            )

        # If the file exists but the diff is empty, it means the file is a redundant but in-sync copy.
        # This can be a WARNING to encourage its removal.
        if not findings:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.WARNING,
                    message=f"SSOT Redundancy: Legacy file '{yaml_path}' exists. It should be removed as the DB is the SSOT.",
                    file_path=yaml_path,
                )
            )

        return findings
