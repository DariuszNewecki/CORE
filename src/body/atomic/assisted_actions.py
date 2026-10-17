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

ADR-168 Amendment 2026-10-10 A3 adds a *general* mode for a change not born
from a finding: CORE chooses the checks. It refuses a patch touching governed
text (A5, declared in governance_paths.yaml), then runs ruff, the full
stateless audit over the patched worktree — the same audit the commit gate and
CI run, accepted on the same terms (PASS or DEGRADED, no blocking finding) —
and the tests of every touched source and test file. Every rule the audit
could not evaluate is named in the result.

Constitutional note (governance.dangerous_execution_primitives): subprocess calls
for ``git apply``, ``ruff``, and the stateless audit runner are concentrated in
``ToolRunner`` (``body.atomic.tool_runner``) — the designated Body validation
sanctuary; pytest itself runs only in the sandbox runner
(``body.sandbox.repo_tests``, ADR-132 D10.10).
Calls run only against the throwaway worktree, never the main tree.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from body.atomic.registry import ActionCategory, register_action
from body.atomic.tool_runner import ToolRunner
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger
from shared.utils.patch_facts import read_patch


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


def _finding_base_rule(check_id: str) -> str:
    """Strip rule_executor's crash-path suffixes to recover the owning rule id.

    ``rule_executor.execute_rule`` enforces ``finding.check_id == rule.rule_id``
    for genuine findings (issue #485's restored invariant), but a rule that
    raises during evaluation is instead recorded with a
    ``f"{rule.rule_id}.enforcement_failure"``/``".engine_missing"`` check_id.
    Attribution must still land on the owning rule so a crashing rule reads
    as "did not clear" for that rule, not as an orphaned finding no rule
    claims.
    """
    for suffix in (".enforcement_failure", ".engine_missing"):
        if check_id.endswith(suffix):
            return check_id[: -len(suffix)]
    return check_id


