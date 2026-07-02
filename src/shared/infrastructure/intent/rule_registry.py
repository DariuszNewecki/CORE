# src/shared/infrastructure/intent/rule_registry.py
# Constitutional compliance: shared infrastructure. Reads .intent/rules/**/*.json
# via IntentRepository. No writes, no side effects. ADR-040.
"""
RuleRegistry — validated dictionary of all rule IDs from .intent/rules/.

Use get_rule_registry()["rule.id"] instead of hardcoding rule ID strings
as Python constants. KeyError on an unknown ID surfaces renames and removals
at import time rather than silently routing findings to a dead subject.

Pattern:
    from shared.infrastructure.intent.rule_registry import get_rule_registry
    _TARGET_RULE = get_rule_registry()["ai.prompt.model_required"]
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)

CORE_ROLE = "catalog"  # ADR-095 D3


@lru_cache(maxsize=1)
# ID: 3bcf90e5-1bfc-4d45-8476-473e1880559c
def get_rule_registry() -> dict[str, str]:
    """Return a dict mapping every known rule ID to itself.

    Built by scanning .intent/rules/**/*.json via IntentRepository.
    Cached after first call — the registry is immutable across a daemon run.
    KeyError on an unrecognised ID makes stale constants fail loudly at import.
    """
    try:
        repo = get_intent_repository()
        rules_root: Path = repo.root / ".intent" / "rules"
        if not rules_root.exists():
            logger.warning("RuleRegistry: .intent/rules/ not found at %s", rules_root)
            return {}
        index: dict[str, str] = {}
        for path in sorted(rules_root.rglob("*.json")):
            _load_rule_file(path, index)
        logger.debug("RuleRegistry: loaded %d rule IDs from %s", len(index), rules_root)
        return index
    except Exception as exc:
        logger.error("RuleRegistry: failed to build registry: %s", exc)
        return {}


# ID: 6c8bcb47-f8a4-4397-b2c8-2cf11b8bd2fd
def _load_rule_file(path: Path, index: dict[str, str]) -> None:
    """Parse one rule document JSON and populate *index* with its rule IDs."""
    try:
        doc: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        for rule in doc.get("rules", []):
            rule_id = rule.get("id")
            if isinstance(rule_id, str) and rule_id:
                index[rule_id] = rule_id
    except Exception as exc:
        logger.warning("RuleRegistry: could not parse %s: %s", path, exc)
