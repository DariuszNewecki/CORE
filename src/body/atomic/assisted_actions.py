# src/body/atomic/assisted_actions.py

"""Atomic actions for the Assisted Remediation Lane (ADR-109).

This module hosts ``assisted.validate_diff`` — the safety gate (issue #654)
that decides whether an externally-produced (agent-authored) multi-file diff
is allowed to reach the governor's approval queue.

The gate NEVER touches the main tree. It stands up a hermetic worktree at HEAD
(`GitService.create_worktree`, ADR-071 D2.2), applies the candidate patch
*there*, runs the validation suite against the worktree, reports a per-check
verdict, and discards the worktree. The real application to ``main`` only
happens later, on governor approval, through the existing proposal-execution
path (ADR-101 D2). The verdict is the auto-firing oracle ADR-109 §Mechanism 4
requires: it fires regardless of what the authoring agent claims.

Constitutional note (governance.dangerous_execution_primitives): this module
shells out to ``git apply`` and ``ruff`` against the hermetic worktree. This is
the designated Body validation sanctuary — the same posture as the pytest
subprocess in ``shared.infrastructure.validation.test_runner`` — and runs only
against the throwaway worktree, never the main tree.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


def _git(
    worktree: Path, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a git command scoped to *worktree* (validation sanctuary)."""
    # git, fixed argv, run against the throwaway worktree only (Body sanctuary)
    return subprocess.run(
        ["git", "-C", str(worktree), *args],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def _ruff_ok(worktree: Path, files: list[str]) -> bool:
    """Run ruff against *files* in the worktree (sync; Body sanctuary)."""
    proc = subprocess.run(
        ["ruff", "check", *files],
        cwd=str(worktree),
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


@register_action(
    action_id="assisted.validate_diff",
    description=(
        "Validate an agent-authored diff in a hermetic worktree (audit + ruff "
        "+ mapped tests) before it may enter the governor approval queue"
    ),
    category=ActionCategory.CHECK,
    policies=["rules/code/purity"],
    requires_db=False,
    requires_vectors=False,
)
@atomic_action(
    action_id="assisted.validate_diff",
    intent=(
        "Apply a candidate diff in a throwaway worktree and report whether it "
        "clears the validation gate; never mutates the main tree"
    ),
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: 8a0719c8-92a7-482f-9bb3-ef958fc62442
async def action_assisted_validate_diff(
    *,
    patch: str | None = None,
    finding_rule: str | None = None,
    core_context: CoreContext | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Assisted Remediation Lane safety gate (ADR-109 #654).

    Args:
        patch: a unified diff (the agent's candidate change) to validate.
        finding_rule: the rule id the delegated finding fired on; the gate
            requires this rule to NO LONGER fire on the touched files.
        core_context: injected by ActionExecutor; supplies ``git_service``
            for worktree creation.

    Returns an ``ActionResult`` whose ``data['validation_results']`` is a
    ``{check: bool}`` map and whose ``ok`` is the AND of every check. A
    failing verdict means the diff is not approvable. ``data['production_set']``
    lists the touched repo-relative paths (the eventual commit set, ADR-101 D2).
    """
    started = time.perf_counter()
    aid = "assisted.validate_diff"

    if not patch or not finding_rule:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "error": "assisted.validate_diff requires 'patch' and 'finding_rule'"
            },
            impact=ActionImpact.WRITE_DATA,
            duration_sec=time.perf_counter() - started,
        )
    if core_context is None or core_context.git_service is None:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "error": "assisted.validate_diff requires a core_context with git_service"
            },
            impact=ActionImpact.WRITE_DATA,
            duration_sec=time.perf_counter() - started,
        )

    worktree = core_context.git_service.create_worktree("HEAD")
    wt_path = Path(worktree.repo_path)
    checks: dict[str, bool] = {}
    touched: list[str] = []
    try:
        # 1. Patch must apply cleanly in the hermetic worktree.
        applied = _git(wt_path, "apply", "--whitespace=nowarn", stdin=patch)
        checks["patch_applies"] = applied.returncode == 0
        if applied.returncode != 0:
            return ActionResult(
                action_id=aid,
                ok=False,
                data={
                    "validation_results": checks,
                    "production_set": [],
                    "error": f"git apply failed: {applied.stderr.strip()[:400]}",
                },
                impact=ActionImpact.WRITE_DATA,
                duration_sec=time.perf_counter() - started,
            )

        touched = [
            p for p in _git(wt_path, "diff", "--name-only").stdout.splitlines() if p
        ]
        touched_py = [p for p in touched if p.endswith(".py")]

        # 2. ruff must pass on the touched Python files.
        checks["ruff"] = _ruff_ok(wt_path, touched_py) if touched_py else True

        # 3. The offending rule must no longer fire on the touched files.
        #    Body invokes the Mind auditor against the worktree path — the
        #    established canary pattern (crate_processing_service,
        #    constitutional_evaluator). Deferred import keeps module load clean.
        if touched_py:
            from mind.governance.audit_context import AuditorContext
            from mind.governance.filtered_audit import run_filtered_audit

            actx = AuditorContext(wt_path)
            await actx.load_knowledge_graph()
            findings, _, _ = await run_filtered_audit(
                actx, rule_ids=[finding_rule], files=touched_py
            )
            checks["audit_rule_cleared"] = len(findings) == 0
        else:
            checks["audit_rule_cleared"] = True

        # 4. Mapped tests for the touched sources must pass (when they exist).
        from shared.infrastructure.intent.test_coverage_paths import (
            source_to_test_path,
        )
        from shared.infrastructure.validation.test_runner import run_tests

        test_targets = {source_to_test_path(p) for p in touched_py}
        existing_tests = [t for t in test_targets if t and (wt_path / t).is_file()]
        tests_pass = True
        for t in existing_tests:
            r = await run_tests(target=t, action_id=aid, repo_root=wt_path)
            if not r.ok:
                tests_pass = False
        checks["tests"] = tests_pass

        verdict = all(checks.values())
        return ActionResult(
            action_id=aid,
            ok=verdict,
            data={
                "validation_results": checks,
                "production_set": touched,
                "finding_rule": finding_rule,
                "tests_run": existing_tests,
            },
            impact=ActionImpact.WRITE_DATA,
            duration_sec=time.perf_counter() - started,
        )
    finally:
        worktree.cleanup()