def _findings_by_rule(
    findings: list[dict[str, Any]], rule_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Partition a multi-rule audit's findings back out per rule id.

    Safe because ``run_filtered_audit(rule_ids=rule_ids, ...)`` only ever
    executes the requested rules, and every finding it returns carries a
    ``check_id`` attributable to exactly one of them via
    ``_finding_base_rule``.
    """
    by_rule: dict[str, list[dict[str, Any]]] = {rid: [] for rid in rule_ids}
    for finding in findings:
        base_rule = _finding_base_rule(str(finding.get("check_id") or ""))
        if base_rule in by_rule:
            by_rule[base_rule].append(finding)
    return by_rule


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
    runs_candidate_code=True,
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
    finding_rules: list[str] | None = None,
    subject_files: list[str] | None = None,
    base_sha: str | None = None,
    general: bool = False,
    core_context: CoreContext | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Assisted Remediation Lane safety gate (ADR-109 #654, ADR-141, ADR-154 D1).

    Args:
        patch: a unified diff (the agent's candidate change) to validate.
        finding_rules: the complete set of rule ids the backing finding(s)
            fired on; the gate requires EVERY one of these rules to NO LONGER
            flag the finding's subject (or any touched file). Callers must
            pass the full canonical set — this action does not know, and
            cannot verify, whether a caller silently narrowed it.
        subject_files: the file(s) the delegated finding fired on. Required for
            findings whose fix lives in a different file than the subject (e.g.
            a detector-bug fix, where the engine is patched but the flagged file
            is unchanged): the gate confirms the rule no longer flags the
            subject, which a touched-files-only check could not.
        base_sha: the exact commit the candidate patch was generated against.
            The validation worktree is created at this SHA rather than
            floating "HEAD", so a caller that captured a base commit earlier
            (e.g. RemediationCeremony's ``plan.baseline_sha``) validates
            against precisely that commit, not whatever HEAD has drifted to
            since. Callers with no captured base (the external-agent Lane 1b
            path, which has none until it dispatches this action) may omit it
            — the worktree then floats to current HEAD, unchanged from prior
            behavior.
        general: validate a change not born from a finding (ADR-168
            Amendment 2026-10-10 A3). *finding_rules* and *subject_files* are
            not used; CORE chooses the checks — see ``_validate_general``.
        core_context: injected by ActionExecutor; supplies ``git_service``
            for worktree creation and ``file_handler`` for var/tmp writes.

    Returns an ``ActionResult`` whose ``data['validation_results']`` is a flat
    ``{check: bool}`` map and whose ``ok`` is the AND of every check. A
    failing verdict means the diff is not approvable. Per-rule audit evidence
    uses explicit keys ``f"audit_rule_cleared:{rule_id}"`` (or
    ``f"subprocess_audit:{rule_id}"`` on the engine-touch path) — one entry
    per rule in *finding_rules*, so a passing verdict is traceable to every
    individual rule clearing, not just an aggregate. ``data['production_set']``
    lists the touched repo-relative paths (the eventual commit set, ADR-101 D2).

    Engine-touching diffs (ADR-141):
    - Graph-dependent engine touch (knowledge_gate.py): ``not_graph_engine=False``,
      immediate refusal.
    - Graph-independent engine touch (all other 15): ``not_graph_engine=True``,
      per-rule ``subprocess_audit:<rule_id>`` replaces the in-process
      ``audit_rule_cleared:<rule_id>`` checks.
    - No engine touch: normal in-process ``audit_rule_cleared:<rule_id>`` checks.
    """
    started = time.perf_counter()
    aid = "assisted.validate_diff"

    rule_ids = sorted(set(finding_rules or []))
    if not patch or not (rule_ids or general):
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "error": (
                    "assisted.validate_diff requires 'patch' and either "
                    "'finding_rules' or general=True"
                )
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

    worktree = core_context.git_service.create_worktree(base_sha or "HEAD")
    wt_path = Path(worktree.repo_path)
    # ADR-154 D2: the exact commit SHA of the hermetic worktree this run
    # validates against — captured immediately at worktree creation, never
    # re-derived from a later read of production HEAD. This is the value
    # assisted.apply_diff must later match before it is allowed to apply.
    validated_base_sha = worktree.get_current_commit()
    checks: dict[str, bool] = {}
    touched: list[str] = []
    subprocess_error: str | None = None
    try:
        # 1. Patch must apply cleanly in the hermetic worktree.
        applied = _apply_to_index(wt_path, patch)
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

        touched = _touched_paths(wt_path)
        touched_py = [p for p in touched if p.endswith(".py")]

        if general:
            return await _validate_general(
                aid=aid,
                patch=patch,
                wt_path=wt_path,
                touched=touched,
                checks=checks,
                validated_base_sha=validated_base_sha,
                core_context=core_context,
                started=started,
            )

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
        # (deleted files are touched but gone; run_ruff_paths skips them)
        checks["ruff"] = ToolRunner.run_ruff_paths(wt_path, touched_py)

        # 3a. Graph-independent engine touch → the patched engine judges the
        #     patch (ADR-141 D3/D4): candidate code, so it runs as a sandbox
        #     audit job, and only a result from inside the sandbox service
        #     counts (external review F1).
        if engine_touch.serviceable:
            checks["not_graph_engine"] = True
            from body.sandbox.repo_audit import isolated_audit, run_audit_in_sandbox

            sub_audit, subprocess_error = isolated_audit(
                await run_audit_in_sandbox(wt_path, rule_ids=rule_ids)
            )
            sub_by_rule = _findings_by_rule(
                (sub_audit or {}).get("findings") or [], rule_ids
            )
            for rid in rule_ids:
                checks[f"subprocess_audit:{rid}"] = sub_audit is not None and (
                    _rule_cleared(sub_by_rule[rid], subject_files, touched_py)
                )

        else:
            # 3b. No engine touch → in-process audit (original ADR-109 path).
            #     Run at FULL scope (files=None): run_filtered_audit skips
            #     context-level rules under a file filter, so a file-scoped check
            #     would pass knowledge_gate rules vacuously. _rule_cleared then
            #     confirms none of the guarded files is still flagged. One audit
            #     invocation covers every rule in rule_ids — rule_executor
            #     enforces check_id == rule.rule_id (issue #485), so
            #     _findings_by_rule can attribute each returned finding back to
            #     its owning rule without a separate call per rule.
            guarded = bool((subject_files or []) or touched_py)
            if guarded:
                from mind.governance.audit_context import AuditorContext
                from mind.governance.filtered_audit import run_filtered_audit

                actx = AuditorContext(wt_path)
                await actx.load_knowledge_graph()
                findings, _, _ = await run_filtered_audit(
                    actx, rule_ids=rule_ids, files=None
                )
                by_rule = _findings_by_rule(findings, rule_ids)
                for rid in rule_ids:
                    checks[f"audit_rule_cleared:{rid}"] = _rule_cleared(
                        by_rule[rid], subject_files, touched_py
                    )
            else:
                for rid in rule_ids:
                    checks[f"audit_rule_cleared:{rid}"] = True

        # 4. Mapped tests for the touched sources must pass (when they exist).
        from body.sandbox.repo_tests import run_tests
        from shared.infrastructure.intent.test_coverage_paths import (
            source_to_test_path,
        )

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
            "finding_rules": rule_ids,
            # ADR-154 D3: which original finding subject(s) this run treated
            # as guarded — durably recorded so build_validated_candidate can
            # verify a caller's asserted subject_files against what was
            # actually validated, the same way it already verifies rule_ids.
            "subject_files": subject_files or [],
            "tests_run": existing_tests,
            # Bind this verdict to the exact bytes validated. `lane propose`
            # re-checks this hash against the patch it submits, so an agent
            # who edits the diff after validating cannot ride a stale PASS
            # into the approval queue (ADR-109 mechanism §4).
            "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
            # ADR-154 D2: the exact worktree commit this run validated
            # against — assisted.apply_diff fails closed unless the
            # executing repository's HEAD still equals this value.
            "validated_base_sha": validated_base_sha,
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


# The CI gate's acceptance terms for the full audit (#907):
# verdict PASS or DEGRADED, and no finding of blocking severity.
_GATE_VERDICTS = frozenset({"PASS", "DEGRADED"})
_BLOCK_SEVERITIES = frozenset({"block", "blocking"})
# Tests that reach shared live state (the core_test database, a live daemon)
# are not run on a producer's behalf; the result says so.
_GENERAL_TEST_MARKERS = "not trio and not integration"


async def _validate_general(
    *,
    aid: str,
    patch: str,
    wt_path: Path,
    touched: list[str],
    checks: dict[str, bool],
    validated_base_sha: str,
    core_context: CoreContext,
    started: float,
) -> ActionResult:
    """CORE chooses the checks for a change not born from a finding (A3)."""
    from shared.infrastructure.intent.governed_text import (
        governed_paths_touched,
        load_governed_text_paths,
    )

    # A5: governed text enters only under ADR-170, never as a code proposal.
    governed_hits = governed_paths_touched(touched, load_governed_text_paths())
    checks["governed_text_untouched"] = not governed_hits
    if governed_hits:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "validation_mode": "general",
                "validation_results": checks,
                "production_set": touched,
                "governed_paths": governed_hits,
                "error": (
                    "Patch touches governed text ("
                    + ", ".join(governed_hits)
                    + "); governed text enters only as a law proposal (ADR-170)."
                ),
            },
            impact=ActionImpact.WRITE_DATA,
            duration_sec=time.perf_counter() - started,
        )

    touched_py = [p for p in touched if p.endswith(".py")]
    checks["ruff"] = ToolRunner.run_ruff_paths(wt_path, touched_py)

    # The full audit over the patched tree with the tree's own engine (ADR-141
    # D3, extended to every rule): candidate code, so a sandbox job whose
    # result counts only from inside the sandbox service (external review F1).
    present_py = [p for p in touched_py if (wt_path / p).is_file()]
    audit, audit_error = await _run_full_audit(wt_path, present_py)
    blocking: list[dict[str, Any]] = []
    not_evaluated: list[dict[str, Any]] = []
    audit_verdict: str | None = None
    if audit is None:
        checks["full_audit"] = False
    else:
        audit_verdict = audit.get("verdict")
        blocking = [
            f
            for f in audit.get("findings") or []
            if str(f.get("severity", "")).lower() in _BLOCK_SEVERITIES
        ]
        not_evaluated = [
            {"rule_id": r.get("rule_id"), "enforcement": r.get("enforcement")}
            for r in audit.get("skipped_rules") or []
        ]
        checks["full_audit"] = audit_verdict in _GATE_VERDICTS and not blocking

    # The Class B write-time rules (code.tests.*, code.imports.generated_*)
    # bind every producer, not only CORE's own test generator (proposal 0011).
    class_b = (audit or {}).get("class_b")
    if not isinstance(class_b, dict):
        checks["class_b_rules"] = False
        class_b = {"rules": [], "checked": [], "violations": []}
    else:
        checks["class_b_rules"] = not class_b.get("violations")

    tests_run = _general_test_targets(wt_path, touched_py)
    checks["tests"] = await _run_test_files(aid, wt_path, tests_run)

    data: dict[str, Any] = {
        "validation_mode": "general",
        "validation_results": checks,
        "production_set": touched,
        "finding_rules": [],
        "subject_files": [],
        "audit_verdict": audit_verdict,
        "blocking_findings": [
            {
                "rule_id": f.get("check_id") or f.get("rule_id"),
                "file_path": f.get("file_path"),
                "line_number": f.get("line_number"),
                "message": str(f.get("message"))[:300],
            }
            for f in blocking[:20]
        ],
        "blocking_findings_count": len(blocking),
        "class_b": class_b,
        "not_evaluated": not_evaluated,
        "tests_run": tests_run,
        "tests_not_run_markers": _GENERAL_TEST_MARKERS,
        "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
        "validated_base_sha": validated_base_sha,
    }
    if audit_error is not None:
        data["audit_error"] = audit_error
    return ActionResult(
        action_id=aid,
        ok=all(checks.values()),
        data=data,
        impact=ActionImpact.WRITE_DATA,
        duration_sec=time.perf_counter() - started,
    )


