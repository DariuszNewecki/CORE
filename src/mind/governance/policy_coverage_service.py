# src/mind/governance/policy_coverage_service.py
"""
Provides a service to perform a meta-audit on the constitution itself,
checking for policy coverage and structural integrity by introspecting the
governance checks.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# We only need the canonical settings object.
from shared.config import settings
from shared.logger import getLogger

from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# (Dataclasses and Report Model remain unchanged)
@dataclass
class _RuleRef:
    policy_id: str
    rule_id: str
    enforcement: str


# ID: 7f1a7783-899c-432f-9e03-123503b93ccd
class PolicyCoverageReport(BaseModel):
    report_id: str
    generated_at_utc: str
    repo_root: str
    summary: dict[str, int]
    records: list[dict[str, Any]]
    exit_code: int


# ID: 2cf6528f-62e7-41a7-9350-820f0137a3a4
class PolicyCoverageService:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root: Path = repo_root or settings.REPO_PATH
        self.enforcement_model = self._load_enforcement_model()
        self.all_rules, self.coverage_map = self._discover_rules_and_coverage()
        logger.info(
            "Discovered coverage for %d unique policy rules.", len(self.coverage_map)
        )

    def _load_enforcement_model(self) -> dict[str, int]:
        try:
            return {"error": 1, "warn": 0, "info": 0}  # Simplified default
        except Exception:
            return {"error": 1, "warn": 0, "info": 0}

    # --- THIS IS THE FINAL, CONSOLIDATED, AND CORRECTED METHOD ---
    def _discover_rules_and_coverage(self) -> tuple[list[_RuleRef], dict[str, str]]:
        """
        Loads all policies, extracts all rules, and introspects all checks
        to build a complete coverage map.
        """
        # --- START: RELIABLE POLICY LOADER (using canonical settings) ---
        all_policies = {}
        policy_logical_paths = []

        # This recursive function finds all logical paths from meta.yaml
        def _find_policy_paths(node: Any, prefix: str):
            if isinstance(node, dict):
                for key, value in node.items():
                    _find_policy_paths(value, f"{prefix}.{key}")
            elif isinstance(node, str) and node.endswith(".yaml"):
                policy_logical_paths.append(prefix)

        charter_policies = settings._meta_config.get("charter", {}).get("policies", {})
        _find_policy_paths(charter_policies, "charter.policies")

        # --- FORCE LOAD CRITICAL POLICIES FOR DYNAMIC CHECKS ---
        critical_policies = [
            "agent_governance",
            "code_standards",
            "data_governance",
            "operations",
            "quality_assurance",
            "safety_framework",
        ]
        for policy_id in critical_policies:
            logical_path = f"charter.policies.{policy_id}"
            try:
                all_policies[policy_id] = settings.load(logical_path)
            except Exception as e:
                logger.warning("Could not load critical policy %s: %s", policy_id, e)

        # Also load from meta.yaml (for future extensibility) — avoid overwriting critical ones
        for logical_path in policy_logical_paths:
            policy_id = logical_path.rsplit(".", 1)[-1]
            if policy_id not in all_policies:  # avoid overwrite
                try:
                    all_policies[policy_id] = settings.load(logical_path)
                except Exception as e:
                    logger.warning("Could not load policy %s: %s", policy_id, e)

        # Add other critical policies needed by checks' __init__ methods.
        for policy_name in [
            "audit_ignore_policy",
            "project_structure",
            "runtime_requirements",
        ]:
            try:
                logical_path = f"charter.policies.governance.{policy_name}"
                all_policies[policy_name] = settings.load(logical_path)
            except (FileNotFoundError, AttributeError):
                pass  # It's okay if these optional policies don't exist.
        # --- END: RELIABLE POLICY LOADER ---

        # Extract all rules from the loaded policies.
        all_rules: list[_RuleRef] = []
        for policy_id, policy_data in all_policies.items():
            # ID: 8c172639-8a73-4952-8b85-dd4ce31dac4b
            def visit(node: Any):
                if isinstance(node, dict) and "id" in node and "statement" in node:
                    all_rules.append(
                        _RuleRef(
                            policy_id,
                            str(node["id"]),
                            str(node.get("enforcement", "warn")).lower(),
                        )
                    )
                elif isinstance(node, dict):
                    [visit(v) for v in node.values()]
                elif isinstance(node, list):
                    [visit(i) for i in node]

            visit(policy_data)
        unique_rules = list({(r.policy_id, r.rule_id): r for r in all_rules}.values())

        # Build the complete, accurate Mock Context.
        mock_context = type(
            "MockAuditorContext",
            (),
            {
                "repo_path": self.repo_root,
                "intent_path": self.repo_root / ".intent",
                "mind_path": self.repo_root / ".intent" / "mind",
                "src_dir": self.repo_root / "src",
                "policies": all_policies,  # Now correctly populated
                "python_files": [],
                "symbols_list": [],
                "symbols_map": {},
                "knowledge_graph": {},
            },
        )()

        # Discover coverage by instantiating checks.
        coverage_map: dict[str, str] = {}
        checks_dir = self.repo_root / "src" / "mind" / "governance" / "checks"
        src_root = self.repo_root / "src"

        for path in checks_dir.glob("*.py"):
            if path.name in ("__init__.py", "base_check.py", "knowledge_differ.py"):
                continue
            module_name = str(path.relative_to(src_root).with_suffix("")).replace(
                "/", "."
            )
            try:
                module = importlib.import_module(module_name)
                for member_name, member in inspect.getmembers(module, inspect.isclass):
                    if issubclass(member, BaseCheck) and member is not BaseCheck:
                        # Instantiate all checks (except the one with special needs) to get their rules.
                        rule_ids = (
                            member(mock_context).policy_rule_ids
                            if member_name != "DuplicationCheck"
                            else member.policy_rule_ids
                        )
                        for rule_id in rule_ids:
                            coverage_map[rule_id] = member_name
            except Exception as e:
                logger.error(
                    "Failed to import or inspect check module %s: %s", module_name, e
                )

        return unique_rules, coverage_map

    # ID: e2b692bd-4f43-4032-b146-7f6fa66bf993
    def run(self) -> PolicyCoverageReport:
        records, uncovered_error_rules = [], []
        for rule in self.all_rules:
            coverage = "direct" if rule.rule_id in self.coverage_map else "none"
            covered = coverage == "direct"
            records.append(
                {
                    "policy_id": rule.policy_id,
                    "rule_id": rule.rule_id,
                    "enforcement": rule.enforcement,
                    "coverage": coverage,
                    "covered": covered,
                }
            )
            if not covered and rule.enforcement == "error":
                uncovered_error_rules.append(rule)

        summary = {
            "policies_seen": len(set(r.policy_id for r in self.all_rules)),
            "rules_found": len(self.all_rules),
            "rules_direct": len(self.coverage_map),
            "rules_bound": 0,
            "rules_inferred": 0,
            "uncovered_rules": len(self.all_rules) - len(self.coverage_map),
            "uncovered_error_rules": len(uncovered_error_rules),
        }

        exit_code = self.enforcement_model["error"] if uncovered_error_rules else 0
        report_dict = {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "repo_root": str(self.repo_root),
            "summary": summary,
            "records": records,
            "exit_code": exit_code,
        }
        report_json = json.dumps(report_dict, sort_keys=True, separators=(",", ":"))
        report_id = hashlib.sha256(report_json.encode("utf-8")).hexdigest()
        report_dict["report_id"] = report_id

        return PolicyCoverageReport(**report_dict)
