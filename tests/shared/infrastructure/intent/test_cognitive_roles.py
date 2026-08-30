# tests/shared/infrastructure/intent/test_cognitive_roles.py
"""cognitive_roles.py loader tests.

Covers both projections of the shared parse: `load_cognitive_roles`
(role names only -- pre-existing, unchanged behavior after the #821
Unit 2 refactor that extracted the shared `_load_roles_block` helper)
and `load_cognitive_role_capabilities` (role -> required_capabilities,
added for #821 Unit 2's YAML->DB projection).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.cognitive_roles import (
    CognitiveRolesTaxonomyError,
    load_cognitive_role_capabilities,
    load_cognitive_roles,
)


def _write_taxonomy(tmp_path: Path, content: str) -> Path:
    repo_root = tmp_path
    taxonomy_dir = repo_root / ".intent" / "taxonomies"
    taxonomy_dir.mkdir(parents=True)
    (taxonomy_dir / "cognitive_roles.yaml").write_text(content, encoding="utf-8")
    return repo_root


_VALID_DOC = """
roles:
  Architect:
    description: Plans changes.
    required_capabilities:
      - reasoning
      - planning
  Coder:
    description: Writes code.
    required_capabilities:
      - code_generation
  Vectorizer:
    description: Embeds content; declares no capabilities.
"""


# ID: 9c2e6a0f-4b8d-4c1e-b7f5-0a4c8e2f6b9d
def test_load_cognitive_roles_returns_name_set(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, _VALID_DOC)
    assert load_cognitive_roles(repo_root) == frozenset(
        {"Architect", "Coder", "Vectorizer"}
    )


# ID: 0d3f7b1a-5c9e-4d2f-c8a6-1b5d9f3a7c0e
def test_load_cognitive_role_capabilities_maps_role_to_capabilities(
    tmp_path: Path,
) -> None:
    repo_root = _write_taxonomy(tmp_path, _VALID_DOC)
    result = load_cognitive_role_capabilities(repo_root)
    assert result == {
        "Architect": frozenset({"reasoning", "planning"}),
        "Coder": frozenset({"code_generation"}),
        "Vectorizer": frozenset(),
    }


# ID: 1e4a8c2b-6d0f-4e3a-d9b7-2c6e0a4b8d1f
def test_missing_file_fails_closed_for_both_loaders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No repo-relative file and no bundled floor fallback -> fail closed.

    A bundled floor copy of cognitive_roles.yaml legitimately exists
    (src/shared/_machinery_floor/taxonomies/) for wheel installs without
    .intent/, so a plain missing-repo-file case alone doesn't prove the
    fail-closed path -- it must also cover the floor being absent.
    """
    monkeypatch.setattr(
        "shared.infrastructure.intent.cognitive_roles.resolve_floor_path",
        lambda _rel: None,
    )
    with pytest.raises(CognitiveRolesTaxonomyError, match="missing"):
        load_cognitive_roles(tmp_path)
    with pytest.raises(CognitiveRolesTaxonomyError, match="missing"):
        load_cognitive_role_capabilities(tmp_path)


# ID: 2f5b9d3c-7e1a-4f4b-e0c8-3d7f1b5a9e2a
def test_empty_roles_block_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, "roles: {}\n")
    with pytest.raises(CognitiveRolesTaxonomyError, match="declares no roles"):
        load_cognitive_roles(repo_root)
    with pytest.raises(CognitiveRolesTaxonomyError, match="declares no roles"):
        load_cognitive_role_capabilities(repo_root)


# ID: 3a6c0e4d-8f2b-4a5c-f1d9-4e8a2c6b0f3b
def test_role_entry_not_a_mapping_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, "roles:\n  Architect: not_a_mapping\n")
    with pytest.raises(CognitiveRolesTaxonomyError, match="is not a mapping"):
        load_cognitive_role_capabilities(repo_root)


# ID: 4b7d1f5e-9a3c-4b6d-a2e0-5f9b3d7c1a4c
def test_non_list_required_capabilities_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(
        tmp_path,
        "roles:\n  Architect:\n    required_capabilities: not_a_list\n",
    )
    with pytest.raises(CognitiveRolesTaxonomyError, match="non-list"):
        load_cognitive_role_capabilities(repo_root)


# ID: 5c8e2a6f-0b4d-4c7e-b3f1-6a0c4e8d2b5d
def test_malformed_yaml_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, "roles: [unclosed")
    with pytest.raises(CognitiveRolesTaxonomyError, match="malformed YAML"):
        load_cognitive_roles(repo_root)
