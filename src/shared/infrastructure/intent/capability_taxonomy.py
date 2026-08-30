# src/shared/infrastructure/intent/capability_taxonomy.py
"""
Capability taxonomy loader.

Sole sanctioned reader of ``.intent/taxonomies/capability_taxonomy.yaml`` —
the canonical declaration of capability ids, grouped into families, that
`core.cognitive_roles.required_capabilities` and
`core.llm_resources.provided_capabilities` values must be drawn from
(enforced today by `mind.logic.engines.knowledge_gate.KnowledgeGateEngine`'s
`capability_taxonomy_whitelist` check, blocking rules
`capability.taxonomy.roles_require_canonical_capabilities` /
`...resources_provide_canonical_capabilities`).

Fail-closed by design, mirroring `cognitive_roles.py`'s contract: any
failure to obtain the declared capability set (missing file, malformed
YAML, missing or empty ``families:`` map) raises
``CapabilityTaxonomyError``. The loader NEVER returns an empty set and
NEVER falls back to a permissive default. Callers that cannot honour a
fail-closed contract must not call this function.

This is the write-time counterpart to `KnowledgeGateEngine`'s read-time
audit check: both should validate against the same canonical set, though
today they parse the taxonomy independently (the engine via
`context.intent_repo.load_document`, this loader via direct file read
following `cognitive_roles.py`'s established gateway pattern).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.config import resolve_default_repo_path
from shared.infrastructure.intent._floor import resolve_floor_path
from shared.infrastructure.intent.errors import GovernanceError


CAPABILITY_TAXONOMY_REL = ".intent/taxonomies/capability_taxonomy.yaml"


# ID: 2d8e4f1a-6b9c-4d3e-a7f2-5c8b1e4a9d6f
class CapabilityTaxonomyError(GovernanceError):
    """Raised when the capability taxonomy cannot be loaded fail-closed."""


# ID: 9a3c7e2b-4f8d-4a1e-9c6b-3d7f2a8e5c1b
def load_capability_taxonomy(repo_root: Path | None = None) -> frozenset[str]:
    """
    Return the declared canonical capability id set as a frozenset.

    Reads ``.intent/taxonomies/capability_taxonomy.yaml`` and returns the
    union of keys under every family's ``capabilities:`` map (i.e.
    ``families.<family>.capabilities.<capability_id>``). Family names
    themselves are not canonical capability ids. Raises
    ``CapabilityTaxonomyError`` on any failure — including an empty
    result, which is treated as a structural defect rather than a
    permissive state.
    """
    root = (repo_root or resolve_default_repo_path()).resolve()
    path = root / CAPABILITY_TAXONOMY_REL

    if not path.is_file():
        fallback = resolve_floor_path(CAPABILITY_TAXONOMY_REL)
        if fallback is not None:
            path = fallback
        else:
            raise CapabilityTaxonomyError(
                f"capability taxonomy missing: {CAPABILITY_TAXONOMY_REL}"
            )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CapabilityTaxonomyError(
            f"cannot read {CAPABILITY_TAXONOMY_REL}: {exc}"
        ) from exc

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CapabilityTaxonomyError(
            f"malformed YAML in {CAPABILITY_TAXONOMY_REL}: {exc}"
        ) from exc

    if not isinstance(document, dict):
        raise CapabilityTaxonomyError(
            f"{CAPABILITY_TAXONOMY_REL}: top-level document must be a mapping."
        )

    families_block = document.get("families")
    if not isinstance(families_block, dict):
        raise CapabilityTaxonomyError(
            f"{CAPABILITY_TAXONOMY_REL}: missing or non-mapping 'families:' block."
        )

    capability_ids: set[str] = set()
    for family_name, family in families_block.items():
        if not isinstance(family, dict):
            raise CapabilityTaxonomyError(
                f"{CAPABILITY_TAXONOMY_REL}: family '{family_name}' is not a mapping."
            )
        family_capabilities = family.get("capabilities")
        if not isinstance(family_capabilities, dict):
            raise CapabilityTaxonomyError(
                f"{CAPABILITY_TAXONOMY_REL}: family '{family_name}' has missing or "
                f"non-mapping 'capabilities:' block."
            )
        capability_ids.update(str(cap_id) for cap_id in family_capabilities.keys())

    if not capability_ids:
        raise CapabilityTaxonomyError(
            f"{CAPABILITY_TAXONOMY_REL}: no capability ids declared under any family."
        )

    return frozenset(capability_ids)
