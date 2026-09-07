"""Unit D parent orchestrator: prepares a disposable target exactly as
Unit C's real materializer produces it (unmodified -- the target's
`.intent/` carries only the machinery floor plus the fixture's own
committed overlay: the ratified safe_auto_approval_envelope and, per the
Governor's 2026-09-07 ruling, one proposal_consumer_worker declaration
scoped to package/example.py), provisions an isolated database, runs the
real governed fix.format scenario in a fresh child process, and verifies
the "Required proof" invariant set against filesystem/git/database/
Blackboard evidence -- or, if the real governed path cannot complete
without a production correction, reports exactly where and why it
stopped.

Never mocks, monkeypatches, or fakes any component of the live governed
run -- see ``unit_d_child.py``, which this module spawns as a genuinely
fresh subprocess with REPO_PATH/MIND/DATABASE_URL already bound.
"""

from __future__ import annotations

import hashlib
import json
import os
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
from materialize import (
    REPO_ROOT,
    MaterializedTarget,
    git_snapshot,
    materialize_external_target,
)


_CHILD_SCRIPT = Path(__file__).resolve().parent / "unit_d_child.py"
_TARGET_FILE = "package/example.py"
_UNREACHABLE_DATABASE_URL = (
    "postgresql+asyncpg://u:p@nonexistent-host-unitd.invalid:5432/db"
)

# Canary files: recorded and compared byte-for-byte before/after the live
# run, in addition to package/example.py (the one authorized, governed
# target).
_CANARY_RELATIVE_PATHS = (
    "scripts/outside.py",
    "tests/test_example.py",
    "conftest.py",
    "package/__init__.py",
    "package/sub/__init__.py",
    "package/sub/nested.py",
)

# One deterministic, semantics-preserving formatting violation: ruff's
# canonical double-quoted string literal replaced with an identical
# single-quoted one. fix.format (ruff format) demonstrably normalizes
# this back.
_VIOLATION_ORIGINAL = 'return f"Hello, {name}!"\n'
_VIOLATION_INTRODUCED = "return f'Hello, {name}!'\n"


@dataclass
# ID: 2157d16a-2015-4765-8289-e163b0bcb72f
class ScenarioResult:
    """Sanitized, structured Unit D result -- never a credential or DSN."""

    target: str
    pristine_commit: str
    pristine_tree: str
    violation_commit: str | None = None
    violation_tree: str | None = None
    repair_commit: str | None = None
    repair_tree: str | None = None
    proposal_id: str | None = None
    lifecycle_states: list[str] = field(default_factory=list)
    executed_action_id: str | None = None
    changed_paths: list[str] = field(default_factory=list)
    native_tests_pristine: bool | None = None
    native_tests_post_violation: bool | None = None
    native_tests_post_repair: bool | None = None
    formatter_check_pristine: bool | None = None
    formatter_check_post_violation: bool | None = None
    formatter_check_post_repair: bool | None = None
    blackboard_report_present: bool = False
    root_agreement_ok: bool | None = None
    secret_scan_clean: bool = True
    checks: dict[str, bool] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    verdict: str = "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "pristine_commit": self.pristine_commit,
            "pristine_tree": self.pristine_tree,
            "violation_commit": self.violation_commit,
            "violation_tree": self.violation_tree,
            "repair_commit": self.repair_commit,
            "repair_tree": self.repair_tree,
            "proposal_id": self.proposal_id,
            "lifecycle_states": self.lifecycle_states,
            "executed_action_id": self.executed_action_id,
            "changed_paths": self.changed_paths,
            "native_tests": {
                "pristine": self.native_tests_pristine,
                "post_violation": self.native_tests_post_violation,
                "post_repair": self.native_tests_post_repair,
            },
            "formatter_check": {
                "pristine": self.formatter_check_pristine,
                "post_violation": self.formatter_check_post_violation,
                "post_repair": self.formatter_check_post_repair,
            },
            "blackboard_report_present": self.blackboard_report_present,
            "root_agreement_ok": self.root_agreement_ok,
            "secret_scan_clean": self.secret_scan_clean,
            "checks": self.checks,
            "blockers": self.blockers,
            "verdict": self.verdict,
        }


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_tree(
    root: Path, *, exclude_dirs: frozenset[str] = frozenset({".git"})
) -> dict[str, str]:
    """Return {relative_posix_path: sha256} for every regular, non-symlink
    file under root."""
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if any(part in exclude_dirs for part in path.relative_to(root).parts):
            continue
        if path.is_file() and not path.is_symlink():
            out[path.relative_to(root).as_posix()] = sha256_file(path)
    return out


