# src/shared/infrastructure/intent/action_risk.py
"""
Action-id to impact-level mapping helper.

Single source of truth for atomic-action impact classification. The
mapping is owned by .intent/enforcement/config/action_risk.yaml and
governs which actions auto-execute (safe), require human approval
(moderate), or are blocked unless explicitly authorized (dangerous).

Authority: policy. The governing document is
.intent/enforcement/config/action_risk.yaml, accessed exclusively
via IntentRepository. No other module may hardcode the action_id ->
impact_level mapping — all call sites route through this helper. See
ADR-008.

The _FALLBACK_* constants below are last-resort graceful degradation
for the narrow case where the policy document cannot be loaded (e.g.
bootstrap races, corrupt YAML). They MUST NOT be treated as
defaults-in-logic — when the policy loads successfully, it always wins.

LAYER: shared/infrastructure/intent — pure helper. No imports from
will/, body/, or cli/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


_VALID_LEVELS: frozenset[str] = frozenset({"safe", "moderate", "dangerous"})

_FALLBACK_MAPPING: dict[str, str] = {
    "build.tests": "safe",
    "check.imports": "safe",
    "claim.proposal": "safe",
    "crate.create": "safe",
    "file.create": "moderate",
    "file.edit": "moderate",
    "file.read": "safe",
    "file.tag_metadata": "safe",
    "fix.atomic_actions": "moderate",
    "fix.docstrings": "moderate",
    "fix.duplicate_ids": "moderate",
    "fix.format": "safe",
    "fix.headers": "safe",
    "fix.ids": "safe",
    "fix.imports": "safe",
    "fix.logging": "safe",
    "fix.modularity": "moderate",
    "fix.placeholders": "safe",
    "sync.db": "moderate",
    "sync.vectors_code": "moderate",
    "sync.vectors_constitution": "moderate",
}


# ID: 4b8d2e7c-1f9a-4d6b-8c3e-5a7f9b2d4e6c
def _extract_impact_level(action_id: str, raw: Any) -> str:
    """Extract and validate impact_level from a string or dict entry."""
    if isinstance(raw, str):
        level = raw
    elif isinstance(raw, dict):
        level = raw.get("impact_level", "")
    else:
        raise ValueError(
            f"action_risk: actions[{action_id!r}] must be a string or mapping, "
            f"got {type(raw).__name__}"
        )
    if level not in _VALID_LEVELS:
        raise ValueError(
            f"action_risk: actions[{action_id!r}] impact_level={level!r} is not "
            f"valid; allowed values are {sorted(_VALID_LEVELS)}"
        )
    return level


# ID: 90ae779d-8d60-4831-9d06-ebd7aa752d6e
def _extract_artifact_types(raw: Any) -> tuple[str, ...]:
    """Extract artifact_types from a dict entry; returns empty tuple for string entries."""
    if isinstance(raw, dict):
        types = raw.get("artifact_types") or []
        return tuple(str(t) for t in types)
    return ()


# ID: 8c403ddd-8879-4081-8a82-35a9a7d70744
def _validate_config(mapping: dict[str, Any]) -> None:
    """
    Validate every entry in the mapping. Accepts both the old flat-string
    format (action_id: impact_level) and the new dict format introduced by
    ADR-120 D1 (action_id: {impact_level: ..., artifact_types: [...]}).
    Raises ValueError on the first invalid entry.
    """
    for action_id, raw in mapping.items():
        _extract_impact_level(action_id, raw)


# ID: 5c9e3f8d-2a0b-4e7c-9d4f-6b8a0c3e5f7d
def load_action_risk() -> dict[str, str]:
    """
    Load .intent/enforcement/config/action_risk.yaml via IntentRepository.

    Returns the action_id → impact_level mapping. Handles both the old
    flat-string format and the new dict format (ADR-120 D1). On any
    failure returns fallback defaults and logs a warning.
    """
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/action_risk.yaml")
        config = repo.load_document(config_path)
        if isinstance(config, dict):
            actions = config.get("actions")
            if isinstance(actions, dict):
                _validate_config(actions)
                return {
                    aid: _extract_impact_level(aid, raw) for aid, raw in actions.items()
                }
            logger.warning(
                "action_risk: action_risk.yaml missing 'actions' dict "
                "— using fallback defaults."
            )
        else:
            logger.warning(
                "action_risk: action_risk.yaml did not parse as a dict "
                "— using fallback defaults."
            )
    except ValueError:
        raise
    except Exception as exc:
        logger.warning(
            "action_risk: could not load .intent/enforcement/config/"
            "action_risk.yaml (%s) — using fallback defaults.",
            exc,
        )
    return dict(_FALLBACK_MAPPING)


# ID: 1cc5aa00-4cde-41aa-b9b6-62e50de5ea2f
def load_action_risk_raw() -> dict[str, Any]:
    """
    Load .intent/enforcement/config/action_risk.yaml and return the raw
    per-action entries (string or dict) keyed by action_id.

    Used by ActionExecutor.__init__ to overlay both impact_level and
    artifact_types onto ActionDefinition in a single pass (ADR-120 D1).
    On failure returns a fallback of plain strings (impact_level only,
    no artifact_types).
    """
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/action_risk.yaml")
        config = repo.load_document(config_path)
        if isinstance(config, dict):
            actions = config.get("actions")
            if isinstance(actions, dict):
                _validate_config(actions)
                return dict(actions)
            logger.warning(
                "action_risk: action_risk.yaml missing 'actions' dict "
                "— using fallback defaults."
            )
        else:
            logger.warning(
                "action_risk: action_risk.yaml did not parse as a dict "
                "— using fallback defaults."
            )
    except ValueError:
        raise
    except Exception as exc:
        logger.warning(
            "action_risk: could not load .intent/enforcement/config/"
            "action_risk.yaml (%s) — using fallback defaults.",
            exc,
        )
    return dict(_FALLBACK_MAPPING)


# ID: 6da0f4ae-3b1c-4f8d-ae5b-7c9b1d4f6a8e
def get_impact_level(action_id: str) -> str:
    """
    Return the impact level for a given action_id.

    Raises KeyError if the action_id is not present in the mapping —
    callers must register every action in
    .intent/enforcement/config/action_risk.yaml.
    """
    mapping = load_action_risk()
    return mapping[action_id]


_SAFE_AUTO_APPROVAL_ENVELOPE_KEYS: frozenset[str] = frozenset(
    {"authorized_actions", "authorized_path_prefixes", "authorized_extensions"}
)

# Envelope authorization modes (Governor ruling F, 2026-09-15, ADR-159 Trial 0).
# `allow_listed` -- the original and default shape: every list non-empty, the
# listed actions/paths/extensions are what safe auto-approval may grant.
# `deny_all` -- an EXPLICIT nothing-is-authorized envelope: every list must be
# empty. An empty list is valid ONLY under this explicit mode; it is never
# inferred, and a no-op entry is never used to satisfy the loader.
ENVELOPE_MODE_ALLOW_LISTED = "allow_listed"
ENVELOPE_MODE_DENY_ALL = "deny_all"
_ENVELOPE_MODES: frozenset[str] = frozenset(
    {ENVELOPE_MODE_ALLOW_LISTED, ENVELOPE_MODE_DENY_ALL}
)


def _envelope_mode(envelope: dict[str, Any]) -> str:
    mode = envelope.get("authorization_mode", ENVELOPE_MODE_ALLOW_LISTED)
    if mode not in _ENVELOPE_MODES:
        raise ValueError(
            "safe_auto_approval_envelope: 'authorization_mode' must be one of "
            f"{sorted(_ENVELOPE_MODES)}, got {mode!r}"
        )
    return str(mode)


def _validate_envelope(envelope: dict[str, Any]) -> None:
    """Raise ValueError on the first malformed field in the envelope section."""
    mode = _envelope_mode(envelope)
    for key in _SAFE_AUTO_APPROVAL_ENVELOPE_KEYS:
        if key not in envelope:
            raise ValueError(
                f"safe_auto_approval_envelope: required key {key!r} is missing"
            )
        value = envelope[key]
        if not isinstance(value, list):
            raise ValueError(
                f"safe_auto_approval_envelope: {key!r} must be a list, got {value!r}"
            )
        if mode == ENVELOPE_MODE_DENY_ALL:
            if value:
                raise ValueError(
                    f"safe_auto_approval_envelope: {key!r} must be empty under "
                    f"authorization_mode: {ENVELOPE_MODE_DENY_ALL}, got {value!r}"
                )
            continue
        if not value:
            raise ValueError(
                f"safe_auto_approval_envelope: {key!r} must be a non-empty list "
                f"under authorization_mode: {ENVELOPE_MODE_ALLOW_LISTED} (an empty "
                f"list is valid only with an explicit authorization_mode: "
                f"{ENVELOPE_MODE_DENY_ALL}), got {value!r}"
            )
        for item in value:
            if not isinstance(item, str) or not item:
                raise ValueError(
                    f"safe_auto_approval_envelope: {key!r} entries must be "
                    f"non-empty strings, got {item!r}"
                )


def _parsed_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """The loader's success shape (both loaders return exactly this)."""
    return {
        "authorization_mode": _envelope_mode(envelope),
        "authorized_actions": frozenset(envelope["authorized_actions"]),
        "authorized_path_prefixes": tuple(envelope["authorized_path_prefixes"]),
        "authorized_extensions": tuple(envelope["authorized_extensions"]),
    }


