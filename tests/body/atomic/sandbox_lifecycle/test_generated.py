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


# ID: 5fb1e344-ffc0-4c00-8aaa-0183488f41bb
def test_SandboxLifecycle_propagate_changes(tmp_path: Path) -> None:
    core_context = MagicMock()
    core_context.git_service.status_porcelain.return_value = ""

    lifecycle = SandboxLifecycle(core_context)

    scoped_git = MagicMock()
    scoped_git.repo_path = tmp_path
    scoped_git.status_porcelain.return_value = "M modified.txt"

    (tmp_path / "modified.txt").write_bytes(b"new content")

    file_handler = MagicMock()
    core_context.file_handler = file_handler

    result = lifecycle.propagate_changes(scoped_git)

    assert result == {"modified.txt"}
    file_handler.write.assert_called_once_with("modified.txt", b"new content")


from unittest.mock import patch


# ID: b06a6d94-85fb-4365-b3ed-2bb981f43b85
def test_build_flow_execution_context() -> None:
    core_context = MagicMock()
    core_context.git_service = MagicMock()

    lifecycle = SandboxLifecycle(core_context)

    scoped_context = MagicMock()
    scoped_git = MagicMock()

    with (
        patch(
            "body.atomic.sandbox_lifecycle._flow_has_sandboxable_step",
            return_value=True,
        ),
        patch.object(
            lifecycle,
            "_make_scoped_context",
            return_value=(scoped_context, scoped_git),
        ) as mock_make_scoped,
    ):
        result_context, result_git = lifecycle.build_flow_execution_context(
            "flow-123", write=True, pre_execution_sha="abc123"
        )

    assert result_context is scoped_context
    assert result_git is scoped_git
    mock_make_scoped.assert_called_once_with("abc123", "flow-123")





# ID: 39271fca-92c0-4b2a-82a9-202e4f0d4f65
def test_SandboxLifecycle_build_execution_context():
    core_context = MagicMock()
    core_context.git_service = MagicMock()

    lifecycle = SandboxLifecycle(core_context)

    definition = MagicMock()
    definition.action_id = "action-123"
    definition.executor = MagicMock()

    metadata = MagicMock()
    metadata.impact = "WRITE_CODE"
    definition.executor._atomic_action_metadata = metadata

    scoped_git = MagicMock()
    scoped_context = MagicMock()

    with patch.object(
        SandboxLifecycle,
        "_make_scoped_context",
        return_value=(scoped_context, scoped_git),
    ) as mock_make_scoped:
        with patch(
            "body.atomic.sandbox_lifecycle._SANDBOXED_IMPACTS",
            frozenset({"WRITE_CODE", "WRITE_METADATA"}),
        ):
            context, result_git = lifecycle.build_execution_context(
                definition=definition,
                write=True,
                pre_execution_sha="abc123sha",
            )

    assert context is scoped_context
    assert result_git is scoped_git
    mock_make_scoped.assert_called_once_with("abc123sha", "action-123")