async def _run_full_audit(
    wt_path: Path, check_files: list[str]
) -> tuple[dict[str, Any] | None, str | None]:
    """The full stateless audit over *wt_path*, plus the Class B rules on
    *check_files*, run in the sandbox; (result, None) or (None, error)."""
    from body.sandbox.repo_audit import isolated_audit, run_audit_in_sandbox

    audit, error = isolated_audit(
        await run_audit_in_sandbox(wt_path, check_files=check_files)
    )
    if audit is None:
        return None, error or "full audit returned no result"
    return audit, None


def _general_test_targets(wt_path: Path, touched_py: list[str]) -> list[str]:
    """Existing test files for a general change: the governed and sibling
    tests of every touched source file, and every touched test file itself."""
    from shared.infrastructure.intent.test_coverage_paths import (
        load_test_coverage_config,
        sibling_test_paths,
        source_to_test_path,
    )

    config = load_test_coverage_config()
    test_prefix = f"{config.get('test_root', 'tests')}/"
    targets: set[str] = set()
    for path in touched_py:
        if path.startswith(test_prefix):
            if Path(path).name.startswith("test_"):
                targets.add(path)
            continue
        try:
            targets.add(source_to_test_path(path, config))
        except ValueError:
            continue
        targets.update(sibling_test_paths(wt_path, path, config))
    return sorted(t for t in targets if (wt_path / t).is_file())


