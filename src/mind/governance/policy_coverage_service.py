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

from mind.governance.checks.base_check import BaseCheck

# We only need the canonical settings object.
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
class _RuleRef:
    policy_id: str
    rule_id: str
    enforcement: str


# ID: 8fcd8be3-c283-4034-9a69-0af548b1c6d1
class PolicyCoverageReport(BaseModel):
    report_id: str
    generated_at_utc: str
    repo_root: str
    summary: dict[str, int]
    records: list[dict[str, Any]]
    exit_code: int


# ID: 116bb208-a6a7-4aee-8981-9140320d7ba9
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

    def _discover_rules_and_coverage(self) -> tuple[list[_RuleRef], dict[str, str]]:
        """
        Loads all policies, extracts all rules, and introspects all checks
        to build a complete coverage map.
        """
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

        # Extract all rules from the loaded policies.
        all_rules: list[_RuleRef] = []
        for policy_id, policy_data in all_policies.items():
            # ID: e5fe8c03-90d1-4f16-b25d-a909b5a87b5f
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
        # FIX: Added source_structure
        mock_context = type(
            "MockAuditorContext",
            (),
            {
                "repo_path": self.repo_root,
                "intent_path": self.repo_root / ".intent",
                "mind_path": self.repo_root / ".intent" / "mind",
                "src_dir": self.repo_root / "src",
                "policies": all_policies,
                "source_structure": all_policies.get("project_structure", {}),
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
                        try:
                            # Instantiate all checks (except the one with special needs) to get their rules.
                            if member_name == "DuplicationCheck":
                                # DuplicationCheck needs extra args sometimes, but defaults to None
                                # However, we can just inspect the class attribute directly if we don't need instance
                                # But BaseCheck subclasses usually set it on the class.
                                # Let's try instantiation to be safe as some might be dynamic (like SecurityChecks)
                                instance = member(mock_context)
                                rule_ids = instance.policy_rule_ids
                            else:
                                instance = member(mock_context)
                                rule_ids = instance.policy_rule_ids

                            for rule_id in rule_ids:
                                coverage_map[rule_id] = member_name
                        except Exception as e:
                            logger.error(
                                f"Could not instantiate check {member_name}: {e}"
                            )

            except Exception as e:
                logger.error(
                    "Failed to import or inspect check module %s: %s", module_name, e
                )

        return unique_rules, coverage_map

    # ID: 2b6e0823-f351-469c-aaec-f418cd5ad7bf
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
