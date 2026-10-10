"""CCC triage carries forward (ADR-067 note 2026-10-10, proposal 0012).

Before: every run re-raised every dismissed candidate, so triage repeated
without end. Now an identical candidate (same check, documents, claim) on
documents unchanged since the dismissal is not raised again — and is counted.
"""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from body.services.coherence_service import CoherenceService
from cli.logic.coherence_coverage import check_class_coverage, coverage_lines
from mind.coherence.checks.base import CoherenceCandidate
from shared.infrastructure.git_service import GitService


def _git(cwd: Path, *args: str, when: str | None = None) -> None:
    env = dict(os.environ)
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


# ID: 0093d6da-7ca6-40d1-817d-b1e54501a659
def test_changed_since_reads_commits_and_the_working_tree(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.invalid")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "doc.md").write_text("v1\n")
    _git(tmp_path, "add", "doc.md")
    _git(tmp_path, "commit", "-q", "-m", "v1", when="2026-10-01T10:00:00+00:00")
    git = GitService(tmp_path)

    assert git.changed_since("doc.md", datetime(2026, 10, 5, tzinfo=UTC)) is False
    assert git.changed_since("doc.md", datetime(2026, 9, 30, tzinfo=UTC)) is True
    (tmp_path / "doc.md").write_text("v2, uncommitted\n")
    assert git.changed_since("doc.md", datetime(2026, 10, 5, tzinfo=UTC)) is True


def _service(dismissed_at: object) -> CoherenceService:
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = dismissed_at
    session.execute = AsyncMock(return_value=result)
    return CoherenceService(session)


# ID: ff7b98ce-91f2-4a32-9443-a5e84f1ad8d4
async def test_dismissal_holds_only_while_documents_are_unchanged() -> None:
    when = datetime(2026, 10, 10, tzinfo=UTC)
    git = MagicMock()
    with patch("shared.infrastructure.git_service.GitService", return_value=git):
        git.changed_since.return_value = False
        assert await _service(when).dismissed_and_unchanged(
            "PATH_REF", ["a.md"], "c", "."
        )
        git.changed_since.return_value = True
        assert not await _service(when).dismissed_and_unchanged(
            "PATH_REF", ["a.md"], "c", "."
        )
    assert not await _service(None).dismissed_and_unchanged(
        "PATH_REF", ["a.md"], "c", "."
    )


# ID: e49ca60c-f92f-449d-8e5f-d69703cd4905
async def test_checker_counts_carried_forward_and_raises_the_rest() -> None:
    from mind.coherence.checker import CoherenceChecker

    service = AsyncMock()
    service.dismissed_and_unchanged = AsyncMock(side_effect=[True, False])
    checker = CoherenceChecker(
        cognitive_service=MagicMock(),
        coherence_service=service,
        repo_root=Path("var/tmp"),
        claims_service=None,
    )
    two = [
        CoherenceCandidate(
            relation="PATH_REF", documents=["a.md"], claim="old", rationale="r"
        ),
        CoherenceCandidate(
            relation="PATH_REF", documents=["b.md"], claim="new", rationale="r"
        ),
    ]
    none = AsyncMock(return_value=[])
    others = [
        "dispatch_parity.DispatchParityCheck",
        "row2_grounding.Row2GroundingCheck",
        "row3_citation.Row3CitationCheck",
        "row4_naming.Row4NamingCheck",
        "vocabulary.VocabularyCheck",
        "specgap.SpecGapCheck",
        "intent_binding.IntentBindingCheck",
        "cross_ns_direction.CrossNsDirectionCheck",
    ]
    patches = [patch(f"mind.coherence.checks.{p}.run", new=none) for p in others]
    patches += [
        patch(
            "mind.coherence.checks.path_ref.PathRefCheck.run",
            new=AsyncMock(return_value=two),
        ),
        patch(
            "shared.infrastructure.intent.intent_repository.get_intent_repository",
            return_value=MagicMock(),
        ),
        patch(
            "shared.governance.coherence_harvester.NormativeMarkerRegister.from_intent",
            return_value=MagicMock(),
        ),
    ]
    for p in patches:
        p.start()
    try:
        status = await checker._dispatch_checks(run_id="run-1")
    finally:
        for p in patches:
            p.stop()

    assert status["PATH_REF"] == {"status": "ok", "emitted": 1, "carried_forward": 1}
    service.add_candidate.assert_awaited_once()
    assert service.add_candidate.await_args.kwargs["claim"] == "new"

    manifest = [
        {"domain": "_meta", "type": "check_classes_run", "check_status": status}
    ]
    assert any(
        "1 candidate(s) carried forward" in line
        for line in coverage_lines(check_class_coverage(manifest))
    )
