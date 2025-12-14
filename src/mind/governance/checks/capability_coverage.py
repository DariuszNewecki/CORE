# src/mind/governance/checks/capability_coverage.py
"""
Ensures knowledge integrity between the Mind (YAML) and the Database (SSOT).
Enforces 'knowledge.database_ssot' by verifying capability alignment.
"""

from __future__ import annotations

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 92f0b3ec-48d7-49f0-aace-2c894186a46f
class CapabilityCoverageCheck(BaseCheck):
    """
    Verifies that capabilities declared in the Mind (domain_definitions.yaml)
    are correctly mirrored in the Database SSOT.
    """

    policy_rule_ids = ["knowledge.database_ssot"]

    # ID: e0730fb8-2616-42b2-915b-48f30ff4ac17
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # 1. Resolve Path to Domain Definitions (The Read-Only Mirror)
        domain_def_path = self.context.mind_path / "knowledge/domain_definitions.yaml"

        if not domain_def_path.exists():
            findings.append(
                AuditFinding(
                    check_id="knowledge.database_ssot",
                    severity=AuditSeverity.ERROR,
                    message="The domain_definitions.yaml mirror is missing.",
                    file_path=str(domain_def_path.relative_to(self.context.repo_path)),
                )
            )
            return findings

        # 2. Extract Declared Capability Domains from YAML
        try:
            with open(domain_def_path, encoding="utf-8") as f:
                content = yaml.safe_load(f)

            # Per domain_definitions.yaml schema: list of objects with 'name'
            declared_domains = {
                d["name"] for d in content.get("capability_domains", []) if "name" in d
            }
        except Exception as exc:
            logger.error("Failed to parse domain definitions: %s", exc)
            return findings

        # 3. Extract Implemented Domains from Database (Operational SSOT)
        # self.context.knowledge_graph is the bridge to the DB
        implemented_symbols = self.context.knowledge_graph.get("symbols", {}).values()

        # We check which domains are actually associated with symbols in the DB
        implemented_domains: set[str] = {
            s.get("domain") for s in implemented_symbols if s.get("domain")
        }

        # 4. Find Drift (Drift = Declared in YAML but missing from DB)
        missing_in_db = declared_domains - implemented_domains

        for domain in sorted(missing_in_db):
            findings.append(
                AuditFinding(
                    check_id="knowledge.database_ssot",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Operational Drift: Domain '{domain}' is declared in "
                        "domain_definitions.yaml but has no symbols in the Database SSOT."
                    ),
                    file_path=str(domain_def_path.relative_to(self.context.repo_path)),
                )
            )

        return findings
