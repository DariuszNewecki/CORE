# src/body/atomic/assisted_actions.py

"""Atomic actions for the Assisted Remediation Lane (ADR-109, ADR-141).

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

ADR-141 extends the lane to handle graph-independent engine-touching diffs via
subprocess audit: a fresh subprocess prepends the worktree's src to sys.path
and runs the offending rule under a stateless AuditorContext. Graph-dependent
engine touches (knowledge_gate.py) continue to refuse — the DB graph is stale
relative to the worktree patch.

Constitutional note (governance.dangerous_execution_primitives): subprocess calls
for ``git apply``, ``ruff``, and the stateless audit runner are concentrated in
``ToolRunner`` (``body.atomic.tool_runner``) — the designated Body validation
sanctuary, mirroring the pytest subprocess in
``shared.infrastructure.validation.test_runner``.
Calls run only against the throwaway worktree, never the main tree.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from body.atomic.registry import ActionCategory, register_action
from body.atomic.tool_runner import AUDIT_SUBPROCESS_BOOTSTRAP, ToolRunner
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


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


# ID: b54c7365-2961-4ac0-9736-e7c42bb522cc
class _EngineTouchResult(NamedTuple):
    """Partition of engine-touching files by subprocess-serviceability.

    ADR-141 D2: graph-independent engine touches are routed to subprocess
    audit; graph-dependent touches (knowledge_gate) must refuse.
    """

    serviceable: list[str]  # engine files the subprocess audit can validate
    must_refuse: list[str]  # graph-dependent engine files that require refusal


def _touches_audit_engine(
    touched_py: list[str],
    engine_files: frozenset[str],
    graph_dependent_files: frozenset[str],
) -> _EngineTouchResult:
    """Partition touched engine files by subprocess-serviceability.

    Returns an ``_EngineTouchResult`` with:
    - ``serviceable``: engine files that are graph-independent → subprocess audit.
    - ``must_refuse``: graph-dependent engine files (knowledge_gate) → refusal.

    ADR-141 D2::

        serviceable = engine_source_files ∩ touched_py - graph_dependent_files
        must_refuse  = graph_dependent_engine_files ∩ touched_py
    """
    engine_norm = {_norm_path(p) for p in engine_files}
    graph_norm = {_norm_path(p) for p in graph_dependent_files}
    touched_engines = [p for p in touched_py if _norm_path(p) in engine_norm]
    return _EngineTouchResult(
        serviceable=sorted(
            p for p in touched_engines if _norm_path(p) not in graph_norm
        ),
        must_refuse=sorted(p for p in touched_engines if _norm_path(p) in graph_norm),
    )


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
    """Assisted Remediation Lane safety gate (ADR-109 #654, ADR-141).

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
            for worktree creation and ``file_handler`` for var/tmp writes.

    Returns an ``ActionResult`` whose ``data['validation_results']`` is a
    ``{check: bool}`` map and whose ``ok`` is the AND of every check. A
    failing verdict means the diff is not approvable. ``data['production_set']``
    lists the touched repo-relative paths (the eventual commit set, ADR-101 D2).

    Engine-touching diffs (ADR-141):
    - Graph-dependent engine touch (knowledge_gate.py): ``not_graph_engine=False``,
      immediate refusal.
    - Graph-independent engine touch (all other 15): ``not_graph_engine=True``,
      ``subprocess_audit`` replaces the in-process ``audit_rule_cleared`` check.
    - No engine touch: normal in-process ``audit_rule_cleared`` check.
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
    subprocess_error: str | None = None
    try:
        # 1. Patch must apply cleanly in the hermetic worktree.
        applied = ToolRunner.run_git(
            wt_path, "apply", "--whitespace=nowarn", stdin=patch
        )
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
            p
            for p in ToolRunner.run_git(
                wt_path, "diff", "--name-only"
            ).stdout.splitlines()
            if p
        ]
        touched_py = [p for p in touched if p.endswith(".py")]

        # 1b. Engine-touch routing (ADR-141 D1/D2/D6).
        #     Derive the engine-file sets from the registry (no hardcoded path
        #     literals; discovery tracks what is actually registered).
        from mind.logic.engines.registry import EngineRegistry

        engine_touch = _touches_audit_engine(
            touched_py,
            EngineRegistry.engine_source_files(),
            EngineRegistry.graph_dependent_engine_files(),
        )

        # Graph-dependent engine touch → refuse (ADR-109 D6 / ADR-141 D1).
        # Updated message names the distinction so callers understand why the
        # subprocess path is unavailable for this engine family.
        if engine_touch.must_refuse:
            checks["not_graph_engine"] = False
            return ActionResult(
                action_id=aid,
                ok=False,
                data={
                    "validation_results": checks,
                    "production_set": touched,
                    "must_refuse_engines": engine_touch.must_refuse,
                    "error": (
                        "Diff modifies graph-dependent audit engine module(s): "
                        + ", ".join(engine_touch.must_refuse)
                        + ". These engines require a live DB knowledge graph that "
                        "is stale relative to the worktree patch; subprocess audit "
                        "cannot produce a reliable verdict. Disposition as a direct "
                        "governed commit (ADR-141 D1)."
                    ),
                },
                impact=ActionImpact.WRITE_DATA,
                duration_sec=time.perf_counter() - started,
            )

        # 2. ruff must pass on the touched Python files.
        checks["ruff"] = (
            ToolRunner.run_ruff(wt_path, touched_py) if touched_py else True
        )

        # 3a. Graph-independent engine touch → subprocess audit (ADR-141 D3/D4).
        #     Write bootstrap + input JSON to var/tmp via file_handler, spawn a
        #     subprocess that prepends the worktree's src to sys.path and runs
        #     run_filtered_audit with stateless=True AuditorContext.
        if engine_touch.serviceable:
            checks["not_graph_engine"] = True
            file_handler = core_context.file_handler
            run_id = uuid.uuid4().hex[:8]
            input_rel = f"var/tmp/core-subaudit-input-{run_id}.json"
            bootstrap_rel = f"var/tmp/core-subaudit-runner-{run_id}.py"
            file_handler.write_runtime_text(
                input_rel,
                json.dumps(
                    {
                        "worktree_path": str(wt_path),
                        "rule_id": finding_rule,
                        "subject_files": subject_files or [],
                    }
                ),
            )
            file_handler.write_runtime_text(bootstrap_rel, AUDIT_SUBPROCESS_BOOTSTRAP)
            bootstrap_abs = file_handler.repo_path / bootstrap_rel
            input_abs = file_handler.repo_path / input_rel
            try:
                sub_result = ToolRunner.run_audit_rule_subprocess(
                    bootstrap_abs, input_abs
                )
            finally:
                file_handler.remove_file(bootstrap_rel)
                file_handler.remove_file(input_rel)

            if sub_result.get("ok"):
                sub_findings = sub_result.get("findings") or []
                checks["subprocess_audit"] = _rule_cleared(
                    sub_findings, subject_files, touched_py
                )
            else:
                checks["subprocess_audit"] = False
                subprocess_error = sub_result.get("error")

        else:
            # 3b. No engine touch → in-process audit (original ADR-109 path).
            #     Run at FULL scope (files=None): run_filtered_audit skips
            #     context-level rules under a file filter, so a file-scoped check
            #     would pass knowledge_gate rules vacuously. _rule_cleared then
            #     confirms none of the guarded files is still flagged.
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
        result_data: dict[str, Any] = {
            "validation_results": checks,
            "production_set": touched,
            "finding_rule": finding_rule,
            "tests_run": existing_tests,
            # Bind this verdict to the exact bytes validated. `lane propose`
            # re-checks this hash against the patch it submits, so an agent
            # who edits the diff after validating cannot ride a stale PASS
            # into the approval queue (ADR-109 mechanism §4).
            "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
        }
        if subprocess_error is not None:
            result_data["subprocess_error"] = subprocess_error
        return ActionResult(
            action_id=aid,
            ok=verdict,
            data=result_data,
            impact=ActionImpact.WRITE_DATA,
            duration_sec=time.perf_counter() - started,
        )
    finally:
        worktree.cleanup()


