# src/will/self_healing/symbol_coverage_remediation.py

"""
Symbol-granular coverage remediation orchestrator (ADR-135 D7 retirement, #814).

Replaces EnhancedTestGenerator (retired) as the implementation behind
coverage_runner.py's synchronous generation routes (POST /coverage/generate,
/generate:batch, /tests/interactive). Reuses the exact primitives
TestRemediatorWorker's autonomous Proposal path already relies on
(TestGapEvaluator, TestGenCognitiveDelegate, FlowExecutor, SandboxLifecycle)
but invokes them directly and synchronously — no Proposal object, no DB
persistence, no separate consumer worker. Both are legitimate ways to drive
the same governed primitives (flow.build_test_for_symbol / PromptModelIterativeAgent,
ADR-140 D5/D6); this module is for the synchronous, API/CLI-triggered caller —
a role the retiring EnhancedTestGenerator path filled too.

Requires the #815 fix to SandboxLifecycle (file_service scoped alongside
git_service/file_handler) — without it, this orchestrator would inherit the
same split-brain filesystem defect #815 closed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.sandbox_lifecycle import SandboxLifecycle
from body.evaluators.test_gap_evaluator import TestGapEvaluator
from body.flows.executor import FlowExecutor
from body.flows.result import declared_production
from body.quality.coverage_candidate_selector import select_batch_candidates
from shared.logger import getLogger
from will.agents.test_gen_cognitive_delegate import TestGenCognitiveDelegate


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

_WRITE_FALSE_UNSUPPORTED = (
    "write=false is unsupported: symbol remediation has no dry-run contract "
    "and writes test files unconditionally when untested public symbols exist."
)


# ID: 08b4fdc3-153e-43c6-bb5a-49a0c92f1e79
async def remediate_file_by_symbol(
    context: CoreContext, source_file: str, *, write: bool
) -> dict[str, Any]:
    """Generate tests for every untested public symbol in one file.

    Gap enumeration (TestGapEvaluator) runs against the main tree first —
    it is read-only AST analysis, so this is a pure efficiency choice: files
    with zero gaps skip worktree creation entirely. Every symbol found is
    then generated inside one hermetic worktree shared across the whole
    file (each flow.build_test_for_symbol call appends its symbol to the
    same in-worktree file), with a single propagate_changes() call at the
    end restricted to the union of what each successful flow execution
    declared as its production (ADR-107 D1) — never the full worktree diff.
    A failed symbol's write (build.test_for_symbol can succeed before a
    later required step like test.sandbox_validate fails, and FlowExecutor
    does not roll that back) is explicitly restored to its pre-symbol state
    via _restore_test_file — otherwise a *different*, later-succeeding
    symbol sharing the same path would carry the failed symbol's leftover
    content into the propagate allowlist.

    `status="completed"` means the orchestration reached a controlled
    terminal state, not that every symbol succeeded — per-symbol outcomes
    live in `summary`/`results`. `status` is `"failed"` for a precondition
    that never touched a worktree (write=False, missing source file, gap
    evaluation itself failing) and `"error"` for an infrastructure failure
    (sandbox creation, an uncaught exception mid-flow, propagation conflict)
    — mirrors the batch service's prior status vocabulary so callers that
    already branch on 'failed' vs an unexpected exception keep working.
    """
    if not write:
        return {
            "status": "failed",
            "source_file": source_file,
            "error": _WRITE_FALSE_UNSUPPORTED,
        }
    if context.git_service is None:
        return {
            "status": "error",
            "source_file": source_file,
            "error": "git_service unavailable",
        }

    repo_root = context.git_service.repo_path
    source_path = (repo_root / source_file).resolve()
    if not source_path.exists() or not source_path.is_file():
        return {
            "status": "failed",
            "source_file": source_file,
            "error": f"source_file does not exist: {source_file}",
        }

    scoped_git = None
    try:
        evaluator = TestGapEvaluator(repo_root=repo_root)
        gap_result = await evaluator.execute(source_file=source_file)
        if not gap_result.ok:
            return {
                "status": "failed",
                "source_file": source_file,
                "error": gap_result.data.get("error", "gap evaluation failed"),
            }

        gaps = gap_result.data.get("gaps", [])
        test_file = gap_result.data.get("test_file")
        assert isinstance(test_file, str), (
            "TestGapEvaluator.execute() always sets test_file to a str on ok=True"
        )

        if not gaps:
            return {
                "status": "completed",
                "source_file": source_file,
                "test_file": test_file,
                "summary": {"gaps": 0, "succeeded": 0, "failed": 0, "skipped": 0},
                "results": [],
                "files_produced": [],
            }

        sha = context.git_service.get_current_commit()
        sandbox = SandboxLifecycle(context)
        scoped_context, scoped_git = sandbox.build_flow_execution_context(
            "flow.build_test_for_symbol", write=True, pre_execution_sha=sha
        )
        if scoped_git is None:
            return {
                "status": "error",
                "source_file": source_file,
                "error": (
                    "flow.build_test_for_symbol did not sandbox — "
                    "git_service or pre_execution_sha unavailable"
                ),
            }

        delegate = TestGenCognitiveDelegate(scoped_context)
        flow_executor = FlowExecutor(scoped_context, cognitive_delegate=delegate)
        test_path_in_worktree = scoped_git.repo_path / test_file

        results: list[dict[str, Any]] = []
        declared: set[str] = set()
        for gap in gaps:
            # A required step can fail *after* an earlier required step already
            # wrote — FlowExecutor halts on failure but does not roll back prior
            # steps' writes (build.test_for_symbol writes, then test.sandbox_validate
            # validates; a validation failure leaves the write in place). Since
            # every symbol for this file shares test_path_in_worktree, a failed
            # symbol's leftover write would otherwise get swept into the main tree
            # by a *different* symbol's success (same path, both in the allowlist).
            # Snapshot before and restore after failure so only accepted content
            # ever survives to be a propagation candidate.
            pre_content = (
                test_path_in_worktree.read_text(encoding="utf-8")
                if test_path_in_worktree.exists()
                else None
            )

            flow_result = await flow_executor.execute(
                flow_id="flow.build_test_for_symbol",
                write=True,
                source_file=source_file,
                symbol_name=gap["name"],
                symbol_kind=gap["kind"],
                signature=gap["signature"],
            )
            results.append(
                {
                    "symbol_name": gap["name"],
                    "symbol_kind": gap["kind"],
                    "ok": flow_result.ok,
                    "error": (
                        None if flow_result.ok else _first_failure_reason(flow_result)
                    ),
                }
            )
            if flow_result.ok:
                produced = declared_production(flow_result)
                if produced:
                    declared |= produced
            else:
                _restore_test_file(
                    scoped_context, test_file, test_path_in_worktree, pre_content
                )

        propagated: set[str] = set()
        if declared:
            propagated = sandbox.propagate_changes(scoped_git, only_paths=declared)

        succeeded = sum(1 for r in results if r["ok"])
        return {
            "status": "completed",
            "source_file": source_file,
            "test_file": test_file,
            "summary": {
                "gaps": len(gaps),
                "succeeded": succeeded,
                "failed": len(results) - succeeded,
                "skipped": 0,
            },
            "results": results,
            "files_produced": sorted(propagated),
        }
    except Exception as exc:
        logger.exception(
            "symbol_coverage_remediation: %s crashed mid-remediation", source_file
        )
        return {
            "status": "error",
            "source_file": source_file,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        if scoped_git is not None:
            scoped_git.cleanup()


# ID: 362ef6aa-bf1f-4456-a286-f4ed4a085f45
async def remediate_batch_by_symbol(
    context: CoreContext,
    *,
    write: bool,
    count: int = 5,
    max_complexity: str = "MODERATE",
) -> dict[str, Any]:
    """Generate tests for the lowest-coverage, complexity-eligible files.

    Selects candidates via `select_batch_candidates` (coverage-ranked,
    complexity-filtered — extracted from the retired BatchRemediationService)
    then remediates each file independently: one worktree per file, not one
    for the whole batch, so a single pathological file cannot sink the rest
    of the batch. `status` vocabulary matches the retired
    BatchRemediationService.process_batch()'s: `no_candidates` (nothing below
    the coverage threshold) or `completed` (batch loop ran; per-file outcomes
    are in `results`/`summary`). The prior three-way `no_candidates` /
    `no_matches` split (before vs. after complexity filtering) collapses to
    `no_candidates` here — select_batch_candidates applies both filters in
    one pass; the distinction had no behavioral consequence downstream
    (coverage_runner.py already treats both as an "ok" outcome).
    """
    if not write:
        return {"status": "failed", "error": _WRITE_FALSE_UNSUPPORTED}
    if context.git_service is None:
        return {"status": "error", "error": "git_service unavailable"}

    repo_root = context.git_service.repo_path
    candidates = select_batch_candidates(
        repo_root, count, max_complexity=max_complexity
    )
    if not candidates:
        return {
            "status": "no_candidates",
            "processed": 0,
            "results": [],
            "summary": {"success": 0, "failed": 0, "skipped": 0},
        }

    results: list[dict[str, Any]] = []
    for file_path, original_coverage in candidates:
        rel_path = str(file_path.relative_to(repo_root))
        file_result = await remediate_file_by_symbol(context, rel_path, write=True)
        results.append(
            {"file": rel_path, "original_coverage": original_coverage, **file_result}
        )

    summary = _summarize_batch(results)
    return {
        "status": "completed",
        "processed": len(results),
        "results": results,
        "summary": summary,
    }


# ID: b264777e-924a-4b0c-a4a6-379ccc72dfff
def _first_failure_reason(flow_result: Any) -> str:
    """Human-readable reason from a failed FlowResult's first failing step."""
    failed_steps = flow_result.failed_required_steps or flow_result.failed_steps
    if not failed_steps:
        return "flow failed with no step-level detail"
    step = failed_steps[0]
    data = step.data if isinstance(step.data, dict) else {}
    return str(data.get("error") or data.get("summary") or f"{step.ref_id} failed")


