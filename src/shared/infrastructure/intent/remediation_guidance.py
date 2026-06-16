# src/shared/infrastructure/intent/remediation_guidance.py

"""Read-only accessor for a rule's remediation guidance (ADR-109 #653).

The Assisted Remediation Lane context bundle needs the human-readable
remediation hint for a delegated finding's rule — the ``description`` (and
DELEGATE/ACTIVE ``status``) recorded in
``.intent/enforcement/remediation/auto_remediation.yaml``. This module is the
sanctioned `.intent`-read door for that one projection (it lives under
``src/shared/infrastructure/intent/``, the gateway location that
``architecture.namespace.no_direct_protected_access`` exempts).

This is a deliberately thin, guidance-only projection. The executor-facing
loader — ``body.autonomy.audit_analyzer._load_remediation_map`` — reads the same
file but projects ``ref_id``/``ref_kind``/``confidence`` for dispatch; the two
serve different consumers. If the YAML's shape changes, both readers update.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.config import resolve_default_repo_path
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: f8eedf82-3c21-4e8e-b4a3-9c59ee49580d
def load_remediation_guidance(
    rule_id: str | None, repo_root: Path | None = None
) -> dict[str, Any] | None:
    """Return the remediation guidance for *rule_id*, or None if unavailable.

    Args:
        rule_id: the rule the finding fired on. None / empty returns None.
        repo_root: optional override; defaults to the active repo root
            (``resolve_default_repo_path``), so this works both in the source
            tree and against a consumer repo.

    Returns a ``{description, status, confidence}`` dict when the rule has a
    remediation-map entry, else None (rule absent from the map, or the map is
    missing). Never raises on a missing rule/file — the bundle treats guidance
    as best-effort context.
    """
    if not rule_id:
        return None

    root = repo_root or resolve_default_repo_path()
    map_path = PathResolver(root).remediation_map_path
    if not map_path.exists():
        logger.debug("Remediation map not found at %s", map_path)
        return None

    try:
        data = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # malformed map is non-fatal for the bundle
        logger.warning("Could not parse remediation map: %s", exc)
        return None

    entry = (data.get("mappings") or {}).get(rule_id)
    if not entry:
        return None
    return {
        "description": entry.get("description"),
        "status": entry.get("status"),
        "confidence": entry.get("confidence"),
    }
