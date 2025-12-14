# src/mind/governance/checks/knowledge_source_check.py
"""
Compares DB single-source-of-truth tables with legacy YAML files to detect drift.
Enforces data_governance policy (Knowledge Integrity).
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from mind.governance.checks.knowledge_differ import KnowledgeDiffer
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Config defines the mapping between DB Tables (SSOT) and Legacy Files
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
    Ensures that if legacy knowledge files exist, they match the Database (SSOT).
    Drift indicates a 'Split-Brain' scenario which is a critical violation.

    Note: FileChecks.py may also flag the existence of these files as an error,
    but this check specifically validates *data integrity* before they are removed.
    """

    policy_rule_ids = [
        "db.ssot_for_operational_data",
        "db.cli_registry_in_db",
        "db.llm_resources_in_db",
        "db.cognitive_roles_in_db",
    ]

    # ID: b846d3ab-5762-4bc8-9dfc-f3fa060da29c
    async def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # Use a fresh session for the check logic
        # Note: Mind layer is permitted to access infrastructure directly for audit purposes
        try:
            async with get_session() as session:
                differ = KnowledgeDiffer(session, self.repo_root)

                for config_name, config in TABLE_CONFIGS.items():
                    try:
                        result = await differ.compare(config)

                        if result["status"] == "failed":
                            findings.extend(
                                self._create_findings_from_result(result, config)
                            )
                        elif result["status"] == "error":
                            # Handle DB/YAML read errors reported by Differ
                            findings.append(
                                AuditFinding(
                                    check_id=config["rule_id"],
                                    severity=AuditSeverity.WARNING,
                                    message=f"SSOT Check Error for {config_name}: {result.get('error')}",
                                    file_path=str(config["yaml_paths"][0]),
                                )
                            )

                    except Exception as e:
                        logger.error("Knowledge diff failed for %s: %s", config_name, e)
                        findings.append(
                            AuditFinding(
                                check_id="db.ssot_for_operational_data",
                                severity=AuditSeverity.ERROR,
                                message=f"Internal error auditing {config_name}: {e}",
                                file_path="N/A",
                            )
                        )
        except Exception as e:
            logger.error("Failed to acquire DB session for KnowledgeSourceCheck: %s", e)
            # Fail open or closed? If DB is down, we probably have bigger problems.

        return findings

    def _create_findings_from_result(
        self, result: dict, config: dict
    ) -> list[AuditFinding]:
        """Translates a diff result into a list of AuditFinding objects."""
        findings = []
        diff = result.get("diff", {})
        rule_id = config["rule_id"]

        # Safe path resolution
        try:
            yaml_path = str(result["yaml_path"].relative_to(self.repo_root))
        except (AttributeError, ValueError):
            yaml_path = config["yaml_paths"][0]

        # 1. Missing in DB (Critical: File has data DB doesn't)
        if diff.get("missing_in_db"):
            keys = ", ".join(sorted(diff["missing_in_db"]))
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"SSOT Violation (Data Loss Risk): Legacy file contains entries missing "
                        f"from Database: [{keys}]. Run `core-admin manage database sync-knowledge`."
                    ),
                    file_path=yaml_path,
                    context={"missing_keys": diff["missing_in_db"]},
                )
            )

        # 2. Mismatched Data (Critical: Split Brain)
        if diff.get("mismatched"):
            keys = ", ".join(sorted([m["key"] for m in diff["mismatched"]]))
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"SSOT Violation (Split Brain): Data mismatch between Legacy file and Database "
                        f"for keys: [{keys}]. Database is authoritative."
                    ),
                    file_path=yaml_path,
                    context={"mismatches": diff["mismatched"]},
                )
            )

        return findings
