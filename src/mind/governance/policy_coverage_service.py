# src/mind/governance/policy_coverage_service.py

"""
Policy Coverage Service - Meta-Auditor for the Constitution.

REFACTORED:
- Removed dependency on 'mind.governance.checks' (Legacy Class Scanning).
- Determines coverage by cross-referencing Intent (JSON) with Evidence (Audit Ledger).
- Aligned with 'knowledge.database_ssot' principle.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
class _RuleRef:
    """Internal reference for a rule discovered in the Constitution."""

    policy_id: str
    rule_id: str
    enforcement: str
    has_engine: bool


# ID: eaccc6c0-1443-401b-94ca-d905c4a7c0bd
class PolicyCoverageReport(BaseModel):
    """Structured report for constitutional coverage."""

    report_id: str
    generated_at_utc: str
    repo_root: str
    summary: dict[str, int]
    records: list[dict[str, Any]]
    exit_code: int


# ID: ea004e9f-115b-4764-b739-5eefb6e1e301
class PolicyCoverageService:
    """
    Analyzes the Constitution to determine which rules are:
    1. Enforced (found in latest audit evidence)
    2. Implementable (has an engine defined in JSON)
    3. Declared Only (exists but no engine defined)
    """

    def __init__(self, repo_root: Path | None = None):
        self.repo_root: Path = repo_root or settings.REPO_PATH
        self.evidence_path = self.repo_root / "reports/audit/latest_audit.json"

        # Load evidence of what actually ran
        self.executed_rules = self._load_audit_evidence()

        # Discover all rules declared in the Mind (.intent)
        self.all_rules = self._discover_rules_via_intent()

    def _load_audit_evidence(self) -> set[str]:
        """Loads executed rule IDs from the authoritative Evidence Ledger."""
        if not self.evidence_path.exists():
            logger.debug("Evidence Ledger not found at %s", self.evidence_path)
            return set()
        try:
            data = json.loads(self.evidence_path.read_text(encoding="utf-8"))
            return set(data.get("executed_rules", []))
        except Exception as e:
            logger.warning("Failed to parse Evidence Ledger: %s", e)
            return set()

    def _discover_rules_via_intent(self) -> list[_RuleRef]:
        """
        Crawls .intent/ and .intent/charter/standards to find rule declarations.
        Replaces the legacy Python class introspection.
        """
        rules_found: list[_RuleRef] = []
        intent_root = self.repo_root / ".intent"

        # We look in both modular policies and the foundational standards
        search_roots = [intent_root / "policies", intent_root / "charter/standards"]

        for root in search_roots:
            if not root.exists():
                continue

            for file_path in root.rglob("*.json"):
                try:
                    content = json.loads(file_path.read_text(encoding="utf-8"))
                    policy_id = content.get("id", file_path.stem)

                    # Rules are usually in a flat 'rules' array (v2 format)
                    rules_list = content.get("rules", [])
                    if isinstance(rules_list, list):
                        for r in rules_list:
                            if isinstance(r, dict) and "id" in r:
                                # A rule is implementable if it declares an engine
                                engine_defined = "check" in r and "engine" in r["check"]
                                rules_found.append(
                                    _RuleRef(
                                        policy_id=policy_id,
                                        rule_id=str(r["id"]),
                                        enforcement=str(
                                            r.get("enforcement", "warn")
                                        ).lower(),
                                        has_engine=engine_defined,
                                    )
                                )
                except Exception as e:
                    logger.debug("Skipping unparseable policy %s: %s", file_path, e)

        return rules_found

    # ID: 0d9c360a-0817-4df7-8465-728cfc924a5a
    def run(self) -> PolicyCoverageReport:
        """
        Builds the coverage report by cross-referencing intent with evidence.
        """
        records = []
        uncovered_error_rules = []

        for rule in self.all_rules:
            # A rule is 'enforced' if its ID is in the Evidence Ledger
            is_enforced = rule.rule_id in self.executed_rules

            if is_enforced:
                status = "enforced"
            elif rule.has_engine:
                status = "implementable"
            else:
                status = "declared_only"

            records.append(
                {
                    "policy_id": rule.policy_id,
                    "rule_id": rule.rule_id,
                    "enforcement": rule.enforcement,
                    "coverage": status,
                    "covered": is_enforced,
                }
            )

            # Track critical gaps (rules that MUST be error-level but didn't run)
            if not is_enforced and rule.enforcement == "error":
                uncovered_error_rules.append(rule)

        summary = {
            "rules_total": len(self.all_rules),
            "rules_enforced": sum(1 for r in records if r["coverage"] == "enforced"),
            "rules_implementable": sum(
                1 for r in records if r["coverage"] == "implementable"
            ),
            "rules_declared_only": sum(
                1 for r in records if r["coverage"] == "declared_only"
            ),
            "uncovered_error_rules": len(uncovered_error_rules),
        }

        # The system fails if critical rules are not enforced
        exit_code = 1 if uncovered_error_rules else 0

        report_data = {
            "report_id": hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:12],
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "repo_root": str(self.repo_root),
            "summary": summary,
            "records": records,
            "exit_code": exit_code,
        }

        return PolicyCoverageReport(**report_data)