# Governed location of the envelope (ADR-159 Note 2026-09-15, #894 Condition 1).
# Overlay-owned: never a floor file. `.intent/`-relative, as IntentRepository
# resolves it.
SAFE_AUTO_APPROVAL_ENVELOPE_REL_PATH = (
    "enforcement/config/safe_auto_approval_envelope.yaml"
)


# ID: 2d9e4f1a-7b3c-4e8d-9a5f-1c6b8d3e7f2a
def load_safe_auto_approval_envelope() -> dict[str, Any]:
    """
    Load the safe_auto_approval_envelope from its own governed file (#853, #894).

    Location: ``enforcement/config/safe_auto_approval_envelope.yaml``,
    top-level key ``safe_auto_approval_envelope``. It lived as a section of
    ``action_risk.yaml`` until ADR-159 Note 2026-09-15 (#894 Condition 1):
    under one Mind per process the floor's ``action_risk.yaml`` must stay
    byte-identical to the shipped floor, so the envelope -- overlay-owned,
    target-specific -- moved to a file the overlay owns. There is NO
    fallback to the old location.

    Independently governed authorization boundary for
    risk_classification.safe_auto_approval — distinct from, and never
    inferred from, the impact_level classification loaded by
    load_action_risk() above. NO HARDCODED FALLBACK: this loader is
    deliberately different from load_action_risk() — where the YAML is
    missing, the section is absent, or an entry is malformed, it returns
    the error sentinel

        {"_error": True, "reason": "<human-readable reason>"}

    and does NOT substitute default values. Callers MUST treat the sentinel
    as "deny safe auto-approval" — an envelope that failed to load must
    never be read as "nothing is authorized so nothing needs checking" and
    must never fall back to a hardcoded permissive default. This mirrors
    shared.infrastructure.intent.audit_verdict's fail-closed contract.

    On success, returns:
        {
            "authorization_mode": "allow_listed" | "deny_all",
            "authorized_actions": frozenset[str],
            "authorized_path_prefixes": tuple[str, ...],
            "authorized_extensions": tuple[str, ...],
        }

    ``authorization_mode: deny_all`` (Governor ruling F, 2026-09-15) is the
    explicit nothing-is-authorized envelope -- every list empty, by
    declaration, never by inference.
    """
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel(SAFE_AUTO_APPROVAL_ENVELOPE_REL_PATH)
        config = repo.load_document(config_path)
        if not isinstance(config, dict):
            reason = (
                f"{SAFE_AUTO_APPROVAL_ENVELOPE_REL_PATH} did not parse as a dict "
                f"(got {type(config).__name__})"
            )
            logger.error("safe_auto_approval_envelope: %s", reason)
            return {"_error": True, "reason": reason}

        envelope = config.get("safe_auto_approval_envelope")
        if not isinstance(envelope, dict):
            reason = (
                f"{SAFE_AUTO_APPROVAL_ENVELOPE_REL_PATH} missing "
                "'safe_auto_approval_envelope' dict"
            )
            logger.error("safe_auto_approval_envelope: %s", reason)
            return {"_error": True, "reason": reason}

        _validate_envelope(envelope)
        return _parsed_envelope(envelope)

    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error(
            "safe_auto_approval_envelope: could not load .intent/%s (%s)",
            SAFE_AUTO_APPROVAL_ENVELOPE_REL_PATH,
            reason,
        )
        return {"_error": True, "reason": reason}


