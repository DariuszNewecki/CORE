# tests/mind/coherence/test_row2_grounding__inherited_bind.py
"""Tests for the inherited-bind verification added to Row2GroundingCheck (#615).

Covers:
- _extract_supersedes_adr_ids: correctly parses ADR IDs from Supersedes lines
- adr_has_grounding_or_supersedes: detects paper citations and Supersedes
- Row2GroundingCheck.run(): emits ROW2_GROUNDING for broken chains; exempts
  valid chains; still emits for ADRs with no grounding and no supersedes
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from mind.coherence.checks.row2_grounding import (
    Row2GroundingCheck,
    _extract_supersedes_adr_ids,
    adr_has_grounding_or_supersedes,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _adr(
    tmp_path: Path,
    name: str,
    *,
    accepted: bool = True,
    paper: bool = False,
    supersedes: str = "",
) -> Path:
    """Write a minimal fake ADR file and return its path."""
    status_line = "**Status:** Accepted" if accepted else "**Status:** Proposed"
    paper_line = (
        "See `.specs/papers/CORE-Governance-Topology.md` for background."
        if paper
        else ""
    )
    supersedes_line = f"**Supersedes:** {supersedes}" if supersedes else ""
    content = "\n".join(
        filter(None, [status_line, paper_line, supersedes_line, "# Body"])
    )
    path = tmp_path / "decisions" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _fake_intent_type(tmp_path: Path) -> None:
    """Create just enough of the repo structure for Row2GroundingCheck to work."""
    # The checker calls get_intent_repository() to get discovery globs.
    # We bypass that by monkeypatching in the test below.
    pass


# ── _extract_supersedes_adr_ids ───────────────────────────────────────────────


def test_extract_ids_simple() -> None:
    content = "**Supersedes:** ADR-042 (partially)\n"
    assert _extract_supersedes_adr_ids(content) == ["ADR-42"]


def test_extract_ids_multiple_on_one_line() -> None:
    content = "**Supersedes:** ADR-021 D3, ADR-021 D5\n"
    ids = _extract_supersedes_adr_ids(content)
    assert ids == ["ADR-21", "ADR-21"]  # duplicates are fine; broken-chain set handles it


def test_extract_ids_none_returns_empty() -> None:
    assert _extract_supersedes_adr_ids("**Supersedes:** none\n") == []
    assert _extract_supersedes_adr_ids("**Supersedes:** nothing\n") == []


def test_extract_ids_absent_returns_empty() -> None:
    assert _extract_supersedes_adr_ids("# No supersedes line here\n") == []


def test_extract_ids_partial_form() -> None:
    content = "**Supersedes (in part):** ADR-015 D3 write-path prescription\n"
    assert _extract_supersedes_adr_ids(content) == ["ADR-15"]


# ── adr_has_grounding_or_supersedes ──────────────────────────────────────────


def test_has_grounding_paper_citation() -> None:
    content = "See `.specs/papers/CORE-Governance-Topology.md` for rationale.\n"
    assert adr_has_grounding_or_supersedes(content) is True


def test_has_supersedes_line() -> None:
    content = "**Supersedes:** ADR-007 (partially)\n"
    assert adr_has_grounding_or_supersedes(content) is True


def test_has_neither() -> None:
    content = "# Simple ADR\n**Status:** Accepted\nNo grounding mentioned.\n"
    assert adr_has_grounding_or_supersedes(content) is False


# ── Row2GroundingCheck.run() ──────────────────────────────────────────────────


@pytest.fixture()
def decisions(tmp_path: Path) -> Path:
    d = tmp_path / ".specs" / "decisions"
    d.mkdir(parents=True)
    return d


async def _run_check(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> list:
    """Run Row2GroundingCheck with the tmp_path repo root, monkeypatching discovery."""

    class _FakeArtifactType:
        content: ClassVar[dict] = {"discovery": [".specs/decisions/*.md"]}

    class _FakeRepo:
        def get_artifact_type(self, _name: str) -> _FakeArtifactType:
            return _FakeArtifactType()

    import mind.coherence.checks.row2_grounding as module

    monkeypatch.setattr(
        module,
        "get_intent_repository",
        lambda: _FakeRepo(),  # type: ignore[arg-type]
        raising=False,
    )
    # Patch the import inside run() as well
    import shared.infrastructure.intent.intent_repository as ir_module

    monkeypatch.setattr(ir_module, "get_intent_repository", lambda: _FakeRepo())

    check = Row2GroundingCheck(repo_root=tmp_path)
    return await check.run()


@pytest.mark.asyncio
async def test_no_grounding_no_supersedes_emits(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accepted ADR with neither grounding nor supersedes → ROW2_GROUNDING."""
    _adr(tmp_path, "ADR-099-bare", accepted=True, paper=False, supersedes="")
    candidates = await _run_check(tmp_path, decisions, monkeypatch)
    assert any("ADR-099-bare" in c.claim for c in candidates)