def disable_incidental_caches_env() -> dict[str, str]:
    """Environment overrides keeping bytecode/pytest/ruff caches out of the
    disposable target's own tree."""
    cache_dir = tempfile.mkdtemp(prefix="unitd_caches_")
    return {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": cache_dir,
        "RUFF_CACHE_DIR": str(Path(cache_dir) / "ruff_cache"),
    }


def run_native_tests(target_root: Path, extra_env: dict[str, str]) -> bool:
    env = {**os.environ, **extra_env}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=target_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode == 0


def run_formatter_check(target_root: Path, extra_env: dict[str, str]) -> bool:
    """True iff package/example.py is formatter-compliant right now (ruff
    format --check exits 0). Runs the real ruff binary directly, deliberately
    independent of fix.format's own invocation mechanism -- this verifies
    file *state*, not the action under test."""
    env = {**os.environ, **extra_env}
    result = subprocess.run(
        ["ruff", "format", "--check", _TARGET_FILE],
        cwd=target_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


def introduce_violation(target_root: Path) -> None:
    """Introduce one deterministic, semantics-preserving formatting
    violation in exactly package/example.py, committed as a synthetic
    operator commit -- not a CORE action."""
    path = target_root / _TARGET_FILE
    content = path.read_text("utf-8")
    if _VIOLATION_ORIGINAL not in content:
        raise RuntimeError(
            f"expected pristine content containing {_VIOLATION_ORIGINAL!r} "
            f"in {_TARGET_FILE}; template may have drifted"
        )
    path.write_text(
        content.replace(_VIOLATION_ORIGINAL, _VIOLATION_INTRODUCED), "utf-8"
    )

    _git(["add", _TARGET_FILE], target_root)
    _git(["commit", "-m", "test operator: introduce formatting violation"], target_root)


def run_external_verify_precheck(target_root: Path) -> tuple[bool, str]:
    """Run Unit B's real `core-admin runtime external-verify` with an
    explicit, unreachable DATABASE_URL, before any mutation. Returns
    (succeeded, combined_output) -- output is scanned by the caller for
    DATABASE_URL leakage."""
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "DATABASE_URL": _UNREACHABLE_DATABASE_URL,
    }
    for key in ("REPO_PATH", "MIND"):
        env.pop(key, None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.admin_cli",
            "runtime",
            "external-verify",
            "--target",
            str(target_root),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = result.stdout + result.stderr
    return result.returncode == 0, combined


def run_live_scenario(
    target_root: Path, database_url: str, result_path: Path
) -> dict[str, Any]:
    """Spawn unit_d_child.py in a fresh process with REPO_PATH/MIND/
    DATABASE_URL bound before any bootstrap-sensitive import."""
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "REPO_PATH": str(target_root),
        "MIND": str(target_root / ".intent"),
        "DATABASE_URL": database_url,
    }
    subprocess.run(
        [sys.executable, str(_CHILD_SCRIPT), str(target_root), str(result_path)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if not result_path.exists():
        return {
            "ok": False,
            "stage": "child_process",
            "error": "no result file written",
        }
    return json.loads(result_path.read_text("utf-8"))


def scan_for_secrets(*texts: str | None) -> bool:
    """True iff none of *texts* contain a DATABASE_URL-shaped credential.

    Looks for the driver prefix plus an embedded `user:password@` shape --
    conservative and specific rather than a broad heuristic that would
    also flag harmless strings.
    """
    for text in texts:
        if text is None:
            continue
        if (
            "://" in text
            and "@" in text
            and ("postgresql" in text or "asyncpg" in text)
        ):
            return False
    return True


# ID: 963ddb37-6256-4c80-9354-daa6868a9148
def run_unit_d(*, keep_target: bool = True) -> ScenarioResult:
    workdir = Path(tempfile.mkdtemp(prefix="unitd_run_"))
    blockers: list[str] = []
    checks: dict[str, bool] = {}
    extra_env = disable_incidental_caches_env()

    core_status_before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    core_head_before = _git(["rev-parse", "HEAD"], REPO_ROOT)

    # Unmodified Unit C materializer -- the fixture's own committed
    # overlay only (safe_auto_approval_envelope + proposal_consumer_worker
    # declaration); no ad hoc widening by this orchestrator.
    materialized: MaterializedTarget = materialize_external_target(workdir / "target")
    target_root = materialized.root

    pristine_hashes = hash_tree(target_root)
    pristine_file_hashes = {
        rel: sha256_file(target_root / rel) for rel in _CANARY_RELATIVE_PATHS
    }
    pristine_file_hashes[_TARGET_FILE] = sha256_file(target_root / _TARGET_FILE)

    native_pristine = run_native_tests(target_root, extra_env)
    fmt_pristine = run_formatter_check(target_root, extra_env)
    verify_ok, verify_output = run_external_verify_precheck(target_root)
    secret_scan_clean = scan_for_secrets(verify_output)

    checks["pristine_worktree_clean"] = git_snapshot(target_root)[2] == ""
    checks["pristine_native_tests_pass"] = native_pristine
    checks["pristine_formatter_compliant"] = fmt_pristine
    checks["external_verify_precheck_ok"] = verify_ok
    checks["external_verify_no_database_url_leak"] = secret_scan_clean
    if not verify_ok:
        blockers.append("core-admin runtime external-verify failed before mutation")

    result = ScenarioResult(
        target=str(target_root),
        pristine_commit=materialized.baseline_commit,
        pristine_tree=materialized.baseline_tree,
        native_tests_pristine=native_pristine,
        formatter_check_pristine=fmt_pristine,
        secret_scan_clean=secret_scan_clean,
        checks=checks,
        blockers=blockers,
    )

    if blockers:
        result.verdict = "BLOCKED"
        return result

    introduce_violation(target_root)
    violation_commit = _git(["rev-parse", "HEAD"], target_root)
    violation_tree = _git(["write-tree"], target_root)
    violation_changed = _git(
        ["diff", "--name-only", f"{violation_commit}^", violation_commit], target_root
    ).splitlines()

    native_post_violation = run_native_tests(target_root, extra_env)
    fmt_post_violation = run_formatter_check(target_root, extra_env)
    checks["violation_changed_exactly_one_file"] = violation_changed == [_TARGET_FILE]
    checks["violation_native_tests_still_pass"] = native_post_violation
    checks["violation_formatter_check_fails"] = not fmt_post_violation
    checks["violation_worktree_clean"] = git_snapshot(target_root)[2] == ""

    result.violation_commit = violation_commit
    result.violation_tree = violation_tree
    result.native_tests_post_violation = native_post_violation
    result.formatter_check_post_violation = fmt_post_violation

    if not (
        checks["violation_changed_exactly_one_file"]
        and checks["violation_native_tests_still_pass"]
        and checks["violation_formatter_check_fails"]
        and checks["violation_worktree_clean"]
    ):
        result.blockers.append(
            "controlled violation setup did not satisfy its own required invariants"
        )
        result.verdict = "BLOCKED"
        return result

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

    checks["live_run_reached_success_path"] = bool(child.get("ok"))
    result.proposal_id = child.get("proposal_id")
    if child.get("pre_approval_status"):
        result.lifecycle_states.append(child["pre_approval_status"])
    if child.get("final_status"):
        result.lifecycle_states.append(child["final_status"])

    if not child.get("ok"):
        # This is the expected, honestly-reported outcome if the real
        # governed path cannot complete without a production correction --
        # see the final report for the exact stage and reason.
        result.blockers.append(
            f"live governed run did not reach a success path — "
            f"stage={child.get('stage')} error={child.get('error')}"
        )
        checks["proposal_reached_completed"] = False
        result.checks = checks
        result.verdict = "BLOCKED"
        core_status_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        ).stdout
        core_head_after = _git(["rev-parse", "HEAD"], REPO_ROOT)
        checks["core_repo_untouched"] = (
            core_status_after == core_status_before
            and core_head_after == core_head_before
        )
        return result

    checks["proposal_reached_completed"] = child.get("final_status") == "completed"
    action_rows = child.get("action_results_rows") or []
    fix_format_rows = [r for r in action_rows if r.get("action_type") == "fix.format"]
    checks["exactly_one_fix_format_action_result"] = len(fix_format_rows) == 1
    result.executed_action_id = "fix.format" if fix_format_rows else None

    consequence_rows = child.get("consequence_rows") or []
    changed_paths: list[str] = []
    if consequence_rows:
        raw = consequence_rows[0].get("files_changed") or []
        changed_paths = [
            str(e.get("path")) if isinstance(e, dict) else str(e) for e in raw
        ]
    result.changed_paths = changed_paths
    checks["changed_path_set_is_exactly_target_file"] = changed_paths == [_TARGET_FILE]

    post_scenario_head = _git(["rev-parse", "HEAD"], target_root)
    checks["exactly_one_new_commit_over_violation"] = (
        post_scenario_head != violation_commit
    )
    repair_parent = None
    if post_scenario_head != violation_commit:
        repair_parent = _git(["rev-parse", f"{post_scenario_head}^"], target_root)
    checks["repair_commit_parent_is_violation_commit"] = (
        repair_parent == violation_commit
    )

    result.repair_commit = (
        post_scenario_head if post_scenario_head != violation_commit else None
    )
    result.repair_tree = (
        _git(["write-tree"], target_root) if result.repair_commit else None
    )

    if result.repair_commit:
        commit_changed = _git(
            ["diff", "--name-only", f"{result.repair_commit}^", result.repair_commit],
            target_root,
        ).splitlines()
        checks["commit_changed_path_set_is_exactly_target_file"] = commit_changed == [
            _TARGET_FILE
        ]

    fmt_post_repair = run_formatter_check(target_root, extra_env)
    native_post_repair = run_native_tests(target_root, extra_env)
    result.formatter_check_post_repair = fmt_post_repair
    result.native_tests_post_repair = native_post_repair
    checks["repaired_file_formatter_compliant"] = fmt_post_repair
    checks["repaired_native_tests_pass"] = native_post_repair

    repaired_hash = sha256_file(target_root / _TARGET_FILE)
    checks["repaired_bytes_equal_pristine"] = (
        repaired_hash == pristine_file_hashes[_TARGET_FILE]
    )
    checks["repaired_tree_equals_pristine_tree"] = (
        result.repair_tree == materialized.baseline_tree
    )
    checks["working_tree_clean_after_repair"] = git_snapshot(target_root)[2] == ""

    post_hashes = hash_tree(target_root)
    canary_ok = all(
        post_hashes.get(rel) == pristine_hashes.get(rel)
        for rel in _CANARY_RELATIVE_PATHS
    )
    checks["canaries_byte_identical"] = canary_ok
    checks["no_symlink_in_package"] = not any(
        p.is_symlink() for p in (target_root / "package").rglob("*")
    )

    report = child.get("blackboard_report")
    result.blackboard_report_present = bool(report)
    checks["blackboard_report_identifies_proposal"] = bool(
        report
        and any(
            r.get("proposal_id") == result.proposal_id
            for r in (report.get("results") or [])
        )
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
    result = run_unit_d(keep_target=True)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