# ID: bcc4c1b8-6fad-46ef-a9dd-62e4a4dff3b4
def _restore_test_file(
    scoped_context: Any,
    test_file: str,
    test_path_in_worktree: Path,
    pre_content: str | None,
) -> None:
    """Undo a failed symbol's write to the shared per-file test target.

    FlowExecutor halts on a required-step failure but does not roll back
    writes already made by earlier required steps in the *same* flow
    execution — build.test_for_symbol writes, then test.sandbox_validate
    (or an optional fix.* step ahead of it) can still leave that write, or
    a further mutation of it, on disk even though the flow's overall
    ok=False. Every symbol for one source file shares test_path_in_worktree,
    so an untouched leftover here would be swept into the main tree by a
    *different*, later-succeeding symbol's propagate_changes — same path,
    both in the declared-production allowlist. Comparing current content
    against the pre-symbol snapshot (rather than assuming a write happened)
    is deliberate: a flow that failed before ever reaching
    build.test_for_symbol (e.g. generate.test_snippet itself) leaves the
    file untouched, and this is then correctly a no-op.
    """
    current = (
        test_path_in_worktree.read_text(encoding="utf-8")
        if test_path_in_worktree.exists()
        else None
    )
    if current == pre_content:
        return
    if pre_content is None:
        scoped_context.file_handler.remove_file(test_file)
    else:
        scoped_context.file_handler.write(test_file, pre_content)


# ID: aff2c2cd-fd8e-4fa7-a3fc-a75ccf81a8d8
def _summarize_batch(results: list[dict[str, Any]]) -> dict[str, int]:
    """Count per-file outcomes: success (every gap generated), skipped (no
    gaps to begin with), failed (any symbol failed, or the file itself
    errored/failed before generation could start)."""
    success = failed = skipped = 0
    for result in results:
        summary = result.get("summary") or {}
        if result.get("status") != "completed":
            failed += 1
        elif summary.get("gaps", 0) == 0:
            skipped += 1
        elif summary.get("failed", 0) == 0:
            success += 1
        else:
            failed += 1
    return {"success": success, "failed": failed, "skipped": skipped}
