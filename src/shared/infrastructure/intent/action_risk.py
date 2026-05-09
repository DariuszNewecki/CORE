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
    "sync.vectors.code": "moderate",
    "sync.vectors.constitution": "moderate",
}


# ID: 4b8d2e7c-1f9a-4d6b-8c3e-5a7f9b2d4e6c
def _validate_config(mapping: dict[str, Any]) -> None:
    """
    Validate at load time that every value in the mapping is one of
    {safe, moderate, dangerous}. Raises ValueError with a clear message
    on the first offending key/value encountered.
    """
    for action_id, level in mapping.items():
        if level not in _VALID_LEVELS:
            raise ValueError(
                f"action_risk: actions[{action_id!r}] = {level!r} is not a "
                f"valid impact level; allowed values are {sorted(_VALID_LEVELS)}"
            )


# ID: 5c9e3f8d-2a0b-4e7c-9d4f-6b8a0c3e5f7d
def load_action_risk() -> dict[str, str]:
    """
    Load .intent/enforcement/config/action_risk.yaml via IntentRepository.

    Returns the action_id -> impact_level mapping on success. On any
    failure — missing file, parse error, unexpected top-level type —
    returns fallback defaults and logs a warning so callers degrade
    gracefully rather than halting.

    The loader validates every impact level against
    {safe, moderate, dangerous} before returning. A YAML that maps an
    action to anything else raises ValueError at load time, not at the
    call site.
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
