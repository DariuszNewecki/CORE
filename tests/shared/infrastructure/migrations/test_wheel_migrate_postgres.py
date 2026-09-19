# tests/shared/infrastructure/migrations/test_wheel_migrate_postgres.py
"""ADR-162 D8 (U7) -- ``database status`` and ``migrate --write`` work from a
clean wheel install, with no checkout, against an ephemeral Postgres.

Builds the wheel from this tree (``poetry build``), installs it into a fresh
venv, and drives the installed ``core-admin`` from a directory that is not a
checkout against a disposable database loaded with the released v2.10.1
schema: the bundled manifest and SQL are what ``--adopt-baseline v2.10.1
--write`` and ``migrate --write`` read. Skipped when poetry is unavailable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import venv
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from shared.infrastructure.repositories.db.common import REPO_ROOT


if TYPE_CHECKING:
    from .conftest import FreshDatabase


pytestmark = [pytest.mark.integration, pytest.mark.slow]

assert REPO_ROOT is not None
SCHEMA_V2_10_1 = REPO_ROOT / "tests" / "fixtures" / "schema" / "schema-v2.10.1.sql"


def _build_and_install_wheel(tmp_path: Path) -> Path:
    poetry = shutil.which("poetry")
    if poetry is None:
        pytest.skip("poetry is not available to build the wheel")
    dist = tmp_path / "dist"
    built = subprocess.run(
        [poetry, "build", "--format", "wheel", "--output", str(dist)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert built.returncode == 0, built.stderr[-1500:]
    wheel = sorted(dist.glob("core_runtime-*.whl"))[-1]
    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    install = subprocess.run(
        [str(venv_dir / "bin" / "pip"), "install", "--quiet", str(wheel)],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert install.returncode == 0, install.stderr[-1500:]
    return venv_dir / "bin"


# ID: 99aefedf-fcff-4b58-8e9a-284d8cc49919
async def test_wheel_migrates_an_external_database_without_a_checkout(
    fresh_database: FreshDatabase, tmp_path: Path
) -> None:
    db = fresh_database
    await db.load_schema(SCHEMA_V2_10_1)
    bin_dir = _build_and_install_wheel(tmp_path)
    workspace = tmp_path / "not-a-checkout"
    workspace.mkdir()
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "DATABASE_URL": db.url,
    }
    assert "PYTEST_CURRENT_TEST" not in env and "pyproject.toml" not in os.listdir(
        workspace
    )

    def core_admin(*args: str) -> tuple[int, str]:
        proc = subprocess.run(
            [str(bin_dir / "core-admin"), "database", *args],
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr

    code, out = core_admin("status", "--format", "json")
    assert code == 2, out[-1200:]
    payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert payload["assets"] == "bundled"
    assert payload["baseline_suggestion"] == "v2.10.1"

    code, out = core_admin("migrate", "--adopt-baseline", "v2.10.1", "--write")
    assert code == 0 and "adopted" in out, out[-1200:]

    code, out = core_admin("migrate", "--write")
    assert code == 0 and "1 applied, 4 reconciled" in out, out[-1200:]

    code, out = core_admin("status", "--format", "json")
    assert code == 0, out[-1200:]
    payload = json.loads(out[out.index("{") : out.rindex("}") + 1])
    assert payload["current"] is True and payload["assets"] == "bundled"
    assert "20260919_adr162_migrations_reconciled.sql" in payload["applied_migrations"]
