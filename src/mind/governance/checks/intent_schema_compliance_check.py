# src/mind/governance/checks/intent_schema_compliance_check.py
"""
Intent Schema Compliance Governance Check

Enforces operations rule declared in standard_operations_general:
- intent.schema_compliance

Conservative, evidence-backed enforcement (no pretend-pass):
1) Confirm the rule exists in the operations policy.
2) Discover schema documents under .intent/schemas/**.(yaml|yml|json)
   and index them by declared schema "id".
3) Discover intent artefacts under .intent/**.(yaml|yml|json), excluding schemas.
4) For each artefact:
   - Must declare schema_id (string)
   - schema_id must resolve to a known schema (by schema id)
   - Artefact must be parseable
   - Minimal required-field validation:
       If schema declares "required: [..]" at top-level, ensure those keys exist.

This check intentionally does NOT attempt full JSON Schema validation.
It enforces the minimum contract needed to make schema governance real and actionable.

Design constraints:
- Evidence-backed; errors include actionable file samples.
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

RULE_INTENT_SCHEMA_COMPLIANCE = "intent.schema_compliance"


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


def _is_schema_path(p: Path) -> bool:
    return "/schemas/" in str(p).replace("\\", "/")


def _discover_intent_files(intent_root: Path) -> list[Path]:
    out: list[Path] = []
    for p in intent_root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".yaml", ".yml", ".json"):
            continue
        if _is_schema_path(p):
            continue
        out.append(p)
    return sorted({p.resolve() for p in out})


def _discover_schema_files(intent_root: Path) -> list[Path]:
    schemas_root = intent_root / "schemas"
    if not schemas_root.exists():
        return []
    out: list[Path] = []
    for p in schemas_root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in (".yaml", ".yml", ".json"):
            continue
        out.append(p)
    return sorted({p.resolve() for p in out})


def _schema_id_from_doc(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return None
    sid = doc.get("id") or doc.get("schema_id")
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    return None


def _required_list_from_schema_doc(doc: Any) -> list[str]:
    """
    Minimal support: top-level JSON schema style `required: [..]`.
    If absent, return [].
    """
    if not isinstance(doc, dict):
        return []
    req = doc.get("required")
    if isinstance(req, list):
        out: list[str] = []
        for x in req:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out
    return []


def _get_schema_id_from_artifact(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return None
    sid = doc.get("schema_id")
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    return None


def _artifact_missing_required(doc: Any, required: list[str]) -> list[str]:
    if not required:
        return []
    if not isinstance(doc, dict):
        # If it's not an object, it cannot satisfy object-required keys.
        return required
    missing = [k for k in required if k not in doc]
    return missing


# ID: 46a4bcd0-5649-4d01-9c8b-e82642ab8e38
class IntentSchemaComplianceEnforcement(EnforcementMethod):
    """
    Enforces intent.schema_compliance via minimal schema linkage checks.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 5b7f3fa6-8f61-49e5-8c9a-12efc2a5f04f
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path
        intent_root = repo_path / ".intent"

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
                    message="Operations policy not found; cannot validate intent.schema_compliance.",
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
        if not any(r.get("id") == RULE_INTENT_SCHEMA_COMPLIANCE for r in rules):
            return [
                _create_finding_safe(
                    self,
                    message="intent.schema_compliance is not declared in operations policy.",
                    file_path=_rel(repo_path, operations_policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "expected_rule_id": RULE_INTENT_SCHEMA_COMPLIANCE,
                        "operations_policy": _rel(repo_path, operations_policy_path),
                    },
                )
            ]

        if not intent_root.exists():
            return [
                _create_finding_safe(
                    self,
                    message=".intent directory not found; cannot validate intent.schema_compliance.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                )
            ]

        schema_files = _discover_schema_files(intent_root)
        if not schema_files:
            return [
                _create_finding_safe(
                    self,
                    message="No schema files found under .intent/schemas; cannot validate intent.schema_compliance.",
                    file_path=".intent/schemas",
                    severity=AuditSeverity.ERROR,
                )
            ]

        # Build schema index by id
        schema_index: dict[str, dict[str, Any]] = {}
        schema_source: dict[str, str] = {}
        schema_parse_errors: list[dict[str, Any]] = []

        for p in schema_files:
            try:
                doc = _safe_load(p)
            except Exception as exc:
                schema_parse_errors.append(
                    {"file": _rel(repo_path, p), "error": str(exc)}
                )
                continue

            sid = _schema_id_from_doc(doc)
            if not sid:
                # Schema without id is itself a governance defect, but we keep this check focused;
                # report as WARN, because other checks may enforce schema naming/shape.
                schema_parse_errors.append(
                    {"file": _rel(repo_path, p), "error": "schema missing id"}
                )
                continue

            # Last one wins if duplicates; still provides coverage and evidence.
            schema_index[sid] = doc if isinstance(doc, dict) else {}
            schema_source[sid] = _rel(repo_path, p)

        if not schema_index:
            return [
                _create_finding_safe(
                    self,
                    message="No usable schemas indexed (schemas exist but missing ids or failed parsing).",
                    file_path=".intent/schemas",
                    severity=AuditSeverity.ERROR,
                    evidence={"schema_parse_issues": schema_parse_errors[:50]},
                )
            ]

        intent_files = _discover_intent_files(intent_root)
        if not intent_files:
            return [
                _create_finding_safe(
                    self,
                    message="No intent artefact files found under .intent (excluding schemas); nothing to validate for intent.schema_compliance.",
                    file_path=".intent",
                    severity=AuditSeverity.WARNING,
                )
            ]

        missing_schema_id: list[dict[str, Any]] = []
        schema_not_found: list[dict[str, Any]] = []
        artifact_parse_errors: list[dict[str, Any]] = []
        required_missing: list[dict[str, Any]] = []

        for p in intent_files:
            relp = _rel(repo_path, p)

            try:
                doc = _safe_load(p)
            except Exception as exc:
                artifact_parse_errors.append({"file": relp, "error": str(exc)})
                continue

            sid = _get_schema_id_from_artifact(doc)
            if not sid:
                missing_schema_id.append({"file": relp})
                continue

            schema_doc = schema_index.get(sid)
            if schema_doc is None:
                schema_not_found.append(
                    {"file": relp, "schema_id": sid, "hint": "schema id not indexed"}
                )
                continue

            req = _required_list_from_schema_doc(schema_doc)
            miss = _artifact_missing_required(doc, req)
            if miss:
                required_missing.append(
                    {
                        "file": relp,
                        "schema_id": sid,
                        "schema_file": schema_source.get(sid, "<unknown>"),
                        "missing_required": miss,
                    }
                )

        findings: list[AuditFinding] = []

        if missing_schema_id:
            findings.append(
                _create_finding_safe(
                    self,
                    message="Some intent artefacts do not declare schema_id (required for schema governance).",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "count": len(missing_schema_id),
                        "samples": missing_schema_id[:80],
                    },
                )
            )

        if schema_not_found:
            findings.append(
                _create_finding_safe(
                    self,
                    message="Some intent artefacts reference schema_id values that do not resolve to a known schema.",
                    file_path=".intent/schemas",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "count": len(schema_not_found),
                        "samples": schema_not_found[:80],
                        "indexed_schema_ids_sample": sorted(list(schema_index.keys()))[
                            :50
                        ],
                    },
                )
            )

        if required_missing:
            findings.append(
                _create_finding_safe(
                    self,
                    message="Some intent artefacts are missing required keys declared by their schema.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "count": len(required_missing),
                        "samples": required_missing[:80],
                    },
                )
            )

        if artifact_parse_errors:
            findings.append(
                _create_finding_safe(
                    self,
                    message="Some intent artefacts failed to parse during schema compliance validation.",
                    file_path=".intent",
                    severity=AuditSeverity.WARNING,
                    evidence={
                        "count": len(artifact_parse_errors),
                        "samples": artifact_parse_errors[:40],
                    },
                )
            )

        if schema_parse_errors:
            findings.append(
                _create_finding_safe(
                    self,
                    message="Some schema files failed to parse or are missing ids; schema compliance validation may be incomplete.",
                    file_path=".intent/schemas",
                    severity=AuditSeverity.WARNING,
                    evidence={
                        "count": len(schema_parse_errors),
                        "samples": schema_parse_errors[:40],
                    },
                )
            )

        return findings


# ID: 7b0b5591-711f-4ae9-91d8-42b0bd5f2f5a
class IntentSchemaComplianceCheck(RuleEnforcementCheck):
    """
    Enforces intent.schema_compliance.

    Ref:
    - standard_operations_general
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTENT_SCHEMA_COMPLIANCE]

    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntentSchemaComplianceEnforcement(
            rule_id=RULE_INTENT_SCHEMA_COMPLIANCE,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
