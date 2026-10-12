# tests/body/sandbox/test_probes.py
"""The M1 closure probes are well-formed (ADR-132 D10.10)."""

from __future__ import annotations

import ast
import asyncio
import subprocess
from pathlib import Path

import pytest

from body.sandbox import probes
from body.sandbox.models import SandboxResult
from body.sandbox.probes import PROBE_NAMES, _leftover_alive, probe_source


def test_probe_source_defines_one_test_per_probe() -> None:
    tree = ast.parse(probe_source())
    tests = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert {f"test_{name}" for name in PROBE_NAMES} <= tests


def test_leftover_detection() -> None:
    child = subprocess.Popen(["sleep", "30"])
    try:
        assert _leftover_alive(f"E   Failed: LEFTOVER_PID={child.pid}") is True
    finally:
        child.kill()
        child.wait()
    assert _leftover_alive(f"LEFTOVER_PID={child.pid}") is False
    assert _leftover_alive("no pid here") is None


def test_an_error_row_carries_the_job_stderr(
    scratch: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 2026-10-12: "the bootstrap produced no report" with no way to see why.
    async def fake(*_a: object, **_k: object) -> SandboxResult:
        return SandboxResult(
            status="error",
            completeness="none",
            isolation="service",
            reason="the bootstrap produced no report",
            stderr="PermissionError: pyproject.toml",
        )

    monkeypatch.setattr(probes, "run_repo_code", fake)
    (scratch / "var" / "tmp").mkdir(parents=True)
    rows = asyncio.run(probes.run_probes(scratch, mode="local"))
    assert rows[0]["detail"] == "PermissionError: pyproject.toml"
