# tests/body/cli/commands/test_fix_code_style__fix_headers_internal.py

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cli.commands.fix.code_style import fix_headers_internal
from shared.action_types import ActionResult


class _FakeActionExecutor:
    def __init__(self, context):
        self._repo_root = context.git_service.repo_path

    async def execute(
        self, action_id: str, write: bool = False, **params
    ) -> ActionResult:
        if action_id == "file.edit":
            rel_path = params["file_path"]
            code = params["code"]
            if write:
                (self._repo_root / rel_path).write_text(code, encoding="utf-8")
            return ActionResult(
                action_id="file.edit",
                ok=True,
                data={"file_path": rel_path, "written": write},
            )

        if action_id == "sync.db":
            return ActionResult(action_id="sync.db", ok=True, data={"written": write})

        return ActionResult(
            action_id=action_id, ok=False, data={"error": "unsupported"}
        )


def _make_context(repo_root: Path):
    return SimpleNamespace(git_service=SimpleNamespace(repo_path=repo_root))


@pytest.mark.asyncio
async def test_fix_headers_replaces_wrong_header(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "body.self_healing.header_service.ActionExecutor", _FakeActionExecutor
    )

    file_path = tmp_path / "src" / "will" / "test_generation" / "validation.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("# src/features/test.py\nprint('ok')\n", encoding="utf-8")

    result = await fix_headers_internal(_make_context(tmp_path), write=True)

    assert result.ok
    assert result.data["total_files_scanned"] == 1
    assert result.data["files_changed"] == 1
    assert result.data["files_unchanged"] == 0
    assert result.data["files_created"] == 0
    assert result.data["changed_file_paths"] == [
        "src/will/test_generation/validation.py"
    ]
    assert (
        file_path.read_text(encoding="utf-8")
        == "# src/will/test_generation/validation.py\nprint('ok')\n"
    )


@pytest.mark.asyncio
async def test_fix_headers_inserts_missing_header(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "body.self_healing.header_service.ActionExecutor", _FakeActionExecutor
    )

    file_path = tmp_path / "src" / "will" / "test_generation" / "sandbox.py"
    file_path.parent.mkdir(parents=True)
    original = "print('hello')\n"
    file_path.write_text(original, encoding="utf-8")

    result = await fix_headers_internal(_make_context(tmp_path), write=True)

    assert result.ok
    assert result.data["files_changed"] == 1
    assert result.data["files_created"] == 0
    assert file_path.read_text(encoding="utf-8") == (
        "# src/will/test_generation/sandbox.py\n" + original
    )


@pytest.mark.asyncio
async def test_fix_headers_keeps_correct_header_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "body.self_healing.header_service.ActionExecutor", _FakeActionExecutor
    )

    file_path = tmp_path / "src" / "will" / "test_generation" / "strategy_link.py"
    file_path.parent.mkdir(parents=True)
    content = "# src/will/test_generation/strategy_link.py\nVALUE = 1\n"
    file_path.write_text(content, encoding="utf-8")

    result = await fix_headers_internal(_make_context(tmp_path), write=True)

    assert result.ok
    assert result.data["files_changed"] == 0
    assert result.data["files_unchanged"] == 1
    assert result.data["changed_file_paths"] == []
    assert file_path.read_text(encoding="utf-8") == content


@pytest.mark.asyncio
async def test_fix_headers_does_not_touch_non_src_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "body.self_healing.header_service.ActionExecutor", _FakeActionExecutor
    )

    src_file = tmp_path / "src" / "will" / "test_generation" / "test_extractor.py"
    src_file.parent.mkdir(parents=True)
    src_content = "# src/will/test_generation/test_extractor.py\nX = 1\n"
    src_file.write_text(src_content, encoding="utf-8")

    outside_file = tmp_path / "scripts" / "tool.py"
    outside_file.parent.mkdir(parents=True)
    outside_content = "print('outside')\n"
    outside_file.write_text(outside_content, encoding="utf-8")

    result = await fix_headers_internal(_make_context(tmp_path), write=True)

    assert result.ok
    assert result.data["total_files_scanned"] == 1
    assert result.data["files_changed"] == 0
    assert outside_file.read_text(encoding="utf-8") == outside_content


@pytest.mark.asyncio
async def test_fix_headers_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "body.self_healing.header_service.ActionExecutor", _FakeActionExecutor
    )

    file_path = tmp_path / "src" / "will" / "test_generation" / "result_aggregator.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("", encoding="utf-8")

    first = await fix_headers_internal(_make_context(tmp_path), write=True)
    second = await fix_headers_internal(_make_context(tmp_path), write=True)

    assert first.ok
    assert first.data["files_changed"] == 1
    assert first.data["files_created"] == 1
    assert second.ok
    assert second.data["files_changed"] == 0
    assert second.data["files_created"] == 0
    assert file_path.read_text(encoding="utf-8") == (
        "# src/will/test_generation/result_aggregator.py\n"
    )
