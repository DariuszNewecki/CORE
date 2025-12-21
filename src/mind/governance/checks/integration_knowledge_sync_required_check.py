# src/mind/governance/checks/integration_knowledge_sync_required_check.py
"""
Integration Knowledge Sync Governance Check

Enforces the rule:
- integration.knowledge_sync_required

Intent:
CORE must have an explicit, discoverable “knowledge sync” integration step so that
the Knowledge Graph (and related derived artefacts) are refreshed as part of the
integration lifecycle (CI/build/release workflows).

Ref:
- standard_operations_general (policy key typically: "operations")

Design constraints:
- Prefer internal CORE conventions first (settings.paths.*, CLI registry conventions).
- Evidence-backed; no pretend-pass when required artefacts cannot be discovered.
- Hardened against evolving EnforcementMethod._create_finding() signatures.
"""

from __future__ import annotations

import inspect
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

RULE_INTEGRATION_KNOWLEDGE_SYNC_REQUIRED = "integration.knowledge_sync_required"

# Prefer the canonical CLI registry location already used elsewhere in CORE.
CLI_REGISTRY_PATH = (
    settings.REPO_PATH / ".intent" / "mind" / "knowledge" / "cli_registry.yaml"
)

# We keep these conservative and “string contains” based.
# If policy defines explicit patterns, we will prefer that.
DEFAULT_SYNC_PATTERNS: tuple[str, ...] = (
    "knowledge sync",
    "knowledge reconcile",
    "knowledge refresh",
    "knowledge update",
    "knowledge-graph sync",
    "introspection sync",
    "introspect sync",
    "core-admin knowledge sync",
    "core-admin knowledge reconcile",
)

# Where integration hooks are typically declared.
DEFAULT_INTEGRATION_FILES: tuple[str, ...] = (
    "Makefile",
    "makefile",
    ".github/workflows",
    "scripts",
)


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


def _safe_load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _extract_rules(policy_doc: Any) -> list[dict[str, Any]]:
    if isinstance(policy_doc, dict):
        rules = policy_doc.get("rules")
        if isinstance(rules, list):
            return [r for r in rules if isinstance(r, dict)]
    return []


def _collect_text_files(repo_path: Path) -> list[Path]:
    """
    Conservative file discovery for integration scripts.

    - Makefile at root
    - .github/workflows/**/*.yml|yaml
    - scripts/**/*.sh|py|yml|yaml|txt
    """
    out: list[Path] = []

    # Root makefiles
    for name in ("Makefile", "makefile"):
        p = repo_path / name
        if p.exists() and p.is_file():
            out.append(p)

    # Workflows
    wf_root = repo_path / ".github" / "workflows"
    if wf_root.exists():
        out.extend(
            [
                p
                for p in wf_root.rglob("*")
                if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
            ]
        )

    # Scripts
    scripts_root = repo_path / "scripts"
    if scripts_root.exists():
        out.extend(
            [
                p
                for p in scripts_root.rglob("*")
                if p.is_file()
                and (
                    p.suffix.lower() in {".sh", ".py", ".yml", ".yaml", ".txt"}
                    or p.name.lower() in {"makefile", "make"}
                )
            ]
        )

    # De-dup + stable order
    uniq = sorted({p.resolve() for p in out})
    return [Path(p) for p in uniq]


def _find_any_patterns_in_text(text: str, patterns: list[str]) -> list[str]:
    hay = text.lower()
    hits: list[str] = []
    for pat in patterns:
        p = pat.strip().lower()
        if p and p in hay:
            hits.append(pat)
    return hits


def _recursive_strings(obj: Any) -> list[str]:
    """
    Extract all string leaves from YAML/JSON-like structures.
    """
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_recursive_strings(k))
            out.extend(_recursive_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_recursive_strings(item))
    return out


