# tests/cli/test_offline_audit_regression_544.py
"""Regression guard for #544 — published wheel's offline audit must work.

Issue #544 documented three defects that broke `core-admin code audit
--offline` when invoked from a fresh pip-installed `core-runtime` with no
environment variables: ``Settings()`` required `DATABASE_URL` and
`QDRANT_URL` at module-import time; ``IntentRepository`` auto-bootstrapped
against the package install dir rather than the consumer's cwd; and the
``@core_command`` decorator eagerly fetched DB/Qdrant services before
typer parsed ``--offline``. F-10.1a/F-10.1b acceptance tests passed because
they ran the CLI from the source tree (where env vars and ``.intent/``
happen to exist); the published-wheel deployment shape (F-10.3) never got
verified.

This test closes that verification gap by building the wheel, installing
into a fresh venv, and invoking ``core-admin code audit --offline``
against a temp workspace with only minimal ``PATH``/``HOME`` shell vars.
Any future regression in import-time side effects, eager service fetch,
or path-resolution will fail this test with a Python traceback in the
output stream.

Run with::

    poetry build
    pytest tests/cli/test_offline_audit_regression_544.py -v -m e2e

The test is marked ``e2e`` + ``slow`` because it creates a venv and runs
``pip install`` (~20-30s per invocation). It is excluded from the default
``unit``-marked test selection.
"""

from __future__ import annotations

import shutil
import subprocess
import venv
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"


def _find_latest_wheel() -> Path | None:
    if not DIST_DIR.exists():
        return None
    wheels = sorted(DIST_DIR.glob("core_runtime-*.whl"))
    return wheels[-1] if wheels else None


@pytest.mark.e2e
@pytest.mark.slow
# ID: 7e84b3f1-9c2a-4f6d-a1e5-3b7d8c2f9a14
def test_offline_audit_from_fresh_venv_with_no_env_vars(tmp_path: Path) -> None:
    """Verify the published wheel's offline audit runs cleanly with no env vars.

    Failure modes this catches (the #544 class):
    - ``Settings()`` ValidationError on missing DATABASE_URL/QDRANT_URL
    - GovernanceError: ``.intent root does not exist`` at the package
      install dir
    - ``ModuleNotFoundError: psycopg2`` from sync engine creation
    - Any Python traceback escaping the typer command boundary
    """
    wheel = _find_latest_wheel()
    if wheel is None:
        pytest.skip(
            "No core_runtime-*.whl in dist/. Run `poetry build` first to "
            "produce the artifact this test exercises."
        )

    # Step 1: fresh venv
    venv_dir = tmp_path / "test-venv"
    venv.create(venv_dir, with_pip=True)
    bin_dir = venv_dir / "bin"

    # Step 2: install the wheel
    install_result = subprocess.run(
        [str(bin_dir / "pip"), "install", "--quiet", str(wheel)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_result.returncode == 0, (
        f"pip install of {wheel.name} failed.\n"
        f"stderr: {install_result.stderr[-1000:]}"
    )

    # Step 3: minimal workspace with a copied .intent/ from this repo
    workspace = tmp_path / "consumer-workspace"
    workspace.mkdir()
    shutil.copytree(REPO_ROOT / ".intent", workspace / ".intent")

    # Step 4: invoke audit with stripped env. The audit must locate
    # .intent/ by cwd-walking (defect 2b fix) — no MIND env var set.
    minimal_env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
    }
    result = subprocess.run(
        [
            str(bin_dir / "core-admin"),
            "code",
            "audit",
            "--offline",
            "--format=text",
            "--severity=block",
        ],
        cwd=str(workspace),
        env=minimal_env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # The audit may legitimately PASS (0), FAIL with findings (1), or
    # report a config error (2). It must NEVER crash with exit 64
    # (EXIT_INTERNAL_ERROR — unhandled exception escape) or any other
    # code, because that signals a regression in the audit's startup
    # chain rather than a property of the consumer's repo.
    assert result.returncode in {0, 1, 2}, (
        f"Audit exited {result.returncode}, expected 0/1/2.\n"
        f"stdout (last 2000 chars):\n{result.stdout[-2000:]}\n\n"
        f"stderr (last 2000 chars):\n{result.stderr[-2000:]}"
    )

    # A Python traceback in stdout means a regression: something in the
    # CLI startup chain raised an unhandled exception that escaped the
    # typer command boundary. Defects 1/2/2b/3 all manifested this way.
    assert "Traceback (most recent call last)" not in result.stdout, (
        f"Audit emitted a Python traceback — regression of #544 class.\n"
        f"stdout (last 2000 chars):\n{result.stdout[-2000:]}"
    )
    assert "ModuleNotFoundError" not in result.stdout, (
        f"Audit hit ModuleNotFoundError — likely defect 3 regression "
        f"(eager DB service fetch importing psycopg2).\n"
        f"stdout (last 2000 chars):\n{result.stdout[-2000:]}"
    )
    assert "ValidationError" not in result.stdout, (
        f"Audit hit pydantic ValidationError — likely defect 1 regression "
        f"(Settings() requiring DATABASE_URL/QDRANT_URL).\n"
        f"stdout (last 2000 chars):\n{result.stdout[-2000:]}"
    )
