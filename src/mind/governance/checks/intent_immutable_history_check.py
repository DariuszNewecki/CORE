# src/mind/governance/checks/intent_immutable_history_check.py
"""
Intent Immutable History Governance Check

Enforces operations rule declared in standard_operations_general:
- intent.immutable_history

Intent:
Changes to constitutional / policy intent must be traceable and non-destructive.
At minimum, intent history must be immutable by policy (no "rewrite history" affordance).

Conservative, evidence-backed enforcement:
1) Locate and parse the operations policy.
2) Confirm the rule `intent.immutable_history` is declared and enforced at error level.
3) Confirm policy forbids destructive history operations (best-effort):
   - disallow "force push" / "rewrite" / "squash as default" / "rebase and force" modes
   - require history retention / audit trail semantics
4) Confirm repository contains at least one governance artifact indicating immutable history
   expectations (best-effort evidence via presence of Git usage / audit integration).
   This is a soft check: we do not fail solely on missing optional artifacts, but we do fail
   if policy is missing or rule is not declared/enforced.

Design constraints:
- Prefer policy content (rule_data) first.
- Fall back to conservative repository discovery only when policy data is insufficient.
- Do not pretend-pass when policy cannot be discovered or parsed.
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

RULE_INTENT_IMMUTABLE_HISTORY = "intent.immutable_history"


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


def _coerce_str_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(x) for x in val if str(x).strip()]
    if isinstance(val, str) and val.strip():
        return [val]
    return []


def _rule_enforcement_level(rule: dict[str, Any]) -> str:
    """
    Normalize enforcement level to one of: error|warn|info|none|unknown
    """
    raw = rule.get("enforcement")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    raw2 = rule.get("level")
    if isinstance(raw2, str) and raw2.strip():
        return raw2.strip().lower()
    return "unknown"


def _rule_text_blob(rule: dict[str, Any]) -> str:
    """
    Collect common text-like fields into one blob for simple substring checks.
    """
    parts: list[str] = []
    for k in ("description", "rationale", "guidance", "notes", "comment", "message"):
        v = rule.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
    return "\n".join(parts).lower()


def _detect_immutability_hints(rule: dict[str, Any]) -> dict[str, Any]:
    """
    Best-effort: detect if rule expresses immutable-history semantics.
    We intentionally stay flexible: policies evolve, so we look for common signals.
    """
    blob = _rule_text_blob(rule)

    # Common signals for immutable history constraints
    require_terms = [
        "immutable",
        "no rewrite",
        "no-rewrite",
        "no force push",
        "no-force-push",
        "force push disabled",
        "history must not be rewritten",
        "audit trail",
        "retain history",
        "append-only",
        "append only",
    ]
    forbid_terms = [
        "force push",
        "force-push",
        "rewrite history",
        "rewrite-history",
        "git push --force",
        "--force",
        "squash and merge as default",
        "rebase and force",
    ]

    require_hits = [t for t in require_terms if t in blob]
    forbid_hits = [t for t in forbid_terms if t in blob]

    # Also allow explicit structured fields:
    forbids = _coerce_str_list(rule.get("forbid") or rule.get("forbidden"))
    requires = _coerce_str_list(rule.get("require") or rule.get("required"))

    return {
        "require_hits": require_hits,
        "forbid_hits": forbid_hits,
        "structured_forbid": forbids[:50],
        "structured_require": requires[:50],
    }


def _discover_git_service_files(repo_path: Path) -> list[str]:
    """
    Best-effort evidence: presence of Git integration used by governance.
    """
    candidates = [
        repo_path / "src" / "shared" / "infrastructure" / "git_service.py",
        repo_path / "src" / "shared" / "infrastructure" / "git_service" / "__init__.py",
        repo_path / "src" / "shared" / "infrastructure" / "git_service" / "service.py",
    ]
    out: list[str] = []
    for p in candidates:
        if p.exists() and p.is_file():
            out.append(_rel(repo_path, p))
    return out


def _intent_root_exists(repo_path: Path) -> bool:
    return (repo_path / ".intent").exists()


# ID: 7c8b94c0-9c8c-4bcb-b0f7-52a2d7c2ea72
class IntentImmutableHistoryEnforcement(EnforcementMethod):
    """
    Ensures intent.immutable_history is declared, enforced as error,
    and includes immutable-history semantics.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 0e3c0a91-1b7c-44bf-b1bb-9e9c3f9c3f21
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
                    message="Operations policy not found; cannot validate intent.immutable_history.",
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

        rules = _extract_rules(operations_doc)
        rule = next(
            (r for r in rules if r.get("id") == RULE_INTENT_IMMUTABLE_HISTORY), None
        )
        if not rule:
            return [
                _create_finding_safe(
                    self,
                    message="intent.immutable_history is not declared in operations policy.",
                    file_path=_rel(repo_path, operations_policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "expected_rule_id": RULE_INTENT_IMMUTABLE_HISTORY,
                        "operations_policy": _rel(repo_path, operations_policy_path),
                    },
                )
            ]

        level = _rule_enforcement_level(rule)
        if level not in ("error", "err", "fatal"):
            return [
                _create_finding_safe(
                    self,
                    message="intent.immutable_history must be enforced at error level.",
                    file_path=_rel(repo_path, operations_policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "rule_id": RULE_INTENT_IMMUTABLE_HISTORY,
                        "found_enforcement": level,
                        "rule": rule,
                    },
                )
            ]

        hints = _detect_immutability_hints(rule)

        # We accept either: strong textual signals OR explicit structured forbid/require
        has_text_signal = bool(hints["require_hits"]) or bool(hints["forbid_hits"])
        has_structured_signal = bool(hints["structured_forbid"]) or bool(
            hints["structured_require"]
        )

        if not (has_text_signal or has_structured_signal):
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "intent.immutable_history is declared but lacks clear immutable-history semantics "
                        "(no 'no force push / no rewrite history / audit trail / append-only' signals found)."
                    ),
                    file_path=_rel(repo_path, operations_policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "rule_id": RULE_INTENT_IMMUTABLE_HISTORY,
                        "immutability_hints": hints,
                        "rule": rule,
                    },
                )
            ]

        # Best-effort supporting evidence (non-failing): .intent exists + git service present
        evidence: dict[str, Any] = {
            "rule_id": RULE_INTENT_IMMUTABLE_HISTORY,
            "operations_policy": _rel(repo_path, operations_policy_path),
            "immutability_hints": hints,
            "intent_root_exists": _intent_root_exists(repo_path),
            "git_service_files": _discover_git_service_files(repo_path),
        }

        # Pass: evidence-backed (no findings)
        # NOTE: RuleEnforcementCheck will record "enforced" because this method exists;
        # runtime audit correctness is validated by integration.* checks.
        _ = evidence  # kept for future expansion (avoid unused variable warnings if linted strictly)
        return []


# ID: 91a1e87a-8e1d-4c0e-9b1f-2f07d2f5f6a0
class IntentImmutableHistoryCheck(RuleEnforcementCheck):
    """
    Enforces intent.immutable_history.

    Ref:
    - standard_operations_general
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTENT_IMMUTABLE_HISTORY]

    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntentImmutableHistoryEnforcement(
            rule_id=RULE_INTENT_IMMUTABLE_HISTORY,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
