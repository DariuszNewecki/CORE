# src/shared/infrastructure/intent/cognitive_roles.py
"""
Cognitive-role taxonomy loader.

Sole sanctioned reader of ``.intent/taxonomies/cognitive_roles.yaml`` —
the canonical declaration of cognitive role names and their
required_capabilities, per ADR-068's taxonomy pattern applied to
cognitive roles (governing paper:
CORE-Cognitive-Role-Capability-Resource-Taxonomy.md).

Fail-closed by design: any failure to obtain the declared role data
(missing file, malformed YAML, missing or empty ``roles:`` map) raises
``CognitiveRolesTaxonomyError``. The loaders NEVER return an empty set
and NEVER fall back to a permissive default — silent pass-all would
defeat the role_abstraction enforcement entirely. Callers that cannot
honour a fail-closed contract must not call these functions.

Two projections of the same document: `load_cognitive_roles` (role names
only — used by artifact_gate.py for prompt-manifest role validation) and
`load_cognitive_role_capabilities` (role name -> required_capabilities —
used by the #821 Unit 2 YAML->DB projection in
body.atomic.cognitive_role_projection_actions).

First loader in ``.intent/taxonomies/``; its shape is precedent for any
future taxonomy consumer (capability_taxonomy.yaml,
governance_namespaces.yaml).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.config import resolve_default_repo_path
from shared.infrastructure.intent._floor import resolve_floor_path
from shared.infrastructure.intent.errors import GovernanceError


COGNITIVE_ROLES_REL = ".intent/taxonomies/cognitive_roles.yaml"


# ID: 45793fcc-9feb-4352-a03e-09c03f44b5a6
class CognitiveRolesTaxonomyError(GovernanceError):
    """Raised when the cognitive-roles taxonomy cannot be loaded fail-closed."""


# ID: 6a1c9e4f-3b7d-4e2a-9c5f-8d1a2b3c4d5e
def _load_roles_block(repo_root: Path | None) -> dict[str, Any]:
    """Read cognitive_roles.yaml and return its top-level 'roles:' mapping.

    Shared by every loader in this module — the single parse of the
    taxonomy file that both `load_cognitive_roles` (names only) and
    `load_cognitive_role_capabilities` (names + required_capabilities)
    project their own shape from.
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

    if not roles_block:
        raise CognitiveRolesTaxonomyError(
            f"{COGNITIVE_ROLES_REL}: 'roles:' block declares no roles."
        )

    return roles_block


# ID: 78ee71b9-225f-48e4-a8ae-cbe94a785360
def load_cognitive_roles(repo_root: Path | None = None) -> frozenset[str]:
    """
    Return the declared cognitive-role name set as a frozenset.

    Reads ``.intent/taxonomies/cognitive_roles.yaml`` and returns the keys
    of its top-level ``roles:`` map. Raises ``CognitiveRolesTaxonomyError``
    on any failure — including an empty role set, which is treated as a
    structural defect rather than a permissive state.
    """
    roles_block = _load_roles_block(repo_root)
    return frozenset(str(name) for name in roles_block.keys())


# ID: 1f9d3c7a-5e8b-4a2f-b6d1-9c4e7a2f8b3d
def load_cognitive_role_capabilities(
    repo_root: Path | None = None,
) -> dict[str, frozenset[str]]:
    """
    Return each declared cognitive role's required_capabilities.

    Reads ``.intent/taxonomies/cognitive_roles.yaml`` and maps each role
    name to the frozenset of capability ids under its ``required_capabilities``
    key (missing or empty list for a role that legitimately declares none).
    Same fail-closed contract as `load_cognitive_roles`: raises
    `CognitiveRolesTaxonomyError` on missing file, malformed YAML, or a
    non-mapping/empty `roles:` block. A role entry that is not a mapping,
    or whose `required_capabilities` is present but not a list, is itself
    a structural defect and raises.
    """
    roles_block = _load_roles_block(repo_root)

    result: dict[str, frozenset[str]] = {}
    for role_name, role_entry in roles_block.items():
        if not isinstance(role_entry, dict):
            raise CognitiveRolesTaxonomyError(
                f"{COGNITIVE_ROLES_REL}: role '{role_name}' is not a mapping."
            )
        capabilities = role_entry.get("required_capabilities", [])
        if not isinstance(capabilities, list):
            raise CognitiveRolesTaxonomyError(
                f"{COGNITIVE_ROLES_REL}: role '{role_name}' has non-list "
                f"required_capabilities."
            )
        result[str(role_name)] = frozenset(str(c) for c in capabilities)

    return result
