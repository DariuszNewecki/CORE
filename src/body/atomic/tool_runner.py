# src/body/atomic/tool_runner.py

"""Designated subprocess sanctuary for validated-diff tooling (ADR-109, ADR-141).

Provides structural backing for the ``governance.dangerous_execution_primitives``
rule: ``git apply``, ``ruff check``, and the stateless subprocess audit runner are
concentrated here as the single authorised Body sanctuary, mirroring the pytest
subprocess in ``shared.infrastructure.validation.test_runner``.

All methods operate against a hermetic worktree path supplied by the caller —
never the main working tree.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


# Bootstrap script written to var/tmp/ and run in a subprocess for each
# graph-independent engine-touching diff (ADR-141 D3/D5). The script:
#   1. Reads the input JSON from the path given as argv[1].
#   2. Prepends {worktree_path}/src to sys.path so the worktree's engine code
#      shadows any installed package versions.
#   3. Runs run_filtered_audit with stateless=True AuditorContext (no DB graph
#      load) at full scope and emits findings as JSON on stdout.
# Written here (not in the caller) so the sanctuary boundary is clear.
AUDIT_SUBPROCESS_BOOTSTRAP = """\
import sys
import json
import asyncio
from pathlib import Path

_data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
sys.path.insert(0, str(Path(_data["worktree_path"]) / "src"))

from mind.governance.audit_context import AuditorContext  # noqa: E402
from mind.governance.filtered_audit import run_filtered_audit  # noqa: E402


async def _main():
    actx = AuditorContext(Path(_data["worktree_path"]), stateless=True)
    findings, _, _ = await run_filtered_audit(
        actx, rule_ids=_data["rule_ids"], files=None
    )
    return findings


_findings = asyncio.run(_main())
print(json.dumps({"findings": _findings, "ok": True, "error": None}))
"""


# Bootstrap for the general validation path (ADR-168 Amendment 2026-10-10 A3):
# the full stateless audit — the same one the commit gate and CI run — over a
# patched worktree, with the worktree's own src/ first on sys.path so a patch
# that changes an engine is judged by the patched engine. Emits the audit's
# result dict (verdict, findings, skipped_rules) as JSON on stdout.
FULL_AUDIT_SUBPROCESS_BOOTSTRAP = """\
import sys
import json
import asyncio
from pathlib import Path

_data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
_wt = Path(_data["worktree_path"])
sys.path.insert(0, str(_wt / "src"))

from shared.infrastructure.intent.intent_repository import IntentRepository  # noqa: E402
from mind.governance.stateless_audit import run_stateless_audit  # noqa: E402


async def _main():
    repo = IntentRepository(strict=True, root=_wt / ".intent")
    repo.initialize()
    return await run_stateless_audit(intent_repo=repo, repo_path=_wt)


def _class_b_violations():
    # The write-time rules CORE applies to its own generated tests (mappings
    # with engine passive_gate and attestation_class "B", enforced by
    # PatternValidators) applied to every producer's files, each rule within
    # its own declared scope. Runs here so imports resolve against the
    # patched tree.
    from body.governance.intent_pattern_validators import PatternValidators
    from mind.governance.audit_context import _include_matches
    from mind.governance.enforcement_loader import EnforcementMappingLoader

    mappings = EnforcementMappingLoader(_wt / ".intent").load_all_mappings()
    scopes = {
        rule_id: list((entry.get("scope") or {}).get("applies_to") or [])
        for rule_id, entry in mappings.items()
        if isinstance(entry, dict)
        and entry.get("engine") == "passive_gate"
        and (entry.get("params") or {}).get("attestation_class") == "B"
    }
    checked, found = [], []
    for rel in _data.get("check_files") or []:
        if not any(_include_matches(rel, g) for g in sum(scopes.values(), [])):
            continue
        checked.append(rel)
        code = (_wt / rel).read_text(encoding="utf-8")
        for v in PatternValidators.validate_test_file_pattern(code, rel):
            globs = scopes.get(v.rule_name)
            if globs is not None and not any(_include_matches(rel, g) for g in globs):
                continue
            found.append({"rule_id": v.rule_name, "file_path": rel, "message": v.message})
    return {"rules": sorted(scopes), "checked": checked, "violations": found}


