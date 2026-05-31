# src/shared/infrastructure/intent/filesystem_operations.py
"""
Filesystem-operation taxonomy loader.

Sole sanctioned reader of ``.intent/taxonomies/filesystem_operations.yaml``
— the canonical call-name → op-class taxonomy declared by ADR-077 §2 and
consumed by the protected-namespace access check.

Fail-closed by design per ADR-068 pattern: any structural deviation raises
``FilesystemOperationTaxonomyError``. The loader never returns an empty
set and never falls back to a permissive default — silent pass-all would
defeat the policy whose authority rests on this vocabulary.

Cross-references ``.intent/META/enums.json`` on every load to resolve the
``fs_audit_op_class`` enum (ADR-080 D3). The op_class value of every entry
is validated against that enum at load time; drift between the YAML and
the enum is a load-time failure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shared.infrastructure.intent.errors import GovernanceError


FILESYSTEM_OPERATIONS_REL = ".intent/taxonomies/filesystem_operations.yaml"
ENUMS_REL = ".intent/META/enums.json"

# src/shared/infrastructure/intent/filesystem_operations.py
#   parents[0] = intent
#   parents[1] = infrastructure
#   parents[2] = shared
#   parents[3] = src
#   parents[4] = repo root
_REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[4]

# Match-mode vocabulary. Closed at code level — extending requires an ADR
# revision and a coordinated loader edit. ADR-077 §2 declares the two
# values; no third match strategy is anticipated.
_VALID_MATCH_MODES = frozenset({"leaf", "qualified"})

# Predicate vocabulary. Closed at code level. ADR-077 §2 names exactly
# one predicate (``write_mode``); growth requires an ADR revision.
_VALID_PREDICATES = frozenset({"write_mode"})

# Required and optional fields per taxonomy entry.
_REQUIRED_ENTRY_FIELDS = frozenset({"op_class", "match"})
_OPTIONAL_ENTRY_FIELDS = frozenset({"predicate"})
_ALL_ENTRY_FIELDS = _REQUIRED_ENTRY_FIELDS | _OPTIONAL_ENTRY_FIELDS

# Required top-level operations sub-blocks (split-structure per the YAML).
_REQUIRED_OPERATION_BLOCKS = frozenset({"pathlib_path", "watched"})


# ID: 4e1aeb6b-4971-4a21-9eed-1c1bcb1a1cdf
class FilesystemOperationTaxonomyError(GovernanceError):
    """Raised when the filesystem-operation taxonomy cannot be loaded fail-closed."""


@dataclass(frozen=True)
# ID: a0babacc-2bbb-4aae-9bdd-90941ec58575
class FsOperationEntry:
    """A single classified filesystem-touching call.

    ``namespace`` is ``pathlib_path`` for the auto-discovered pathlib.Path
    block, or ``watched`` for the curated cross-module block. The
    completeness check uses this discriminator to apply the two halves of
    its discovery contract (introspection for pathlib_path, callable
    resolution for watched).
    """

    name: str
    op_class: str
    match: str
    namespace: str
    predicate: str | None = None


@dataclass(frozen=True)
# ID: b9288eb5-9142-4e45-8867-076063834ad4
class FsOperationTaxonomy:
    """Loaded taxonomy split into its two declared blocks.

    The split mirrors the YAML structure and the two-halves completeness
    contract from ADR-077 §3. ``python_version`` records the interpreter
    version the classifications were authored against; the completeness
    check compares it to runtime ``sys.version_info`` per §5.
    """

    pathlib_path: frozenset[FsOperationEntry]
    watched: frozenset[FsOperationEntry]
    python_version: str

    @property
    # ID: 0ca0721d-2bbf-4a0d-aeda-6c56cc38f988
    def all_entries(self) -> frozenset[FsOperationEntry]:
        """Return every classified entry across both blocks."""
        return self.pathlib_path | self.watched


# ID: 6b5d99f0-0847-4e82-9cff-4047c8125d27
def load_filesystem_operations(
    repo_root: Path | None = None,
) -> FsOperationTaxonomy:
    """Return the declared filesystem-operation taxonomy as a frozen container.

    Reads ``.intent/taxonomies/filesystem_operations.yaml`` and validates
    every entry against ADR-077 §2 and the ``fs_audit_op_class`` enum from
    ``.intent/META/enums.json`` (ADR-080 D3). Raises
    ``FilesystemOperationTaxonomyError`` on any structural deviation.
    """
    root = (repo_root or _REPO_ROOT_DEFAULT).resolve()

    fs_audit_op_classes = _load_fs_audit_op_class_enum(root)
    document = _load_document(root)

    python_version = document.get("python_version")
    if not isinstance(python_version, str) or not python_version.strip():
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: 'python_version' must be a non-empty string "
            f"(ADR-077 §5 determinism anchor)."
        )

    operations_block = document.get("operations")
    if not isinstance(operations_block, dict):
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: missing or non-mapping 'operations:' block."
        )

    actual_blocks = frozenset(operations_block.keys())
    missing_blocks = _REQUIRED_OPERATION_BLOCKS - actual_blocks
    if missing_blocks:
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: 'operations:' missing required "
            f"sub-block(s): {sorted(missing_blocks)}."
        )
    extra_blocks = actual_blocks - _REQUIRED_OPERATION_BLOCKS
    if extra_blocks:
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: 'operations:' has unknown sub-block(s): "
            f"{sorted(extra_blocks)}."
        )

    pathlib_entries = _parse_block(
        block_name="pathlib_path",
        raw=operations_block["pathlib_path"],
        expected_match="leaf",
        fs_audit_op_classes=fs_audit_op_classes,
    )
    watched_entries = _parse_block(
        block_name="watched",
        raw=operations_block["watched"],
        expected_match=None,
        fs_audit_op_classes=fs_audit_op_classes,
    )

    return FsOperationTaxonomy(
        pathlib_path=pathlib_entries,
        watched=watched_entries,
        python_version=python_version.strip(),
    )


def _load_document(root: Path) -> dict[str, Any]:
    """Load and minimally validate the top-level taxonomy YAML document."""
    path = root / FILESYSTEM_OPERATIONS_REL
    if not path.is_file():
        raise FilesystemOperationTaxonomyError(
            f"filesystem-operation taxonomy missing: {FILESYSTEM_OPERATIONS_REL}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FilesystemOperationTaxonomyError(
            f"cannot read {FILESYSTEM_OPERATIONS_REL}: {exc}"
        ) from exc
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise FilesystemOperationTaxonomyError(
            f"malformed YAML in {FILESYSTEM_OPERATIONS_REL}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: top-level document must be a mapping."
        )
    return document


def _load_fs_audit_op_class_enum(root: Path) -> frozenset[str]:
    """Resolve fs_audit_op_class.enum from .intent/META/enums.json (ADR-080 D3)."""
    path = root / ENUMS_REL
    if not path.is_file():
        raise FilesystemOperationTaxonomyError(
            f"required enum file missing: {ENUMS_REL}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FilesystemOperationTaxonomyError(
            f"cannot read {ENUMS_REL}: {exc}"
        ) from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FilesystemOperationTaxonomyError(
            f"malformed JSON in {ENUMS_REL}: {exc}"
        ) from exc

    definitions = document.get("definitions") if isinstance(document, dict) else None
    if not isinstance(definitions, dict):
        raise FilesystemOperationTaxonomyError(
            f"{ENUMS_REL}: missing or non-mapping 'definitions' block."
        )

    enum_def = definitions.get("fs_audit_op_class")
    if not isinstance(enum_def, dict) or not isinstance(enum_def.get("enum"), list):
        raise FilesystemOperationTaxonomyError(
            f"{ENUMS_REL}: missing or malformed 'fs_audit_op_class' enum "
            f"(ADR-080 D3 prerequisite)."
        )
    values = frozenset(str(v) for v in enum_def["enum"])
    if not values:
        raise FilesystemOperationTaxonomyError(
            f"{ENUMS_REL}: 'fs_audit_op_class' enum is empty."
        )
    return values


def _parse_block(
    *,
    block_name: str,
    raw: Any,
    expected_match: str | None,
    fs_audit_op_classes: frozenset[str],
) -> frozenset[FsOperationEntry]:
    """Validate one operations sub-block and assemble its frozenset of entries.

    ``expected_match`` constrains the match mode for entries in this block
    (e.g. pathlib_path requires ``leaf`` per ADR-077 §2). ``None`` permits
    either valid mode — used for the watched block, where leaf entries
    would be theoretically permissible but ADR-077 §2 specifies qualified
    for the module-rooted families that motivate it.
    """
    if not isinstance(raw, dict):
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: '{block_name}:' must be a mapping, "
            f"got {type(raw).__name__}."
        )
    if not raw:
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: '{block_name}:' declares no entries; "
            f"empty taxonomy block is rejected (fail-closed)."
        )

    entries: set[FsOperationEntry] = set()
    for call_name, entry in raw.items():
        entries.add(
            _build_entry(
                block_name=block_name,
                call_name=str(call_name),
                entry=entry,
                expected_match=expected_match,
                fs_audit_op_classes=fs_audit_op_classes,
            )
        )
    return frozenset(entries)


def _build_entry(
    *,
    block_name: str,
    call_name: str,
    entry: Any,
    expected_match: str | None,
    fs_audit_op_classes: frozenset[str],
) -> FsOperationEntry:
    """Assemble and validate one FsOperationEntry from a YAML mapping entry."""
    if not call_name.strip():
        raise FilesystemOperationTaxonomyError(
            f"{FILESYSTEM_OPERATIONS_REL}: '{block_name}:' has an empty call name."
        )
    if not isinstance(entry, dict):
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: entry must be a mapping, "
            f"got {type(entry).__name__}."
        )

    actual_fields = frozenset(entry.keys())
    missing = _REQUIRED_ENTRY_FIELDS - actual_fields
    if missing:
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: missing required field(s): {sorted(missing)}."
        )
    extra = actual_fields - _ALL_ENTRY_FIELDS
    if extra:
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: unknown field(s): {sorted(extra)}."
        )

    op_class = entry["op_class"]
    if not isinstance(op_class, str):
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: 'op_class' must be a string, "
            f"got {type(op_class).__name__}."
        )
    if op_class not in fs_audit_op_classes:
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: op_class '{op_class}' is not in "
            f"fs_audit_op_class.enum {sorted(fs_audit_op_classes)} (ADR-080 D3)."
        )

    match = entry["match"]
    if not isinstance(match, str):
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: 'match' must be a string, "
            f"got {type(match).__name__}."
        )
    if match not in _VALID_MATCH_MODES:
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: match '{match}' is not in "
            f"{sorted(_VALID_MATCH_MODES)} (ADR-077 §2)."
        )
    if expected_match is not None and match != expected_match:
        raise FilesystemOperationTaxonomyError(
            f"{block_name}.{call_name}: match '{match}' violates the '{block_name}' "
            f"block constraint (must be '{expected_match}' per ADR-077 §2)."
        )

    predicate = entry.get("predicate")
    if predicate is not None:
        if not isinstance(predicate, str):
            raise FilesystemOperationTaxonomyError(
                f"{block_name}.{call_name}: 'predicate' must be a string when present, "
                f"got {type(predicate).__name__}."
            )
        if predicate not in _VALID_PREDICATES:
            raise FilesystemOperationTaxonomyError(
                f"{block_name}.{call_name}: predicate '{predicate}' is not in "
                f"{sorted(_VALID_PREDICATES)} (ADR-077 §2)."
            )

    return FsOperationEntry(
        name=call_name,
        op_class=op_class,
        match=match,
        namespace=block_name,
        predicate=predicate,
    )
