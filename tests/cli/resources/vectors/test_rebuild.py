# tests/cli/resources/vectors/test_rebuild.py
"""Guard tests for `core-admin vectors rebuild` (#203).

The command is destructive (deletes a Qdrant collection), so the load-bearing
safety property is that an unknown/typo'd collection name never reaches
delete_collection. Full behavioral coverage (delete + chunk_count reset) is an
integration concern against live Qdrant/Postgres; these unit tests pin the
collection-validation guard.
"""

from __future__ import annotations

import pytest
import typer

from cli.resources.vectors.rebuild import _ensure_known_collection


def test_known_collection_passes() -> None:
    # No raise when the collection is one Qdrant currently holds.
    _ensure_known_collection("core-code", ["core-code", "core-specs"])


def test_unknown_collection_refuses() -> None:
    # A typo'd or absent collection must abort before any deletion.
    with pytest.raises(typer.Exit) as exc:
        _ensure_known_collection("core-cdoe", ["core-code", "core-specs"])
    assert exc.value.exit_code == 1


def test_empty_known_set_refuses() -> None:
    with pytest.raises(typer.Exit):
        _ensure_known_collection("core-code", [])