_result = asyncio.run(_main())
_result["class_b"] = _class_b_violations()
print(json.dumps({"ok": True, "error": None, "result": _result}, default=str))
"""

# The commit gate's own ceiling for the same audit (.claude/hooks/core-verdict.sh).
_FULL_AUDIT_TIMEOUT_SEC = 540


# ID: f8d1f6c2-4218-45eb-aa05-be4869d59da1
class ToolRunner:
    """Subprocess sanctuary for git, ruff, and stateless-audit invocations."""

    @staticmethod
    # ID: c0aba4ec-ad56-4b7f-b2f1-9235ecfce9a0
    def run_git(
        worktree: Path, *args: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command scoped to *worktree*."""
        return subprocess.run(
            ["git", "-C", str(worktree), *args],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    # ID: 87732bbe-11c4-42e7-959a-9a786d4ff9c8
    def run_ruff(worktree: Path, files: list[str]) -> bool:
        """Run ``ruff check`` on *files* within *worktree*. Returns True on clean."""
        proc = subprocess.run(
            ["ruff", "check", *files],
            cwd=str(worktree),
            text=True,
            capture_output=True,
            check=False,
        )
        return proc.returncode == 0

    @staticmethod
    # ID: c0fd6c6c-f437-40ad-8ebd-3da060640aea
    def run_audit_rule_subprocess(
        bootstrap_path: Path,
        input_path: Path,
    ) -> dict[str, Any]:
        """Run a single audit rule in a subprocess against the worktree.

        Invokes the pre-written bootstrap script (``AUDIT_SUBPROCESS_BOOTSTRAP``)
        with the input JSON file as argv[1]. The bootstrap prepends the worktree's
        ``src/`` to ``sys.path``, initialises a stateless ``AuditorContext``, and
        runs ``run_filtered_audit`` for the requested rule at full scope. Output
        is a JSON dict on stdout.

        ADR-141 D3/D4/D5. Only graph-independent engines produce reliable results
        in this mode (``requires_knowledge_graph = False``).

        Returns:
            Parsed dict ``{"findings": [...], "ok": bool, "error": str | None}``.
            On timeout, non-zero exit, or parse failure: ``{"findings": [],
            "ok": False, "error": "<reason>"}``.
        """
        try:
            proc = subprocess.run(
                [sys.executable, str(bootstrap_path), str(input_path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return {
                "findings": [],
                "ok": False,
                "error": "Subprocess audit timed out (120 s).",
            }

        if proc.returncode != 0:
            return {
                "findings": [],
                "ok": False,
                "error": (proc.stderr or proc.stdout or "non-zero exit").strip()[:400],
            }

        try:
            return json.loads(proc.stdout)
        except Exception as exc:
            return {
                "findings": [],
                "ok": False,
                "error": f"Subprocess stdout parse error: {exc}",
            }

    @staticmethod
    # ID: 2e12e1db-cba4-437d-9924-830d7484f64c
    def run_full_audit_subprocess(
        bootstrap_path: Path, input_path: Path
    ) -> dict[str, Any]:
        """Run the full stateless audit over a worktree in a subprocess.

        Invokes ``FULL_AUDIT_SUBPROCESS_BOOTSTRAP`` with the input JSON as
        argv[1]. Returns ``{"ok": True, "error": None, "result": {...}}``
        where ``result`` is ``run_stateless_audit``'s dict; on timeout,
        non-zero exit or unparseable output, ``{"ok": False, "error": ...,
        "result": None}`` — the caller fails closed.
        """
        try:
            proc = subprocess.run(
                [sys.executable, str(bootstrap_path), str(input_path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=_FULL_AUDIT_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": f"Full audit timed out ({_FULL_AUDIT_TIMEOUT_SEC} s).",
                "result": None,
            }

        if proc.returncode != 0:
            return {
                "ok": False,
                "error": (proc.stderr or proc.stdout or "non-zero exit").strip()[-400:],
                "result": None,
            }

        # Log lines may precede the JSON; the result is the last stdout line.
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        try:
            return json.loads(lines[-1])
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Full audit stdout parse error: {exc}",
                "result": None,
            }

    @staticmethod
    # ID: 2da620be-9bda-496a-904b-34463fbaf6ac
    def run_ruff_paths(worktree: Path, files: list[str]) -> bool:
        """``run_ruff`` limited to *files* that exist in *worktree*.

        A patch's deleted files are in its touched set but no longer on disk;
        ruff would report them as unreadable (E902) and fail the check.
        """
        present = [f for f in files if (worktree / f).is_file()]
        return ToolRunner.run_ruff(worktree, present) if present else True
