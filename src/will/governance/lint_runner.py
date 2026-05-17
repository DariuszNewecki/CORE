# src/will/governance/lint_runner.py

"""
Lint runner facade — Will-layer entry point for POST /v1/lint
(ADR-054 Phase 1).

Runs `black --check` and `ruff check` against src/ and tests/ using
asyncio.create_subprocess_exec so the FastAPI event loop is not
blocked. The body-layer equivalent (mind.enforcement.audit.lint) is
synchronous and tailored for the daemon's internal use; we keep
that surface intact and route the API path through this async
variant instead.

asyncio.create_subprocess_exec is the canonical async-process
pattern in CORE (body/project_lifecycle/integration_service.py uses
it for the same reason). It is not in
governance.dangerous_execution_primitives' forbidden list.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from shared.logger import getLogger


__all__ = ["run_lint"]


logger = getLogger(__name__)


# Resolve tool binaries from the same venv as the running interpreter.
# Avoids depending on shell PATH (the systemd unit running uvicorn has
# the minimal user PATH and does not see `poetry`).
_VENV_BIN = Path(sys.executable).parent


# ID: e623ad27-9ba1-4ce1-9c33-dd30c6547acf
async def _run_tool(binary: Path, args: list[str]) -> dict:
    """Run a single tool by absolute path and capture output."""
    process = await asyncio.create_subprocess_exec(
        str(binary),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await process.communicate()
    return {
        "returncode": process.returncode or 0,
        "stdout": stdout_b.decode(errors="replace"),
        "stderr": stderr_b.decode(errors="replace"),
    }


# ID: cc5f0a1d-6d07-4b47-9007-102297a2937b
async def run_lint() -> dict:
    """Run black --check and ruff check, return structured result.

    Returns:
        dict: {
          "ok": bool,              # True iff both tools returned 0
          "tools": {
            "black": {"returncode", "stdout", "stderr"},
            "ruff":  {"returncode", "stdout", "stderr"},
          },
          "error": str | None,     # populated when a binary is missing
        }
    """
    black = _VENV_BIN / "black"
    ruff = _VENV_BIN / "ruff"
    missing = [name for name, p in [("black", black), ("ruff", ruff)] if not p.exists()]
    if missing:
        return {
            "ok": False,
            "tools": {},
            "error": f"missing venv binaries: {', '.join(missing)} (looked in {_VENV_BIN})",
        }

    tools = {
        "black": await _run_tool(black, ["--check", "src", "tests"]),
        "ruff": await _run_tool(ruff, ["check", "src", "tests"]),
    }
    overall_ok = all(t["returncode"] == 0 for t in tools.values())
    logger.info(
        "lint_runner: black=%d ruff=%d overall_ok=%s",
        tools["black"]["returncode"],
        tools["ruff"]["returncode"],
        overall_ok,
    )
    return {"ok": overall_ok, "tools": tools, "error": None}