@register_action(
    action_id="assisted.apply_diff",
    description=(
        "Apply a validated, governor-approved agent-authored diff to the main "
        "working tree (the final write step after lane proposal approval)"
    ),
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    requires_db=False,
    requires_vectors=False,
)
@atomic_action(
    action_id="assisted.apply_diff",
    intent=(
        "Apply a pre-validated diff to the main tree; only runs after governor "
        "approval of the matching lane proposal"
    ),
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 6e2c4f8a-1b3d-4a9c-8f7e-5d2b0a1c6e4f
async def action_assisted_apply_diff(
    *,
    patch: str | None = None,
    core_context: CoreContext | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Apply a validated diff to the main working tree.

    This is the write step that runs ONLY after the governor has approved the
    lane proposal. The validation gate (``assisted.validate_diff``) runs
    earlier and is decoupled from this action. This action NEVER validates —
    it assumes the governor's approval is the authorization.

    Args:
        patch: a unified diff to apply to the main working tree.
        core_context: injected by ActionExecutor; supplies ``git_service``.
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

    result = ToolRunner.run_git(
        Path(core_context.git_service.repo_path),
        "apply",
        "--whitespace=nowarn",
        stdin=patch,
    )
    ok = result.returncode == 0
    return ActionResult(
        action_id=aid,
        ok=ok,
        data={
            "applied": ok,
            "error": result.stderr.strip()[:400] if not ok else None,
        },
        impact=ActionImpact.WRITE_CODE,
        duration_sec=time.perf_counter() - started,
    )
