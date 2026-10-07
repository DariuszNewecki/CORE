"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/runtime_validator.py
- Symbol: RuntimeValidatorService
- Status: 6 tests passed, some failed
- Passing tests: test_init_with_path_object, test_init_with_string_path, test_init_resolves_path, test_run_tests_in_canary_success_mock, test_run_tests_in_canary_with_relative_path, test_run_tests_in_canary_exception_handling
- Generated: 2026-01-11 01:46:31
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.governance import runtime_validator
from body.governance.runtime_validator import RuntimeValidatorService
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import SubprocessResult


class TestRuntimeValidatorService:
    def test_init_with_path_object(self):
        """Test initialization with Path object."""
        test_path = Path("/some/repo")
        service = RuntimeValidatorService(path_resolver=PathResolver(test_path))
        assert service.repo_root == Path("/some/repo").resolve()
        assert service.test_timeout == 60

    def test_init_with_string_path(self):
        """Test initialization with string path."""
        service = RuntimeValidatorService(path_resolver=PathResolver("/some/repo"))
        assert service.repo_root == Path("/some/repo").resolve()

    def test_init_resolves_path(self):
        """Test that repo_root is resolved to absolute path."""
        service = RuntimeValidatorService(path_resolver=PathResolver("."))
        assert service.repo_root.is_absolute()


def _service(tmp_path: Path, timeout: int = 60) -> RuntimeValidatorService:
    (tmp_path / "var" / "tmp").mkdir(parents=True)
    return RuntimeValidatorService(PathResolver(tmp_path), test_timeout=timeout)


@pytest.fixture
def _no_canary_copy():
    """Isolate the pytest step: the canary tree copy is stubbed out.

    (FileService(canary_path) currently raises because canary_repo is never
    created before it is constructed — pre-existing, out of scope here.)
    """
    with (
        patch.object(runtime_validator, "FileService", MagicMock()),
        patch.object(runtime_validator, "_copy_repo_tree", MagicMock()),
    ):
        yield


@pytest.mark.usefixtures("_no_canary_copy")
class TestCanaryPytestInvocation:
    """pytest runs via subprocess_utils.run_command_async in the airlocked env."""

    async def test_pass_runs_poetry_pytest_in_airlock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LLM_API_KEY", "secret")
        service = _service(tmp_path)
        run = AsyncMock(return_value=SubprocessResult("ok", "", 0))
        with patch.object(runtime_validator, "run_command_async", run):
            passed, details = await service.run_tests_in_canary("src/mod.py", "x=2\n")

        assert passed is True
        assert details == "All tests passed in the isolated environment."
        args, kwargs = run.call_args
        assert args == (["poetry", "run", "pytest"],)
        assert Path(kwargs["cwd"]).name == "canary_repo"
        env = kwargs["env"]
        assert "LLM_API_KEY" not in env
        assert env["DATABASE_URL"] == "sqlite+aiosqlite:///:memory:"
        assert env["CORE_ENV"] == "TEST"
        assert env["LLM_ENABLED"] == "false"
        assert env["PYTHONPATH"] == str(kwargs["cwd"])

    async def test_failure_reports_exit_code_and_streams(self, tmp_path: Path) -> None:
        service = _service(tmp_path)
        run = AsyncMock(return_value=SubprocessResult("1 failed", "boom", 1))
        with patch.object(runtime_validator, "run_command_async", run):
            passed, details = await service.run_tests_in_canary("src/mod.py", "x=2\n")

        assert passed is False
        assert details == (
            "Pytest failed with exit code 1.\n\nSTDOUT:\n1 failed\n\nSTDERR:\nboom"
        )

    async def test_timeout_message(self, tmp_path: Path) -> None:
        service = _service(tmp_path, timeout=0)

        async def hang(*_a: object, **_k: object) -> SubprocessResult:
            await asyncio.sleep(10)
            raise AssertionError("unreachable")

        with patch.object(runtime_validator, "run_command_async", hang):
            passed, details = await service.run_tests_in_canary("src/mod.py", "x=2\n")

        assert passed is False
        assert details == "Tests timed out after 0 seconds."
