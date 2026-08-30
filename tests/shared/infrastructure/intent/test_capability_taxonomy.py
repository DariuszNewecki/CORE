# tests/shared/infrastructure/intent/test_capability_taxonomy.py
"""#821 Unit 2: capability_taxonomy.py loader tests.

Mirrors the edge cases already proven for the audit-time counterpart in
tests/mind/logic/engines/test_knowledge_gate__capability_taxonomy_whitelist.py
(missing file, malformed YAML, empty root, family-name-as-capability
rejection) plus this module's own fail-closed contract (non-mapping
document/family/capabilities block).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.capability_taxonomy import (
    CapabilityTaxonomyError,
    load_capability_taxonomy,
)


def _write_taxonomy(tmp_path: Path, content: str) -> Path:
    repo_root = tmp_path
    taxonomy_dir = repo_root / ".intent" / "taxonomies"
    taxonomy_dir.mkdir(parents=True)
    (taxonomy_dir / "capability_taxonomy.yaml").write_text(content, encoding="utf-8")
    return repo_root


# ID: 1a4c8e2f-6b9d-4a3e-8f1c-2d6b9a4e7f1c
def test_load_capability_taxonomy_returns_canonical_ids(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(
        tmp_path,
        """
families:
  reasoning:
    description: Reasoning family
    capabilities:
      reasoning:
        description: General reasoning
      analysis:
        description: Analytical reasoning
  code:
    description: Code family
    capabilities:
      code_generation:
        description: Generate code
""",
    )
    result = load_capability_taxonomy(repo_root)
    assert result == frozenset({"reasoning", "analysis", "code_generation"})


# ID: 2b5d9f3a-7c1e-4b4f-9a2d-3e7c1b5a8f2d
def test_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(CapabilityTaxonomyError, match="missing"):
        load_capability_taxonomy(tmp_path)


# ID: 3c6e0a4b-8d2f-4c5a-b3e1-4f8d2c6b9a3e
def test_malformed_yaml_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, "families: [unclosed")
    with pytest.raises(CapabilityTaxonomyError, match="malformed YAML"):
        load_capability_taxonomy(repo_root)


# ID: 4d7f1b5c-9e3a-4d6b-c4f2-5a9e3d7c0b4f
def test_empty_families_block_fails_closed(tmp_path: Path) -> None:
    """families: {} is a valid mapping with zero families -- fails via the
    empty-capability-set check, not the missing-block check."""
    repo_root = _write_taxonomy(tmp_path, "families: {}\n")
    with pytest.raises(CapabilityTaxonomyError, match="no capability ids declared"):
        load_capability_taxonomy(repo_root)


# ID: 9c3f7b1e-4a8d-4c2f-9e6b-1d5f9a3c7e0b
def test_non_mapping_families_block_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, "families: not_a_mapping\n")
    with pytest.raises(CapabilityTaxonomyError, match="missing or non-mapping"):
        load_capability_taxonomy(repo_root)


# ID: 5e8a2c6d-0f4b-4e7c-d5a3-6b0f4e8d1c5a
def test_no_capabilities_declared_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(
        tmp_path,
        """
families:
  reasoning:
    description: Empty family
    capabilities: {}
""",
    )
    with pytest.raises(CapabilityTaxonomyError, match="no capability ids declared"):
        load_capability_taxonomy(repo_root)


# ID: 6f9b3d7e-1a5c-4f8d-e6b4-7c1a5f9e2d6b
def test_family_name_is_not_treated_as_a_capability(tmp_path: Path) -> None:
    """Only keys under capabilities: are canonical -- family names are not."""
    repo_root = _write_taxonomy(
        tmp_path,
        """
families:
  reasoning:
    description: Reasoning family
    capabilities:
      analysis:
        description: Analytical reasoning
""",
    )
    result = load_capability_taxonomy(repo_root)
    assert "reasoning" not in result
    assert result == frozenset({"analysis"})


# ID: 7a0c4e8f-2b6d-4a9e-f7c5-8d2b6a0f3e7c
def test_non_mapping_document_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(CapabilityTaxonomyError, match="must be a mapping"):
        load_capability_taxonomy(repo_root)


# ID: 8b1d5f9a-3c7e-4b0f-a8d6-9e3c7b1a4f8d
def test_family_not_a_mapping_fails_closed(tmp_path: Path) -> None:
    repo_root = _write_taxonomy(tmp_path, "families:\n  reasoning: not_a_mapping\n")
    with pytest.raises(CapabilityTaxonomyError, match="is not a mapping"):
        load_capability_taxonomy(repo_root)
