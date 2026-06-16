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

import hashlib
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


def _norm_path(path: str | None) -> str:
    """Normalize a repo-relative path to POSIX for set comparison."""
    p = (path or "").replace("\\", "/")
    return p[2:] if p.startswith("./") else p


def _rule_cleared(
    findings: list[dict[str, Any]],
    subject_files: list[str] | None,
    touched_py: list[str],
) -> bool:
    """Decide whether the offending rule still flags the work's guarded files.

    The *guarded* set is the finding's subject file(s) plus the diff's touched
    Python files. ``findings`` is the result of running the offending rule at
    FULL repo scope (no file filter) — full scope is mandatory because
    ``run_filtered_audit`` SKIPS context-level rules when a file filter is set
    (``knowledge_gate``: orphan / ast_duplication / semantic_duplication /
    duplicate_ids …), which is exactly the finding-class this lane exists to
    drain. The verdict is whether any guarded path is still among the flagged
    paths: this validates a fix that lives in a *different* file than the
    finding's subject (e.g. a detector-bug fix) against the subject itself,
    not merely against the edited file.
    """
    guarded = {_norm_path(p) for p in (*(subject_files or []), *touched_py)}
    if not guarded:
        return True
    flagged = {_norm_path(f.get("file_path")) for f in findings}
    return not (guarded & flagged)


def _touches_audit_engine(
    touched_py: list[str], engine_files: frozenset[str]
) -> list[str]:
    """Return the touched files that are themselves audit-engine modules.

    A non-empty result means the diff is self-referential to the validator:
    the lane runs the IN-PROCESS auditor, so patching an engine in the worktree
    cannot change the logic that validates the patch (#661). Such a finding is
    a direct governed commit, not lane work.
    """
    engine_norm = {_norm_path(p) for p in engine_files}
    return sorted(p for p in touched_py if _norm_path(p) in engine_norm)


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
    subject_files: list[str] | None = None,
    core_context: CoreContext | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Assisted Remediation Lane safety gate (ADR-109 #654).

    Args:
        patch: a unified diff (the agent's candidate change) to validate.
        finding_rule: the rule id the delegated finding fired on; the gate
            requires this rule to NO LONGER flag the finding's subject (or any
            touched file).
        subject_files: the file(s) the delegated finding fired on. Required for
            findings whose fix lives in a different file than the subject (e.g.
            a detector-bug fix, where the engine is patched but the flagged file
            is unchanged): the gate confirms the rule no longer flags the
            subject, which a touched-files-only check could not.
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

        # 1b. A fix that patches an audit engine is self-referential: the lane
        #     validates with the in-process auditor, so the worktree patch does
        #     not change the engine logic that runs the validation (#661). Such
        #     a finding is a direct governed commit, not lane work — refuse with
        #     guidance rather than the misleading "rule still fires" a vacuous
        #     in-process audit would produce. Engine module set is derived from
        #     EngineRegistry (no hardcoded engines-dir literal).
        from mind.logic.engines.registry import EngineRegistry

        self_referential = _touches_audit_engine(
            touched_py, EngineRegistry.engine_source_files()
        )
        checks["not_audit_engine"] = not self_referential
        if self_referential:
            return ActionResult(
                action_id=aid,
                ok=False,
                data={
                    "validation_results": checks,
                    "production_set": touched,
                    "self_referential_engines": self_referential,
                    "error": (
                        "Diff modifies audit engine module(s): "
                        + ", ".join(self_referential)
                        + ". The assisted lane validates with the in-process "
                        "auditor, so it cannot confirm a fix to the auditor "
                        "itself — the worktree patch does not change the "
                        "validating engine. Disposition this finding as a "
                        "direct governed commit and resolve it (see #661)."
                    ),
                },
                impact=ActionImpact.WRITE_DATA,
                duration_sec=time.perf_counter() - started,
            )

        # 2. ruff must pass on the touched Python files.
        checks["ruff"] = _ruff_ok(wt_path, touched_py) if touched_py else True

        # 3. The offending rule must no longer flag the finding's subject or
        #    any touched file. Body invokes the Mind auditor against the
        #    worktree path — the established canary pattern
        #    (crate_processing_service, constitutional_evaluator). Deferred
        #    import keeps module load clean.
        #
        #    Run the rule at FULL scope (files=None): run_filtered_audit skips
        #    context-level rules under a file filter (the knowledge_gate family
        #    — orphan / duplication — which is the lane's core caseload), so a
        #    file-scoped check would pass them vacuously. _rule_cleared then
        #    confirms none of the guarded files (subject + touched) is still
        #    flagged. Full-scope is one rule, once, on a governor-initiated
        #    worktree validation — not the hot write-time gate.
        guarded = bool((subject_files or []) or touched_py)
        if guarded:
            from mind.governance.audit_context import AuditorContext
            from mind.governance.filtered_audit import run_filtered_audit

            actx = AuditorContext(wt_path)
            await actx.load_knowledge_graph()
            findings, _, _ = await run_filtered_audit(
                actx, rule_ids=[finding_rule], files=None
            )
            checks["audit_rule_cleared"] = _rule_cleared(
                findings, subject_files, touched_py
            )
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
                # Bind this verdict to the exact bytes validated. `lane propose`
                # re-checks this hash against the patch it submits, so an agent
                # who edits the diff after validating cannot ride a stale PASS
                # into the approval queue (ADR-109 mechanism §4).
                "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
            },
            impact=ActionImpact.WRITE_DATA,
            duration_sec=time.perf_counter() - started,
        )
    finally:
        worktree.cleanup()


@register_action(
    action_id="assisted.apply_diff",
    description=(
        "Apply a validated, governor-approved agent diff to the working tree "
        "(assisted-lane execution half; runs only post-approval)"
    ),
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    requires_db=False,
    requires_vectors=False,
)
@atomic_action(
    action_id="assisted.apply_diff",
    intent=(
        "Apply a validated, governor-approved diff; the touched paths commit as "
        "the production set (ADR-101 D2)"
    ),
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: a4b16ca5-e96e-4781-8466-089cae9150e9
async def action_assisted_apply_diff(
    *,
    patch: str | None = None,
    core_context: CoreContext | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Apply a candidate diff to the tree (ADR-109 / #652 execution half).

    Runs only after the diff cleared ``assisted.validate_diff`` and the governor
    approved the proposal. ActionExecutor sandboxes this WRITE_CODE action
    (ADR-071): ``core_context.git_service.repo_path`` is the hermetic worktree,
    so we ``git apply`` the patch there; SandboxLifecycle.propagate_changes then
    copies the touched files back to the main tree through FileHandler and the
    production set is committed (ADR-101 D2). The touched paths are declared in
    ``files_produced`` so they reach the commit set.
    """
    started = time.perf_counter()
    aid = "assisted.apply_diff"
    if not patch:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={"error": "assisted.apply_diff requires 'patch'"},
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.perf_counter() - started,
        )
    if core_context is None or core_context.git_service is None:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "error": "assisted.apply_diff requires a core_context with git_service"
            },
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.perf_counter() - started,
        )

    repo = Path(core_context.git_service.repo_path)
    applied = _git(repo, "apply", "--whitespace=nowarn", stdin=patch)
    if applied.returncode != 0:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={"error": f"git apply failed: {applied.stderr.strip()[:400]}"},
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.perf_counter() - started,
        )
    touched = [p for p in _git(repo, "diff", "--name-only").stdout.splitlines() if p]
    return ActionResult(
        action_id=aid,
        ok=True,
        data={"files_produced": touched},
        impact=ActionImpact.WRITE_CODE,
        duration_sec=time.perf_counter() - started,
    )
