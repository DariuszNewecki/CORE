"""ADR-162 D8 (U7) -- the core-engine entrypoint's ledger wrappers.

`.docker/core-engine/entrypoint.sh status|migrate ...` dispatch to
`core-admin database status|migrate ...` (the wheel bundles the migration
assets, so the image can inspect and migrate its external database without
a checkout). Both require DATABASE_URL and exit 78 (EX_CONFIG) without it;
an arbitrary command still passes through unchanged, and the default daemon
path keeps its DATABASE_URL / workspace gates.

Driven against the real script with a fake `core-admin` on PATH that records
its argv (the pattern of tests/infra/test_audit_gate_entrypoint.py).
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO / ".docker" / "core-engine" / "entrypoint.sh"


def _run(
    tmp_path: Path, *args: str, database_url: str | None
) -> tuple[int, str, list[str]]:
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir(exist_ok=True)
    log = tmp_path / "argv.log"
    shim = shim_dir / "core-admin"
    shim.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" >> "$ARGV_LOG"\nexit 0\n', encoding="utf-8"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    env = {
        "PATH": os.pathsep.join([str(shim_dir), os.environ.get("PATH", "")]),
        "ARGV_LOG": str(log),
    }
    if database_url is not None:
        env["DATABASE_URL"] = database_url
    proc = subprocess.run(
        ["bash", str(ENTRYPOINT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=tmp_path,
    )
    argv = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return proc.returncode, proc.stdout + proc.stderr, argv


# ID: e39c65f2-29bf-43d7-8ced-587b8f7777cf
def test_status_wrapper_dispatches_to_database_status(tmp_path: Path) -> None:
    code, _, argv = _run(
        tmp_path,
        "status",
        "--format",
        "json",
        database_url="postgresql+asyncpg://u:p@h/db",
    )
    assert code == 0
    assert argv == ["database", "status", "--format", "json"]


# ID: 86d9f454-8e1a-434e-85b2-bea5f620e2b2
def test_migrate_wrapper_passes_flags_through(tmp_path: Path) -> None:
    code, _, argv = _run(
        tmp_path,
        "migrate",
        "--adopt-baseline",
        "v2.9.1",
        "--write",
        database_url="x://y",
    )
    assert code == 0
    assert argv == ["database", "migrate", "--adopt-baseline", "v2.9.1", "--write"]


# ID: 98540c7c-e75a-46d8-b36a-5bca6a53f4a4
def test_wrappers_refuse_without_database_url_exit_78(tmp_path: Path) -> None:
    for sub in ("status", "migrate"):
        code, out, argv = _run(tmp_path, sub, database_url=None)
        assert code == 78, sub
        assert "DATABASE_URL is not set" in out
        assert argv == []


# ID: c1ca00b8-a5b2-45ad-b941-449dca6145e9
def test_arbitrary_command_still_passes_through(tmp_path: Path) -> None:
    code, _, argv = _run(tmp_path, "core-admin", "code", "audit", database_url=None)
    assert code == 0
    assert argv == ["code", "audit"]


# ID: fe653872-deb6-4a10-b588-10fb3a7cca57
def test_daemon_default_path_keeps_its_gates(tmp_path: Path) -> None:
    code, out, _ = _run(tmp_path, database_url=None)
    assert code == 78 and "daemon" in out
    code, out, _ = _run(tmp_path, database_url="x://y")  # no /workspace/.intent
    assert code == 78 and ".intent" in out
