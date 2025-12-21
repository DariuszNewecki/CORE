# src/mind/governance/checks/integration_knowledge_sync_check.py
"""
Integration Knowledge Sync Governance Check

Enforces integration rule declared in standard_operations_general:
- integration.knowledge_sync_required

Intent:
CORE must have an explicit, discoverable mechanism to sync "knowledge" after changes
(e.g., regenerate maps, reconcile CLI registry/capabilities, sync DB-backed knowledge, etc.).
This is enforced as an integration prerequisite: if the mechanism is missing, integrations
cannot claim to be complete/safe.

Design constraints:
- Prefer policy-provided expectations (rule_data) first.
- Prefer internal CORE conventions (PathResolver, cli_registry) before fallback scanning.
- Evidence-backed; do not pretend-pass when discovery cannot run.
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


def _safe_yaml_load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _as_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


def _default_expected_command_tokens() -> list[str]:
    """
    Conservative tokens for discovering "knowledge sync" capability.

    We intentionally match broadly (tokens, not exact command names), because CORE
    implementations may evolve (e.g., 'dev-sync', 'knowledge sync', 'reconcile', etc.).
    """
    return [
        "knowledge",
        "sync",
        "dev-sync",
        "reconcile",
        "coverage",
        "audit",
        "introspect",
    ]


def _tokenize(s: str) -> set[str]:
    return {
        t.strip().lower()
        for t in s.replace("/", " ").replace("-", " ").split()
        if t.strip()
    }


def _cli_registry_path() -> Path:
    """
    Prefer settings-based canonical location; fallback to common CORE convention.
    """
    try:
        # If present in your tree, this is the canonical location previously used.
        return (
            settings.REPO_PATH / ".intent" / "mind" / "knowledge" / "cli_registry.yaml"
        )
    except Exception:
        return Path(".intent/mind/knowledge/cli_registry.yaml")


def _discover_cli_registry_entries(
    repo_path: Path, registry_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Returns (entries, meta_evidence).
    """
    evidence: dict[str, Any] = {
        "cli_registry_path": _rel(repo_path, registry_path),
        "exists": registry_path.exists(),
    }
    if not registry_path.exists():
        return [], evidence

    try:
        data = _safe_yaml_load(registry_path)
    except Exception as exc:
        evidence["parse_error"] = str(exc)
        return [], evidence

    # Tolerate a few registry shapes:
    # - {commands: [...]}
    # - {registry: [...]}
    # - [...] (raw list)
    entries: list[dict[str, Any]] = []
    if isinstance(data, list):
        entries = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        for k in ("commands", "registry", "entries", "items"):
            v = data.get(k)
            if isinstance(v, list):
                entries = [x for x in v if isinstance(x, dict)]
                break

    evidence["entry_count"] = len(entries)
    evidence["registry_shape"] = (
        "list"
        if isinstance(data, list)
        else ("dict" if isinstance(data, dict) else str(type(data)))
    )
    return entries, evidence


