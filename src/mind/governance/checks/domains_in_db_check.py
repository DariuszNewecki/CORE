# src/mind/governance/checks/domains_in_db_check.py
"""
Enforces db.domains_in_db: Code must only reference valid, registered domains.
Validates code usage against the Constitutional Domain Definitions.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 77e5c60a-7802-4d64-be11-c1bc20cde9d9
class DomainsInDbCheck(BaseCheck):
    """
    Scans source code for 'get_domain("string")' calls and verifies the string
    corresponds to a valid domain defined in domain_definitions.yaml.
    """

    policy_rule_ids = ["db.domains_in_db"]

    # ID: 73e385d6-375d-440e-b8f3-b9b4abe78c25
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # 1. Load Valid Domains from Intent (The Source of Truth for Definitions)
        domain_def_path = self.context.mind_path / "knowledge/domain_definitions.yaml"
        valid_domains = set()

        if domain_def_path.exists():
            try:
                data = yaml.safe_load(domain_def_path.read_text(encoding="utf-8"))
                # Extract 'name' from capability_domains list
                valid_domains = {
                    d.get("name")
                    for d in data.get("capability_domains", [])
                    if isinstance(d, dict) and d.get("name")
                }
            except Exception as e:
                logger.error(
                    "Failed to load domain definitions from %s: %s", domain_def_path, e
                )
                # Fail open or closed? Failing open (return findings) avoids crashing,
                # but we can't validate without definitions.
                return []
        else:
            logger.warning(
                "domain_definitions.yaml missing. Cannot validate domain usage."
            )
            return []

        # 2. Scan Codebase
        # self.context.src_dir is preferred over self.context.python_files if not available
        # Assuming BaseCheck provides a way to iterate files, or we use src_dir.rglob
        for file_path in self.src_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Detect usage: get_domain("some_domain") or self.get_domain("...")
                        if self._is_get_domain_call(node):
                            # Extract the first argument if it's a string literal
                            if node.args and isinstance(
                                node.args[0], ast.Constant
                            ):  # ast.Constant for Py3.8+
                                domain_arg = node.args[0].value
                                if (
                                    isinstance(domain_arg, str)
                                    and domain_arg not in valid_domains
                                ):
                                    findings.append(
                                        self._create_finding(
                                            file_path, node.lineno, domain_arg
                                        )
                                    )
            except SyntaxError:
                continue  # Skip unparseable files
            except Exception as e:
                logger.debug("Error analyzing file %s: %s", file_path, e)

        return findings

    def _is_get_domain_call(self, node: ast.Call) -> bool:
        """Helper to identify get_domain(...) calls."""
        if isinstance(node.func, ast.Name) and node.func.id == "get_domain":
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get_domain":
            return True
        return False

    def _create_finding(self, file_path: Path, line: int, domain: str) -> AuditFinding:
        return AuditFinding(
            check_id="db.domains_in_db",
            severity=AuditSeverity.ERROR,
            message=(
                f"Unregistered domain reference: '{domain}'. "
                "All domains must be defined in domain_definitions.yaml."
            ),
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
