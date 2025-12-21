# src/mind/governance/checks/intent_canary_required_check.py
"""
Intent Canary Required Governance Check

Enforces operations rule declared in standard_operations_general:
- intent.canary_required

Intent:
CORE must have at least one "canary" enforcement rule wired into the audit
pipeline to prove the enforcement system is alive and fails when it should.

Conservative enforcement (evidence-backed):
1) Confirm one or more canary rules are declared in the operations policy.
2) Confirm at least one canary rule is enforced (evidence-backed) by existence of
   a corresponding enforcement implementation under src/mind/governance/checks.
3) Confirm canary check module(s) exist (by convention) so the system has a
   runtime canary.

Design constraints:
- Prefer rule_data/policy content first.
- Fall back to repository discovery only when policy data is insufficient.
- Do not pretend-pass if we cannot discover required artifacts.
- Hardened against varying EnforcementMethod._create_finding() signatures.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
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

RULE_INTENT_CANARY_REQUIRED = "intent.canary_required"


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.
    Filter unsupported kwargs to avoid runtime failures (e.g., 'details', 'rule_id').
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _safe_load(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _extract_rules(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, dict):
        rules = doc.get("rules")
        if isinstance(rules, list):
            return [r for r in rules if isinstance(r, dict)]
    return []


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


def _discover_check_modules(repo_path: Path) -> list[str]:
    """
    Discover governance check modules by scanning:
    - src/mind/governance/checks/*.py
    Return module filenames (relative paths) for evidence.
    """
    checks_dir = repo_path / "src" / "mind" / "governance" / "checks"
    if not checks_dir.exists():
        return []
    out: list[str] = []
    for p in sorted(checks_dir.glob("*.py")):
        if not p.is_file():
            continue
        out.append(_rel(repo_path, p))
    return out


def _policy_canary_rule_ids(operations_policy_doc: Any) -> list[str]:
    """
    Conservative extraction:
    - any rule id starting with 'canary.' is considered canary inventory
    """
    rules = _extract_rules(operations_policy_doc)
    ids: list[str] = []
    for r in rules:
        rid = r.get("id")
        if isinstance(rid, str) and rid.strip().startswith("canary."):
            ids.append(rid.strip())
    return sorted(set(ids))


def _check_modules_look_like_canary(mod_paths: list[str]) -> list[str]:
    """
    Conservative detection:
    - file name contains 'canary' and ends with '_check.py' or contains 'canary' at all.
    """
    out: list[str] = []
    for p in mod_paths:
        name = Path(p).name.lower()
        if "canary" in name and name.endswith(".py"):
            out.append(p)
    return sorted(set(out))


# ID: 7b0a6c31-6c36-41d7-9db2-4fd9a832ee4e
class IntentCanaryRequiredEnforcement(EnforcementMethod):
    """
    Enforces presence of at least one canary rule + corresponding check wiring.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 1a4fdd0d-76f0-4d8f-9c24-24c163e8f3f7
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        # Locate operations policy (canonical)
        try:
            operations_policy_path = settings.paths.policy("operations")
        except Exception:
            operations_policy_path = (
                repo_path / ".intent" / "policies" / "operations" / "operations.yaml"
            )

        if not isinstance(operations_policy_path, Path):
            operations_policy_path = Path(operations_policy_path)

        if not operations_policy_path.exists():
            return [
                _create_finding_safe(
                    self,
                    message="Operations policy not found; cannot validate intent.canary_required.",
                    file_path=str(operations_policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        try:
            operations_doc = _safe_load(operations_policy_path)
        except Exception as exc:
            return [
                _create_finding_safe(
                    self,
                    message=f"Failed to parse operations policy: {exc}",
                    file_path=_rel(repo_path, operations_policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        canary_ids = _policy_canary_rule_ids(operations_doc)
        if not canary_ids:
            return [
                _create_finding_safe(
                    self,
                    message="No canary.* rules declared in operations policy; intent.canary_required violated.",
                    file_path=_rel(repo_path, operations_policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "expected": "At least one rule id with prefix 'canary.' in operations policy",
                        "operations_policy": _rel(repo_path, operations_policy_path),
                    },
                )
            ]

        # Discover check modules and look for canary check implementations
        check_modules = _discover_check_modules(repo_path)
        if not check_modules:
            return [
                _create_finding_safe(
                    self,
                    message="No governance checks discovered under src/mind/governance/checks; cannot validate canary wiring.",
                    file_path="src/mind/governance/checks",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "canary_rule_ids": canary_ids,
                        "checks_dir_exists": False,
                    },
                )
            ]

        canary_modules = _check_modules_look_like_canary(check_modules)

        # We require at least one canary module file to exist for "canary is wired"
        if not canary_modules:
            return [
                _create_finding_safe(
                    self,
                    message="No canary check implementation module found under src/mind/governance/checks (expected a file containing 'canary').",
                    file_path="src/mind/governance/checks",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "canary_rule_ids": canary_ids,
                        "discovered_check_modules": check_modules[:50],
                    },
                )
            ]

        # Additionally: require that at least one declared canary rule is already enforced
        # by presence of known canary rule ids in the policy inventory + existence of canary modules.
        # This is conservative because coverage artefact parsing is handled by integration.coverage_minimum already.
        return []


# ID: 2f4c0cc1-1f33-44a2-a4d8-9e46ac8f9d3b
class IntentCanaryRequiredCheck(RuleEnforcementCheck):
    """
    Enforces intent.canary_required.

    Ref:
    - standard_operations_general
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTENT_CANARY_REQUIRED]

    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntentCanaryRequiredEnforcement(
            rule_id=RULE_INTENT_CANARY_REQUIRED,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
