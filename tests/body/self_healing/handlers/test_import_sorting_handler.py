# tests/body/self_healing/handlers/test_import_sorting_handler.py

"""sort_imports_handler runs ruff through subprocess_utils."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from body.self_healing.handlers import import_sorting_handler
from body.self_healing.handlers.import_sorting_handler import sort_imports_handler
from shared.utils.subprocess_utils import SubprocessResult


_UNSORTED = "import sys\nimport os\n"
_SORTED = "import os\nimport sys\n"


def _setup(tmp_path: Path) -> tuple[Path, SimpleNamespace]:
    (tmp_path / "src").mkdir()
    target = tmp_path / "src" / "probe.py"
    target.write_text(_UNSORTED, encoding="utf-8")
    return target, SimpleNamespace(file_path="src/probe.py", message="m")


async def test_dry_run_invokes_ruff_without_fix(tmp_path: Path) -> None:
    target, finding = _setup(tmp_path)
    run = AsyncMock(return_value=SubprocessResult("", "", 0))
    with patch.object(import_sorting_handler, "run_command_async", run):
        result = await sort_imports_handler(
            finding,  # type: ignore[arg-type]
            file_handler=MagicMock(),
            repo_root=tmp_path,
            write=False,
        )

    run.assert_awaited_once_with(
        ["ruff", "check", str(target), "--select", "I", "--exit-zero"]
    )
    assert result.ok
    assert result.changes_made is not None
    assert result.changes_made["dry_run"] is True


async def test_write_rewrites_file_via_file_handler(tmp_path: Path) -> None:
    target, finding = _setup(tmp_path)

    async def fake_ruff(cmd: list[str]) -> SubprocessResult:
        assert cmd[-1] == "--fix"
        target.write_text(_SORTED, encoding="utf-8")
        return SubprocessResult("", "", 0)

    file_handler = MagicMock()
    with patch.object(import_sorting_handler, "run_command_async", fake_ruff):
        result = await sort_imports_handler(
            finding,  # type: ignore[arg-type]
            file_handler=file_handler,
            repo_root=tmp_path,
            write=True,
        )

    assert result.ok
    assert result.changes_made is not None
    assert result.changes_made["imports_changed"] is True
    file_handler.write.assert_called_once_with("src/probe.py", _SORTED)


async def test_missing_ruff_is_reported(tmp_path: Path) -> None:
    _target, finding = _setup(tmp_path)
    run = AsyncMock(side_effect=FileNotFoundError("ruff"))
    with patch.object(import_sorting_handler, "run_command_async", run):
        result = await sort_imports_handler(
            finding,  # type: ignore[arg-type]
            file_handler=MagicMock(),
            repo_root=tmp_path,
            write=False,
        )

    assert not result.ok
    assert result.error_message is not None
    assert result.error_message.startswith("Ruff failed:")
