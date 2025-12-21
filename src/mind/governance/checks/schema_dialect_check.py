# src/mind/governance/checks/schema_dialect_check.py
"""
Schema Dialect Governance Check

Enforces schema dialect rules declared in schema_dialect:
- schemas.dialect.forbid_nullable_keyword
- schemas.dialect.standard_json_schema
- schemas.style.closed_objects.root

What this check enforces (evidence-backed, conservative):
1) Discover schema artefacts under:
   - .intent/schemas/**/*
   - any file matching *schema*.json / *schema*.yaml / *schema*.yml under .intent/**

2) Dialect rules:
   - forbid_nullable_keyword:
       Reject any usage of the "nullable" keyword anywhere in the schema tree.
   - standard_json_schema:
       Require root-level "$schema" and a supported JSON Schema draft URI
       (default accepted: 2020-12). Require root-level "type".
   - closed_objects.root:
       If root type is "object", require root-level "additionalProperties": false.

Non-goals (intentionally):
- We do not validate full JSON Schema correctness.
- We do not validate nested "additionalProperties" policies yet (root only).

Design constraints:
- No pretend-pass: if schema resources exist and violations exist, fail with evidence.
- If no schema resources are found, fail (cannot validate dialect rules).
- Hardened against varying EnforcementMethod._create_finding() signatures.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Iterable
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

RULE_FORBID_NULLABLE = "schemas.dialect.forbid_nullable_keyword"
RULE_STANDARD_JSON_SCHEMA = "schemas.dialect.standard_json_schema"
RULE_CLOSED_OBJECTS_ROOT = "schemas.style.closed_objects.root"

_ALLOWED_DRAFT_URIS: tuple[str, ...] = (
    "https://json-schema.org/draft/2020-12/schema",
    "http://json-schema.org/draft/2020-12/schema",
)


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.

    We only pass parameters supported by the runtime signature to prevent
    unexpected keyword argument errors.
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


def _safe_load_schema(path: Path) -> Any:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        return json.loads(text)
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(text)
    raise ValueError(f"Unsupported schema file type: {suffix}")


def _walk_keys(obj: Any) -> Iterable[str]:
    """
    Yield keys found anywhere in a nested mapping/list tree.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _walk_keys(it)


def _discover_schema_files(repo_path: Path) -> list[Path]:
    """
    Discover schema artefacts conservatively.
    """
    intent_root = repo_path / ".intent"
    if not intent_root.exists():
        return []

    out: list[Path] = []

    # Primary schema root
    schemas_root = intent_root / "schemas"
    if schemas_root.exists():
        for p in schemas_root.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".json", ".yaml", ".yml"):
                out.append(p)

    # Also accept schema-named files anywhere under .intent
    for p in intent_root.rglob("*"):
        if not p.is_file():
            continue
        suf = p.suffix.lower()
        if suf not in (".json", ".yaml", ".yml"):
            continue
        name = p.name.lower()
        if "schema" in name:
            out.append(p)

    uniq = sorted({p.resolve() for p in out})
    return [Path(p) for p in uniq]


def _root_type(schema: Any) -> str:
    if isinstance(schema, dict):
        t = schema.get("type")
        if isinstance(t, str):
            return t.strip().lower()
    return ""


def _bool_or_missing(val: Any) -> str:
    if val is False:
        return "false"
    if val is True:
        return "true"
    return "missing_or_non_bool"


# Resolve policy file robustly (PathResolver keys vary between repos)
try:
    _POLICY_FILE = settings.paths.policy("schema_dialect")
except Exception:
    _POLICY_FILE = (
        settings.REPO_PATH / ".intent" / "policies" / "schemas" / "schema_dialect.yaml"
    )


