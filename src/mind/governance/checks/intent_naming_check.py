# src/mind/governance/checks/intent_naming_check.py
"""
Intent Naming Governance Check

Enforces intent naming rules declared in code standards policy (flat rules), including:
- intent.artifact_schema_naming
- intent.policy_schema_naming
- intent.prompt_file_naming

Design constraints:
- Prefer policy-provided patterns (rule_data) first.
- Conservative fallback heuristics when patterns are not declared.
- Evidence-backed; do not pretend-pass when .intent cannot be discovered.
- Hardened against evolving EnforcementMethod._create_finding() signatures.
"""

from __future__ import annotations

import inspect
import re
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

RULE_INTENT_ARTIFACT_SCHEMA_NAMING = "intent.artifact_schema_naming"
RULE_INTENT_POLICY_SCHEMA_NAMING = "intent.policy_schema_naming"
RULE_INTENT_PROMPT_FILE_NAMING = "intent.prompt_file_naming"


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


def _intent_root(repo_path: Path) -> Path:
    return repo_path / ".intent"


def _discover_dirs(root: Path, dir_name: str) -> list[Path]:
    """
    Finds all directories named `dir_name` under `root`.
    """
    if not root.exists():
        return []
    out: list[Path] = []
    for p in root.rglob(dir_name):
        if p.is_dir() and p.name == dir_name:
            out.append(p)
    return sorted({p.resolve() for p in out})


