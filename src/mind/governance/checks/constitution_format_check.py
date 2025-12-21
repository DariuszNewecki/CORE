# src/mind/governance/checks/constitution_format_check.py
"""
Constitution Format Governance Check

Enforces constitutional primary format rules declared in:
- .intent/charter/standards/operations/constitution_format.(yaml|yml|json)
  (policy key: "constitution_format")

Targets:
- constitution.primary_format

Design constraints:
- Prefer internal CORE path resolution and existing conventions first.
- Conservative validation: ensure one primary constitution format exists and is discoverable.
- Evidence-backed; do not pretend-pass when constitution resources cannot be discovered.
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

RULE_CONSTITUTION_PRIMARY_FORMAT = "constitution.primary_format"


def _safe_load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


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


def _extract_rules(policy_doc: Any) -> list[dict[str, Any]]:
    if not isinstance(policy_doc, dict):
        return []
    rules = policy_doc.get("rules")
    if not isinstance(rules, list):
        return []
    return [r for r in rules if isinstance(r, dict)]


def _discover_constitution_resources(repo_path: Path) -> list[Path]:
    """
    Discover constitutional documents (non-schema intent documents).

    Conservative, deterministic:
    - .intent/constitution/**
    - .intent/charter/constitution/**

    Only accepts JSON/YAML documents; skips anything under a 'schemas' segment.
    """
    intent_root = repo_path / ".intent"
    if not intent_root.exists():
        return []

    roots = [
        intent_root / "constitution",
        intent_root / "charter" / "constitution",
    ]

    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            norm = str(p).replace("\\", "/")
            if "/schemas/" in norm:
                continue
            if p.suffix.lower() not in (".json", ".yaml", ".yml"):
                continue
            out.append(p)

    # Deduplicate & sort
    uniq = sorted({p.resolve() for p in out})
    return [Path(p) for p in uniq]


def _rel(repo_path: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_path))
    except Exception:
        return str(path)


# ID: a5cb6389-d83f-49ee-a602-72e4a649d8a0
class ConstitutionPrimaryFormatEnforcement(EnforcementMethod):
    """
    Ensures a "primary" constitution format is declared and consistent.

    Evidence-backed validations:
    1) Policy declares accepted primary format (json/yaml).
    2) Constitution resources exist under expected locations.
    3) All constitution resources are of the declared primary format OR,
       if mixed formats exist, the policy must explicitly allow it.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 2721da72-1c52-4c58-8363-52f1938de38a
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        # Prefer canonical policy resolution first
        try:
            policy_path = settings.paths.policy("constitution_format")
        except Exception:
            # Fallback aligned with your standard location convention
            policy_path = (
                repo_path
                / ".intent"
                / "charter"
                / "standards"
                / "operations"
                / "constitution_format.yaml"
            )

        if not isinstance(policy_path, Path):
            policy_path = Path(policy_path)

        if not policy_path.exists():
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "Constitution format policy file missing; cannot validate "
                        "constitution.primary_format."
                    ),
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        try:
            policy_doc = _safe_load(policy_path)
        except Exception as exc:
            return [
                _create_finding_safe(
                    self,
                    message=f"Failed to parse constitution format policy: {exc}",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        rules = _extract_rules(policy_doc)
        this_rule = next(
            (r for r in rules if r.get("id") == RULE_CONSTITUTION_PRIMARY_FORMAT), None
        )

        if not this_rule:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "constitution.primary_format rule not declared in "
                        "constitution_format policy."
                    ),
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        # Expected keys (best-effort; keep flexible)
        primary = (
            this_rule.get("primary_format")
            or this_rule.get("format")
            or this_rule.get("primary")
        )
        allowed = this_rule.get("allowed_formats") or this_rule.get("formats") or []
        allow_mixed = bool(
            this_rule.get("allow_mixed") or this_rule.get("mixed_allowed") or False
        )

        primary_fmt = primary.strip().lower() if isinstance(primary, str) else ""

        allowed_list: list[str] = []
        if isinstance(allowed, list):
            allowed_list = [str(x).strip().lower() for x in allowed if str(x).strip()]
        elif isinstance(allowed, str) and allowed.strip():
            allowed_list = [allowed.strip().lower()]

        if not primary_fmt:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "constitution.primary_format rule does not define a primary "
                        "format (expected e.g. primary_format: json)."
                    ),
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={"rule": this_rule},
                )
            ]

        if allowed_list and primary_fmt not in allowed_list:
            return [
                _create_finding_safe(
                    self,
                    message="Primary constitution format is not included in allowed_formats.",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "primary_format": primary_fmt,
                        "allowed_formats": allowed_list,
                    },
                )
            ]

        resources = _discover_constitution_resources(repo_path)
        if not resources:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "No constitutional resources discovered under .intent/constitution "
                        "(or .intent/charter/constitution)."
                    ),
                    file_path=".intent/constitution",
                    severity=AuditSeverity.ERROR,
                )
            ]

        # Determine formats present
        fmt_map: dict[str, list[str]] = {"json": [], "yaml": []}
        for p in resources:
            suf = p.suffix.lower()
            relp = _rel(repo_path, p)
            if suf == ".json":
                fmt_map["json"].append(relp)
            elif suf in (".yaml", ".yml"):
                fmt_map["yaml"].append(relp)

        present = [k for k, v in fmt_map.items() if v]
        evidence = {
            "primary_format": primary_fmt,
            "allow_mixed": allow_mixed,
            "present_formats": present,
            "counts": {k: len(v) for k, v in fmt_map.items()},
            "samples": {k: v[:10] for k, v in fmt_map.items()},
            "policy_file": _rel(repo_path, policy_path),
        }

        # Enforce supported primary formats only
        if primary_fmt not in ("json", "yaml"):
            return [
                _create_finding_safe(
                    self,
                    message="Unsupported primary constitution format (expected 'json' or 'yaml').",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence=evidence,
                )
            ]

        # Mixed and not allowed -> error
        if len(present) > 1 and not allow_mixed:
            return [
                _create_finding_safe(
                    self,
                    message="Constitution resources are mixed-format but policy does not allow mixed formats.",
                    file_path=".intent/constitution",
                    severity=AuditSeverity.ERROR,
                    evidence=evidence,
                )
            ]

        # Single-format but not the declared primary -> error
        if len(present) == 1 and present[0] != primary_fmt:
            return [
                _create_finding_safe(
                    self,
                    message="Constitution resources do not match declared primary format.",
                    file_path=".intent/constitution",
                    severity=AuditSeverity.ERROR,
                    evidence=evidence,
                )
            ]

        # Mixed but allowed: ensure at least one primary-format file exists
        if len(present) > 1 and allow_mixed and not fmt_map[primary_fmt]:
            return [
                _create_finding_safe(
                    self,
                    message="Mixed constitution formats allowed, but no files exist in the declared primary format.",
                    file_path=".intent/constitution",
                    severity=AuditSeverity.ERROR,
                    evidence=evidence,
                )
            ]

        return []


# ID: 9ba89594-3f62-4484-84bf-7f894d7dbfa1
class ConstitutionFormatCheck(RuleEnforcementCheck):
    """
    Enforces constitution format constraints.

    Ref:
    - standard_operations_constitution_format
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_CONSTITUTION_PRIMARY_FORMAT]

    # PathResolver policy key expected: "constitution_format"
    policy_file: ClassVar[Path] = settings.paths.policy("constitution_format")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        ConstitutionPrimaryFormatEnforcement(
            rule_id=RULE_CONSTITUTION_PRIMARY_FORMAT,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
