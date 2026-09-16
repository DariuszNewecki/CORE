# tests/body/analyzers/test_target_reconnaissance_analyzer.py

"""Tests for TargetReconnaissanceAnalyzer — PARSE-phase target comprehension (#895 U1)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from body.analyzers.target_reconnaissance_analyzer import TargetReconnaissanceAnalyzer
from shared.component_primitive import ComponentPhase
from shared.models.refusal_result import RefusalResult


@dataclass(frozen=True)
class _StubTypeRef:
    """Stands in for IntentRepository's ArtifactTypeRef."""

    id: str
    content: dict[str, Any]


class _StubRepository:
    """Registry stub: serves fixed discovery globs without touching .intent/."""

    def __init__(self, types: dict[str, list[str]]) -> None:
        self._types = types
        self.initialize_calls = 0

    def initialize(self) -> None:
        self.initialize_calls += 1

    def list_artifact_types(self) -> list[_StubTypeRef]:
        return [
            _StubTypeRef(id=type_id, content={"discovery": globs})
            for type_id, globs in sorted(self._types.items())
        ]


class _BrokenRepository:
    """Registry stub that cannot load — exercises the unavailable-topic path."""

    def initialize(self) -> None:
        raise RuntimeError("registry unreadable")

    def list_artifact_types(self) -> list[_StubTypeRef]:  # pragma: no cover
        raise AssertionError("must not be reached after initialize() fails")


@pytest.fixture()
def target_repo(tmp_path: Path) -> Path:
    """A small target: two governed-looking files, one stray, one cached artifact."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# guide\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("loose\n", encoding="utf-8")

    cache = tmp_path / ".mypy_cache" / "3.12"
    cache.mkdir(parents=True)
    (cache / "cached.json").write_text("{}\n", encoding="utf-8")
    return tmp_path


def _analyzer(types: dict[str, list[str]]) -> TargetReconnaissanceAnalyzer:
    return TargetReconnaissanceAnalyzer(intent_repository=_StubRepository(types))


@pytest.mark.asyncio
async def test_reports_parse_phase_and_succeeds(target_repo: Path) -> None:
    result = await _analyzer({"python": ["src/**/*.py"]}).execute(repo_path=target_repo)

    assert result.ok is True
    assert result.phase is ComponentPhase.PARSE
    assert result.component_id == "target_reconnaissance_analyzer"


@pytest.mark.asyncio
async def test_refuses_a_non_directory_target(tmp_path: Path) -> None:
    lone_file = tmp_path / "not-a-dir.txt"
    lone_file.write_text("x\n", encoding="utf-8")

    result = await _analyzer({}).execute(repo_path=lone_file)

    assert isinstance(result, RefusalResult)
    assert result.ok is False
    assert "readable target directory" in result.reason
    assert result.data["boundary"] == "bound target root"
    assert result.refusal_type == "boundary"


@pytest.mark.asyncio
async def test_excludes_derived_cache_directories(target_repo: Path) -> None:
    """A tool cache is not target content and must not inflate the counts."""
    result = await _analyzer({}).execute(repo_path=target_repo)

    assert result.data["recon_raw"]["file_count"] == 3
    assert ".mypy_cache" not in result.data["recon_text"]


@pytest.mark.asyncio
async def test_layout_prefixes_are_directories_not_filenames(target_repo: Path) -> None:
    """Regression: including the filename made every shallow file its own prefix."""
    layout = (await _analyzer({}).execute(repo_path=target_repo)).data["recon_raw"][
        "layout"
    ]

    assert layout == {".": 1, "docs": 1, "src": 1}
    assert not any(key.endswith(".py") or key.endswith(".md") for key in layout)


@pytest.mark.asyncio
async def test_classifies_through_registry_globs(target_repo: Path) -> None:
    result = await _analyzer(
        {"python": ["src/**/*.py"], "doc": ["docs/**/*.md"]}
    ).execute(repo_path=target_repo)

    present = result.data["recon_raw"]["artifact_types_present"]
    assert present == {"doc": 1, "python": 1}
    assert result.data["recon_raw"]["unclassified_count"] == 1
    assert result.data["recon_raw"]["unclassified_suffixes"] == {".txt": 1}


@pytest.mark.asyncio
async def test_absent_type_is_recorded_as_an_explicit_absence(
    target_repo: Path,
) -> None:
    """'No match' must be stated, not left as a silent zero."""
    result = await _analyzer(
        {"python": ["src/**/*.py"], "infra": ["infra/**/*.sql"]}
    ).execute(repo_path=target_repo)

    topics = {item["topic"]: item["reason"] for item in result.data["unavailable"]}
    assert "artifact_type:infra" in topics
    assert "no file in the target matches" in topics["artifact_type:infra"]
    assert "artifact_type:python" not in topics


@pytest.mark.asyncio
async def test_type_without_discovery_globs_is_undeterminable(
    target_repo: Path,
) -> None:
    """A type declaring no globs cannot be found by discovery — say so."""
    result = await _analyzer({"document_corpus": []}).execute(repo_path=target_repo)

    topics = {item["topic"]: item["reason"] for item in result.data["unavailable"]}
    assert "declares no discovery globs" in topics["artifact_type:document_corpus"]


@pytest.mark.asyncio
async def test_unreadable_registry_is_reported_not_silently_empty(
    target_repo: Path,
) -> None:
    """An unreadable registry and an empty one are different facts."""
    analyzer = TargetReconnaissanceAnalyzer(intent_repository=_BrokenRepository())

    result = await analyzer.execute(repo_path=target_repo)

    assert result.ok is True
    topics = {item["topic"]: item["reason"] for item in result.data["unavailable"]}
    assert "registry could not be loaded" in topics["artifact_type_registry"]


@pytest.mark.asyncio
async def test_report_is_deterministic_across_runs(target_repo: Path) -> None:
    """Same target, same report — the digest is only meaningful if this holds."""
    types = {"python": ["src/**/*.py"], "doc": ["docs/**/*.md"]}

    first = await _analyzer(types).execute(repo_path=target_repo)
    second = await _analyzer(types).execute(repo_path=target_repo)

    assert first.data["recon_text"] == second.data["recon_text"]
    assert first.data["recon_digest"] == second.data["recon_digest"]


@pytest.mark.asyncio
async def test_digest_is_a_full_sha256_of_the_report(target_repo: Path) -> None:
    """Trial evidence: the digest must be the whole hash, not a prefix of it."""
    result = await _analyzer({"python": ["src/**/*.py"]}).execute(repo_path=target_repo)

    digest = result.data["recon_digest"]
    expected = hashlib.sha256(result.data["recon_text"].encode("utf-8")).hexdigest()
    assert digest == expected
    assert len(digest) == 64
