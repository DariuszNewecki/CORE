# src/mind/governance/checks/ir_triage_check.py
"""
IR Triage Governance Check

Enforces incident-response triage rule declared in standard_operations_general:
- ir.triage_required

Evidence-backed, conservative enforcement:
1) Verify the rule exists in the operations policy.
2) Discover IR triage artefacts under .intent/ that plausibly represent the IR triage
   definition/flow/playbook (path + filename heuristics).
3) Require at least one artefact that:
   - is parseable (YAML/JSON)
   - declares schema_id (preferred) OR contains clear IR-triage markers
4) Provide actionable evidence (sample files and why they match / do not match).

This check is intentionally minimal: it proves that IR triage is explicitly declared
as an artefact in the governed intent space. It does not validate IR operational quality.

Design constraints:
- No pretend-pass if .intent is missing or nothing is discoverable.
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

RULE_IR_TRIAGE_REQUIRED = "ir.triage_required"

# Heuristics: where triage docs usually live and how they are named
_TRIAGE_PATH_HINTS: tuple[str, ...] = (
    "/.intent/ir/",
    "/.intent/incident_response/",
    "/.intent/operations/ir/",
    "/.intent/runbooks/",
    "/.intent/playbooks/",
    "/.intent/charter/standards/operations/",
)

_TRIAGE_NAME_HINTS: tuple[str, ...] = (
    "triage",
    "incident_triage",
    "ir_triage",
    "incident_response_triage",
    "incident_response",
    "ir",
)

# Content hints (extremely conservative)
_TRIAGE_CONTENT_MARKERS: tuple[str, ...] = (
    "triage",
    "severity",
    "classification",
    "impact",
    "priority",
    "containment",
    "escalation",
)


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
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


def _looks_like_triage_path(p: Path) -> bool:
    ps = str(p).replace("\\", "/").lower()
    return any(h in ps for h in _TRIAGE_PATH_HINTS) or any(
        n in p.name.lower() for n in _TRIAGE_NAME_HINTS
    )


def _score_triage_candidate(doc: Any) -> int:
    """
    Score candidate documents by structure/content. Score >= 2 => strong candidate.
    """
    score = 0
    if isinstance(doc, dict):
        # Prefer schema-governed docs
        sid = doc.get("schema_id")
        if isinstance(sid, str) and sid.strip():
            score += 2

        # Common fields in triage definitions
        keys = {str(k).lower() for k in doc.keys()}
        if "triage" in keys or "severity" in keys or "classification" in keys:
            score += 1
        if "escalation" in keys or "escalate" in keys:
            score += 1

        # Nested markers
        as_text = json.dumps(doc, ensure_ascii=False).lower()
        if sum(1 for m in _TRIAGE_CONTENT_MARKERS if m in as_text) >= 3:
            score += 1
    else:
        # If it's not a dict, we cannot treat it as a governed IR artefact.
        score += 0
    return score


# ID: 6a9271a0-10f5-4bdb-9b39-1f56ed1c9fd0
class IRTriageRequiredEnforcement(EnforcementMethod):
    """
    Validates that IR triage is explicitly represented as a governed intent artefact.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 65f3b4d3-e710-42c2-a4ac-49c7471eecad
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path
        intent_root = repo_path / ".intent"

        # Confirm rule exists in operations policy
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
                    message="Operations policy not found; cannot validate ir.triage_required.",
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

        if not any(
            r.get("id") == RULE_IR_TRIAGE_REQUIRED
            for r in _extract_rules(operations_doc)
        ):
            return [
                _create_finding_safe(
                    self,
                    message="ir.triage_required is not declared in operations policy.",
                    file_path=_rel(repo_path, operations_policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={"expected_rule_id": RULE_IR_TRIAGE_REQUIRED},
                )
            ]

        if not intent_root.exists():
            return [
                _create_finding_safe(
                    self,
                    message=".intent directory not found; cannot validate ir.triage_required.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                )
            ]

        # Discover candidates
        candidates: list[Path] = []
        for p in intent_root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            # Skip schemas
            if "/schemas/" in str(p).replace("\\", "/"):
                continue
            if _looks_like_triage_path(p):
                candidates.append(p)

        candidates = sorted({p.resolve() for p in candidates})

        if not candidates:
            return [
                _create_finding_safe(
                    self,
                    message="No IR triage artefacts discovered in .intent (path/name heuristics found nothing).",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "path_hints": list(_TRIAGE_PATH_HINTS),
                        "name_hints": list(_TRIAGE_NAME_HINTS),
                    },
                )
            ]

        parse_errors: list[dict[str, Any]] = []
        scored: list[dict[str, Any]] = []

        best_score = -1
        best: dict[str, Any] | None = None

        for p in candidates:
            relp = _rel(repo_path, p)
            try:
                doc = _safe_load(p)
            except Exception as exc:
                parse_errors.append({"file": relp, "error": str(exc)})
                continue

            score = _score_triage_candidate(doc)
            item = {"file": relp, "score": score}
            scored.append(item)

            if score > best_score:
                best_score = score
                best = item

        # If we only have parse errors, fail.
        if not scored:
            return [
                _create_finding_safe(
                    self,
                    message="IR triage candidate files were found but none were parseable as YAML/JSON.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "candidate_count": len(candidates),
                        "parse_errors": parse_errors[:40],
                    },
                )
            ]

        # Require at least one strong candidate.
        strong = [x for x in scored if x["score"] >= 2]
        if not strong:
            return [
                _create_finding_safe(
                    self,
                    message="IR triage artefact candidates exist, but none look like a governed triage definition (missing schema_id and insufficient markers).",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "candidate_count": len(candidates),
                        "scored_samples": sorted(
                            scored, key=lambda x: x["score"], reverse=True
                        )[:20],
                        "parse_errors": parse_errors[:20],
                        "minimum_strong_score": 2,
                    },
                )
            ]

        # Pass (no findings)
        return []


# ID: 2a8d3e7d-5da3-4bd5-8a3a-6f418bb0b5c6
class IRTriageCheck(RuleEnforcementCheck):
    """
    Enforces ir.triage_required.

    Ref:
    - standard_operations_general
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_IR_TRIAGE_REQUIRED]
    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IRTriageRequiredEnforcement(
            rule_id=RULE_IR_TRIAGE_REQUIRED,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
