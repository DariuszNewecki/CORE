# src/shared/infrastructure/intent/operational_capabilities.py
"""
Operational-capability taxonomy loader.

Sole sanctioned reader of ``.intent/taxonomies/operational_capabilities.yaml``
— the canonical declaration of operational capabilities and their filesystem
authorization profiles per ADR-078 (schema) and the foundational paper
CORE-Capability-Scoped-Filesystem-Authority.md.

Fail-closed by design per ADR-068 pattern: any structural deviation raises
``OperationalCapabilityTaxonomyError``. The loader never returns an empty
set and never falls back to a permissive default — silent pass-all would
defeat capability-scoped authorization entirely. Callers that cannot honour
a fail-closed contract must not call this function.

The loader cross-references two sibling .intent/ artifacts on every load:

  - ``.intent/META/enums.json`` resolves ``fs_operation_class`` (the
    fs_profile key vocabulary) and ``operational_mode`` (the accepted modes
    vocabulary). Both are sourced from enums.json at load time, not
    hardcoded — adding a fifth op-class is a coordinated enums.json + YAML
    edit, not a Python change.
  - ``.intent/enforcement/config/action_risk.yaml`` is the single source
    of truth for risk classification. Each capability's ``risk`` field
    must be present in action_risk.yaml for that capability_id AND the
    risk values must agree; drift between the two surfaces is a load-time
    failure.

Three-way load-order coupling: ``enums.json`` and ``action_risk.yaml`` must
both be readable and structurally valid before
``operational_capabilities.yaml`` is loadable.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared.config import resolve_default_repo_path
from shared.infrastructure.intent._floor import resolve_floor_path
from shared.infrastructure.intent.errors import GovernanceError


OPERATIONAL_CAPABILITIES_REL = ".intent/taxonomies/operational_capabilities.yaml"
ENUMS_REL = ".intent/META/enums.json"
ACTION_RISK_REL = ".intent/enforcement/config/action_risk.yaml"

# ADR-078 D6: capability-id grammar regex. Exactly one dot; both halves
# lowercase + underscore. The loader fails closed on any violation.
_CAPABILITY_ID_REGEX = re.compile(r"^[a-z][a-z_]*\.[a-z][a-z_]+$")

# ADR-078 D8: chokepoint primitives are not capabilities. Their ids are
# structurally excluded from this taxonomy.
_CHOKEPOINT_PRIMITIVE_PREFIX = "file."

# Closed risk vocabulary per ADR-078 D3 (mirrors action_risk.yaml header).
_VALID_RISKS = frozenset({"safe", "moderate", "dangerous"})

# Required-field discipline.
_REQUIRED_CAPABILITY_FIELDS = frozenset({"description", "risk", "fs_profile"})
# ADR-092 D1 + D4 (Option B): optional artifact_type binding. Capabilities that
# mutate an F-41-registered artifact declare their target; the ~13 infrastructure
# capabilities (DB-only, dispatcher, read-only) omit the field per ADR-092
# sub-question (i). The ActionExecutor chokepoint refuses dispatch when a
# declared artifact_type is not present in the F-41 IntentRepository registry.
_OPTIONAL_CAPABILITY_FIELDS = frozenset({"artifact_type"})
_KNOWN_CAPABILITY_FIELDS = _REQUIRED_CAPABILITY_FIELDS | _OPTIONAL_CAPABILITY_FIELDS
_REQUIRED_PATTERN_ENTRY_FIELDS = frozenset({"path_pattern", "modes"})


# ID: 5157d532-9bb2-4176-92c2-c071a8eecc37
class OperationalCapabilityTaxonomyError(GovernanceError):
    """Raised when the operational-capability taxonomy cannot be loaded fail-closed."""


@dataclass(frozen=True)
# ID: a1376303-989f-4335-8b09-71f59975e32d
class FsPatternEntry:
    """A single filesystem pattern entry within an fs_profile operation-class list."""

    path_pattern: str
    modes: tuple[str, ...]


@dataclass(frozen=True)
# ID: fa5f8ab9-8cf0-43b6-999f-b74d69363787
class OperationalCapability:
    """
    A single operational capability with its filesystem authorization profile.

    ``fs_profile`` is stored as a hashable tuple-of-pairs
    ``(op_class, pattern_entries)`` ordered by ``fs_operation_class``
    values. Mapping access is exposed via the ``as_mapping`` property.
    The tuple-of-pairs shape — rather than a fixed dataclass with one
    field per op-class — keeps the key set sourced from enums.json at load
    time (ADR-078 D10).
    """

    id: str
    description: str
    risk: str
    fs_profile: tuple[tuple[str, tuple[FsPatternEntry, ...]], ...]
    artifact_type: tuple[str, ...] = ()
    """
    F-41 artifact_type IDs this capability mutates. Optional per ADR-092 D4
    Option B + sub-question (i): non-mutating infrastructure capabilities omit
    the field (empty tuple). Mutating capabilities declare their targets; the
    ActionExecutor chokepoint refuses dispatch when any declared ID is not
    present in the F-41 IntentRepository registry (ADR-091 D6 item 3,
    ADR-092 D1).
    """

    @property
    # ID: bd74eb57-912d-409c-9d19-76e154f07aed
    def as_mapping(self) -> Mapping[str, tuple[FsPatternEntry, ...]]:
        """Return fs_profile as a mapping view for ergonomic key access."""
        return dict(self.fs_profile)


# ID: 86d27090-969b-4736-83f1-bbe20dec2aa4
def load_operational_capabilities(
    repo_root: Path | None = None,
) -> frozenset[OperationalCapability]:
    """
    Return the declared operational-capability set as a frozenset of immutable records.

    Reads ``.intent/taxonomies/operational_capabilities.yaml`` and validates
    every entry against ADR-078 D3/D4/D6/D8/D10. Cross-references the
    sibling ``.intent/META/enums.json`` for fs_profile key and mode
    vocabularies, and ``.intent/enforcement/config/action_risk.yaml`` for
    risk classification agreement. Raises
    ``OperationalCapabilityTaxonomyError`` on any structural deviation.
    """
    root = (repo_root or resolve_default_repo_path()).resolve()

    fs_op_classes, valid_modes = _load_enums(root)
    action_risk_map = _load_action_risk(root)
    document = _load_document(root)

    capabilities_block = document.get("capabilities")
    if not isinstance(capabilities_block, dict):
        raise OperationalCapabilityTaxonomyError(
            f"{OPERATIONAL_CAPABILITIES_REL}: missing or non-mapping 'capabilities:' block."
        )
    if not capabilities_block:
        raise OperationalCapabilityTaxonomyError(
            f"{OPERATIONAL_CAPABILITIES_REL}: 'capabilities:' block declares no capabilities."
        )

    capabilities: set[OperationalCapability] = set()
    for cap_id, entry in capabilities_block.items():
        capabilities.add(
            _build_capability(
                cap_id=str(cap_id),
                entry=entry,
                fs_op_classes=fs_op_classes,
                valid_modes=valid_modes,
                action_risk_map=action_risk_map,
            )
        )

    return frozenset(capabilities)


def _load_document(root: Path) -> dict[str, Any]:
    """Load and minimally validate the top-level taxonomy YAML document."""
    path = root / OPERATIONAL_CAPABILITIES_REL
    if not path.is_file():
        fallback = resolve_floor_path(OPERATIONAL_CAPABILITIES_REL)
        if fallback is not None:
            path = fallback
        else:
            raise OperationalCapabilityTaxonomyError(
                f"operational-capability taxonomy missing: {OPERATIONAL_CAPABILITIES_REL}"
            )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OperationalCapabilityTaxonomyError(
            f"cannot read {OPERATIONAL_CAPABILITIES_REL}: {exc}"
        ) from exc
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise OperationalCapabilityTaxonomyError(
            f"malformed YAML in {OPERATIONAL_CAPABILITIES_REL}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise OperationalCapabilityTaxonomyError(
            f"{OPERATIONAL_CAPABILITIES_REL}: top-level document must be a mapping."
        )
    return document


def _load_enums(root: Path) -> tuple[tuple[str, ...], frozenset[str]]:
    """
    Resolve fs_operation_class.enum and operational_mode.enum from .intent/META/enums.json.

    Returns (fs_op_classes ordered tuple, valid_modes frozenset). The order
    of fs_op_classes is preserved as declared in enums.json — it determines
    the canonical ordering of fs_profile pairs in OperationalCapability.
    """
    path = root / ENUMS_REL
    if not path.is_file():
        fallback = resolve_floor_path(ENUMS_REL)
        if fallback is not None:
            path = fallback
        else:
            raise OperationalCapabilityTaxonomyError(
                f"required enum file missing: {ENUMS_REL}"
            )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OperationalCapabilityTaxonomyError(
            f"cannot read {ENUMS_REL}: {exc}"
        ) from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OperationalCapabilityTaxonomyError(
            f"malformed JSON in {ENUMS_REL}: {exc}"
        ) from exc

    definitions = document.get("definitions") if isinstance(document, dict) else None
    if not isinstance(definitions, dict):
        raise OperationalCapabilityTaxonomyError(
            f"{ENUMS_REL}: missing or non-mapping 'definitions' block."
        )

    fs_op_def = definitions.get("fs_operation_class")
    if not isinstance(fs_op_def, dict) or not isinstance(fs_op_def.get("enum"), list):
        raise OperationalCapabilityTaxonomyError(
            f"{ENUMS_REL}: missing or malformed 'fs_operation_class' enum."
        )
    fs_op_classes = tuple(str(v) for v in fs_op_def["enum"])
    if not fs_op_classes:
        raise OperationalCapabilityTaxonomyError(
            f"{ENUMS_REL}: 'fs_operation_class' enum is empty."
        )

    op_mode_def = definitions.get("operational_mode")
    if not isinstance(op_mode_def, dict) or not isinstance(
        op_mode_def.get("enum"), list
    ):
        raise OperationalCapabilityTaxonomyError(
            f"{ENUMS_REL}: missing or malformed 'operational_mode' enum."
        )
    valid_modes = frozenset(str(v) for v in op_mode_def["enum"])
    if not valid_modes:
        raise OperationalCapabilityTaxonomyError(
            f"{ENUMS_REL}: 'operational_mode' enum is empty."
        )

    return fs_op_classes, valid_modes


def _load_action_risk(root: Path) -> Mapping[str, str]:
    """
    Load .intent/enforcement/config/action_risk.yaml and return the action_id → risk mapping.

    Per ADR-078 D3, every capability's risk field must (a) be present as a
    key in this mapping, and (b) carry a value that matches this mapping's
    value for that capability_id. Both checks are enforced in
    _build_capability.
    """
    path = root / ACTION_RISK_REL
    if not path.is_file():
        fallback = resolve_floor_path(ACTION_RISK_REL)
        if fallback is not None:
            path = fallback
        else:
            raise OperationalCapabilityTaxonomyError(
                f"required risk file missing: {ACTION_RISK_REL}"
            )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OperationalCapabilityTaxonomyError(
            f"cannot read {ACTION_RISK_REL}: {exc}"
        ) from exc
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise OperationalCapabilityTaxonomyError(
            f"malformed YAML in {ACTION_RISK_REL}: {exc}"
        ) from exc

    actions_block = document.get("actions") if isinstance(document, dict) else None
    if not isinstance(actions_block, dict):
        raise OperationalCapabilityTaxonomyError(
            f"{ACTION_RISK_REL}: missing or non-mapping 'actions:' block."
        )
    if not actions_block:
        raise OperationalCapabilityTaxonomyError(
            f"{ACTION_RISK_REL}: 'actions:' block declares no entries."
        )

    # Normalise both flat-string (old) and dict (ADR-120 D1 new) entry formats.
    result: dict[str, str] = {}
    for k, v in actions_block.items():
        result[str(k)] = v.get("impact_level", "") if isinstance(v, dict) else str(v)
    return result


def _build_capability(
    *,
    cap_id: str,
    entry: Any,
    fs_op_classes: tuple[str, ...],
    valid_modes: frozenset[str],
    action_risk_map: Mapping[str, str],
) -> OperationalCapability:
    """Assemble and validate one OperationalCapability from a YAML entry."""
    if not _CAPABILITY_ID_REGEX.match(cap_id):
        raise OperationalCapabilityTaxonomyError(
            f"capability id '{cap_id}' violates D6 grammar "
            f"(^[a-z][a-z_]*\\.[a-z][a-z_]+$); rename in the change-set that lands it."
        )
    if cap_id.startswith(_CHOKEPOINT_PRIMITIVE_PREFIX):
        raise OperationalCapabilityTaxonomyError(
            f"capability id '{cap_id}' is a chokepoint primitive (D8) and "
            f"must not appear in {OPERATIONAL_CAPABILITIES_REL}."
        )
    if not isinstance(entry, dict):
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': entry must be a mapping, got {type(entry).__name__}."
        )

    actual_fields = frozenset(entry.keys())
    missing = _REQUIRED_CAPABILITY_FIELDS - actual_fields
    if missing:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': missing required field(s): {sorted(missing)}."
        )
    extra = actual_fields - _KNOWN_CAPABILITY_FIELDS
    if extra:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': unknown field(s): {sorted(extra)}."
        )

    description = entry["description"]
    if not isinstance(description, str) or not description.strip():
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': 'description' must be a non-empty string."
        )

    risk = entry["risk"]
    if not isinstance(risk, str):
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': 'risk' must be a string, got {type(risk).__name__}."
        )
    if risk not in _VALID_RISKS:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': risk '{risk}' is not in "
            f"{{safe, moderate, dangerous}} (ADR-078 D3)."
        )
    declared_risk = action_risk_map.get(cap_id)
    if declared_risk is None:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': not declared in {ACTION_RISK_REL}; "
            f"every capability must have a corresponding action_risk.yaml entry (ADR-078 D3)."
        )
    if declared_risk != risk:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': risk '{risk}' disagrees with "
            f"{ACTION_RISK_REL} value '{declared_risk}'; one of the two must be corrected (ADR-078 D3)."
        )

    fs_profile = _parse_fs_profile(
        cap_id=cap_id,
        raw=entry["fs_profile"],
        fs_op_classes=fs_op_classes,
        valid_modes=valid_modes,
    )

    artifact_type = _parse_artifact_type(cap_id=cap_id, raw=entry.get("artifact_type"))

    return OperationalCapability(
        id=cap_id,
        description=description,
        risk=risk,
        fs_profile=fs_profile,
        artifact_type=artifact_type,
    )


# ID: 9c3b71d4-2e5f-46a8-b1c9-d847e0f3a5b2
def _parse_artifact_type(*, cap_id: str, raw: Any) -> tuple[str, ...]:
    """Validate and normalize the optional artifact_type field (ADR-092 D1).

    Absence and empty list both yield an empty tuple — the capability does not
    engage the F-43 registry-coupling chokepoint. When present and non-empty,
    every element must be a non-empty string; the F-41 registry check happens
    at dispatch time in ActionExecutor.execute(), not at load time, so the
    loader does not consult IntentRepository here.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': 'artifact_type' must be a list of strings, "
            f"got {type(raw).__name__}."
        )
    normalized: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise OperationalCapabilityTaxonomyError(
                f"capability '{cap_id}': 'artifact_type' entries must be "
                f"non-empty strings; got {item!r}."
            )
        normalized.append(item)
    return tuple(normalized)


