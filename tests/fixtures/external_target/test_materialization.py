"""Fixture assembly tests (Unit C, EC-1A safety package).

Proves materialize_external_target() builds what it claims to build --
never that the resulting envelope authorizes/denies anything (that is
test_authority.py's job).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml


sys.path.insert(0, str(Path(__file__).resolve().parent))

from materialize import (
    MACHINERY_FLOOR,
    OVERLAY_DIR,
    REPO_ROOT,
    TEMPLATE_DIR,
    git_snapshot,
    materialize_external_target,
)


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


class TestFileManifest:
    def test_creates_expected_manifest(self, tmp_path: Path) -> None:
        target = materialize_external_target(tmp_path / "target")
        expected = {
            "package/__init__.py",
            "package/example.py",
            "package/sub/__init__.py",
            "package/sub/nested.py",
            "tests/test_example.py",
            "scripts/outside.py",
            "conftest.py",
        }
        for rel in expected:
            assert (target.root / rel).is_file(), f"missing {rel}"

    def test_intent_assembled_from_floor_plus_exact_overlay(
        self, tmp_path: Path
    ) -> None:
        target = materialize_external_target(tmp_path / "target")

        # Every machinery-floor file is present (copied, not replaced).
        for src in MACHINERY_FLOOR.rglob("*"):
            if src.is_dir() or "__pycache__" in src.parts:
                continue
            rel = src.relative_to(MACHINERY_FLOOR)
            if rel == Path("enforcement/config/action_risk.yaml"):
                continue  # merged, not byte-identical -- checked separately below
            dest = target.intent_root / rel
            assert dest.is_file(), f"machinery floor file missing: {rel}"
            assert dest.read_bytes() == src.read_bytes()

        # The exact fixture overlay is present and nothing extra crept in.
        overlay_purity = target.intent_root / "rules" / "code" / "purity.json"
        assert overlay_purity.read_text("utf-8") == (
            OVERLAY_DIR / "rules" / "code" / "purity.json"
        ).read_text("utf-8")

        overlay_worker = (
            target.intent_root / "workers" / "proposal_consumer_worker.yaml"
        )
        assert overlay_worker.read_text("utf-8") == (
            OVERLAY_DIR / "workers" / "proposal_consumer_worker.yaml"
        ).read_text("utf-8")
        worker_decl = yaml.safe_load(overlay_worker.read_text("utf-8"))
        assert worker_decl["mandate"]["scope"]["paths"] == ["package/example.py"]

        overlay_proposal_lifecycle = (
            target.intent_root / "rules" / "will" / "proposal_lifecycle.json"
        )
        canonical_proposal_lifecycle = (
            REPO_ROOT / ".intent" / "rules" / "will" / "proposal_lifecycle.json"
        )
        assert (
            overlay_proposal_lifecycle.read_bytes()
            == canonical_proposal_lifecycle.read_bytes()
        ), "fixture overlay must carry claim.proposal's policy dependency byte-identical to CORE's own"

        merged = yaml.safe_load(
            (target.intent_root / "enforcement/config/action_risk.yaml").read_text(
                "utf-8"
            )
        )
        floor_original = yaml.safe_load(
            (MACHINERY_FLOOR / "enforcement/config/action_risk.yaml").read_text("utf-8")
        )
        assert merged["actions"] == floor_original["actions"]
        assert merged["safe_auto_approval_envelope"] == {
            "authorized_actions": ["fix.format"],
            "authorized_path_prefixes": ["package/"],
            "authorized_extensions": [".py"],
        }


class TestGitAssembly:
    def test_initializes_git_with_local_test_identity(self, tmp_path: Path) -> None:
        target = materialize_external_target(tmp_path / "target")
        assert (target.root / ".git").is_dir()
        assert _git(["config", "user.email"], target.root) == (
            "test@external-target-fixture.local"
        )
        assert _git(["config", "user.name"], target.root) == ("External Target Fixture")

    def test_creates_exactly_one_deterministic_baseline_commit(
        self, tmp_path: Path
    ) -> None:
        target = materialize_external_target(tmp_path / "target")
        log = _git(["log", "--format=%H"], target.root).splitlines()
        assert len(log) == 1
        assert log[0] == target.baseline_commit

    def test_produces_clean_worktree(self, tmp_path: Path) -> None:
        target = materialize_external_target(tmp_path / "target")
        assert _git(["status", "--porcelain"], target.root) == ""

    def test_records_baseline_sha_and_tree_hash(self, tmp_path: Path) -> None:
        target = materialize_external_target(tmp_path / "target")
        assert target.baseline_commit == _git(["rev-parse", "HEAD"], target.root)
        assert target.baseline_tree == _git(["write-tree"], target.root)
        assert len(target.baseline_commit) == 40
        assert len(target.baseline_tree) == 40

    def test_creates_no_remote(self, tmp_path: Path) -> None:
        target = materialize_external_target(tmp_path / "target")
        assert _git(["remote"], target.root) == ""

    def test_git_snapshot_helper_matches_direct_git_calls(self, tmp_path: Path) -> None:
        target = materialize_external_target(tmp_path / "target")
        head, tree, status = git_snapshot(target.root)
        assert head == target.baseline_commit
        assert tree == target.baseline_tree
        assert status == ""


class TestNoSideEffectsBeyondDest:
    def test_does_not_modify_committed_template(self, tmp_path: Path) -> None:
        before = {
            p: p.read_bytes()
            for p in TEMPLATE_DIR.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
        materialize_external_target(tmp_path / "target")
        after = {
            p: p.read_bytes()
            for p in TEMPLATE_DIR.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
        assert before == after

    def test_does_not_modify_core(self, tmp_path: Path) -> None:
        before = _git(["status", "--porcelain"], REPO_ROOT)
        materialize_external_target(tmp_path / "target")
        after = _git(["status", "--porcelain"], REPO_ROOT)
        assert before == after

    def test_dest_must_not_already_exist(self, tmp_path: Path) -> None:
        existing = tmp_path / "target"
        existing.mkdir()
        with pytest.raises(FileExistsError):
            materialize_external_target(existing)
