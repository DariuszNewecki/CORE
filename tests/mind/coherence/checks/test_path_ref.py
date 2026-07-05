# tests/mind/coherence/checks/test_path_ref.py
"""Unit tests for PathRefCheck (CCC F-02 scope gap).

Constructs a minimal repo tree in tmp_path and verifies the check emits
candidates for broken backtick path references and stays silent for valid ones.
No DB, no LLM, no IntentRepository — the _governance_docs() method is patched
to return the test doc directly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from mind.coherence.checks.path_ref import PathRefCheck


def _run(check: PathRefCheck) -> list:
    return asyncio.get_event_loop().run_until_complete(check.run())


def _make_check(tmp_path: Path, docs: list[Path]) -> PathRefCheck:
    check = PathRefCheck(repo_root=tmp_path)
    with patch.object(PathRefCheck, "_governance_docs", return_value=docs):
        return check, docs


class TestPathRefCheck:
    def test_emits_for_missing_path(self, tmp_path: Path) -> None:
        doc = tmp_path / "test.md"
        doc.write_text("see `.specs/papers/Nonexistent.md` for details")
        check = PathRefCheck(repo_root=tmp_path)
        with patch.object(PathRefCheck, "_governance_docs", return_value=[doc]):
            candidates = _run(check)
        assert len(candidates) == 1
        assert candidates[0].relation == "PATH_REF"
        assert ".specs/papers/Nonexistent.md" in candidates[0].claim

    def test_silent_for_existing_path(self, tmp_path: Path) -> None:
        (tmp_path / ".specs" / "papers").mkdir(parents=True)
        target = tmp_path / ".specs" / "papers" / "Exists.md"
        target.write_text("content")
        doc = tmp_path / "test.md"
        doc.write_text("see `.specs/papers/Exists.md` for details")
        check = PathRefCheck(repo_root=tmp_path)
        with patch.object(PathRefCheck, "_governance_docs", return_value=[doc]):
            candidates = _run(check)
        assert candidates == []

    def test_ignores_non_repo_paths(self, tmp_path: Path) -> None:
        doc = tmp_path / "test.md"
        doc.write_text("see `some/relative/path.md` or `/absolute/path.yaml`")
        check = PathRefCheck(repo_root=tmp_path)
        with patch.object(PathRefCheck, "_governance_docs", return_value=[doc]):
            candidates = _run(check)
        assert candidates == []

    def test_deduplicates_same_ref_within_doc(self, tmp_path: Path) -> None:
        doc = tmp_path / "test.md"
        doc.write_text(
            "`.specs/missing.md` is mentioned here and also `.specs/missing.md` again"
        )
        check = PathRefCheck(repo_root=tmp_path)
        with patch.object(PathRefCheck, "_governance_docs", return_value=[doc]):
            candidates = _run(check)
        assert len(candidates) == 1

    def test_strips_trailing_punctuation(self, tmp_path: Path) -> None:
        doc = tmp_path / "test.md"
        # Trailing colon inside the backtick should not prevent matching
        doc.write_text("see `.intent/phases/missing.yaml`.")
        check = PathRefCheck(repo_root=tmp_path)
        with patch.object(PathRefCheck, "_governance_docs", return_value=[doc]):
            candidates = _run(check)
        assert len(candidates) == 1
        assert ".intent/phases/missing.yaml" in candidates[0].claim
