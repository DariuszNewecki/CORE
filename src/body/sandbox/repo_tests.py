# src/body/sandbox/repo_tests.py
"""
The one way CORE runs the repository's tests (ADR-132 D10.10, M2).

Every validation that runs pytest on repository code (test.execute,
test.sandbox_validate, test.candidate_validate, the assisted actions) comes
here, and here the job goes to the sandbox runner (``run_repo_code``), never
to a pytest subprocess of the services account. The mode comes from
``CORE_SANDBOX_MODE`` (``service`` under the release runtime, ``local`` in a
development checkout, where the result says ``isolation: local``).

Fail closed (lessons register L1): a job that did not run is reported
``not_run`` and is never ok. That includes a marker filter that deselects
every test, which the old runner counted as a pass (pytest exit 5), and,
in service mode, a run whose integration tests the sandbox excluded
(``completeness: partial``).

CONSTITUTIONAL ALIGNMENT:
- Body: executes through the sandbox client; evidence is written through
  FileHandler and the action-results table, as before.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.sandbox.client import SandboxRequest, run_repo_code
from body.sandbox.models import SandboxResult
from body.sandbox.snapshot import SKIPPED_NAMES, is_refused_name
from shared.action_types import ActionImpact, ActionResult
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.law_roots import intent_root_for, specs_root_for
from shared.infrastructure.repo_code import CollectOutcome, register_test_collector
from shared.logger import getLogger


if TYPE_CHECKING:
    from body.infrastructure.storage.file_handler import FileHandler

logger = getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 300
# Top-level entries never copied: runtime output, build output, git and the
# venv. Secrets (.env*, .secrets) and caches are dropped by name as well.
EXCLUDED_TOP: frozenset[str] = frozenset(
    {"var", "reports", "work", "dist", "htmlcov", "node_modules", ".git", ".venv"}
)
MODE_ENV = "CORE_SANDBOX_MODE"
DEFAULT_MODE = "local"


# ID: fb3761ae-cab0-40f6-b0d6-2d2aebedea94
def sandbox_mode() -> str:
    """The configured sandbox mode; anything unknown is passed through, and
    run_repo_code reports it as not run rather than guessing."""
    return os.environ.get(MODE_ENV, DEFAULT_MODE).strip() or DEFAULT_MODE


# ID: e9d5a6db-f084-4e78-b419-4930a5ace281
async def run_tests(
    suppress_logging: bool = True,
    target: str | None = None,
    action_id: str = "test.execute",
    repo_root: Path | None = None,
    file_handler: FileHandler | None = None,
    extra_targets: Sequence[str] = (),
    markers: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    overlay: Sequence[tuple[str, bytes]] = (),
) -> ActionResult:
    """Run pytest on the repository in the sandbox; one canonical ActionResult.

    ``target`` (and ``extra_targets``, run after it in the same job) are
    repo-relative paths or node ids; without ``target`` the whole ``tests/``
    tree runs. ``repo_root`` is the tree to snapshot (a flow's worktree under
    ADR-106); it defaults to CORE's bound repository. ``markers`` is a pytest
    ``-m`` expression. ``overlay`` files (repo-relative path, bytes) are
    added to the sandbox copy only; a target may name one of them.
    """
    start = time.perf_counter()
    if not suppress_logging:
        logger.info("Running repository tests in the sandbox")

    result = await run_in_sandbox(
        repo_root,
        (target, *extra_targets) if target else ("tests",),
        markers=markers,
        timeout_sec=timeout_sec,
        overlay=overlay,
    )

    data = _result_data(result)
    action_result = ActionResult(
        action_id=action_id,
        ok=result.ok,
        data=data,
        duration_sec=time.perf_counter() - start,
        impact=ActionImpact.READ_ONLY,
        suggestions=[] if result.ok else ["Run 'pytest --lf' to retry failed tests."],
    )

    _log_test_result_to_file(data, file_handler)
    _store_failure_artifact(data, file_handler)
    await _persist_result_to_db(action_result)

    if not suppress_logging:
        logger.info("Test run complete: %s", data["summary"])
    return action_result


# ID: 25ba8f87-287d-44de-982c-12171a33846d
async def run_in_sandbox(
    tree: Path | None,
    targets: Sequence[str],
    *,
    markers: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    overlay: Sequence[tuple[str, bytes]] = (),
    collect_only: bool = False,
    coverage: bool = False,
) -> SandboxResult:
    """Run the pytest *targets* of *tree* (default: CORE's bound repository)
    in the sandbox, with *overlay* files added; the raw SandboxResult.

    The copy is written to the bound repository's inbox whatever *tree* is:
    the sandbox service reads only that inbox, so a flow worktree's own
    var/tmp would never be seen.
    """
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    bound = Path(BootstrapRegistry.get_repo_path())
    tree = Path(tree) if tree is not None else bound
    law = tuple(
        root for root in (intent_root_for(tree), specs_root_for(tree)) if root.is_dir()
    )
    return await run_repo_code(
        SandboxRequest(
            tree=tree,
            targets=tuple(targets),
            timeout_sec=timeout_sec,
            markers=markers,
            include=repo_include(tree),
            law=law,
            overlay=tuple(overlay),
            collect_only=collect_only,
            coverage=coverage,
        ),
        repo_root=bound,
        mode=sandbox_mode(),
    )


# ID: f5cedfa0-7194-4b0f-962d-4dbd299fe17c
def repo_include(tree: Path) -> tuple[str, ...]:
    """What of *tree* the sandbox copies: every top-level entry the tests may
    read (src/, tests/, infra/, docs/, pyproject.toml, ...) except runtime
    and build output, secrets and caches; plus the tracked parts of var/."""
    try:
        names = sorted(os.listdir(tree))
    except OSError:
        return ()
    top = tuple(
        name
        for name in names
        if name not in EXCLUDED_TOP
        and name not in SKIPPED_NAMES
        and not name.startswith(".coverage")
        and not is_refused_name(name)
    )
    return top + _tracked_var(tree)


def _tracked_var(tree: Path) -> tuple[str, ...]:
    """The tracked parts of var/ the tests read (prompts, knowledge, mind and
    var/core); var/ itself is runtime output and stays out."""
    from shared.path_resolver import PathResolver

    pr = PathResolver(tree)
    dirs = (pr.prompts_dir, pr.knowledge_dir, pr.mind_dir, pr.var_dir / "core")
    rels = sorted({d.relative_to(tree).as_posix() for d in dirs})
    # A directory already copied whole carries its subdirectories.
    return tuple(r for r in rels if not any(r.startswith(o + "/") for o in rels))


def _result_data(result: SandboxResult) -> dict[str, Any]:
    summary = _summarize(result.stdout) if result.stdout else ""
    if result.status in ("not_run", "error", "timeout") or not summary:
        summary = (
            f"{result.status}: {result.reason}" if result.reason else result.status
        )
    if result.status == "passed" and result.completeness != "full":
        summary = f"{summary} (partial: {result.reason or 'some tests were excluded'})"
    return {
        "exit_code": result.exit_code if result.exit_code is not None else -1,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "summary": summary,
        "error": None if result.ok else summary,
        "status": result.status,
        "completeness": result.completeness,
        "isolation": result.isolation,
        "counts": dict(result.counts),
        "excluded": list(result.excluded),
        "snapshot_sha256": result.snapshot_sha256,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _summarize(output: str) -> str:
    """pytest's final summary line ("3 passed, 1 failed in 0.2s")."""
    for line in reversed(output.strip().splitlines()):
        if any(word in line for word in ("passed", "failed", "error", "skipped")):
            return line.strip()
    return ""


async def _persist_result_to_db(result: ActionResult) -> None:
    """Writes the result to the core.action_results table."""
    from shared.models.action_result import ActionResult as ActionResultModel

    try:
        async with get_session() as session:
            session.add(
                ActionResultModel(
                    action_type="test_execution",
                    ok=result.ok,
                    error_message=result.data.get("error") if not result.ok else None,
                    action_metadata={
                        "summary": result.data.get("summary"),
                        "exit_code": result.data.get("exit_code"),
                        "status": result.data.get("status"),
                        "isolation": result.data.get("isolation"),
                        "timestamp": result.data.get("timestamp"),
                    },
                    agent_id="test_runner_infra",
                    duration_ms=int(result.duration_sec * 1000),
                )
            )
            await session.commit()
    except Exception as e:
        logger.warning("Failed to persist test result to DB: %s", e)


def _log_test_result_to_file(
    data: dict[str, Any], file_handler: FileHandler | None
) -> None:
    if file_handler is None:
        return
    try:
        from shared.path_resolver import PathResolver

        pr = PathResolver(file_handler.repo_path)
        rel = str((pr.logs_dir / "tests.jsonl").relative_to(pr.repo_root))
        file_handler.write_runtime_text(
            rel, json.dumps(data, ensure_ascii=False) + "\n"
        )
    except Exception as e:
        logger.debug("Test file logging skipped: %s", e)


def _store_failure_artifact(
    data: dict[str, Any], file_handler: FileHandler | None
) -> None:
    if file_handler is None:
        return
    try:
        from shared.path_resolver import PathResolver

        pr = PathResolver(file_handler.repo_path)
        rel = str((pr.reports_dir / "test_failures.json").relative_to(pr.repo_root))
        if data.get("status") != "passed":
            file_handler.write_runtime_json(rel, data)
        else:
            file_handler.remove_file(rel)
    except Exception as e:
        logger.debug("Test failure artifact update skipped: %s", e)


# ID: 914304b6-cd8e-492f-a745-5e56de33f373
async def collect_tests(tree: Path, timeout_sec: int) -> CollectOutcome:
    """Collect (do not run) the whole tests/ tree of *tree* in the sandbox."""
    result = await run_in_sandbox(
        tree, ["tests"], timeout_sec=timeout_sec, collect_only=True
    )
    output = "\n".join(s for s in (result.stdout, result.stderr) if s)
    return CollectOutcome(status=result.status, output=output, reason=result.reason)


# Mind's workflow gate reaches the collector only through this seam.
register_test_collector(collect_tests)