def _parse_fs_profile(
    *,
    cap_id: str,
    raw: Any,
    fs_op_classes: tuple[str, ...],
    valid_modes: frozenset[str],
) -> tuple[tuple[str, tuple[FsPatternEntry, ...]], ...]:
    """
    Validate fs_profile shape and assemble the hashable tuple-of-pairs.

    Pairs are emitted in the order declared by fs_operation_class.enum so
    that two OperationalCapability instances with the same content hash
    identically regardless of the source YAML's key order.
    """
    if not isinstance(raw, dict):
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': 'fs_profile' must be a mapping, "
            f"got {type(raw).__name__}."
        )
    expected_keys = frozenset(fs_op_classes)
    actual_keys = frozenset(raw.keys())
    missing = expected_keys - actual_keys
    if missing:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile missing required op-class key(s): "
            f"{sorted(missing)} (must match fs_operation_class.enum exactly per ADR-078 D4)."
        )
    extra = actual_keys - expected_keys
    if extra:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile has unknown key(s): {sorted(extra)} "
            f"(must match fs_operation_class.enum exactly per ADR-078 D4)."
        )

    pairs: list[tuple[str, tuple[FsPatternEntry, ...]]] = []
    for op_class in fs_op_classes:
        entries = raw[op_class]
        if not isinstance(entries, list):
            raise OperationalCapabilityTaxonomyError(
                f"capability '{cap_id}': fs_profile.{op_class} must be a list, "
                f"got {type(entries).__name__}."
            )
        parsed = tuple(
            _parse_pattern_entry(
                cap_id=cap_id,
                op_class=op_class,
                raw=item,
                valid_modes=valid_modes,
            )
            for item in entries
        )
        pairs.append((op_class, parsed))
    return tuple(pairs)


