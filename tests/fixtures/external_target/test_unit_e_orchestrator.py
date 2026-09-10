"""Focused tests for Unit E's own support code (staging, fingerprinting,
result shaping) against a real materialized target. Does not run the live
Proposal/worker scenario or provision a database -- that is the live run,
executed once, separately, against real components (see the Unit E final
report).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from materialize import materialize_external_target
from unit_e_orchestrator import (
    _OUTSIDE_FILE,
    _OUTSIDE_MARKER,
    RollbackScenarioResult,
    capture_repo_fingerprint,
    stage_outside_scope_file,
)


@pytest.fixture
def real_target(tmp_path: Path):
    return materialize_external_target(tmp_path / "target")


class TestStageOutsideScopeFile:
    def test_appends_marker_to_outside_file_only(self, real_target) -> None:
        root = real_target.root
        before = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        stage_outside_scope_file(root)
        after = {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }
        changed = {k for k in before if before[k] != after.get(k)}
        assert changed == {_OUTSIDE_FILE}
        assert after[_OUTSIDE_FILE].decode("utf-8").endswith(_OUTSIDE_MARKER)

    def test_stages_without_committing(self, real_target) -> None:
        root = real_target.root
        head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        stage_outside_scope_file(root)
        head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert head_after == head_before

    def test_status_shows_exactly_one_staged_modification(self, real_target) -> None:
        root = real_target.root
        stage_outside_scope_file(root)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert status == [f"M  {_OUTSIDE_FILE}"]

    def test_staged_diff_is_non_empty(self, real_target) -> None:
        root = real_target.root
        stage_outside_scope_file(root)
        diff = subprocess.run(
            ["git", "diff", "--cached", "--", _OUTSIDE_FILE],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert _OUTSIDE_MARKER.strip() in diff

    def test_raises_if_marker_already_present(self, real_target) -> None:
        root = real_target.root
        stage_outside_scope_file(root)
        with pytest.raises(RuntimeError):
            stage_outside_scope_file(root)


class TestCaptureRepoFingerprint:
    def test_contains_required_keys(self, real_target) -> None:
        root = real_target.root
        stage_outside_scope_file(root)
        fp = capture_repo_fingerprint(root)
        assert set(fp.keys()) == {
            "outside_bytes_sha256",
            "staged_diff",
            "index_tree",
            "status_porcelain",
            "tracked_file_hashes",
        }

    def test_is_deterministic_across_two_reads(self, real_target) -> None:
        root = real_target.root
        stage_outside_scope_file(root)
        first = capture_repo_fingerprint(root)
        second = capture_repo_fingerprint(root)
        assert first == second

    def test_changes_when_outside_file_changes_further(self, real_target) -> None:
        root = real_target.root
        stage_outside_scope_file(root)
        before = capture_repo_fingerprint(root)
        (root / _OUTSIDE_FILE).write_text(
            (root / _OUTSIDE_FILE).read_text("utf-8") + "\nx = 1\n", "utf-8"
        )
        subprocess.run(
            ["git", "add", _OUTSIDE_FILE], cwd=root, check=True, capture_output=True
        )
        after = capture_repo_fingerprint(root)
        assert after["outside_bytes_sha256"] != before["outside_bytes_sha256"]
        assert after["staged_diff"] != before["staged_diff"]
        assert after["index_tree"] != before["index_tree"]

    def test_tracked_file_hashes_include_target_and_outside_files(
        self, real_target
    ) -> None:
        root = real_target.root
        stage_outside_scope_file(root)
        fp = capture_repo_fingerprint(root)
        assert "package/example.py" in fp["tracked_file_hashes"]
        assert _OUTSIDE_FILE in fp["tracked_file_hashes"]

    def test_unaffected_by_unrelated_unstaged_edit(self, real_target) -> None:
        # A change to a file NOT staged/tracked-modified must not perturb
        # the outside-file-specific fields (index tree still reflects only
        # the actually staged content).
        root = real_target.root
        stage_outside_scope_file(root)
        before = capture_repo_fingerprint(root)
        (root / "package" / "sub" / "nested.py").write_text("z = 1\n", "utf-8")
        after = capture_repo_fingerprint(root)
        assert after["outside_bytes_sha256"] == before["outside_bytes_sha256"]
        assert after["staged_diff"] == before["staged_diff"]
        assert after["index_tree"] == before["index_tree"]
        # but the unstaged edit IS visible in status and in the tracked-file hash
        assert after["status_porcelain"] != before["status_porcelain"]
        assert (
            after["tracked_file_hashes"]["package/sub/nested.py"]
            != before["tracked_file_hashes"]["package/sub/nested.py"]
        )


class TestRollbackScenarioResultShape:
    def test_to_dict_contains_required_fields(self) -> None:
        result = RollbackScenarioResult(target="/tmp/x", pristine_commit="a" * 40)
        d = result.to_dict()
        required = {
            "target",
            "pristine_commit",
            "violation_commit",
            "proposal_id",
            "lifecycle_states",
            "final_status",
            "final_failure_reason",
            "executed_action_id",
            "native_tests",
            "formatter_check",
            "blackboard_report_present",
            "secret_scan_clean",
            "child_process",
            "checks",
            "blockers",
            "verdict",
            "notes",
        }
        assert required.issubset(d.keys())

    def test_default_verdict_is_fail(self) -> None:
        assert (
            RollbackScenarioResult(target="x", pristine_commit="a").verdict == "FAIL"
        )