# ID: 7c0dce8c-0f68-4775-820b-6a9d8c3ccf1f
class SchemaDialectEnforcement(EnforcementMethod):
    """
    Evaluates multiple schema dialect rules in one pass, but emits findings
    targeted to a single rule_id instance (one EnforcementMethod per rule).
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 00a2f5ef-7d0d-4bdb-8e86-0c2c2bfeef3d
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path
        schema_files = _discover_schema_files(repo_path)

        if not schema_files:
            return [
                _create_finding_safe(
                    self,
                    message="No schema artefacts discovered under .intent; cannot validate schema dialect rules.",
                    file_path=".intent/schemas",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "expected_roots": [
                            ".intent/schemas/**",
                            ".intent/**/*schema*.(json|yaml|yml)",
                        ]
                    },
                )
            ]

        violations: list[dict[str, Any]] = []
        parse_errors: list[dict[str, Any]] = []

        for p in schema_files:
            relp = _rel(repo_path, p)
            try:
                doc = _safe_load_schema(p)
            except Exception as exc:
                parse_errors.append({"file": relp, "error": str(exc)})
                continue

            if not isinstance(doc, dict):
                # Not a dict schema; treat as parse/shape error for dialect purposes
                parse_errors.append({"file": relp, "error": "schema_root_not_object"})
                continue

            # Rule-specific evaluation
            if self.rule_id == RULE_FORBID_NULLABLE:
                if any(k == "nullable" for k in _walk_keys(doc)):
                    violations.append({"file": relp, "keyword": "nullable"})

            elif self.rule_id == RULE_STANDARD_JSON_SCHEMA:
                schema_uri = doc.get("$schema")
                root_t = doc.get("type")

                uri_ok = (
                    isinstance(schema_uri, str)
                    and schema_uri.strip() in _ALLOWED_DRAFT_URIS
                )
                type_ok = isinstance(root_t, str) and root_t.strip() != ""

                if not uri_ok or not type_ok:
                    violations.append(
                        {
                            "file": relp,
                            "$schema": schema_uri,
                            "type": root_t,
                            "expected": {
                                "$schema_one_of": list(_ALLOWED_DRAFT_URIS),
                                "type": "<non-empty string>",
                            },
                        }
                    )

            elif self.rule_id == RULE_CLOSED_OBJECTS_ROOT:
                if _root_type(doc) == "object":
                    ap = doc.get("additionalProperties", None)
                    if ap is not False:
                        violations.append(
                            {
                                "file": relp,
                                "root_type": "object",
                                "additionalProperties": _bool_or_missing(ap),
                                "expected": "false",
                            }
                        )

        if violations or parse_errors:
            msg_by_rule = {
                RULE_FORBID_NULLABLE: "Schemas must not use the 'nullable' keyword.",
                RULE_STANDARD_JSON_SCHEMA: "Schemas must declare a standard JSON Schema dialect ($schema) and root 'type'.",
                RULE_CLOSED_OBJECTS_ROOT: "Root object schemas must be closed (additionalProperties: false).",
            }
            return [
                _create_finding_safe(
                    self,
                    message=msg_by_rule.get(self.rule_id, "Schema dialect violation."),
                    file_path=".intent/schemas",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "rule_id": self.rule_id,
                        "policy_file": str(Path(_POLICY_FILE)),
                        "schemas_scanned": len(schema_files),
                        "violations_count": len(violations),
                        "parse_errors_count": len(parse_errors),
                        "violations": violations[:200],
                        "parse_errors": parse_errors[:50],
                    },
                )
            ]

        return []


# ID: 2b3eb45c-2c69-4cc8-97ac-9f6e20b71b2c
class SchemaDialectCheck(RuleEnforcementCheck):
    """
    Enforces schema dialect and style constraints.

    Ref:
    - schema_dialect
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_FORBID_NULLABLE,
        RULE_STANDARD_JSON_SCHEMA,
        RULE_CLOSED_OBJECTS_ROOT,
    ]

    policy_file: ClassVar[Path] = Path(_POLICY_FILE)

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        SchemaDialectEnforcement(
            rule_id=RULE_FORBID_NULLABLE, severity=AuditSeverity.ERROR
        ),
        SchemaDialectEnforcement(
            rule_id=RULE_STANDARD_JSON_SCHEMA, severity=AuditSeverity.ERROR
        ),
        SchemaDialectEnforcement(
            rule_id=RULE_CLOSED_OBJECTS_ROOT, severity=AuditSeverity.ERROR
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