# ID: 9b6b4a89-6c9a-4c2b-9c41-3d9f4c6b0b74
class IntegrationKnowledgeSyncRequiredEnforcement(EnforcementMethod):
    """
    Evidence-backed enforcement for integration.knowledge_sync_required.

    We consider the rule satisfied when ALL of the following hold:
    1) A “knowledge sync” command/intent is discoverable in the CLI registry (preferred),
       OR the repo clearly exposes a knowledge sync command via other internal metadata.
    2) The integration pipeline (Makefile / CI workflow / scripts) references that sync step.

    We intentionally keep matching conservative (substring-based), but allow policy-provided
    patterns to override defaults.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 1f9a1b9f-6b9c-4ee7-88fb-7f73c0fd1c9d
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        # Resolve policy file for evidence (best-effort; do not fail if not resolvable here)
        try:
            policy_path = settings.paths.policy("operations")
        except Exception:
            policy_path = (
                repo_path / ".intent" / "policies" / "operations" / "operations.yaml"
            )

        patterns = self._extract_patterns(rule_data)

        # 1) CLI registry (preferred discovery signal)
        cli_registry_evidence = self._check_cli_registry(repo_path, patterns)

        # 2) Integration wiring evidence (CI/Makefile/scripts)
        integration_evidence = self._check_integration_wiring(repo_path, patterns)

        ok = bool(cli_registry_evidence["has_sync_command"]) and bool(
            integration_evidence["has_integration_reference"]
        )

        evidence = {
            "rule_id": self.rule_id,
            "policy_file": (
                str(Path(policy_path).relative_to(repo_path))
                if Path(policy_path).exists()
                else str(policy_path)
            ),
            "patterns": patterns,
            "cli_registry": cli_registry_evidence,
            "integration": integration_evidence,
        }

        if ok:
            return []

        # Build actionable message (single finding per rule)
        if (
            not cli_registry_evidence["has_sync_command"]
            and not integration_evidence["has_integration_reference"]
        ):
            msg = (
                "Knowledge sync is not discoverable (CLI registry) and not referenced by integration "
                "workflows (Makefile/CI/scripts). integration.knowledge_sync_required is not satisfied."
            )
            file_path = ".intent/mind/knowledge/cli_registry.yaml"
        elif not cli_registry_evidence["has_sync_command"]:
            msg = (
                "Integration workflows reference a knowledge sync step, but no corresponding command is "
                "discoverable in the CLI registry. Ensure the sync command is registered and traceable."
            )
            file_path = (
                str(CLI_REGISTRY_PATH.relative_to(repo_path))
                if CLI_REGISTRY_PATH.exists()
                else ".intent/mind/knowledge/cli_registry.yaml"
            )
        else:
            msg = (
                "A knowledge sync command is discoverable in the CLI registry, but integration workflows "
                "do not reference it. Ensure the sync step is wired into Makefile/CI/scripts."
            )
            # Choose the most relevant integration file (if any scanned)
            scanned = integration_evidence.get("scanned_files", [])
            file_path = scanned[0] if scanned else "Makefile/.github/workflows/*"

        return [
            _create_finding_safe(
                self,
                message=msg,
                file_path=file_path,
                severity=AuditSeverity.ERROR,
                evidence=evidence,
            )
        ]

    def _extract_patterns(self, rule_data: dict[str, Any]) -> list[str]:
        """
        Policy override hooks (best-effort):
        - patterns: [...]
        - commands: [...]
        - required_commands: [...]
        - match: [...]
        """
        candidates: list[str] = []

        for key in ("patterns", "commands", "required_commands", "match"):
            val = rule_data.get(key)
            if isinstance(val, list):
                candidates.extend([str(x) for x in val if str(x).strip()])
            elif isinstance(val, str) and val.strip():
                candidates.append(val.strip())

        # Conservative fallback
        if not candidates:
            return list(DEFAULT_SYNC_PATTERNS)

        # Normalize: de-dup, preserve order
        seen: set[str] = set()
        out: list[str] = []
        for x in candidates:
            s = x.strip()
            if not s:
                continue
            if s.lower() in seen:
                continue
            seen.add(s.lower())
            out.append(s)
        return out

    def _check_cli_registry(
        self, repo_path: Path, patterns: list[str]
    ) -> dict[str, Any]:
        """
        Evidence: discover sync command in CLI registry, by scanning string leaves.
        """
        registry_path = CLI_REGISTRY_PATH
        if not registry_path.exists():
            return {
                "path": str(registry_path.relative_to(repo_path)),
                "exists": False,
                "has_sync_command": False,
                "hits": [],
                "note": "CLI registry not found at expected location.",
            }

        try:
            doc = _safe_load_yaml(registry_path)
        except Exception as exc:
            return {
                "path": str(registry_path.relative_to(repo_path)),
                "exists": True,
                "has_sync_command": False,
                "hits": [],
                "error": f"Failed to parse CLI registry: {exc}",
            }

        strings = _recursive_strings(doc)
        hay = "\n".join(strings)
        hits = _find_any_patterns_in_text(hay, patterns)

        return {
            "path": str(registry_path.relative_to(repo_path)),
            "exists": True,
            "has_sync_command": bool(hits),
            "hits": hits[:20],
            "strings_sample": strings[:50],
        }

    def _check_integration_wiring(
        self, repo_path: Path, patterns: list[str]
    ) -> dict[str, Any]:
        """
        Evidence: integration hooks reference knowledge sync.

        We search for the same patterns across:
        - Makefile
        - .github/workflows/*.yml
        - scripts/*
        """
        files = _collect_text_files(repo_path)
        if not files:
            return {
                "has_integration_reference": False,
                "scanned_files": [],
                "hits": [],
                "note": "No integration files discovered (Makefile/.github/workflows/scripts).",
            }

        hits: list[dict[str, Any]] = []

        for p in files:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            found = _find_any_patterns_in_text(text, patterns)
            if not found:
                continue
            rel = str(p.relative_to(repo_path))
            hits.append({"file": rel, "patterns": found[:10]})

        return {
            "has_integration_reference": bool(hits),
            "scanned_files": [str(p.relative_to(repo_path)) for p in files][:200],
            "hits": hits[:50],
        }


# ID: 2a36b430-c8c5-4e65-9c5d-4bcd0f1c5e5e
class IntegrationKnowledgeSyncRequiredCheck(RuleEnforcementCheck):
    """
    Enforces integration knowledge sync requirement.

    Ref:
    - standard_operations_general
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTEGRATION_KNOWLEDGE_SYNC_REQUIRED]

    # Policy file binding (standard_operations_general typically maps to "operations")
    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntegrationKnowledgeSyncRequiredEnforcement(
            rule_id=RULE_INTEGRATION_KNOWLEDGE_SYNC_REQUIRED,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
