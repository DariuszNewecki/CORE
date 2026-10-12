# src/will/test_generation/sandbox.py

"""
Pytest Sandbox Runner - runs generated tests in the sandbox runner.

Purpose:
- Execute a generated test against the repository as it would be with the
  LimbWorkspace's uncommitted files (the 'Future Truth') applied.
- Return per-test results.

ADR-132 D10.10 (M2): the test runs in the sandbox runner, never as a pytest
subprocess of the services account. The workspace's files and the test are
laid over the copy of the repository (SandboxRequest.overlay); nothing is
written into the tree, and the services' environment is not passed on (the
old runner copied os.environ into the child).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from body.sandbox.repo_tests import run_in_sandbox
from body.services.file_service import FileService
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.config_service import ConfigService
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

logger = getLogger(__name__)

_CFG = load_operational_config().testing


@dataclass(frozen=True)
# ID: b3ecf72b-a9bf-4480-88f5-2f79f5ed1ddf
class SandboxResult:
    passed: bool  # Overall: True if ALL tests passed
    error: str = ""
    passed_tests: list[str] | None = None
    failed_tests: list[str] | None = None
    total_tests: int = 0

    def __post_init__(self):
        # Ensure lists are never None
        if self.passed_tests is None:
            object.__setattr__(self, "passed_tests", [])
        if self.failed_tests is None:
            object.__setattr__(self, "failed_tests", [])


# ID: 485df4ee-97b7-4685-a57b-4a470ce544c7
class PytestSandboxRunner:
    """Run generated tests via pytest with isolation, timeout, and Workspace Materialization."""

    def __init__(
        self,
        file_handler: FileService,
        repo_root: str,
        config_service: ConfigService | None = None,
    ):
        self._fh = file_handler
        self._repo_root = Path(repo_root)
        self.config_service = config_service

    # ID: 49f91d78-3218-411d-b5f4-9cb3207853b4
    async def run(
        self,
        code: str,
        symbol_name: str,
        timeout_seconds: int = _CFG.sandbox_timeout_sec,
        workspace: LimbWorkspace | None = None,
    ) -> SandboxResult:
        """
        Run the generated test *code* in the sandbox runner (ADR-132 D10.10).

        The repository is copied as it is, with the workspace's uncommitted
        files (the "future truth") laid over it and the test added at the
        top level; nothing is written into the tree. The sandbox's own
        environment applies: the services' environment is never passed on.
        """
        safe_name = re.sub(r"\W", "_", symbol_name) or "generated"
        test_rel = f"test_{safe_name}_sandbox.py"
        overlay: list[tuple[str, bytes]] = []
        if workspace:
            for rel_path, content in workspace.get_crate_content().items():
                overlay.append((rel_path, content.encode("utf-8")))
        overlay.append((test_rel, code.encode("utf-8")))

        try:
            result = await run_in_sandbox(
                self._repo_root,
                [test_rel],
                timeout_sec=timeout_seconds,
                overlay=overlay,
            )
        except Exception as e:
            return SandboxResult(passed=False, error=str(e))

        if result.status == "timeout":
            return SandboxResult(
                passed=False, error=f"Execution timeout ({timeout_seconds}s)."
            )
        passed_tests = [_test_name(n) for n in result.passed_ids]
        failed_tests = [_test_name(n) for n in result.failed_ids]
        output = "\n".join(s for s in (result.stdout, result.stderr) if s)
        return SandboxResult(
            passed=result.ok,
            error="" if result.ok else (output or f"{result.status}: {result.reason}"),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            total_tests=len(passed_tests) + len(failed_tests),
        )


def _test_name(nodeid: str) -> str:
    """``tests/x.py::TestA::test_b[1]`` -> ``test_b`` (the function name the
    callers match generated tests by)."""
    return nodeid.split("::")[-1].split("[", 1)[0]
