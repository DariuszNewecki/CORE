# src/mind/governance/checks/capability_metadata_check.py
"""
Capability Metadata Governance Check

Enforces capability metadata rules declared in:
- .intent/policies/code/code_standards.(yaml|yml|json)  (policy key: "code_standards")

Targets (current top gaps):
- caps.meaningful_description
- caps.owner_required

Design constraints:
- Prefer internal CORE capability sources first (if available).
- Fall back to scanning .intent for capability declarations.
- Never "pretend pass" when capability sources cannot be found or parsed.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
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

RULE_CAPS_MEANINGFUL_DESCRIPTION = "caps.meaningful_description"
RULE_CAPS_OWNER_REQUIRED = "caps.owner_required"


# -------------------------
# Internal representation
# -------------------------
@dataclass(frozen=True)
# ID: 58778e59-0963-4ea4-9dd4-194ce03a5338
class CapabilityDecl:
    cap_id: str
    description: str | None
    owners: dict[str, Any] | None
    source_path: str


# -------------------------
# Utilities
# -------------------------
_PLACEHOLDER_TOKENS: tuple[str, ...] = (
    "tbd",
    "todo",
    "fixme",
    "placeholder",
    "lorem",
    "n/a",
    "na",
    "none",
    "unknown",
)


def _is_meaningful_description(text: str | None) -> bool:
    if text is None:
        return False
    t = " ".join(text.strip().split())
    if len(t) < 12:
        return False
    low = t.lower()
    if any(tok in low for tok in _PLACEHOLDER_TOKENS):
        return False
    # reject pure boilerplate like "short description"
    if low in {"description", "short description", "a description"}:
        return False
    return True


def _has_owner(owners: dict[str, Any] | None) -> bool:
    if not owners or not isinstance(owners, dict):
        return False

    # Common shapes:
    # owners:
    #   accountable: "X"
    #   responsible: ["Y"]
    accountable = owners.get("accountable")
    responsible = owners.get("responsible")

    if isinstance(accountable, str) and accountable.strip():
        return True

    if isinstance(responsible, str) and responsible.strip():
        return True

    if isinstance(responsible, list) and any(
        isinstance(x, str) and x.strip() for x in responsible
    ):
        return True

    # Some manifests use "owner" directly
    owner = owners.get("owner")
    if isinstance(owner, str) and owner.strip():
        return True

    return False


def _safe_load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _safe_load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _discover_capability_decls_from_intent(repo_path: Path) -> list[CapabilityDecl]:
    """
    Conservative fallback: scan .intent for files likely to contain capability declarations.

    We intentionally support multiple shapes:
    - {"capabilities": [{id, description, owners}, ...]}
    - {"items": [...]}
    - [{"id": ..., ...}, ...]
    - {"<id>": {description, owners, ...}, ...}
    """
    intent_root = repo_path / ".intent"
    if not intent_root.exists():
        return []

    candidates: list[Path] = []
    for ext in ("*.yaml", "*.yml", "*.json"):
        for p in intent_root.rglob(ext):
            if not p.is_file():
                continue
            name = p.name.lower()
            # Prefer likely capability registries/manifests.
            if "cap" in name or "capability" in name or "manifest" in name:
                candidates.append(p)

    decls: list[CapabilityDecl] = []

    for p in sorted(set(candidates)):
        try:
            data = (
                _safe_load_json(p)
                if p.suffix.lower() == ".json"
                else _safe_load_yaml(p)
            )
        except Exception:
            continue

        # ID: 6404f296-e9e6-40f4-919e-7da3386e3688
        def add_item(item: dict[str, Any]) -> None:
            cap_id = str(item.get("id") or item.get("capability_id") or "").strip()
            if not cap_id:
                return
            desc = item.get("description")
            owners = item.get("owners") or item.get("owner")
            if isinstance(owners, dict):
                owners_dict = owners
            elif isinstance(owners, str) and owners.strip():
                owners_dict = {"owner": owners}
            else:
                owners_dict = None
            decls.append(
                CapabilityDecl(
                    cap_id=cap_id,
                    description=str(desc) if isinstance(desc, str) else None,
                    owners=owners_dict,
                    source_path=str(p.relative_to(repo_path)),
                )
            )

        # Case 1: list at top-level
        if isinstance(data, list):
            for x in data:
                if isinstance(x, dict):
                    add_item(x)
            continue

        # Case 2: dict with list field
        if isinstance(data, dict):
            for key in ("capabilities", "items", "registry", "entries"):
                val = data.get(key)
                if isinstance(val, list):
                    for x in val:
                        if isinstance(x, dict):
                            add_item(x)
                    break
            else:
                # Case 3: mapping id -> dict
                # Only accept if values are dict-like and resemble capability metadata.
                for k, v in data.items():
                    if not isinstance(k, str) or not isinstance(v, dict):
                        continue
                    if "description" in v or "owners" in v or "owner" in v:
                        add_item({"id": k, **v})

    # De-duplicate by id (keep first occurrence; retain source evidence)
    seen: set[str] = set()
    uniq: list[CapabilityDecl] = []
    for d in decls:
        if d.cap_id in seen:
            continue
        seen.add(d.cap_id)
        uniq.append(d)

    return uniq


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    CORE has evolved: EnforcementMethod._create_finding signatures can differ.
    We only pass parameters supported by the current runtime signature.
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


# -------------------------
# Enforcement Methods
# -------------------------
# ID: ad8fe616-694c-45b1-8b94-12ba85c40cf5
class CapMeaningfulDescriptionEnforcement(EnforcementMethod):
    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 1a562003-d579-4565-951d-05ecc78692b0
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        # Prefer internal loaders if available (non-fatal if missing)
        decls: list[CapabilityDecl] = []
        try:
            # Optional internal service (if you have one); keep defensive.
            from features.introspection.capability_discovery_service import (  # type: ignore
                CapabilityDiscoveryService,
            )

            svc = CapabilityDiscoveryService(repo_path=repo_path)  # type: ignore[call-arg]
            maybe = svc.list_declared_capabilities()  # type: ignore[attr-defined]
            if isinstance(maybe, list):
                for x in maybe:
                    if isinstance(x, dict):
                        decls.append(
                            CapabilityDecl(
                                cap_id=str(x.get("id") or "").strip(),
                                description=x.get("description"),
                                owners=x.get("owners"),
                                source_path=str(x.get("source_path") or "<internal>"),
                            )
                        )
        except Exception:
            decls = []

        if not decls:
            decls = _discover_capability_decls_from_intent(repo_path)

        if not decls:
            return [
                _create_finding_safe(
                    self,
                    message="No capability declarations could be discovered; cannot validate caps.meaningful_description.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                )
            ]

        bad: list[dict[str, Any]] = []
        for d in decls:
            if not d.cap_id:
                continue
            if not _is_meaningful_description(d.description):
                bad.append(
                    {
                        "id": d.cap_id,
                        "description": d.description,
                        "source": d.source_path,
                    }
                )

        if not bad:
            return []

        # NOTE: do not pass unsupported kwargs (e.g., details=...) into _create_finding
        return [
            _create_finding_safe(
                self,
                message="Capabilities must have a meaningful description (non-trivial, non-placeholder).",
                file_path=".intent",
                severity=AuditSeverity.ERROR,
                evidence={"invalid": bad[:250], "invalid_count": len(bad)},
            )
        ]


# ID: 0e636fd4-e9c1-4672-9545-a5b44f07daa5
class CapOwnerRequiredEnforcement(EnforcementMethod):
    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 536ae724-f1e4-4023-9780-e96f6a667094
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        decls: list[CapabilityDecl] = []
        try:
            from features.introspection.capability_discovery_service import (  # type: ignore
                CapabilityDiscoveryService,
            )

            svc = CapabilityDiscoveryService(repo_path=repo_path)  # type: ignore[call-arg]
            maybe = svc.list_declared_capabilities()  # type: ignore[attr-defined]
            if isinstance(maybe, list):
                for x in maybe:
                    if isinstance(x, dict):
                        decls.append(
                            CapabilityDecl(
                                cap_id=str(x.get("id") or "").strip(),
                                description=x.get("description"),
                                owners=x.get("owners") or x.get("owner"),
                                source_path=str(x.get("source_path") or "<internal>"),
                            )
                        )
        except Exception:
            decls = []

        if not decls:
            decls = _discover_capability_decls_from_intent(repo_path)

        if not decls:
            return [
                _create_finding_safe(
                    self,
                    message="No capability declarations could be discovered; cannot validate caps.owner_required.",
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                )
            ]

        bad: list[dict[str, Any]] = []
        for d in decls:
            if not d.cap_id:
                continue
            if not _has_owner(d.owners):
                bad.append(
                    {"id": d.cap_id, "owners": d.owners, "source": d.source_path}
                )

        if not bad:
            return []

        return [
            _create_finding_safe(
                self,
                message="Capabilities must declare an owner (accountable or responsible).",
                file_path=".intent",
                severity=AuditSeverity.ERROR,
                evidence={"invalid": bad[:250], "invalid_count": len(bad)},
            )
        ]


# -------------------------
# Check
# -------------------------
# ID: 1b6ced71-e86e-497f-897b-9a3e25281a0f
class CapabilityMetadataCheck(RuleEnforcementCheck):
    """
    Enforces capability metadata requirements.

    Policy: code_standards
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_CAPS_MEANINGFUL_DESCRIPTION,
        RULE_CAPS_OWNER_REQUIRED,
    ]

    # Matches existing usage in your coverage output: policies/code/code_standards
    policy_file: ClassVar[Path] = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CapMeaningfulDescriptionEnforcement(
            rule_id=RULE_CAPS_MEANINGFUL_DESCRIPTION,
            severity=AuditSeverity.ERROR,
        ),
        CapOwnerRequiredEnforcement(
            rule_id=RULE_CAPS_OWNER_REQUIRED,
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