async def _run_test_files(aid: str, wt_path: Path, targets: list[str]) -> bool:
    """True when every test file in *targets* passes in *wt_path*."""
    from body.sandbox.repo_tests import run_tests

    passed = True
    for target in targets:
        result = await run_tests(
            target=target,
            action_id=aid,
            repo_root=wt_path,
            markers=_GENERAL_TEST_MARKERS,
        )
        if not result.ok:
            passed = False
    return passed


def _apply_to_index(wt_path: Path, patch: str) -> Any:
    """Apply *patch* to the hermetic worktree's files AND its index.

    Staging is what makes a file the patch creates visible to
    ``_touched_paths``: a plain ``git apply`` leaves it untracked, and
    ``git diff --name-only`` never lists untracked files — so a new file
    used to skip ruff, the audit subject set, its mapped test, and the
    production set. The worktree is disposable; its index is never used
    for a commit.
    """
    return ToolRunner.run_git(
        wt_path, "apply", "--index", "--whitespace=nowarn", stdin=patch
    )


def _touched_paths(wt_path: Path) -> list[str]:
    """Every path the applied patch changed: modified, added and deleted."""
    listed = ToolRunner.run_git(wt_path, "diff", "--cached", "--name-only").stdout
    return [p for p in listed.splitlines() if p]