@pytest.mark.asyncio
async def test_direct_paper_grounding_exempt(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Accepted ADR with a paper citation → exempt from ROW2_GROUNDING."""
    _adr(tmp_path, "ADR-099-grounded", accepted=True, paper=True)
    candidates = await _run_check(tmp_path, decisions, monkeypatch)
    assert not any("ADR-099" in c.claim for c in candidates)


@pytest.mark.asyncio
async def test_valid_supersedes_chain_exempt(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-B supersedes ADR-A which has a paper citation → chain is valid, no finding."""
    _adr(tmp_path, "ADR-010-grounded", accepted=True, paper=True)
    _adr(tmp_path, "ADR-011-supersedes-010", accepted=True, supersedes="ADR-10")
    candidates = await _run_check(tmp_path, decisions, monkeypatch)
    assert not any("ADR-011" in c.claim for c in candidates)


@pytest.mark.asyncio
async def test_broken_supersedes_chain_emits(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-B supersedes ADR-A but ADR-A has no grounding → broken chain finding."""
    _adr(tmp_path, "ADR-020-no-grounding", accepted=True, paper=False, supersedes="")
    _adr(tmp_path, "ADR-021-supersedes-020", accepted=True, supersedes="ADR-20")
    candidates = await _run_check(tmp_path, decisions, monkeypatch)
    claims = [c.claim for c in candidates]
    assert any("ADR-021-supersedes-020" in c and "broken" in c for c in claims), claims


@pytest.mark.asyncio
async def test_supersedes_predecessor_not_found_emits(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR supersedes a predecessor that doesn't exist → broken bind finding."""
    _adr(tmp_path, "ADR-030-missing-pred", accepted=True, supersedes="ADR-999")
    candidates = await _run_check(tmp_path, decisions, monkeypatch)
    claims = [c.claim for c in candidates]
    assert any("ADR-030" in c and "broken" in c for c in claims), claims


@pytest.mark.asyncio
async def test_proposed_adr_skipped(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proposed (non-accepted) ADR is skipped entirely."""
    _adr(tmp_path, "ADR-040-proposed", accepted=False, paper=False, supersedes="")
    candidates = await _run_check(tmp_path, decisions, monkeypatch)
    assert not any("ADR-040" in c.claim for c in candidates)


@pytest.mark.asyncio
async def test_supersedes_none_no_real_bind(
    tmp_path: Path, decisions: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR with 'Supersedes: none' has no real bind; still fires as missing grounding."""
    content = "**Status:** Accepted\n**Supersedes:** none\n# Body"
    (decisions / "ADR-050-none.md").write_text(content, encoding="utf-8")
    candidates = await _run_check(tmp_path, decisions, monkeypatch)
    # No ADR ID extracted → falls through to basic grounding check
    assert any("ADR-050" in c.claim for c in candidates)
