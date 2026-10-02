# tests/shared/infrastructure/validation/test_test_runner__extra_targets.py
"""run_tests(extra_targets=...) runs further paths after target, in order."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from shared.infrastructure.validation.test_runner import run_tests


async def _argv(tmp_path: Path, **kwargs) -> tuple:
    process = MagicMock()
    process.communicate = AsyncMock(return_value=(b"1 passed", b""))
    process.returncode = 0
    spawn = AsyncMock(return_value=process)
    with (
        patch(
            "shared.infrastructure.validation.test_runner.asyncio.create_subprocess_exec",
            new=spawn,
        ),
        patch(
            "shared.infrastructure.validation.test_runner._persist_result_to_db",
            new=AsyncMock(),
        ),
    ):
        await run_tests(repo_root=tmp_path, **kwargs)
    return spawn.call_args.args


# ID: 2e987a1d-7c6d-436b-b0c9-1d2ce8e26eb0
async def test_extra_targets_follow_target_in_order(tmp_path: Path) -> None:
    argv = await _argv(
        tmp_path,
        target="var/tmp/c/test_generated.py",
        extra_targets=["tests/b.py", "tests/a.py"],
    )

    assert argv[1:4] == (
        str(tmp_path / "var/tmp/c/test_generated.py"),
        str(tmp_path / "tests/b.py"),
        str(tmp_path / "tests/a.py"),
    )


# ID: 479715b3-6cd1-43e7-ba62-4d1bda3ac0bd
async def test_extra_targets_ignored_without_target(tmp_path: Path) -> None:
    argv = await _argv(tmp_path, extra_targets=["tests/b.py"])

    assert argv[1] == str(tmp_path / "tests")
    assert str(tmp_path / "tests/b.py") not in argv
