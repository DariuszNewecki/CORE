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
        actx, rule_ids=[_data["rule_id"]], files=None
    )
    return findings


_findings = asyncio.run(_main())
print(json.dumps({"findings": _findings, "ok": True, "error": None}))
"""


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
