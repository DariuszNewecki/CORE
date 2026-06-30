"""Tests for ADR-123 `project onboard --stage` airlock and `project onboard promote`.

Covers:
- _stage_dir_for(): path formula (D1)
- initialize_repository with stage_dir: skips .intent/ existence check; writes to stage (D1)
- promote_staged: refuses missing stage, refuses existing .intent/, copies and cleans up (D2)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(core_root: Path) -> MagicMock:
    ctx = MagicMock()
    ctx.git_service.repo_path = core_root
    ctx.file_handler.ensure_dir = MagicMock()
    return ctx


# ---------------------------------------------------------------------------
# _stage_dir_for
# ---------------------------------------------------------------------------


def test_stage_dir_for_uses_target_basename(tmp_path: Path) -> None:
    from cli.logic.byor import _stage_dir_for

    core_root = tmp_path / "core"
    target = tmp_path / "repos" / "my-project"
    result = _stage_dir_for(core_root, target)
    assert result == core_root / "work" / "staged" / "my-project"


def test_stage_dir_for_resolves_target(tmp_path: Path) -> None:
    from cli.logic.byor import _stage_dir_for

    core_root = tmp_path / "core"
    # Relative path — should resolve against cwd, but basename is the same.
    target_name = "another-repo"
    result = _stage_dir_for(core_root, Path(target_name))
    assert result.name == target_name


# ---------------------------------------------------------------------------
# initialize_repository — stage mode
# ---------------------------------------------------------------------------


async def test_stage_skips_existing_intent_check(tmp_path: Path) -> None:
    """In stage mode, a pre-existing .intent/ on the real target does NOT block."""
    from cli.logic.byor import _stage_dir_for, initialize_repository

    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "target-repo"
    target.mkdir()

    # Plant an existing .intent/ on the real target — in direct mode this would block.
    (target / ".intent").mkdir()

    context = _make_context(core_root)
    stage_dir = _stage_dir_for(core_root, target)

    # Should NOT raise — stage_dir bypasses the existence check.
    await initialize_repository(context=context, path=target, dry_run=False, stage_dir=stage_dir)

    # Staged files landed in work/staged/target-repo/.intent/, not in target/.intent/.
    staged_intent = stage_dir / ".intent"
    assert staged_intent.is_dir()
    staged_files = list(staged_intent.rglob("*"))
    assert any(f.is_file() for f in staged_files), "Expected staged files under work/staged/"


async def test_stage_writes_to_stage_not_target(tmp_path: Path) -> None:
    """Files delivered with --stage land in work/staged/<name>/, not <target>/.intent/."""
    from cli.logic.byor import _stage_dir_for, initialize_repository

    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "my-repo"
    target.mkdir()

    context = _make_context(core_root)
    stage_dir = _stage_dir_for(core_root, target)

    await initialize_repository(context=context, path=target, dry_run=False, stage_dir=stage_dir)

    # Real target has no .intent/.
    assert not (target / ".intent").exists()
    # Stage has .intent/ with content.
    assert (stage_dir / ".intent").is_dir()


async def test_stage_without_write_is_dry_run(tmp_path: Path) -> None:
    """dry_run=True with stage_dir set still does a dry-run (no stage files written)."""
    from cli.logic.byor import _stage_dir_for, initialize_repository

    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "my-repo"
    target.mkdir()

    context = _make_context(core_root)
    stage_dir = _stage_dir_for(core_root, target)

    await initialize_repository(context=context, path=target, dry_run=True, stage_dir=stage_dir)

    # Dry run: no files written anywhere.
    assert not stage_dir.is_dir()
    assert not (target / ".intent").exists()


# ---------------------------------------------------------------------------
# promote_staged
# ---------------------------------------------------------------------------


async def test_promote_refuses_missing_stage(tmp_path: Path) -> None:

    from cli.logic.byor import promote_staged

    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "my-repo"
    target.mkdir()

    context = _make_context(core_root)

    with pytest.raises(SystemExit):
        await promote_staged(context=context, path=target)


async def test_promote_refuses_existing_intent(tmp_path: Path) -> None:
    """Promote refuses when the target already has .intent/ (ADR-111 D3 / ADR-123 D2)."""
    from cli.logic.byor import _stage_dir_for, promote_staged

    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "my-repo"
    target.mkdir()

    # Plant a stage dir.
    stage_intent = _stage_dir_for(core_root, target) / ".intent"
    stage_intent.mkdir(parents=True)
    (stage_intent / "dummy.yaml").write_text("x: 1", encoding="utf-8")

    # Plant an existing .intent/ on the target.
    (target / ".intent").mkdir()

    context = _make_context(core_root)

    with pytest.raises(SystemExit):
        await promote_staged(context=context, path=target)


async def test_promote_copies_to_target_and_cleans_stage(tmp_path: Path) -> None:
    """Promote copies all staged files to the target and removes the stage dir."""
    from cli.logic.byor import _stage_dir_for, promote_staged

    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "my-repo"
    target.mkdir()

    # Create a staged .intent/ with some files.
    stage_dir = _stage_dir_for(core_root, target)
    stage_intent = stage_dir / ".intent"
    (stage_intent / "META").mkdir(parents=True)
    (stage_intent / "META" / "schema.yaml").write_text("kind: test", encoding="utf-8")
    (stage_intent / "META" / "vocab.yaml").write_text("terms: []", encoding="utf-8")

    context = _make_context(core_root)

    await promote_staged(context=context, path=target)

    # Files landed in the target.
    assert (target / ".intent" / "META" / "schema.yaml").is_file()
    assert (target / ".intent" / "META" / "vocab.yaml").is_file()

    # Stage dir was cleaned up.
    assert not stage_dir.exists()


async def test_stage_then_promote_roundtrip(tmp_path: Path) -> None:
    """Full roundtrip: stage machinery floor, then promote it to the target."""
    from cli.logic.byor import _stage_dir_for, initialize_repository, promote_staged

    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "project"
    target.mkdir()

    context = _make_context(core_root)
    stage_dir = _stage_dir_for(core_root, target)

    # Stage.
    await initialize_repository(context=context, path=target, dry_run=False, stage_dir=stage_dir)

    assert (stage_dir / ".intent").is_dir(), "Stage should have .intent/ after staging"
    assert not (target / ".intent").exists(), "Target should be untouched after staging"

    # Promote.
    await promote_staged(context=context, path=target)

    assert (target / ".intent").is_dir(), "Target should have .intent/ after promotion"
    assert not stage_dir.exists(), "Stage dir should be cleaned up after promotion"
