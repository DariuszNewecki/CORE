# src/shared/infrastructure/intent/target_class.py
"""
Target-class taxonomy loader for the single filesystem write chokepoint.

Sole sanctioned reader of ``.intent/taxonomies/target_class_boundaries.yaml``
— the path-prefix → target-class mapping declared by ADR-097 D2 and consumed
by FileHandler's target-aware dispatch (ADR-097 D4).

Fail-closed by design per ADR-068 pattern: any structural deviation raises
``TargetClassBoundariesError``. The loader never returns an empty taxonomy
and never falls back to a permissive default — silent pass-all would defeat
the dispatch whose authority rests on this vocabulary.

Cross-references ``.intent/META/enums.json`` on every load to resolve the
``target_class`` enum. Each boundary entry's ``target_class`` value is
validated against that enum at load time; drift between the YAML and the
enum is a load-time failure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared.config import resolve_default_repo_path
from shared.infrastructure.intent.errors import GovernanceError


TARGET_CLASS_BOUNDARIES_REL = ".intent/taxonomies/target_class_boundaries.yaml"
ENUMS_REL = ".intent/META/enums.json"


# ID: 8f1d7c3a-2b4e-4a91-9c8f-3e7d2a1b5f64
class TargetClassBoundariesError(GovernanceError):
    """Raised when the target-class boundaries cannot be loaded fail-closed."""


@dataclass(frozen=True)
# ID: a4c91e7b-5d28-4f63-b1a0-7c2e9f8d3b51
class TargetClassBoundary:
    """A single path-prefix → target-class mapping entry."""

    prefix: str
    target_class: str


@dataclass(frozen=True)
# ID: c7e2f843-9b15-4a08-8d6c-5f1e3b9a2d47
class TargetClassBoundaries:
    """Loaded boundaries plus default fallback.

    ``boundaries`` is the declared order; resolution walks it top-to-bottom
    and returns the first matching entry's ``target_class``. ``default``
    is returned when no prefix matches (ADR-097 D2 third rule).
    """

    boundaries: tuple[TargetClassBoundary, ...]
    default: str


# ID: 2b5a8d14-7e93-4c61-a8f2-9d4b3e7c1f08
def load_target_class_boundaries(
    repo_root: Path | None = None,
) -> TargetClassBoundaries:
    """Return the declared target-class boundaries as a frozen container.

    Reads ``.intent/taxonomies/target_class_boundaries.yaml`` and validates
    every entry against the ``target_class`` enum from
    ``.intent/META/enums.json`` (ADR-097 D2). Raises
    ``TargetClassBoundariesError`` on any structural deviation.
    """
    root = (repo_root or resolve_default_repo_path()).resolve()

    valid_classes = _load_target_class_enum(root)
    document = _load_document(root)

    raw_boundaries = document.get("boundaries")
    if not isinstance(raw_boundaries, list) or not raw_boundaries:
        raise TargetClassBoundariesError(
            f"{TARGET_CLASS_BOUNDARIES_REL}: 'boundaries:' must be a non-empty list."
        )

    parsed: list[TargetClassBoundary] = []
    for i, entry in enumerate(raw_boundaries):
        if not isinstance(entry, dict):
            raise TargetClassBoundariesError(
                f"{TARGET_CLASS_BOUNDARIES_REL}: boundaries[{i}] must be a mapping."
            )
        prefix = entry.get("prefix")
        target_class = entry.get("target_class")
        if not isinstance(prefix, str) or not prefix:
            raise TargetClassBoundariesError(
                f"{TARGET_CLASS_BOUNDARIES_REL}: boundaries[{i}].prefix must be a non-empty string."
            )
        if not isinstance(target_class, str) or not target_class:
            raise TargetClassBoundariesError(
                f"{TARGET_CLASS_BOUNDARIES_REL}: boundaries[{i}].target_class must be a non-empty string."
            )
        if target_class not in valid_classes:
            raise TargetClassBoundariesError(
                f"{TARGET_CLASS_BOUNDARIES_REL}: boundaries[{i}].target_class={target_class!r} "
                f"is not in the target_class enum {sorted(valid_classes)}."
            )
        unknown_fields = set(entry.keys()) - {"prefix", "target_class"}
        if unknown_fields:
            raise TargetClassBoundariesError(
                f"{TARGET_CLASS_BOUNDARIES_REL}: boundaries[{i}] has unknown field(s): "
                f"{sorted(unknown_fields)}."
            )
        parsed.append(TargetClassBoundary(prefix=prefix, target_class=target_class))

    default = document.get("default")
    if not isinstance(default, str) or not default:
        raise TargetClassBoundariesError(
            f"{TARGET_CLASS_BOUNDARIES_REL}: 'default:' must be a non-empty string."
        )
    if default not in valid_classes:
        raise TargetClassBoundariesError(
            f"{TARGET_CLASS_BOUNDARIES_REL}: default={default!r} is not in the "
            f"target_class enum {sorted(valid_classes)}."
        )

    return TargetClassBoundaries(boundaries=tuple(parsed), default=default)


# Module-level cache: target-class resolution is a hot path (every write
# call through FileHandler). The boundaries file is read-once-per-process
# per the .intent/ taxonomy pattern; mutations require an ADR-097 D2
# amendment and a process restart to take effect.
_CACHED_BOUNDARIES: TargetClassBoundaries | None = None


# ID: 5e8d2a14-9b73-4f06-a1c8-7d3e9f4b2c85
def resolve_target_class(rel_path: str, repo_root: Path | None = None) -> str:
    """Resolve a repo-relative path to its target_class.

    The path is matched against declared boundaries in order — first
    match wins. The match is prefix-based and path-string-aware: a
    ``var/tmp/foo/src/bar.py`` path matches the ``var/tmp/`` boundary
    BEFORE any ``src/`` boundary, foreclosing the substring bug that
    ADR-097 D2 names as the load-bearing motivation for this dispatch.

    The leading ``./`` is stripped if present (mirrors FileHandler's
    own ``removeprefix("./")`` normalization). No other path resolution
    is performed; callers pass already-normalized repo-relative posix
    paths.
    """
    global _CACHED_BOUNDARIES
    if _CACHED_BOUNDARIES is None:
        _CACHED_BOUNDARIES = load_target_class_boundaries(repo_root)
    boundaries = _CACHED_BOUNDARIES

    normalized = str(rel_path).removeprefix("./").replace("\\", "/")
    for entry in boundaries.boundaries:
        if normalized.startswith(entry.prefix):
            return entry.target_class
    return boundaries.default


# ID: f3a7b1e4-6c25-4d98-8a73-1e9f4b5c2d80
def reset_target_class_cache() -> None:
    """Drop the cached boundaries. Test-only — production should not call this.

    The taxonomy is process-immutable by ADR-097 D2 / ADR-068 pattern;
    cache invalidation is a test-fixture concern, not a runtime control.
    """
    global _CACHED_BOUNDARIES
    _CACHED_BOUNDARIES = None


def _load_document(root: Path) -> dict[str, Any]:
    """Load and minimally validate the top-level boundaries YAML document."""
    path = root / TARGET_CLASS_BOUNDARIES_REL
    if not path.is_file():
        raise TargetClassBoundariesError(
            f"target-class boundaries missing: {TARGET_CLASS_BOUNDARIES_REL}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TargetClassBoundariesError(
            f"cannot read {TARGET_CLASS_BOUNDARIES_REL}: {exc}"
        ) from exc
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TargetClassBoundariesError(
            f"malformed YAML in {TARGET_CLASS_BOUNDARIES_REL}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise TargetClassBoundariesError(
            f"{TARGET_CLASS_BOUNDARIES_REL}: top-level document must be a mapping."
        )
    return document


def _load_target_class_enum(root: Path) -> frozenset[str]:
    """Resolve target_class.enum from .intent/META/enums.json (ADR-097 D2)."""
    path = root / ENUMS_REL
    if not path.is_file():
        raise TargetClassBoundariesError(f"required enum file missing: {ENUMS_REL}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TargetClassBoundariesError(f"cannot read {ENUMS_REL}: {exc}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TargetClassBoundariesError(
            f"malformed JSON in {ENUMS_REL}: {exc}"
        ) from exc
    defs = document.get("definitions")
    if not isinstance(defs, dict):
        raise TargetClassBoundariesError(
            f"{ENUMS_REL}: missing or non-mapping 'definitions' block."
        )
    target_class_def = defs.get("target_class")
    if not isinstance(target_class_def, dict):
        raise TargetClassBoundariesError(
            f"{ENUMS_REL}: missing or non-mapping 'definitions.target_class'."
        )
    enum_values = target_class_def.get("enum")
    if not isinstance(enum_values, list) or not enum_values:
        raise TargetClassBoundariesError(
            f"{ENUMS_REL}: 'definitions.target_class.enum' must be a non-empty list."
        )
    for v in enum_values:
        if not isinstance(v, str):
            raise TargetClassBoundariesError(
                f"{ENUMS_REL}: 'definitions.target_class.enum' contains non-string value {v!r}."
            )
    return frozenset(enum_values)
