# src/mind/governance/checks/domain_placement.py
"""
A constitutional audit check to ensure capabilities are declared in the
correct domain manifest file, enforcing the 'structural_compliance' rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.utils.yaml_processor import yaml_processor

logger = getLogger(__name__)


# ID: 0cd8ad5a-ed46-4f18-8335-f95b747d6164
class DomainPlacementCheck(BaseCheck):
    """
    Validates that capability keys declared in a domain manifest file
    match the domain of that file, contributing to the 'structural_compliance' rule.

    Example:
        - File: .intent/mind/knowledge/domains/core.yaml
        - Capability key: "core.introspection.analyze_code" ✅ OK
        - Capability key: "llm.router.select_model"        ❌ Wrong domain
    """

    # Fulfills the contract from BaseCheck.
    policy_rule_ids = [
        "structural_compliance",
    ]

    def __init__(self, context: AuditorContext) -> None:
        super().__init__(context)
        # self.context is set by the parent class.
        self.domains_dir: Path = self.context.mind_path / "knowledge" / "domains"

    # ID: 7eb75aef-6463-450d-8088-e9a64e3d85c8
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by scanning all domain manifests for misplaced capabilities.
        """
        findings: list[AuditFinding] = []

        if not self.domains_dir.is_dir():
            # No domain manifests present yet – nothing to validate.
            return findings

        for domain_file in sorted(self.domains_dir.glob("*.yaml")):
            findings.extend(self._check_domain_file(domain_file))

        return findings

    def _check_domain_file(self, domain_file: Path) -> list[AuditFinding]:
        """Validate a single domain manifest file."""
        findings: list[AuditFinding] = []
        domain_name = domain_file.stem

        try:
            manifest_content: dict[str, Any] | None = yaml_processor.load(domain_file)
        except Exception as exc:
            logger.warning("Failed to load domain manifest %s: %s", domain_file, exc)
            return findings

        if not manifest_content:
            return findings

        capabilities = manifest_content.get("tags", [])
        if not isinstance(capabilities, list):
            return findings

        for cap in capabilities:
            if not isinstance(cap, dict):
                continue
            cap_key = cap.get("key")
            if not cap_key or not isinstance(cap_key, str):
                continue

            if not cap_key.startswith(f"{domain_name}."):
                findings.append(
                    AuditFinding(
                        # Standardized check_id for better traceability.
                        check_id="structural_compliance.domain_placement",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Capability '{cap_key}' is misplaced in '{domain_file.name}'. "
                            f"It should be declared in '{cap_key.split('.')[0]}.yaml'."
                        ),
                        file_path=str(domain_file.relative_to(self.repo_root)),
                        context={
                            "domain_file": domain_file.name,
                            "expected_domain": cap_key.split(".")[0],
                            "actual_domain": domain_name,
                        },
                    )
                )

        return findings
