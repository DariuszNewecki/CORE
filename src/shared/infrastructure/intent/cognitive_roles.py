# src/shared/infrastructure/intent/cognitive_roles.py
"""
Cognitive-role taxonomy loader.

Sole sanctioned reader of ``.intent/taxonomies/cognitive_roles.yaml`` —
the canonical declaration of cognitive role names per ADR-068's taxonomy
pattern applied to cognitive roles (governing paper:
CORE-Cognitive-Role-Capability-Resource-Taxonomy.md).

Fail-closed by design: any failure to obtain the declared role set
(missing file, malformed YAML, missing or empty ``roles:`` map) raises
``CognitiveRolesTaxonomyError``. The loader NEVER returns an empty set
and NEVER falls back to a permissive default — silent pass-all would
defeat the role_abstraction enforcement entirely. Callers that cannot
honour a fail-closed contract must not call this function.

First loader in ``.intent/taxonomies/``; its shape is precedent for any
future taxonomy consumer (capability_taxonomy.yaml,
governance_namespaces.yaml).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.config import resolve_default_repo_path
from shared.infrastructure.intent._floor import resolve_floor_path
from shared.infrastructure.intent.errors import GovernanceError


COGNITIVE_ROLES_REL = ".intent/taxonomies/cognitive_roles.yaml"


# ID: 45793fcc-9feb-4352-a03e-09c03f44b5a6
class CognitiveRolesTaxonomyError(GovernanceError):
    """Raised when the cognitive-roles taxonomy cannot be loaded fail-closed."""


# ID: 78ee71b9-225f-48e4-a8ae-cbe94a785360
def load_cognitive_roles(repo_root: Path | None = None) -> frozenset[str]:
    """
    Return the declared cognitive-role name set as a frozenset.

    Reads ``.intent/taxonomies/cognitive_roles.yaml`` and returns the keys
    of its top-level ``roles:`` map. Raises ``CognitiveRolesTaxonomyError``
    on any failure — including an empty role set, which is treated as a
    structural defect rather than a permissive state.
    """
    root = (repo_root or resolve_default_repo_path()).resolve()
    path = root / COGNITIVE_ROLES_REL

    if not path.is_file():
        fallback = resolve_floor_path(COGNITIVE_ROLES_REL)
        if fallback is not None:
            path = fallback
        else:
            raise CognitiveRolesTaxonomyError(
                f"cognitive-role taxonomy missing: {COGNITIVE_ROLES_REL}"
            )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CognitiveRolesTaxonomyError(
            f"cannot read {COGNITIVE_ROLES_REL}: {exc}"
        ) from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CognitiveRolesTaxonomyError(
            f"malformed YAML in {COGNITIVE_ROLES_REL}: {exc}"
        ) from exc

    if not isinstance(document, dict):
        raise CognitiveRolesTaxonomyError(
            f"{COGNITIVE_ROLES_REL}: top-level document must be a mapping."
        )

    roles_block = document.get("roles")
    if not isinstance(roles_block, dict):
        raise CognitiveRolesTaxonomyError(
            f"{COGNITIVE_ROLES_REL}: missing or non-mapping 'roles:' block."
        )

    role_names = frozenset(str(name) for name in roles_block.keys())
    if not role_names:
        raise CognitiveRolesTaxonomyError(
            f"{COGNITIVE_ROLES_REL}: 'roles:' block declares no roles."
        )

    return role_names
