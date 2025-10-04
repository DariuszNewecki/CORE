# src/features/governance/policy_coverage_service.py
"""
Provides a service to perform a meta-audit on the constitution itself,
checking for policy coverage and structural integrity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel
from shared.config import settings
from shared.logger import getLogger

log = getLogger("policy_coverage_service")


# ID: 01a2975a-5754-435d-9e5a-78fc10648abc
class PolicyCoverageReport(BaseModel):
    report_id: str
    generated_at_utc: str
    repo_root: str
    summary: Dict[str, int]
    records: List[Dict[str, Any]]
    exit_code: int


@dataclass
class _PolicyRef:
    """Internal helper to track discovered policies."""

    id: str
    path: Path
    status: str = "active"
    title: Optional[str] = None


# ID: 78d662f3-f672-4f51-b73e-fb411c106728
class PolicyCoverageService:
    """
    Runs a meta-audit on the constitution to ensure all active policies
    are well-formed and covered by the governance model.
    """

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root: Path = repo_root or settings.REPO_PATH
        # --- THIS IS THE REFACTOR ---
        # The service now loads its governing policy via the settings object
        self.enforcement_model_policy = settings.load(
            "charter.policies.governance.enforcement_model_policy"
        )
        self.enforcement_model = self._load_enforcement_model()
        # --- END OF REFACTOR ---

    def _load_enforcement_model(self) -> Dict[str, int]:
        """Loads and parses the enforcement model from the pre-loaded policy content."""
        levels = self.enforcement_model_policy.get("levels", {})
        # Note: exit_code is not a standard part of the model, so we default to standard behavior
        return {
            "error": (
                1 if (levels.get("error") or {}).get("ci_behavior") == "fail" else 0
            ),
            "warn": 0,
            "info": 0,
        }

    def _discover_active_policies(self) -> List[_PolicyRef]:
        """Discovers all active policies by reading the meta.yaml index via settings."""
        refs = []
        # settings._meta_config is a private but convenient accessor here
        policies_in_meta = settings._meta_config.get("charter", {}).get("policies", {})

        # ID: 1fead1e3-077b-4243-92dc-5b151d6fc690
        def find_policies_recursive(data: Any, prefix: str):
            if isinstance(data, dict):
                for key, value in data.items():
                    find_policies_recursive(value, f"{prefix}.{key}" if prefix else key)
            elif isinstance(data, str) and data.endswith("_policy.yaml"):
                logical_path = prefix.replace("charter.policies.", "", 1)
                full_path = settings.get_path(prefix)
                if full_path.exists():
                    refs.append(_PolicyRef(id=logical_path, path=full_path))

        find_policies_recursive(policies_in_meta, "charter.policies")
        return refs

    @staticmethod
    def _extract_rules(policy_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extracts and normalizes rule definitions from a policy file."""
        rules = policy_data.get("rules", [])
        if not isinstance(rules, list):
            return [{"id": "__policy_present__", "enforcement": "warn"}]

        extracted = []
        for r in rules:
            if isinstance(r, dict):
                extracted.append(
                    {
                        "id": str(r.get("id", "__missing_id__")),
                        "enforcement": str(r.get("enforcement", "warn")).lower(),
                    }
                )
        return extracted or [{"id": "__policy_present__", "enforcement": "warn"}]

    # ID: 07977c2f-e3df-4c79-a7eb-f7761d4a6487
    def run(self) -> PolicyCoverageReport:
        """
        Executes the policy coverage audit and returns a structured report.
        """
        policies = self._discover_active_policies()
        records: List[Dict[str, Any]] = []
        failures: List[Tuple[str, str]] = []

        for policy_ref in policies:
            policy_data = settings.load(f"charter.policies.{policy_ref.id}")
            rules = self._extract_rules(policy_data)

            for rule in rules:
                level = rule["enforcement"]
                is_covered = bool(rule["id"] != "__missing_id__") and level in [
                    "error",
                    "warn",
                    "info",
                ]

                records.append(
                    {
                        "policy_id": policy_ref.id,
                        "policy_path": str(policy_ref.path.relative_to(self.repo_root)),
                        "rule_id": rule["id"],
                        "enforcement": level,
                        "covered": is_covered,
                    }
                )
                if not is_covered:
                    failures.append((policy_ref.id, level))

        exit_code = 0
        for _, level in failures:
            exit_code = max(exit_code, self.enforcement_model.get(level, 0))

        report_dict = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "repo_root": str(self.repo_root),
            "summary": {
                "policies_seen": len(policies),
                "rules_found": len(records),
                "uncovered_rules": len(failures),
            },
            "records": records,
            "exit_code": exit_code,
        }

        report_json = json.dumps(report_dict, sort_keys=True, separators=(",", ":"))
        report_id = hashlib.sha256(report_json.encode("utf-8")).hexdigest()
        report_dict["report_id"] = report_id

        return PolicyCoverageReport(**report_dict)
