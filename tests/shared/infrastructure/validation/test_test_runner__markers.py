# tests/shared/infrastructure/validation/test_test_runner__markers.py
"""run_tests(markers=...) passes -m to pytest; a fully deselected run passes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from shared.infrastructure.validation.test_runner import run_tests
from shared.utils.subprocess_utils import SubprocessResult


async def _run(tmp_path: Path, returncode: int, **kwargs):
    spawn = AsyncMock(
        return_value=SubprocessResult(stdout="", stderr="", returncode=returncode)
    )
    with (
        patch(
            "shared.infrastructure.validation.test_runner.run_command_async",
            new=spawn,
        ),
        patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ),
    ):
        result = await run_tests(repo_root=tmp_path, target="tests/t.py", **kwargs)
    return result, tuple(spawn.call_args.args[0])


# ID: 2b68228e-6470-4baf-a09e-a2aea8a7cf2d
async def test_markers_are_passed_to_pytest(tmp_path: Path) -> None:
    _, argv = await _run(tmp_path, 0, markers="not integration")
    i = argv.index("-m")
    assert argv[i + 1] == "not integration"


# ID: 21c32d57-210f-4136-84b7-6f26f884de69
async def test_no_markers_no_filter(tmp_path: Path) -> None:
    _, argv = await _run(tmp_path, 0)
    assert "-m" not in argv


# ID: 3c7e9480-3c2b-4ae9-92f2-e6daf2c96480
async def test_everything_deselected_is_a_pass_only_under_markers(
    tmp_path: Path,
) -> None:
    filtered, _ = await _run(tmp_path, 5, markers="not integration")
    unfiltered, _ = await _run(tmp_path, 5)
    assert filtered.ok is True
    assert unfiltered.ok is False
