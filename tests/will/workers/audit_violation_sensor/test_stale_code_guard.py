"""The daemon must not silently audit stale code.

2026-10-12/13: CORE's clone followed a branch nobody merged to any more, so
every audit for a day judged old code. Each cycle now records the commit it
audited, and two consecutive cycles behind the merge branch raise one
blocking finding for the governor.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from shared.infrastructure.git_service import GitService
from will.audit_violation.staleness import (
    STALE_SUBJECT,
    AuditedCommit,
    audited_commit,
    guard_stale_audit,
)
from will.workers.audit_violation_sensor import AuditViolationSensor


def _git(head: str, upstream: str | None, upstream_in_head: bool = False) -> MagicMock:
    git = MagicMock()
    git.get_current_commit.return_value = head
    git.resolve_ref.return_value = upstream
    git.is_ancestor.return_value = upstream_in_head
    return git


def test_audited_commit_states() -> None:
    assert not audited_commit(_git("a", "a"), "main").behind
    assert audited_commit(_git("a", "b"), "main").behind
    assert not audited_commit(_git("b", "a", upstream_in_head=True), "main").behind
    assert not audited_commit(_git("a", None), "main").behind  # never fetched
    git = _git("a", "b")
    audited_commit(git, "main")
    git.resolve_ref.assert_called_once_with("refs/remotes/upstream/main")


def _blackboard(active: set[str]) -> MagicMock:
    bb = MagicMock()
    bb.fetch_active_finding_subjects_by_prefix = AsyncMock(return_value=active)
    bb.adjudicate_indeterminate_findings = AsyncMock()
    return bb


async def test_one_finding_only_after_two_cycles_behind() -> None:
    worker = MagicMock()
    worker.post_observation = AsyncMock()
    behind = AuditedCommit("a", "b")

    await guard_stale_audit(worker, _blackboard(set()), behind, behind_cycles=1)
    worker.post_observation.assert_not_awaited()

    await guard_stale_audit(worker, _blackboard(set()), behind, behind_cycles=2)
    worker.post_observation.assert_awaited_once()
    call = worker.post_observation.await_args.kwargs
    assert call["subject"] == STALE_SUBJECT
    assert call["status"] == "indeterminate"
    assert call["payload"]["severity"] == "block"
    assert call["payload"]["audited_commit"] == "a"

    await guard_stale_audit(worker, _blackboard({STALE_SUBJECT}), behind, 3)
    worker.post_observation.assert_awaited_once()  # never a second one


async def test_current_again_resolves_the_finding() -> None:
    bb = _blackboard({STALE_SUBJECT})
    await guard_stale_audit(MagicMock(), bb, AuditedCommit("b", "b"), 0)
    bb.adjudicate_indeterminate_findings.assert_awaited_once()
    assert (
        bb.adjudicate_indeterminate_findings.await_args.kwargs["subject_prefix"]
        == STALE_SUBJECT
    )


def _sensor(git: MagicMock, bb: MagicMock, tmp_path: Path) -> AuditViolationSensor:
    core_context = MagicMock()
    core_context.git_service = git
    core_context.registry.get_blackboard_service = AsyncMock(return_value=bb)
    core_context.auditor_context.repo_path = tmp_path
    sensor = AuditViolationSensor(
        core_context=core_context,
        declaration_name="audit_violation_sensor",
        rule_namespace="test_ns",
    )
    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = AsyncMock()
    sensor.post_observation = AsyncMock()
    return sensor


async def test_sensor_records_the_audited_commit_and_raises_when_stale(
    tmp_path: Path,
) -> None:
    artifact = MagicMock()
    artifact.content = {"discovery": ["**/*.none"]}  # no files: the short path
    repo = MagicMock()
    repo.get_artifact_type.return_value = artifact
    repo._rule_index = {}
    sensor = _sensor(_git("old", "new"), _blackboard(set()), tmp_path)

    with patch(
        "will.workers.audit_violation_sensor.get_intent_repository", return_value=repo
    ):
        await sensor.run()
        sensor.post_observation.assert_not_awaited()
        await sensor.run()

    payload = sensor.post_report.await_args.kwargs["payload"]
    assert payload["audited_commit"] == "old"
    assert payload["upstream_commit"] == "new"
    assert payload["behind_upstream"] is True
    sensor.post_observation.assert_awaited_once()
    assert sensor.post_observation.await_args.kwargs["subject"] == STALE_SUBJECT


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_resolve_ref_on_a_real_clone(tmp_path: Path) -> None:
    _run(["git", "init", "-q"], tmp_path)
    _run(["git", "config", "user.email", "t@example.com"], tmp_path)
    _run(["git", "config", "user.name", "T"], tmp_path)
    (tmp_path / "f").write_text("x\n")
    _run(["git", "add", "f"], tmp_path)
    _run(["git", "commit", "-qm", "x"], tmp_path)
    head = _run(["git", "rev-parse", "HEAD"], tmp_path)
    _run(["git", "update-ref", "refs/remotes/upstream/main", head], tmp_path)
    git = GitService(tmp_path)
    assert git.resolve_ref("refs/remotes/upstream/main") == head
    assert git.resolve_ref("refs/remotes/upstream/nope") is None