def _registry_has_knowledge_sync(
    entries: list[dict[str, Any]], tokens: list[str]
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Find entries that plausibly represent a "knowledge sync" mechanism.
    """
    toks = {t.lower() for t in tokens if t.strip()}
    matches: list[dict[str, Any]] = []

    for e in entries:
        # Common fields across registries
        name = str(e.get("name") or e.get("command") or e.get("id") or "").strip()
        desc = str(e.get("description") or e.get("desc") or "").strip()
        path = str(e.get("path") or e.get("module") or e.get("impl") or "").strip()

        blob = " ".join([name, desc, path]).lower()
        blob_tokens = _tokenize(blob)

        # A conservative match: requires "sync" OR "dev sync" AND "knowledge" somewhere,
        # OR explicit known operations like "coverage" + "audit" (often a sync step).
        has_sync = (
            ("sync" in blob_tokens)
            or ("dev" in blob_tokens and "sync" in blob_tokens)
            or ("dev-sync" in blob)
        )
        has_knowledge = "knowledge" in blob_tokens
        has_alt_sync = ("coverage" in blob_tokens and "audit" in blob_tokens) or (
            "reconcile" in blob_tokens
        )

        if (has_sync and has_knowledge) or has_alt_sync:
            matches.append(
                {
                    "name": name,
                    "description": desc,
                    "path": path,
                }
            )
            continue

        # Policy-driven token match (broad)
        if toks and (blob_tokens & toks):
            # still require some “sync-like” signal to avoid accidental matches
            if has_sync or has_alt_sync:
                matches.append({"name": name, "description": desc, "path": path})

    return (len(matches) > 0), matches[:25]


def _fallback_scan_for_sync_implementation(
    repo_path: Path, tokens: list[str]
) -> tuple[bool, dict[str, Any]]:
    """
    Fallback (file-system) scan to detect a concrete implementation if registry is absent.

    We scan src/body/cli and src/body/cli/logic for python modules that look like they
    implement sync/reconcile/coverage/audit operations.

    This does not validate correctness; it validates "existence + discoverability".
    """
    body_root = repo_path / "src" / "body"
    cli_root = body_root / "cli"
    logic_root = cli_root / "logic"

    evidence: dict[str, Any] = {
        "body_root": _rel(repo_path, body_root),
        "cli_root": _rel(repo_path, cli_root),
        "logic_root": _rel(repo_path, logic_root),
        "scanned": [],
        "matches": [],
        "tokens": tokens,
    }

    if not body_root.exists():
        evidence["reason"] = "src/body not found"
        return False, evidence

    scan_roots = [p for p in (cli_root, logic_root) if p.exists()]
    evidence["scanned"] = [_rel(repo_path, p) for p in scan_roots]

    if not scan_roots:
        evidence["reason"] = "src/body/cli not found"
        return False, evidence

    toks = {t.lower() for t in tokens if t.strip()}
    candidates: list[str] = []

    for root in scan_roots:
        for p in root.rglob("*.py"):
            if not p.is_file():
                continue
            name = p.name.lower()
            # quick filename heuristics
            if any(
                t in name
                for t in (
                    "sync",
                    "dev_sync",
                    "dev-sync",
                    "reconcile",
                    "coverage",
                    "audit",
                    "introspect",
                )
            ):
                candidates.append(_rel(repo_path, p))
                continue

            # token-based (policy-driven) filename match
            if toks and any(tok in name for tok in toks):
                candidates.append(_rel(repo_path, p))

    candidates = sorted({c for c in candidates})
    evidence["matches"] = candidates[:50]
    return (len(candidates) > 0), evidence


# ID: 2bba1d4f-1e68-4b54-9a9b-1a7f2c94e7b6
class IntegrationKnowledgeSyncEnforcement(EnforcementMethod):
    """
    Enforces that the repo provides a discoverable "knowledge sync" mechanism.

    Evidence sources (in order):
    1) CLI registry entry under .intent/mind/knowledge/cli_registry.yaml
    2) Fallback: presence of plausible implementation in src/body/cli/**

    Policy overrides (rule_data) supported (best-effort):
    - required_tokens: ["knowledge", "sync", ...]
    - cli_registry_path: ".intent/.../cli_registry.yaml"
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 5f6dc1f1-4f6a-47a2-8846-962f5b1b7b02
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path
        intent_root = repo_path / ".intent"
        if not intent_root.exists():
            return [
                _create_finding_safe(
                    self,
                    message=".intent directory not found; cannot validate integration.knowledge_sync_required.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={"intent_root": str(intent_root)},
                )
            ]

        tokens = (
            _as_list(rule_data.get("required_tokens"))
            or _default_expected_command_tokens()
        )

        registry_path_raw = rule_data.get("cli_registry_path")
        registry_path = (
            (repo_path / str(registry_path_raw))
            if isinstance(registry_path_raw, str) and registry_path_raw.strip()
            else _cli_registry_path()
        )
        if not isinstance(registry_path, Path):
            registry_path = Path(registry_path)

        entries, reg_evidence = _discover_cli_registry_entries(repo_path, registry_path)
        has_registry_match, matches = _registry_has_knowledge_sync(entries, tokens)

        if has_registry_match:
            # Pass: registry makes it discoverable (this is what we enforce here)
            return []

        # Fallback to filesystem scan
        has_impl, impl_evidence = _fallback_scan_for_sync_implementation(
            repo_path, tokens
        )

        if has_impl:
            # Pass: still discoverable (though not via registry)
            # We keep it passing but record evidence as a warning-level finding only if your framework supports it.
            # Conservative: no finding.
            return []

        # Fail: no discoverable mechanism
        evidence = {
            "required_tokens": tokens,
            "registry": reg_evidence,
            "registry_matches": matches,
            "fallback_scan": impl_evidence,
        }

        return [
            _create_finding_safe(
                self,
                message=(
                    "No discoverable 'knowledge sync' mechanism found. "
                    "Expected a CLI registry entry and/or a concrete implementation under src/body/cli/** "
                    "that enables knowledge synchronization (coverage/audit map regeneration, reconcile, dev-sync, etc.)."
                ),
                file_path=(
                    _rel(repo_path, registry_path)
                    if registry_path.exists()
                    else ".intent/mind/knowledge/cli_registry.yaml"
                ),
                severity=AuditSeverity.ERROR,
                evidence=evidence,
            )
        ]


# ID: 9d7d8d5d-6a67-4c7a-a9c8-0e6f0c4b7d2a
class IntegrationKnowledgeSyncCheck(RuleEnforcementCheck):
    """
    Enforces integration.knowledge_sync_required.

    Ref:
    - standard_operations_general
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTEGRATION_KNOWLEDGE_SYNC_REQUIRED]

    # Most "integration.*" rules in your coverage come from standard_operations_general;
    # the canary check already uses settings.paths.policy("operations") for that layer.
    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntegrationKnowledgeSyncEnforcement(
            rule_id=RULE_INTEGRATION_KNOWLEDGE_SYNC_REQUIRED,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
