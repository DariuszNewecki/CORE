# src/mind/governance/checks/core_safety_check.py

"""
CORE Safety Governance Check

Enforces safety rules that prevent autonomous or accidental modification of CORE's
mission and protected assets.

Targets:
- safety.immutable_core_mission
- safety.no_autonomous_core_modification

Evidence-backed strategy (conservative):
1) Policy must exist and declare required deny patterns (safety.json).
2) Enforcement must exist in code, at minimum at a known write-gate/choke point
   (proposal_service) and/or explicit "dangerous" command gates.

This check will NOT pretend-pass if:
- policy cannot be found/parsed
- deny patterns are missing
- enforcement evidence cannot be located
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

RULE_IMMUTABLE_CORE_MISSION = "safety.immutable_core_mission"
RULE_NO_AUTONOMOUS_CORE_MODIFICATION = "safety.no_autonomous_core_modification"

# These are the minimum protected assets we can assert from your policy grep.
REQUIRED_MISSION_PATTERNS: set[str] = {"mind_export/northstar.yaml"}

# Where we expect enforcement evidence to exist (based on your grep results).
PROPOSAL_SERVICE_PATH = Path("src/body/cli/logic/proposal_service.py")
DANGEROUS_COMMANDS_PATH = Path("src/body/cli/commands/run.py")


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.

    We only pass parameters supported by the runtime signature to prevent
    unexpected keyword argument errors (e.g., 'details', 'rule_id', etc.).
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _read_text(repo_path: Path, rel: Path) -> str:
    p = (repo_path / rel).resolve()
    return p.read_text(encoding="utf-8")


def _resolve_safety_policy_path(repo_path: Path) -> Path:
    """
    Prefer PathResolver first, then fall back to a conservative known path.
    """
    try:
        p = settings.paths.policy("safety")
        return Path(p) if not isinstance(p, Path) else p
    except Exception:
        return repo_path / ".intent" / "policies" / "operations" / "safety.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_rules(policy_doc: Any) -> list[dict[str, Any]]:
    if isinstance(policy_doc, dict):
        rules = policy_doc.get("rules")
        if isinstance(rules, list):
            return [r for r in rules if isinstance(r, dict)]
    return []


def _extract_denies(policy_doc: Any) -> list[dict[str, Any]]:
    """
    Your policy file appears to contain 'denies' entries (deny patterns).
    We keep this robust: accept either 'denies' or 'deny' lists.
    """
    if not isinstance(policy_doc, dict):
        return []
    candidates = []
    for k in ("denies", "deny"):
        v = policy_doc.get(k)
        if isinstance(v, list):
            candidates.extend([d for d in v if isinstance(d, dict)])
    return candidates


def _deny_patterns(policy_doc: Any) -> set[str]:
    denies = _extract_denies(policy_doc)
    out: set[str] = set()
    for d in denies:
        pat = d.get("pattern")
        if isinstance(pat, str) and pat.strip():
            out.add(pat.strip())
    return out


def _rule_by_id(policy_doc: Any, rule_id: str) -> dict[str, Any] | None:
    for r in _extract_rules(policy_doc):
        if r.get("id") == rule_id:
            return r
    return None


def _evidence_proposal_service_denies_mission(repo_path: Path) -> dict[str, Any] | None:
    """
    Evidence: proposal_service blocks modifications to mission / protected assets,
    typically by raising PermissionError.

    We cannot require exact implementation details; we require:
    - file exists
    - it contains PermissionError
    - it references at least one REQUIRED_MISSION_PATTERNS (or the rule id)
    """
    abs_path = repo_path / PROPOSAL_SERVICE_PATH
    if not abs_path.exists():
        return None

    try:
        src = _read_text(repo_path, PROPOSAL_SERVICE_PATH)
    except Exception:
        return None

    if "PermissionError" not in src:
        return None

    # Strong evidence: explicit mission file references OR rule-id references.
    patterns_hit = [p for p in REQUIRED_MISSION_PATTERNS if p in src]
    rule_hit = RULE_IMMUTABLE_CORE_MISSION in src or "deny_northstar" in src

    if not patterns_hit and not rule_hit:
        return None

    return {
        "file": str(PROPOSAL_SERVICE_PATH),
        "permission_error_present": True,
        "patterns_hit": patterns_hit,
        "rule_or_deny_symbol_hit": rule_hit,
    }


def _evidence_dangerous_command_gating(repo_path: Path) -> dict[str, Any] | None:
    """
    Evidence: some CLI commands are marked dangerous=True, which indicates
    non-default permissions are required for file/DB modifications.

    We require:
    - run.py exists
    - it contains '@core_command(dangerous=True)' at least once
    """
    abs_path = repo_path / DANGEROUS_COMMANDS_PATH
    if not abs_path.exists():
        return None

    try:
        src = _read_text(repo_path, DANGEROUS_COMMANDS_PATH)
    except Exception:
        return None

    token = "@core_command(dangerous=True)"
    if token not in src:
        return None

    return {
        "file": str(DANGEROUS_COMMANDS_PATH),
        "dangerous_decorators_present": src.count(token),
    }


# ID: 1b8e8f58-9cc2-4c0a-9c25-9a8a8d8b3d17
class ImmutableCoreMissionEnforcement(EnforcementMethod):
    """
    Enforces safety.immutable_core_mission.

    Requirements (evidence-backed):
    - safety policy exists and declares the rule.
    - deny patterns include mind_export/northstar.yaml (minimum).
    - enforcement evidence exists in proposal_service (PermissionError gate).
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 7f9aa365-0a93-4c3c-a5e5-6d8b6a0b2a84
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        policy_path = _resolve_safety_policy_path(repo_path)
        if not policy_path.exists():
            return [
                _create_finding_safe(
                    self,
                    message="Safety policy file missing; cannot validate safety.immutable_core_mission.",
                    file_path=str(policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        try:
            policy_doc = _load_json(policy_path)
        except Exception as exc:
            return [
                _create_finding_safe(
                    self,
                    message=f"Failed to parse safety policy JSON: {exc}",
                    file_path=str(policy_path.relative_to(repo_path)),
                    severity=AuditSeverity.ERROR,
                )
            ]

        rule = _rule_by_id(policy_doc, RULE_IMMUTABLE_CORE_MISSION)
        if not rule:
            return [
                _create_finding_safe(
                    self,
                    message="safety.immutable_core_mission not declared in safety policy.",
                    file_path=str(policy_path.relative_to(repo_path)),
                    severity=AuditSeverity.ERROR,
                )
            ]

        denies = _deny_patterns(policy_doc)
        missing = sorted(REQUIRED_MISSION_PATTERNS - denies)
        if missing:
            return [
                _create_finding_safe(
                    self,
                    message="Safety policy deny patterns missing required mission protections.",
                    file_path=str(policy_path.relative_to(repo_path)),
                    severity=AuditSeverity.ERROR,
                    evidence={"missing_patterns": missing, "rule": rule},
                )
            ]

        evidence = _evidence_proposal_service_denies_mission(repo_path)
        if not evidence:
            return [
                _create_finding_safe(
                    self,
                    message="No enforcement evidence found: proposal_service does not appear to deny mission modifications (PermissionError gate missing or no mission reference).",
                    file_path=str(PROPOSAL_SERVICE_PATH),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "expected_file": str(PROPOSAL_SERVICE_PATH),
                        "required_patterns": sorted(REQUIRED_MISSION_PATTERNS),
                    },
                )
            ]

        return []


# ID: 7c7d25e1-75b2-4b71-9228-7225b1f245aa
class NoAutonomousCoreModificationEnforcement(EnforcementMethod):
    """
    Enforces safety.no_autonomous_core_modification.

    Evidence-backed (conservative) requirements:
    - safety policy declares the rule (we do not enforce a specific structure).
    - there is at least one explicit gating mechanism in code:
      - dangerous=True command markers AND/OR proposal_service PermissionError gating.

    This is deliberately conservative: it ensures that there is at least one
    explicit mechanism preventing "default" execution from modifying core assets.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 05a5d5ad-0bfe-4d56-aafb-5fd2d8f9d87a
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        policy_path = _resolve_safety_policy_path(repo_path)
        if not policy_path.exists():
            return [
                _create_finding_safe(
                    self,
                    message="Safety policy file missing; cannot validate safety.no_autonomous_core_modification.",
                    file_path=str(policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        try:
            policy_doc = _load_json(policy_path)
        except Exception as exc:
            return [
                _create_finding_safe(
                    self,
                    message=f"Failed to parse safety policy JSON: {exc}",
                    file_path=str(policy_path.relative_to(repo_path)),
                    severity=AuditSeverity.ERROR,
                )
            ]

        rule = _rule_by_id(policy_doc, RULE_NO_AUTONOMOUS_CORE_MODIFICATION)
        if not rule:
            return [
                _create_finding_safe(
                    self,
                    message="safety.no_autonomous_core_modification not declared in safety policy.",
                    file_path=str(policy_path.relative_to(repo_path)),
                    severity=AuditSeverity.ERROR,
                )
            ]

        evidence: dict[str, Any] = {"rule": rule}

        proposal_evidence = _evidence_proposal_service_denies_mission(repo_path)
        if proposal_evidence:
            evidence["proposal_service_gate"] = proposal_evidence

        dangerous_evidence = _evidence_dangerous_command_gating(repo_path)
        if dangerous_evidence:
            evidence["dangerous_command_gates"] = dangerous_evidence

        if (
            "proposal_service_gate" not in evidence
            and "dangerous_command_gates" not in evidence
        ):
            return [
                _create_finding_safe(
                    self,
                    message="No enforcement evidence found for safety.no_autonomous_core_modification (expected dangerous command gating and/or explicit PermissionError write gate).",
                    file_path=str(DANGEROUS_COMMANDS_PATH),
                    severity=AuditSeverity.ERROR,
                    evidence=evidence,
                )
            ]

        return []


# ID: 5db4d0f3-9d17-41a9-9f9c-8e7d2e6a2b4b
class CoreSafetyCheck(RuleEnforcementCheck):
    """
    CORE safety check enforcing mission immutability and autonomous modification constraints.

    Ref:
    - standard_operations_safety
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_IMMUTABLE_CORE_MISSION,
        RULE_NO_AUTONOMOUS_CORE_MODIFICATION,
    ]

    # Prefer PathResolver if available; fallback handled in enforcement methods.
    # Keeping this as best-effort prevents import-time crashes if resolver changes.
    try:
        policy_file: ClassVar[Path] = settings.paths.policy("safety")
    except Exception:
        policy_file = Path(".intent/policies/operations/safety.json")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        ImmutableCoreMissionEnforcement(
            rule_id=RULE_IMMUTABLE_CORE_MISSION,
            severity=AuditSeverity.ERROR,
        ),
        NoAutonomousCoreModificationEnforcement(
            rule_id=RULE_NO_AUTONOMOUS_CORE_MODIFICATION,
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
