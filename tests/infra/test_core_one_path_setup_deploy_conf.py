"""core-one-path-setup writes the database commands core-deploy's migration needs.

BACKUP_COMMAND (the dump), and for the dump's restore check (#1113)
PSQL_COMMAND (read-only row counts on the live database) and RESTORE_IMAGE
(the throwaway container's image). The real block of step 5 is cut from the
script and run in bash against a temporary deploy.conf and secrets.env, with
``docker`` stubbed on PATH.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = (REPO / "infra" / "core-one-path-setup").read_text()
_BLOCK = re.search(r'^db_url=""\n.*?(?=^say "6\.)', SCRIPT, re.S | re.M)
assert _BLOCK, "step 5's database block not found in infra/core-one-path-setup"
URL = "postgresql+asyncpg://core_app:s3cret@127.0.0.1:5432/core"


def _run(
    tmp: Path, *, container: bool, dry: int = 0
) -> subprocess.CompletedProcess[str]:
    etc = tmp / "etc"
    etc.mkdir(exist_ok=True)
    (etc / "secrets.env").write_text(f'DATABASE_URL="{URL}"\n')
    stub = tmp / "bin"
    stub.mkdir(exist_ok=True)
    names = "core_postgres_db" if container else "other"
    (stub / "docker").write_text(
        "#!/bin/sh\n"
        f'[ "$1" = ps ] && echo {names}\n'
        '[ "$1" = inspect ] && echo postgres:16\n'
        "exit 0\n"
    )
    (stub / "docker").chmod(0o755)
    block = _BLOCK.group(0).replace("/opt/core/etc", str(etc))
    harness = f'set -euo pipefail\nDRY={dry}\nsay() {{ echo "$*"; }}\n' + block
    return subprocess.run(
        ["bash", "-c", harness],
        capture_output=True,
        text=True,
        timeout=30,
        env={"PATH": f"{stub}:/usr/bin:/bin"},
    )


def _conf(tmp: Path) -> dict[str, str]:
    lines = (tmp / "etc" / "deploy.conf").read_text().splitlines()
    return dict(line.split("=", 1) for line in lines)


# ID: cb003d06-a958-4772-8a95-a8129946f6be
def test_container_install_gets_all_three_and_a_rerun_keeps_them(
    tmp_path: Path,
) -> None:
    done = _run(tmp_path, container=True)
    assert done.returncode == 0, done.stderr
    assert _conf(tmp_path) == {
        "BACKUP_COMMAND": "docker exec core_postgres_db pg_dump -U core_app -Fc core > {out}",
        "PSQL_COMMAND": "docker exec -i core_postgres_db psql -U core_app -d core",
        "RESTORE_IMAGE": "postgres:16",
    }
    again = _run(tmp_path, container=True)
    assert again.returncode == 0, again.stderr
    assert "added" not in again.stdout
    assert len(_conf(tmp_path)) == 3


# ID: 6391476e-01ad-48bc-839c-acc47dc047e8
def test_without_container_no_image_and_the_password_is_never_printed(
    tmp_path: Path,
) -> None:
    done = _run(tmp_path, container=False)
    assert done.returncode == 0, done.stderr
    conf = _conf(tmp_path)
    assert conf["PSQL_COMMAND"].startswith("psql --dbname=postgresql://")
    assert "RESTORE_IMAGE" not in conf
    assert "no RESTORE_IMAGE" in done.stdout
    assert "s3cret" not in done.stdout + done.stderr


# ID: a86b0594-3e2b-4404-8e9e-47136d1f16ab
def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    done = _run(tmp_path, container=True, dry=1)
    assert done.returncode == 0, done.stderr
    assert "would add PSQL_COMMAND" in done.stdout
    assert not (tmp_path / "etc" / "deploy.conf").exists()