def _parse_pattern_entry(
    *,
    cap_id: str,
    op_class: str,
    raw: Any,
    valid_modes: frozenset[str],
) -> FsPatternEntry:
    """Validate a single path_pattern/modes entry and return the frozen record."""
    if not isinstance(raw, dict):
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile.{op_class} entry must be a mapping, "
            f"got {type(raw).__name__}."
        )
    actual_keys = frozenset(raw.keys())
    missing = _REQUIRED_PATTERN_ENTRY_FIELDS - actual_keys
    if missing:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile.{op_class} entry missing field(s): "
            f"{sorted(missing)}."
        )
    extra = actual_keys - _REQUIRED_PATTERN_ENTRY_FIELDS
    if extra:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile.{op_class} entry has unknown field(s): "
            f"{sorted(extra)}."
        )
    path_pattern = raw["path_pattern"]
    if not isinstance(path_pattern, str) or not path_pattern.strip():
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile.{op_class} entry 'path_pattern' "
            f"must be a non-empty string."
        )
    modes_raw = raw["modes"]
    if not isinstance(modes_raw, list):
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile.{op_class} entry 'modes' must be a list, "
            f"got {type(modes_raw).__name__}."
        )
    if not modes_raw:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile.{op_class} entry 'modes' is empty; "
            f"omit the entry to deny in all modes (ADR-078 D4)."
        )
    modes_tuple = tuple(str(m) for m in modes_raw)
    unknown_modes = {m for m in modes_tuple if m not in valid_modes}
    if unknown_modes:
        raise OperationalCapabilityTaxonomyError(
            f"capability '{cap_id}': fs_profile.{op_class} entry has mode(s) "
            f"outside operational_mode.enum: {sorted(unknown_modes)}."
        )
    return FsPatternEntry(path_pattern=path_pattern, modes=modes_tuple)