# Approval states in which the bound proposal may run its apply (``claim``
# moves an approved proposal to ``executing`` before its actions run).
_APPLY_STATUSES = ("approved", "executing")
_GOVERNOR_AUTHORITY = "principal.governor"


def _proposal_binds(
    actions: Any, patch: str, patch_digest: str, validated_base_sha: str
) -> bool:
    """True when one of *actions* is this exact ``assisted.apply_diff``.

    The stored patch must equal *patch* byte for byte; the stored digest and
    base must equal the ones this call carries.
    """
    for action in actions if isinstance(actions, list) else []:
        if not isinstance(action, dict):
            continue
        params = action.get("parameters") or {}
        if (
            action.get("action_id") == "assisted.apply_diff"
            and params.get("patch") == patch
            and params.get("patch_digest") == patch_digest
            and params.get("validated_base_sha") == validated_base_sha
        ):
            return True
    return False


async def _approved_proposal_for(
    patch: str, patch_digest: str, validated_base_sha: str
) -> str | None:
    """The governor-approved proposal that holds exactly this patch, or None.

    Read from ``core.autonomous_proposals``: status approved or executing,
    approved by ``principal.governor``. Caller-supplied digest and base alone
    authorise nothing; the record must hold the same patch bytes.
    """
    from sqlalchemy import text

    from shared.infrastructure.database.session_manager import get_session

    needle = json.dumps(
        [
            {
                "action_id": "assisted.apply_diff",
                "parameters": {
                    "patch_digest": patch_digest,
                    "validated_base_sha": validated_base_sha,
                },
            }
        ]
    )
    async with get_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT proposal_id, actions FROM core.autonomous_proposals "
                    "WHERE status = ANY(:statuses) "
                    "AND approval_authority = :authority "
                    "AND approved_at IS NOT NULL "
                    "AND actions @> cast(:needle AS jsonb)"
                ),
                {
                    "statuses": list(_APPLY_STATUSES),
                    "authority": _GOVERNOR_AUTHORITY,
                    "needle": needle,
                },
            )
        ).all()
    for proposal_id, actions in rows:
        if _proposal_binds(actions, patch, patch_digest, validated_base_sha):
            return str(proposal_id)
    return None


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
    patch_digest: str | None = None,
    validated_base_sha: str | None = None,
    write: bool = False,
    core_context: CoreContext | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Apply a validated diff to the main working tree.

    This is the write step that runs ONLY after the governor has approved the
    lane proposal. The validation gate (``assisted.validate_diff``) runs
    earlier and is decoupled from this action. This action NEVER validates.

    It refuses, before any file or git change, unless ``write`` is True AND
    ``core.autonomous_proposals`` holds a governor-approved proposal (status
    approved or executing) whose ``assisted.apply_diff`` carries exactly this
    patch, digest and base SHA. Caller-supplied digest and base alone are not
    an approval (external review F2).

    ADR-154 D2 fail-closed checks — approval binds the tuple
    ``patch_digest + production_set + validated_base_sha``; this action
    actively re-verifies the two members of that tuple whose truth is
    determined only at execution time (the third, ``production_set``, is
    ADR-101 D2's commit-set concern, not this action's):

    - *validated_base_sha*: the exact worktree commit the candidate's
      ``assisted.validate_diff`` run validated against (frozen into the
      proposal at draft-creation time). Refuses unless the repository this
      action is actually executing against (``core_context.git_service`` —
      the sandboxed worktree when running under ``ProposalExecutor``)
      currently sits at exactly that commit. An intervening commit between
      validation and execution requires revalidation and renewed approval —
      building against an old base and propagating onto a newer tree is
      never silently allowed.
    - *patch_digest*: sha256 of *patch*, recorded at candidate-construction
      time (never caller-supplied — ADR-154 D2). Refuses unless
      ``sha256(patch)`` still equals it, so that even a code path that
      re-serialises or otherwise alters the frozen ``patch`` bytes between
      proposal creation and execution cannot silently apply something other
      than what the governor actually approved.

    Args:
        patch: a unified diff to apply to the main working tree.
        patch_digest: sha256 of *patch* recorded at validation time.
            Required — an apply with no bound digest is refused.
        validated_base_sha: the commit SHA the candidate was validated
            against. Required — an apply with no bound base SHA is refused.
        write: must be True; a dry run never applies.
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
    if not write:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "applied": False,
                "error": "assisted.apply_diff applies only with write=True",
            },
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
    if not validated_base_sha:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={"error": "assisted.apply_diff requires 'validated_base_sha'"},
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.perf_counter() - started,
        )
    if not patch_digest:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={"error": "assisted.apply_diff requires 'patch_digest'"},
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.perf_counter() - started,
        )

    executing_sha = core_context.git_service.get_current_commit()
    if executing_sha != validated_base_sha:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "applied": False,
                "error": (
                    "Base-SHA mismatch: candidate was validated against "
                    f"{validated_base_sha}, but the repository this action is "
                    f"executing against is at {executing_sha}. An intervening "
                    "commit invalidates this candidate — revalidate and "
                    "obtain renewed approval before applying (ADR-154 D2)."
                ),
                "validated_base_sha": validated_base_sha,
                "executing_sha": executing_sha,
            },
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.perf_counter() - started,
        )

    actual_digest = hashlib.sha256(patch.encode("utf-8")).hexdigest()
    if actual_digest != patch_digest:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "applied": False,
                "error": (
                    "Patch-digest mismatch: the approved candidate was bound "
                    f"to digest {patch_digest}, but the patch bytes reaching "
                    f"apply hash to {actual_digest}. The approved evidence no "
                    "longer matches what would be applied — refusing "
                    "(ADR-154 D2)."
                ),
                "patch_digest": patch_digest,
                "actual_digest": actual_digest,
            },
            impact=ActionImpact.WRITE_CODE,
            duration_sec=time.perf_counter() - started,
        )

    try:
        proposal_id = await _approved_proposal_for(
            patch, patch_digest, validated_base_sha
        )
    except Exception as exc:  # fail closed: no record read, no apply
        proposal_id = None
        lookup_error: str | None = f"approval record not readable: {exc}"
    else:
        lookup_error = None
    if proposal_id is None:
        return ActionResult(
            action_id=aid,
            ok=False,
            data={
                "applied": False,
                "error": lookup_error
                or (
                    "No governor-approved proposal holds this exact patch, digest "
                    "and base SHA; refusing (external review F2)."
                ),
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
    error = result.stderr.strip()[:400] if not ok else None
    if ok:
        # The patch must actually have changed what it names. `git apply`
        # outside its repository root ignores paths and still exits 0 — an
        # "applied" patch that changed nothing (proposal da93593b).
        facts = read_patch(patch)
        named = set(facts.added) | set(facts.modified) | set(facts.deleted)
        status = ToolRunner.run_git(
            Path(core_context.git_service.repo_path),
            "status",
            "--porcelain",
            "--untracked-files=all",
        )
        changed = {
            line[3:].strip().strip('"')
            for line in status.stdout.splitlines()
            if len(line) > 3
        }
        missing = sorted(named - changed)
        if status.returncode != 0 or missing:
            ok = False
            error = (
                "Patch reported applied but the tree does not show its changes "
                f"({', '.join(missing) or status.stderr.strip()[:200]}); refusing."
            )
    return ActionResult(
        action_id=aid,
        ok=ok,
        data={
            "applied": ok,
            "error": error,
            "proposal_id": proposal_id,
            # ADR-168 Amendment 2026-10-10 A3: the files this approved patch
            # deletes; the executor carries exactly these deletions to the
            # main tree and into the commit.
            "declared_deletions": read_patch(patch).deleted if ok else [],
        },
        impact=ActionImpact.WRITE_CODE,
        duration_sec=time.perf_counter() - started,
    )
