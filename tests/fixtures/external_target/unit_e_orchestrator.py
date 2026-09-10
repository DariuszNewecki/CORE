"""Unit E parent orchestrator: live post-propagation rollback qualification.

Governor brief (2026-09-10): prove that a real sandboxed ``fix.format``
mutation of ``package/example.py`` -- genuinely executed and propagated
back to the target's main tree -- has its autonomous commit refused when
the git staging area already carries unrelated operator work
(``scripts/outside.py``, staged but not committed), and that the failure
path (``mark_failed`` + ``rollback_proposal``, ADR-101 D3) restores
``package/example.py`` byte-for-byte while leaving the operator's staged
change exactly as it was.

Reuses Unit D's generic infrastructure unmodified: ``materialize.py``
(fixture assembly), ``db_provisioning.py`` (disposable Postgres), and the
scenario-agnostic helpers in ``unit_d_orchestrator.py`` (violation
injection, formatter/native-test checks, the external-verify precheck,
hashing, secret scanning/redaction). The only new pieces here are what
Unit E's scenario actually adds: staging the out-of-scope file, capturing
a before/after fingerprint of everything that must NOT change, and
driving ``unit_e_child.py`` (Unit D's real child, reused under its own
goal string -- see that module) through the disposable database.

Never mocks, monkeypatches, or fakes any component of the live governed
run. The live scenario is invoked exactly once.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))

from db_provisioning import (
    DisposableDatabase,
    start_disposable_database,
    stop_disposable_database,
)
from materialize import REPO_ROOT, MaterializedTarget, materialize_external_target
from unit_d_orchestrator import (
    _CANARY_RELATIVE_PATHS,
    _TARGET_FILE,
    disable_incidental_caches_env,
    hash_tree,
    introduce_violation,
    redact_secrets,
    run_external_verify_precheck,
    run_formatter_check,
    run_native_tests,
    scan_for_secrets,
    sha256_file,
)


_CHILD_SCRIPT = Path(__file__).resolve().parent / "unit_e_child.py"
_OUTSIDE_FILE = "scripts/outside.py"
_OUTSIDE_MARKER = "\n# synthetic operator edit: unit-e-live-rollback-qualification\n"


@dataclass
# ID: c4d8e1a2-7b3f-4c9e-8a56-1d2e3f4a5b6c
class RollbackScenarioResult:
    """Sanitized, structured Unit E result -- never a credential or DSN."""

    target: str
    pristine_commit: str
    violation_commit: str | None = None
    proposal_id: str | None = None
    lifecycle_states: list[str] = field(default_factory=list)
    final_status: str | None = None
    final_failure_reason: str | None = None
    executed_action_id: str | None = None
    native_tests_post_violation: bool | None = None
    native_tests_post_rollback: bool | None = None
    formatter_check_post_violation: bool | None = None
    formatter_check_post_rollback: bool | None = None
    blackboard_report_present: bool = False
    secret_scan_clean: bool = True
    child_process: dict[str, Any] | None = None
    checks: dict[str, bool] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    verdict: str = "FAIL"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "pristine_commit": self.pristine_commit,
            "violation_commit": self.violation_commit,
            "proposal_id": self.proposal_id,
            "lifecycle_states": self.lifecycle_states,
            "final_status": self.final_status,
            "final_failure_reason": self.final_failure_reason,
            "executed_action_id": self.executed_action_id,
            "native_tests": {
                "post_violation": self.native_tests_post_violation,
                "post_rollback": self.native_tests_post_rollback,
            },
            "formatter_check": {
                "post_violation": self.formatter_check_post_violation,
                "post_rollback": self.formatter_check_post_rollback,
            },
            "blackboard_report_present": self.blackboard_report_present,
            "secret_scan_clean": self.secret_scan_clean,
            "child_process": self.child_process,
            "checks": self.checks,
            "blockers": self.blockers,
            "verdict": self.verdict,
            "notes": self.notes,
        }


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


# ID: 9a1b2c3d-4e5f-6071-8293-a4b5c6d7e8f9
def stage_outside_scope_file(target_root: Path) -> None:
    """Modify and stage -- never commit -- ``scripts/outside.py``.

    Reuses the fixture's own pre-existing "outside the ratified package/
    prefix" file (already used by Unit C's authority tests to prove the
    envelope denies action there) as the synthetic operator edit, rather
    than inventing a new path. Left staged so ADR-129 D1's
    ``commit_paths()`` Layer-1 check finds it in the index outside the
    ``fix.format`` production set and refuses the autonomous commit.
    """
    path = target_root / _OUTSIDE_FILE
    content = path.read_text("utf-8")
    if _OUTSIDE_MARKER in content:
        raise RuntimeError(
            f"expected {_OUTSIDE_FILE} to not already carry the Unit E "
            "marker; template may have drifted"
        )
    path.write_text(content + _OUTSIDE_MARKER, "utf-8")
    _git(["add", _OUTSIDE_FILE], target_root)


# ID: 1b2c3d4e-5f60-7182-93a4-b5c6d7e8f9a0
def capture_repo_fingerprint(target_root: Path) -> dict[str, Any]:
    """Snapshot everything the PASS criteria require to be identical
    before and after the live run: the staged outside-scope file's bytes
    and diff, the index tree, full porcelain status, and a hash of every
    tracked file's working-tree content.
    """
    tracked = _git(["ls-files"], target_root).splitlines()
    return {
        "outside_bytes_sha256": sha256_file(target_root / _OUTSIDE_FILE),
        "staged_diff": _git(["diff", "--cached", "--", _OUTSIDE_FILE], target_root),
        "index_tree": _git(["write-tree"], target_root),
        "status_porcelain": _git(
            ["status", "--porcelain", "--untracked-files=all"], target_root
        ),
        "tracked_file_hashes": {rel: sha256_file(target_root / rel) for rel in tracked},
    }


def run_live_scenario(
    target_root: Path, database_url: str, result_path: Path
) -> dict[str, Any]:
    """Spawn unit_e_child.py in a fresh process with REPO_PATH/MIND/
    DATABASE_URL bound before any bootstrap-sensitive import.

    Mirrors unit_d_orchestrator.run_live_scenario exactly (including
    retaining the child's own redacted stdout/stderr as evidence); the
    only difference is the child script invoked.
    """
    import os

    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "REPO_PATH": str(target_root),
        "MIND": str(target_root / ".intent"),
        "DATABASE_URL": database_url,
    }
    completed = subprocess.run(
        [sys.executable, str(_CHILD_SCRIPT), str(target_root), str(result_path)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    child_process_evidence = {
        "returncode": completed.returncode,
        "stdout": redact_secrets(completed.stdout),
        "stderr": redact_secrets(completed.stderr),
    }
    if not result_path.exists():
        return {
            "ok": False,
            "stage": "child_process",
            "error": "no result file written",
            "child_process": child_process_evidence,
        }
    result = json.loads(result_path.read_text("utf-8"))
    result["child_process"] = child_process_evidence
    return result


# ID: 2c3d4e5f-6071-8293-a4b5-c6d7e8f9a0b1
def run_unit_e(*, keep_target: bool = True) -> RollbackScenarioResult:
    var_tmp = REPO_ROOT / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="unite_run_", dir=var_tmp))
    blockers: list[str] = []
    notes: list[str] = []
    checks: dict[str, bool] = {}
    extra_env = disable_incidental_caches_env()

    core_status_before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    core_head_before = _git(["rev-parse", "HEAD"], REPO_ROOT)

    # Step 1 -- fresh disposable target, pristine commit P (unmodified
    # Unit C materializer, same as Unit D).
    materialized: MaterializedTarget = materialize_external_target(workdir / "target")
    target_root = materialized.root
    checks["pristine_worktree_clean"] = _git(["status", "--porcelain"], target_root) == ""

    result = RollbackScenarioResult(
        target=str(target_root),
        pristine_commit=materialized.baseline_commit,
        checks=checks,
        blockers=blockers,
        notes=notes,
    )

    # Step 2 -- deterministic formatting violation, committed as V.
    introduce_violation(target_root)
    violation_commit = _git(["rev-parse", "HEAD"], target_root)
    result.violation_commit = violation_commit

    native_post_violation = run_native_tests(target_root, extra_env)
    fmt_post_violation = run_formatter_check(target_root, extra_env)
    result.native_tests_post_violation = native_post_violation
    result.formatter_check_post_violation = fmt_post_violation
    checks["violation_native_tests_pass"] = native_post_violation
    checks["violation_formatter_check_fails"] = not fmt_post_violation
    checks["violation_worktree_clean"] = _git(["status", "--porcelain"], target_root) == ""

    # Step 3 -- external-verify precheck, before any contamination.
    verify_ok, verify_output = run_external_verify_precheck(target_root)
    secret_scan_clean = scan_for_secrets(verify_output)
    result.secret_scan_clean = secret_scan_clean
    checks["external_verify_precheck_ok"] = verify_ok
    checks["external_verify_no_database_url_leak"] = secret_scan_clean
    if not verify_ok:
        blockers.append("core-admin runtime external-verify failed before mutation")

    if blockers or not all(
        [
            checks["violation_native_tests_pass"],
            checks["violation_formatter_check_fails"],
            checks["violation_worktree_clean"],
        ]
    ):
        result.blockers.append(
            "controlled violation setup did not satisfy its own required invariants"
        )
        result.verdict = "BLOCKED"
        return result

    # Step 4 -- stage (never commit) the out-of-scope operator edit.
    stage_outside_scope_file(target_root)
    status_after_stage = _git(["status", "--porcelain"], target_root).splitlines()
    checks["exactly_one_staged_entry_after_contamination"] = status_after_stage == [
        f"M  {_OUTSIDE_FILE}"
    ]

    # Step 5 -- record fingerprints before the live run.
    pre_run_fingerprint = capture_repo_fingerprint(target_root)

    canary_paths = (*_CANARY_RELATIVE_PATHS, _TARGET_FILE)
    pre_run_hashes = hash_tree(target_root)

    if not checks["exactly_one_staged_entry_after_contamination"]:
        result.blockers.append(
            "staging setup did not produce exactly one staged, uncommitted "
            f"entry for {_OUTSIDE_FILE}"
        )
        result.verdict = "BLOCKED"
        return result

    # Step 6 -- disposable database; live run exactly once.
    db: DisposableDatabase | None = None
    try:
        db = start_disposable_database()
    except Exception as exc:
        result.blockers.append(f"disposable database provisioning failed: {exc}")
        result.verdict = "BLOCKED"
        return result

    try:
        child_result_path = workdir / "child_result.json"
        child = run_live_scenario(target_root, db.database_url, child_result_path)
    finally:
        stop_disposable_database(db)

    result.child_process = child.get("child_process")
    result.proposal_id = child.get("proposal_id")
    if child.get("pre_approval_status"):
        result.lifecycle_states.append(child["pre_approval_status"])
    if child.get("final_status"):
        result.lifecycle_states.append(child["final_status"])
    result.final_status = child.get("final_status")
    result.final_failure_reason = child.get("final_failure_reason")

    checks["live_harness_completed"] = bool(child.get("ok"))
    if not child.get("ok"):
        result.blockers.append(
            f"live harness did not complete — stage={child.get('stage')} "
            f"error={child.get('error')}"
        )
        result.checks = checks
        result.verdict = "BLOCKED"
        return result

    # -- Required proof: the proposal reached failed, never finalizing/completed.
    checks["proposal_reached_failed"] = result.final_status == "failed"
    checks["proposal_never_finalizing_or_completed"] = result.final_status not in (
        "finalizing",
        "completed",
    )
    checks["failure_reason_cites_staging_contamination"] = bool(
        result.final_failure_reason
        and "ADR-129 D1" in result.final_failure_reason
        and "staging contamination" in result.final_failure_reason
    )

    action_rows = child.get("action_results_rows") or []
    fix_format_rows = [r for r in action_rows if r.get("action_type") == "fix.format"]
    checks["exactly_one_fix_format_action_result"] = len(fix_format_rows) == 1
    checks["fix_format_action_ok"] = bool(
        fix_format_rows and fix_format_rows[0].get("ok") is True
    )
    result.executed_action_id = "fix.format" if fix_format_rows else None
    notes.append(
        "PASS-criterion gap, disclosed rather than papered over: the "
        "runtime-injected '_sandbox_target_paths' key (ActionExecutor, "
        "ADR-101 D2) lives only in the in-process action_results dict "
        "consumed synchronously inside ProposalExecutor.execute(). It is "
        "not independently observable from this live run: "
        "fix.format's own successful ActionResult.data is exactly "
        "{'formatted': True, 'write': write} (src/body/atomic/fix/"
        "format_code.py) — no path key at all — and the audit_log INSERT "
        "(ActionExecutor._audit_log) only ever persists action_metadata = "
        "{write_mode, impact, session_id}, never result.data. No consequence "
        "row exists for a refused commit either (that's itself a required "
        "invariant, checked below). Reading the variable directly would "
        "require a direct ActionExecutor/ProposalExecutor call (explicitly "
        "disallowed for the live run) or a production-code logging change "
        "(outside this unit's boundary) — both refused. What IS reused as "
        "real evidence for 'production reached package/example.py': (a) "
        "the persisted action_results row proves the SOLE fix.format action "
        "in this proposal ran and succeeded (checked below); (b) Unit D's "
        "own closed PASS run — same fixture, same fix.format/"
        "package/example.py action, same Proposal shape — persisted "
        "declared_production == ['package/example.py'] via the identical "
        "compute_production_set() that derives _sandbox_target_paths; (c) "
        "the sandbox worktree is a `git worktree add --detach` checkout at "
        "a commit SHA (GitService.create_worktree), fully isolated from the "
        "main tree's staged scripts/outside.py by construction, so nothing "
        "about Unit E's contamination can alter what the sandboxed "
        "fix.format itself produces relative to Unit D's run. This is "
        "corroborating precedent plus structural isolation, not a fresh "
        "Unit-E-specific raw reading of the variable — reported as such, "
        "not claimed as a directly-observed PASS."
    )

    consequence_rows = child.get("consequence_rows") or []
    checks["no_consequence_row"] = len(consequence_rows) == 0

    report = child.get("blackboard_report")
    result.blackboard_report_present = bool(report)
    report_entries = (report or {}).get("results") or []
    matching_entry = next(
        (r for r in report_entries if r.get("proposal_id") == result.proposal_id), None
    )
    checks["blackboard_report_identifies_proposal"] = matching_entry is not None
    checks["blackboard_report_marks_proposal_failed"] = bool(
        matching_entry
        and (
            matching_entry.get("lifecycle_status") == "failed"
            or matching_entry.get("ok") is False
        )
    )

    # -- Post-run target-repo state.
    post_run_head = _git(["rev-parse", "HEAD"], target_root)
    checks["target_head_unchanged_at_violation_commit"] = post_run_head == violation_commit

    native_post_rollback = run_native_tests(target_root, extra_env)
    fmt_post_rollback = run_formatter_check(target_root, extra_env)
    result.native_tests_post_rollback = native_post_rollback
    result.formatter_check_post_rollback = fmt_post_rollback
    checks["native_tests_pass_after_rollback"] = native_post_rollback
    checks["formatter_check_fails_again_after_rollback"] = not fmt_post_rollback

    post_run_target_hash = sha256_file(target_root / _TARGET_FILE)
    checks["target_file_restored_to_violation_bytes"] = (
        post_run_target_hash == pre_run_hashes[_TARGET_FILE]
    )

    post_run_fingerprint = capture_repo_fingerprint(target_root)
    checks["outside_scope_bytes_unchanged"] = (
        post_run_fingerprint["outside_bytes_sha256"]
        == pre_run_fingerprint["outside_bytes_sha256"]
    )
    checks["outside_scope_staged_diff_unchanged"] = (
        post_run_fingerprint["staged_diff"] == pre_run_fingerprint["staged_diff"]
    )
    checks["index_tree_unchanged"] = (
        post_run_fingerprint["index_tree"] == pre_run_fingerprint["index_tree"]
    )
    checks["status_porcelain_unchanged"] = (
        post_run_fingerprint["status_porcelain"]
        == pre_run_fingerprint["status_porcelain"]
    )
    checks["all_tracked_file_hashes_unchanged"] = (
        post_run_fingerprint["tracked_file_hashes"]
        == pre_run_fingerprint["tracked_file_hashes"]
    )

    post_run_hashes = hash_tree(target_root)
    canary_ok = all(
        post_run_hashes.get(rel) == pre_run_hashes.get(rel) for rel in canary_paths
    )
    checks["canaries_byte_identical"] = canary_ok
    checks["no_symlink_in_package"] = not any(
        p.is_symlink() for p in (target_root / "package").rglob("*")
    )

    result.checks = checks
    core_status_after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    core_head_after = _git(["rev-parse", "HEAD"], REPO_ROOT)
    checks["core_repo_untouched"] = (
        core_status_after == core_status_before and core_head_after == core_head_before
    )

    all_ok = not result.blockers and all(checks.values())
    result.verdict = "PASS" if all_ok else "FAIL"
    return result


def main() -> int:
    result = run_unit_e(keep_target=True)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
