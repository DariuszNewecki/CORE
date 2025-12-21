# src/mind/governance/checks/capability_coverage.py
"""
Ensures knowledge integrity between the Mind (YAML) and the Database (SSOT).
Enforces 'knowledge.database_ssot' by verifying capability alignment.

Ref: .intent/charter/standards/data/governance.json
"""

from __future__ import annotations

from typing import Any, ClassVar

import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: capability-domain-ssot-enforcement
# ID: bd4b4e78-6238-4de1-9616-35f9f086757e
class CapabilityDomainSSOTEnforcement(EnforcementMethod):
    """
    Verifies that capabilities declared in the Mind (domain_definitions.yaml)
    are correctly mirrored in the Database SSOT.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: a7be16ef-6152-457e-9a99-953a923ad92f
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # 1. Resolve Path to Domain Definitions (The Read-Only Mirror)
        domain_def_path = context.mind_path / "knowledge/domain_definitions.yaml"

        if not domain_def_path.exists():
            findings.append(
                self._create_finding(
                    message="The domain_definitions.yaml mirror is missing.",
                    file_path=str(domain_def_path.relative_to(context.repo_path)),
                )
            )
            return findings

        # 2. Extract Declared Capability Domains from YAML
        try:
            content = yaml.safe_load(domain_def_path.read_text(encoding="utf-8"))

            # Per domain_definitions.yaml schema: list of objects with 'name'
            declared_domains = {
                d["name"] for d in content.get("capability_domains", []) if "name" in d
            }
        except Exception as exc:
            logger.error("Failed to parse domain definitions: %s", exc)
            return findings

        # 3. Extract Implemented Domains from Database (Operational SSOT)
        # context.knowledge_graph is the bridge to the DB
        implemented_symbols = context.knowledge_graph.get("symbols", {}).values()

        # We check which domains are actually associated with symbols in the DB
        implemented_domains: set[str] = {
            s.get("domain") for s in implemented_symbols if s.get("domain")
        }

        # DEBUG: Print what we're actually seeing
        logger.info("DEBUG: Declared domains: %s", declared_domains)
        logger.info("DEBUG: Implemented domains: %s", implemented_domains)
        logger.info(
            "DEBUG: Total symbols in knowledge_graph: %s",
            len(list(implemented_symbols)),
        )

        # 4. Find Drift (Drift = Declared in YAML but missing from DB)
        missing_in_db = declared_domains - implemented_domains

        for domain in sorted(missing_in_db):
            findings.append(
                self._create_finding(
                    message=(
                        f"Operational Drift: Domain '{domain}' is declared in "
                        "domain_definitions.yaml but has no symbols in the Database SSOT."
                    ),
                    file_path=str(domain_def_path.relative_to(context.repo_path)),
                )
            )

        return findings


# ID: e0730fb8-2616-42b2-915b-48f30ff4ac17
class CapabilityCoverageCheck(RuleEnforcementCheck):
    """
    Verifies that capabilities declared in the Mind (domain_definitions.yaml)
    are correctly mirrored in the Database SSOT.

    Ref: .intent/charter/standards/data/governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["knowledge.database_ssot"]

    policy_file: ClassVar = settings.paths.policy("governance")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CapabilityDomainSSOTEnforcement(rule_id="knowledge.database_ssot"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
