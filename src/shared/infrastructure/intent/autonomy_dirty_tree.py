# src/shared/infrastructure/intent/autonomy_dirty_tree.py
# ID: shared.infrastructure.intent.autonomy_dirty_tree
"""
Autonomy dirty-tree policy loader.

Provides the working-tree mode used by ProposalExecutor's pre-claim
collision check, governing whether the autonomous daemon yields on
intersection-only or on any-dirty working tree. The governing document
is .intent/enforcement/config/autonomy_dirty_tree.yaml, accessed
exclusively via IntentRepository. See ADR-021.

NO HARDCODED FALLBACK. When the YAML is missing, unparseable, or
validation-fails, this loader returns a sentinel dict

    {"_error": True, "reason": "<human-readable reason>"}

and does NOT substitute default values. Callers MUST treat the
sentinel as mode=any_dirty — the conservative halt-toward-safety
mode — and not as intersection_only. Silent fallback to
intersection_only would convert "the dirty-tree law is missing" into
"the daemon is willing to step on uncommitted changes," which is the
exact failure mode this policy exists to prevent.

LAYER: shared/infrastructure/intent — pure helper. Returns a dict;
does not import ProposalExecutor or the autonomy layer. No imports
from will/, body/, or cli/.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


_VALID_MODES: frozenset[str] = frozenset({"intersection_only", "any_dirty"})


def _validate_policy(policy: dict[str, Any]) -> None:
    """
    Validate the loaded policy dict at load time.

    Raises ValueError with a precise, human-readable message on the
    first offending key/value. The outer loader converts any exception
    to the error sentinel.
    """
    if "mode" not in policy:
        raise ValueError("autonomy_dirty_tree: required key 'mode' is missing")
    if not isinstance(policy["mode"], str):
        raise ValueError(
            f"autonomy_dirty_tree: 'mode' must be a string, got "
            f"{type(policy['mode']).__name__}"
        )
    if policy["mode"] not in _VALID_MODES:
        raise ValueError(
            f"autonomy_dirty_tree: 'mode' value {policy['mode']!r} is not a "
            f"valid mode; allowed values are {sorted(_VALID_MODES)}"
        )


# ID: f1e8d3a9-4b27-4c5e-9f1a-6d8b3e2c7a5f
def load_autonomy_dirty_tree_policy() -> dict[str, Any]:
    """
    Load .intent/enforcement/config/autonomy_dirty_tree.yaml via IntentRepository.

    Returns the parsed-and-validated policy dict on success. On ANY
    failure — missing file, parse error, unexpected top-level type,
    schema validation failure — returns the error sentinel

        {"_error": True, "reason": "<human-readable reason>"}

    and logs the specific reason at ERROR level. Callers MUST treat the
    sentinel as mode=any_dirty (the conservative halt-toward-safety
    mode); see ADR-021.
    """
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/autonomy_dirty_tree.yaml")
        config = repo.load_document(config_path)
        if not isinstance(config, dict):
            reason = (
                f"autonomy_dirty_tree.yaml did not parse as a dict "
                f"(got {type(config).__name__})"
            )
            logger.error("autonomy_dirty_tree: %s", reason)
            return {"_error": True, "reason": reason}

        _validate_policy(config)
        return config

    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error(
            "autonomy_dirty_tree: could not load .intent/enforcement/config/"
            "autonomy_dirty_tree.yaml (%s)",
            reason,
        )
        return {"_error": True, "reason": reason}
