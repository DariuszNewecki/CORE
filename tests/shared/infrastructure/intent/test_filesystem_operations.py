# tests/shared/infrastructure/intent/test_filesystem_operations.py
"""
Loader tests for ``shared.infrastructure.intent.filesystem_operations``.

Focused on the Phase 1 of #489 / ADR-077 §6 step 3 relaxation: the
pathlib_path block no longer asserts ``expected_match="leaf"`` for every
entry. Per-entry overrides to ``match: qualified`` are now schema-valid
(used for collision-prone leaves like ``replace``, ``rename``, and
``open``). The loader still rejects unknown match modes and missing
required fields — the relaxation is narrow.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from shared.infrastructure.intent.filesystem_operations import (
    FilesystemOperationTaxonomyError,
    load_filesystem_operations,
)


_MINIMAL_ENUMS: dict = {
    "definitions": {
        "fs_audit_op_class": {
            "enum": ["read", "traverse", "parse", "write", "neutral"]
        },
    }
}

_MINIMAL_TAXONOMY_HEADER = (
    'version: "1.0.0"\n'
    "status: active\n"
    "authority: constitutional\n"
    "title: Test fs taxonomy\n"
    'python_version: "3.12"\n'
    "description: minimal test fixture\n"
    "operations:\n"
)


@pytest.fixture
def intent_tree(tmp_path: Path) -> Callable[..., Path]:
    """Build a minimal valid .intent/ tree under tmp_path for loader tests."""

    def _factory(
        *,
        pathlib_block: str | None = None,
        watched_block: str | None = None,
        enums_json: str | None = None,
    ) -> Path:
        (tmp_path / ".intent/META").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".intent/taxonomies").mkdir(parents=True, exist_ok=True)

        (tmp_path / ".intent/META/enums.json").write_text(
            enums_json if enums_json is not None else json.dumps(_MINIMAL_ENUMS)
        )

        default_pathlib = (
            "  pathlib_path:\n"
            "    write_text: { op_class: write, match: leaf }\n"
            "    read_text:  { op_class: read,  match: leaf }\n"
        )
        default_watched = (
            "  watched:\n"
            '    "os.replace": { op_class: write, match: qualified }\n'
        )

        yaml = (
            _MINIMAL_TAXONOMY_HEADER
            + (pathlib_block if pathlib_block is not None else default_pathlib)
            + (watched_block if watched_block is not None else default_watched)
        )
        (tmp_path / ".intent/taxonomies/filesystem_operations.yaml").write_text(yaml)
        return tmp_path

    return _factory


# ---------------------------------------------------------------------------
# #489 Phase 1 relaxation
# ---------------------------------------------------------------------------


def test_pathlib_path_qualified_entries_accepted(
    intent_tree: Callable[..., Path],
) -> None:
    """Phase 1: pathlib_path block accepts per-entry ``match: qualified`` overrides.

    Pre-#489 the loader asserted every pathlib_path entry was ``leaf``;
    the relaxation lets collision-prone leaves (``replace``, ``rename``,
    ``open``) declare ``qualified`` to avoid colliding with str.replace,
    tarfile.open, and similar non-FS attribute names.
    """
    pathlib_block = (
        "  pathlib_path:\n"
        "    write_text: { op_class: write, match: leaf }\n"
        "    replace:    { op_class: write, match: qualified }\n"
        "    rename:     { op_class: write, match: qualified }\n"
        "    open:       { op_class: write, match: qualified, predicate: write_mode }\n"
    )
    root = intent_tree(pathlib_block=pathlib_block)
    taxonomy = load_filesystem_operations(repo_root=root)

    by_name = {e.name: e for e in taxonomy.pathlib_path}
    assert by_name["write_text"].match == "leaf"
    assert by_name["replace"].match == "qualified"
    assert by_name["rename"].match == "qualified"
    assert by_name["open"].match == "qualified"
    assert by_name["open"].predicate == "write_mode"


def test_pathlib_path_invalid_match_mode_still_rejected(
    intent_tree: Callable[..., Path],
) -> None:
    """Relaxation is narrow: unknown match modes remain rejected."""
    pathlib_block = (
        "  pathlib_path:\n"
        "    write_text: { op_class: write, match: nonsense }\n"
    )
    root = intent_tree(pathlib_block=pathlib_block)

    with pytest.raises(FilesystemOperationTaxonomyError, match="match 'nonsense'"):
        load_filesystem_operations(repo_root=root)


def test_pathlib_path_missing_match_field_still_rejected(
    intent_tree: Callable[..., Path],
) -> None:
    """``match`` remains a required per-entry field after the relaxation."""
    pathlib_block = (
        "  pathlib_path:\n"
        "    write_text: { op_class: write }\n"
    )
    root = intent_tree(pathlib_block=pathlib_block)

    with pytest.raises(FilesystemOperationTaxonomyError, match="missing required"):
        load_filesystem_operations(repo_root=root)
