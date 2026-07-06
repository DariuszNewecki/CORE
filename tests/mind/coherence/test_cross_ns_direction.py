# tests/mind/coherence/test_cross_ns_direction.py
"""Unit tests for CrossNsDirectionCheck (ADR-144 D4, topology §3.4 row 14).

Tests construct a minimal file tree in tmp_path rather than reading the live
repo, so they are hermetic and fast. The manifest is written as a real YAML
file; ADR/paper files are written as plain text matching the structural
patterns the check looks for.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mind.coherence.checks.base import CheckSkipped
from mind.coherence.checks.cross_ns_direction import (
    CrossNsDirectionCheck,
    _extract_project_path_refs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_manifest(root: Path, entries: list[dict]) -> None:
    manifest_dir = root / ".intent" / "governance"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    data = {"classifications": entries}
    (manifest_dir / "namespace_manifest.yaml").write_text(
        yaml.dump(data), encoding="utf-8"
    )


def _fw_adr(root: Path, name: str, body: str, *, accepted: bool = True) -> Path:
    d = root / ".specs" / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    status_line = "**Status:** Accepted" if accepted else "**Status:** Draft"
    path = d / name
    path.write_text(f"{status_line}\n\n{body}", encoding="utf-8")
    return path


def _fw_paper(root: Path, name: str, body: str) -> Path:
    d = root / ".specs" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CheckSkipped cases
# ---------------------------------------------------------------------------


# ID: cb7c6695-85a6-447d-8140-679d09db436b
async def test_skips_when_manifest_absent(tmp_path: Path) -> None:
    """No manifest → CheckSkipped with 'namespace_manifest_absent'."""
    check = CrossNsDirectionCheck(tmp_path)
    with pytest.raises(CheckSkipped, match="namespace_manifest_absent"):
        await check.run()


# ID: 515a2c82-bd4b-42ae-bbfb-1311f361ca3f
async def test_skips_when_manifest_empty(tmp_path: Path) -> None:
    """Empty classifications list → CheckSkipped with 'namespace_manifest_empty'."""
    _write_manifest(tmp_path, [])
    check = CrossNsDirectionCheck(tmp_path)
    with pytest.raises(CheckSkipped, match="namespace_manifest_empty"):
        await check.run()


# ---------------------------------------------------------------------------
# Clean cases (no candidates)
# ---------------------------------------------------------------------------


# ID: e1a2b3c4-d5e6-4f70-8192-a3b4c5d6e7f8
async def test_no_candidates_when_framework_adr_has_no_cross_ref(tmp_path: Path) -> None:
    """Framework ADR with no project-path references → empty result."""
    _write_manifest(tmp_path, [
        {"path": ".specs/decisions/ADR-001-foundation.md", "governance_namespace": "framework"},
        {"path": ".specs/decisions/ADR-200-project-thing.md", "governance_namespace": "project::core"},
    ])
    _fw_adr(tmp_path, "ADR-001-foundation.md",
            "This ADR establishes the foundation.\n\nSee `.specs/papers/CORE-BYOR.md`.")
    # framework paper is not in project set so no violation
    check = CrossNsDirectionCheck(tmp_path)
    result = await check.run()
    assert result == []


# ID: f2a3b4c5-d6e7-4081-9203-b4c5d6e7f809
async def test_no_candidates_when_project_adr_cites_framework(tmp_path: Path) -> None:
    """Project::core ADR citing a framework path is fine — not scanned (correct direction)."""
    _write_manifest(tmp_path, [
        {"path": ".specs/papers/CORE-BYOR.md", "governance_namespace": "framework"},
        {"path": ".specs/decisions/ADR-200-project.md", "governance_namespace": "project::core"},
    ])
    # project ADR cites framework paper — editorial and permitted, not scanned
    check = CrossNsDirectionCheck(tmp_path)
    result = await check.run()
    assert result == []


# ID: a3b4c5d6-e7f8-4192-0304-c5d6e7f80910
async def test_no_candidates_when_no_project_paths(tmp_path: Path) -> None:
    """All paths are framework → nothing to detect, empty result."""
    _write_manifest(tmp_path, [
        {"path": ".specs/decisions/ADR-001-foundation.md", "governance_namespace": "framework"},
        {"path": ".specs/papers/CORE-BYOR.md", "governance_namespace": "framework"},
    ])
    _fw_adr(tmp_path, "ADR-001-foundation.md",
            "See `.specs/papers/CORE-BYOR.md` for the BYOR contract.")
    check = CrossNsDirectionCheck(tmp_path)
    result = await check.run()
    assert result == []


# ID: b4c5d6e7-f809-4203-1415-d6e7f8091011
async def test_draft_adr_not_scanned(tmp_path: Path) -> None:
    """Draft framework ADR with cross-ns reference is not scanned (speculative content)."""
    _write_manifest(tmp_path, [
        {"path": ".specs/decisions/ADR-001-draft.md", "governance_namespace": "framework"},
        {"path": ".specs/decisions/ADR-200-project.md", "governance_namespace": "project::core"},
    ])
    _fw_adr(tmp_path, "ADR-001-draft.md",
            "Draft cross-ref: `.specs/decisions/ADR-200-project.md`",
            accepted=False)
    check = CrossNsDirectionCheck(tmp_path)
    result = await check.run()
    assert result == []


# ---------------------------------------------------------------------------
# Violation cases
# ---------------------------------------------------------------------------


# ID: c5d6e7f8-0910-4314-1516-e7f809101112
async def test_framework_adr_citing_project_path_emits_candidate(tmp_path: Path) -> None:
    """Accepted framework ADR with a project-path reference → one CROSS_NS_DIRECTION candidate."""
    _write_manifest(tmp_path, [
        {"path": ".specs/decisions/ADR-001-foundation.md", "governance_namespace": "framework"},
        {"path": ".specs/decisions/ADR-200-core-specific.md", "governance_namespace": "project::core"},
    ])
    _fw_adr(tmp_path, "ADR-001-foundation.md",
            "Closes: `.specs/decisions/ADR-200-core-specific.md` for background.")
    check = CrossNsDirectionCheck(tmp_path)
    result = await check.run()
    assert len(result) == 1
    c = result[0]
    assert c.relation == "CROSS_NS_DIRECTION"
    assert ".specs/decisions/ADR-001-foundation.md" in c.documents
    assert ".specs/decisions/ADR-200-core-specific.md" in c.documents
    assert "project-namespace" in c.claim


# ID: d6e7f809-1011-4415-1617-f80910111213
async def test_framework_paper_citing_project_path_emits_candidate(tmp_path: Path) -> None:
    """Framework paper (no status check) with a project-path reference → candidate."""
    _write_manifest(tmp_path, [
        {"path": ".specs/papers/CORE-Framework.md", "governance_namespace": "framework"},
        {"path": ".intent/workers/audit_sensor_purity.yaml", "governance_namespace": "project::core"},
    ])
    _fw_paper(tmp_path, "CORE-Framework.md",
              "The purity sensor is at `.intent/workers/audit_sensor_purity.yaml`.")
    check = CrossNsDirectionCheck(tmp_path)
    result = await check.run()
    assert len(result) == 1
    assert ".intent/workers/audit_sensor_purity.yaml" in result[0].documents


# ID: e7f80910-1112-4516-1718-091011121314
async def test_multiple_project_refs_in_one_file_emit_multiple_candidates(
    tmp_path: Path,
) -> None:
    """Each distinct project-path reference in a framework artifact emits one candidate."""
    _write_manifest(tmp_path, [
        {"path": ".specs/decisions/ADR-001-foundation.md", "governance_namespace": "framework"},
        {"path": ".specs/decisions/ADR-200-project-a.md", "governance_namespace": "project::core"},
        {"path": ".specs/decisions/ADR-201-project-b.md", "governance_namespace": "project::core"},
    ])
    _fw_adr(
        tmp_path,
        "ADR-001-foundation.md",
        "See `.specs/decisions/ADR-200-project-a.md` and "
        "`.specs/decisions/ADR-201-project-b.md`.",
    )
    check = CrossNsDirectionCheck(tmp_path)
    result = await check.run()
    assert len(result) == 2
    refs = {doc for c in result for doc in c.documents if "ADR-200" in doc or "ADR-201" in doc}
    assert ".specs/decisions/ADR-200-project-a.md" in refs
    assert ".specs/decisions/ADR-201-project-b.md" in refs


# ---------------------------------------------------------------------------
# _extract_project_path_refs unit tests
# ---------------------------------------------------------------------------


# ID: f8091011-1213-4617-1819-101112131415
def test_extract_strips_trailing_punctuation() -> None:
    """Trailing `.`, `,`, `)` are stripped from matched path strings."""
    project_paths = {".specs/decisions/ADR-200-proj.md"}
    content = "See `.specs/decisions/ADR-200-proj.md`. Also (`.specs/decisions/ADR-200-proj.md`)."
    result = _extract_project_path_refs(content, project_paths)
    assert result == [".specs/decisions/ADR-200-proj.md"]


# ID: 09101112-1314-4718-1920-111213141516
def test_extract_deduplicates_repeated_refs() -> None:
    """Same path appearing multiple times is returned only once."""
    project_paths = {".intent/workers/my_worker.yaml"}
    content = (
        "`.intent/workers/my_worker.yaml` and again `.intent/workers/my_worker.yaml`"
    )
    result = _extract_project_path_refs(content, project_paths)
    assert result == [".intent/workers/my_worker.yaml"]


# ID: 10111213-1415-4819-2021-121314151617
def test_extract_ignores_non_project_paths() -> None:
    """Paths that are not in the project_paths set are not returned."""
    project_paths = {".specs/decisions/ADR-200-proj.md"}
    content = "See `.specs/papers/CORE-BYOR.md` for the framework contract."
    result = _extract_project_path_refs(content, project_paths)
    assert result == []