# ID: 7da5d029-f802-40cb-bd1a-6d74cdc7d991
def validate_envelope_file(intent_root: Path) -> dict[str, Any]:
    """Load and validate the envelope from an explicit ``.intent/`` root -- no
    IntentRepository singleton (#894 Unit 2, bind-time check on a materialized
    copy BEFORE bootstrap binds the singleton to it).

    Same contract as :func:`load_safe_auto_approval_envelope`: the parsed
    triple on success, the ``{"_error": True, "reason": ...}`` sentinel on
    any failure. Never raises.
    """
    import yaml

    path = Path(intent_root) / SAFE_AUTO_APPROVAL_ENVELOPE_REL_PATH
    try:
        if not path.is_file():
            return {
                "_error": True,
                "reason": f"{SAFE_AUTO_APPROVAL_ENVELOPE_REL_PATH} not found under {intent_root}",
            }
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return {"_error": True, "reason": f"{path.name} did not parse as a dict"}
        envelope = config.get("safe_auto_approval_envelope")
        if not isinstance(envelope, dict):
            return {
                "_error": True,
                "reason": f"{path.name} missing 'safe_auto_approval_envelope' dict",
            }
        _validate_envelope(envelope)
        return _parsed_envelope(envelope)
    except Exception as exc:
        return {"_error": True, "reason": f"{type(exc).__name__}: {exc}"}