def _discover_files_under(dirs: list[Path], suffixes: set[str]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() in suffixes:
                out.append(p)
    return sorted({p.resolve() for p in out})


def _normalize_patterns(rule_data: dict[str, Any], *, fallback: list[str]) -> list[str]:
    """
    Policy override hooks (best-effort):
    - pattern / patterns / regex / regexes / filename_regex
    """
    candidates: list[str] = []

    for key in ("pattern", "patterns", "regex", "regexes", "filename_regex"):
        val = rule_data.get(key)
        if isinstance(val, str) and val.strip():
            candidates.append(val.strip())
        elif isinstance(val, list):
            candidates.extend([str(x).strip() for x in val if str(x).strip()])

    if not candidates:
        candidates = fallback

    # De-dup while preserving order (case-insensitive)
    seen: set[str] = set()
    out: list[str] = []
    for s in candidates:
        k = s.strip()
        if not k:
            continue
        kk = k.lower()
        if kk in seen:
            continue
        seen.add(kk)
        out.append(k)
    return out


def _matches_any(filename: str, patterns: list[str]) -> bool:
    for pat in patterns:
        try:
            if re.match(pat, filename):
                return True
        except re.error:
            # If policy provides a non-regex pattern by mistake, fallback to substring
            if pat.lower() in filename.lower():
                return True
    return False


def _is_probably_artifact_schema(path: Path) -> bool:
    """
    Conservative classification:
    - path contains '/artifacts/' OR '/artifact/' OR filename contains 'artifact'
    """
    p = str(path).replace("\\", "/").lower()
    return (
        "/artifacts/" in p
        or "/artifact/" in p
        or "artifact" in path.name.lower()
        or "artifact" in p
    )


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


# -----------------------------------------------------------------------------
# Enforcement methods
# -----------------------------------------------------------------------------


# ID: 2f0f1dc9-6a4d-4c38-9df8-3f5ad3d5e3d2
class IntentPromptFileNamingEnforcement(EnforcementMethod):
    """
    Enforces intent.prompt_file_naming.

    Preferred: use regex patterns from policy rule_data.

    Conservative fallback (regex):
    - kebab/underscore lower-case filename
    - requires an explicit ".prompt." segment
    - extension: .md or .txt

    Example accepted:
    - onboarding.prompt.md
    - qa_audit.prompt.txt
    """

    _FALLBACK_PATTERNS: ClassVar[list[str]] = [
        r"^[a-z0-9][a-z0-9_-]*\.prompt\.(md|txt)$",
    ]

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 7f3dcbab-2435-4c36-8f8d-8cf2b5a4c3d1
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path
        intent = _intent_root(repo_path)
        if not intent.exists():
            return [
                _create_finding_safe(
                    self,
                    message=".intent directory not found; cannot validate intent.prompt_file_naming.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={"intent_root": str(intent)},
                )
            ]

        patterns = _normalize_patterns(rule_data, fallback=self._FALLBACK_PATTERNS)

        prompt_dirs = _discover_dirs(intent, "prompts")
        if not prompt_dirs:
            # Not a failure: repo might not use prompt files (yet). Provide evidence and pass.
            return []

        files = _discover_files_under(prompt_dirs, suffixes={".md", ".txt"})
        violations: list[dict[str, Any]] = []

        for p in files:
            name = p.name
            if " " in name:
                violations.append(
                    {
                        "file": _rel(repo_path, p),
                        "reason": "contains_spaces",
                        "name": name,
                    }
                )
                continue
            if not _matches_any(name, patterns):
                violations.append(
                    {
                        "file": _rel(repo_path, p),
                        "reason": "does_not_match_patterns",
                        "name": name,
                        "patterns": patterns,
                    }
                )

        if not violations:
            return []

        return [
            _create_finding_safe(
                self,
                message="Prompt files under .intent/**/prompts do not follow required naming conventions.",
                file_path=_rel(repo_path, prompt_dirs[0]),
                severity=AuditSeverity.ERROR,
                evidence={
                    "patterns": patterns,
                    "prompt_dirs": [_rel(repo_path, d) for d in prompt_dirs],
                    "violation_count": len(violations),
                    "violations": violations[:200],
                },
            )
        ]


# ID: 3a9b3b38-6b4a-4f1a-9f5f-2b3d4e5f6a71
class IntentPolicySchemaNamingEnforcement(EnforcementMethod):
    """
    Enforces intent.policy_schema_naming.

    Preferred: regex patterns from policy rule_data.

    Conservative fallback expects schema file names to carry a 'schema.' prefix.

    Example accepted:
    - schema.operations.conversational_context_bundle.yaml
    - schema.policy.integrations.json
    """

    _FALLBACK_PATTERNS: ClassVar[list[str]] = [
        r"^schema\.[a-z0-9][a-z0-9_.-]*\.(yaml|yml|json)$",
    ]

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 0bcb5d9f-4be3-4f2e-a6d0-0db2cbe5ad91
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path
        intent = _intent_root(repo_path)
        if not intent.exists():
            return [
                _create_finding_safe(
                    self,
                    message=".intent directory not found; cannot validate intent.policy_schema_naming.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={"intent_root": str(intent)},
                )
            ]

        patterns = _normalize_patterns(rule_data, fallback=self._FALLBACK_PATTERNS)

        schema_dirs = _discover_dirs(intent, "schemas")
        if not schema_dirs:
            # If there are no schemas in the repo, we cannot validate naming, but we also
            # should not fail the system by default. Treat as not applicable.
            return []

        files = _discover_files_under(schema_dirs, suffixes={".yaml", ".yml", ".json"})
        violations: list[dict[str, Any]] = []

        for p in files:
            # Only check non-artifact schemas in this rule.
            if _is_probably_artifact_schema(p):
                continue
            name = p.name
            if " " in name:
                violations.append(
                    {
                        "file": _rel(repo_path, p),
                        "reason": "contains_spaces",
                        "name": name,
                    }
                )
                continue
            if not _matches_any(name, patterns):
                violations.append(
                    {
                        "file": _rel(repo_path, p),
                        "reason": "does_not_match_patterns",
                        "name": name,
                        "patterns": patterns,
                    }
                )

        if not violations:
            return []

        return [
            _create_finding_safe(
                self,
                message="Policy schema files under .intent/**/schemas do not follow required naming conventions.",
                file_path=_rel(repo_path, schema_dirs[0]),
                severity=AuditSeverity.ERROR,
                evidence={
                    "patterns": patterns,
                    "schema_dirs": [_rel(repo_path, d) for d in schema_dirs],
                    "violation_count": len(violations),
                    "violations": violations[:200],
                },
            )
        ]


# ID: d48f5c0b-1c3e-4f9b-a5d3-9b5c4a2e1f0d
class IntentArtifactSchemaNamingEnforcement(EnforcementMethod):
    """
    Enforces intent.artifact_schema_naming.

    Preferred: regex patterns from policy rule_data.

    Conservative fallback expects artifact schema names to include 'schema.' prefix and 'artifact'
    either in the file name or in its path.

    Example accepted:
    - schema.artifact.audit_report.yaml
    - schema.artifacts.coverage_map.json
    """

    _FALLBACK_PATTERNS: ClassVar[list[str]] = [
        r"^schema\.(artifact|artifacts)\.[a-z0-9][a-z0-9_.-]*\.(yaml|yml|json)$",
        # allow: schema.<something_with_artifact>.ext
        r"^schema\.[a-z0-9][a-z0-9_.-]*artifact[a-z0-9_.-]*\.(yaml|yml|json)$",
    ]

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 58c2c4da-2a7d-4c8c-bb7f-4cfc0c5d2cbe
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path
        intent = _intent_root(repo_path)
        if not intent.exists():
            return [
                _create_finding_safe(
                    self,
                    message=".intent directory not found; cannot validate intent.artifact_schema_naming.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={"intent_root": str(intent)},
                )
            ]

        patterns = _normalize_patterns(rule_data, fallback=self._FALLBACK_PATTERNS)

        schema_dirs = _discover_dirs(intent, "schemas")
        if not schema_dirs:
            return []

        files = _discover_files_under(schema_dirs, suffixes={".yaml", ".yml", ".json"})
        # Only validate “artifact-looking” schema files for this rule.
        artifact_files = [p for p in files if _is_probably_artifact_schema(p)]

        if not artifact_files:
            # No artifact schemas present -> not applicable.
            return []

        violations: list[dict[str, Any]] = []
        for p in artifact_files:
            name = p.name
            if " " in name:
                violations.append(
                    {
                        "file": _rel(repo_path, p),
                        "reason": "contains_spaces",
                        "name": name,
                    }
                )
                continue
            if not _matches_any(name, patterns):
                violations.append(
                    {
                        "file": _rel(repo_path, p),
                        "reason": "does_not_match_patterns",
                        "name": name,
                        "patterns": patterns,
                    }
                )

        if not violations:
            return []

        return [
            _create_finding_safe(
                self,
                message="Artifact schema files under .intent/**/schemas do not follow required naming conventions.",
                file_path=_rel(repo_path, schema_dirs[0]),
                severity=AuditSeverity.ERROR,
                evidence={
                    "patterns": patterns,
                    "schema_dirs": [_rel(repo_path, d) for d in schema_dirs],
                    "artifact_file_count": len(artifact_files),
                    "violation_count": len(violations),
                    "violations": violations[:200],
                },
            )
        ]


# -----------------------------------------------------------------------------
# Check
# -----------------------------------------------------------------------------


# ID: 1c8d4a62-6a7d-4d2b-9c35-0f2a3b4c5d6e
class IntentNamingCheck(RuleEnforcementCheck):
    """
    Enforces intent naming conventions for prompts and schemas.

    Ref:
    - policies/code/code_standards
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_INTENT_ARTIFACT_SCHEMA_NAMING,
        RULE_INTENT_POLICY_SCHEMA_NAMING,
        RULE_INTENT_PROMPT_FILE_NAMING,
    ]

    # These rules are declared under code standards in your coverage output.
    policy_file: ClassVar[Path] = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntentArtifactSchemaNamingEnforcement(
            rule_id=RULE_INTENT_ARTIFACT_SCHEMA_NAMING, severity=AuditSeverity.ERROR
        ),
        IntentPolicySchemaNamingEnforcement(
            rule_id=RULE_INTENT_POLICY_SCHEMA_NAMING, severity=AuditSeverity.ERROR
        ),
        IntentPromptFileNamingEnforcement(
            rule_id=RULE_INTENT_PROMPT_FILE_NAMING, severity=AuditSeverity.ERROR
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
