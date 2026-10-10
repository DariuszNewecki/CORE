from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from body.atomic.sandbox_lifecycle import SandboxLifecycle


# ID: 0b27fb46-884c-4d57-98e7-65d54de333d9
def test_SandboxLifecycle_restore_paths(tmp_path: Path) -> None:
    core_context = MagicMock()
    lifecycle = SandboxLifecycle(core_context)

    scoped_context = MagicMock()
    scoped_context.git_service.repo_path = tmp_path

    created_file = tmp_path / "created.txt"
    created_file.write_text("new content", encoding="utf-8")

    deleted_file = tmp_path / "deleted.txt"

    unchanged_file = tmp_path / "unchanged.txt"
    unchanged_file.write_text("same", encoding="utf-8")

    snapshot = {
        "created.txt": "original content",
        "deleted.txt": "should appear",
        "unchanged.txt": "same",
    }

    lifecycle.restore_paths(scoped_context, snapshot)

    scoped_context.file_handler.write.assert_any_call("created.txt", "original content")
    scoped_context.file_handler.write.assert_any_call("deleted.txt", "should appear")
    scoped_context.file_handler.remove_file.assert_not_called()

    write_calls = scoped_context.file_handler.write.call_args_list
    written_paths = [call.args[0] for call in write_calls]
    assert "unchanged.txt" not in written_paths


# ID: a735e563-7239-491e-981a-1f8199c15bfe
def test_SandboxLifecycle_restore_paths_removes_missing(tmp_path: Path) -> None:
    core_context = MagicMock()
    lifecycle = SandboxLifecycle(core_context)

    scoped_context = MagicMock()
    scoped_context.git_service.repo_path = tmp_path

    present_file = tmp_path / "present.txt"
    present_file.write_text("current", encoding="utf-8")

    snapshot = {
        "present.txt": None,
    }

    lifecycle.restore_paths(scoped_context, snapshot)

    scoped_context.file_handler.remove_file.assert_called_once_with("present.txt")
    scoped_context.file_handler.write.assert_not_called()





# ID: f9195cbe-fa22-4c42-9e4b-a9cf9cc3f116
def test_SandboxLifecycle_checkpoint_paths(tmp_path: Path) -> None:
    core_context = MagicMock()
    lifecycle = SandboxLifecycle(core_context)

    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    (worktree_root / "present.txt").write_text("hello", encoding="utf-8")

    scoped_context = MagicMock()
    scoped_context.git_service.repo_path = worktree_root

    result = lifecycle.checkpoint_paths(scoped_context, ["present.txt", "missing.txt"])

    assert result == {"present.txt": "hello", "missing.txt": None}
