"""ADR-162 D8 (U7) -- installed-wheel proof: the migration assets work from a
clean install with no checkout.

Archive inspection (test_migrations_ship_in_wheel.py) proves the wheel
*carries* the assets. This proves the installed package *uses* them: the
wheel is installed into a fresh venv and a probe runs from a directory that
is not a CORE checkout. It asserts that the resolver reports the bundle, the
manifest loads and passes its own disk verification against the bundle,
every bundled migration file passes the transaction lint, schema.sql is
bundled, and the ``core-admin database`` commands are mounted.

Same shape as test_prompts_installed_wheel.py: skipped when no wheel is in
``dist/``; CI's hermetic job builds one before running. The database-backed
half (``status`` / ``migrate --write`` from the wheel against an ephemeral
Postgres) lives in ``tests/shared/infrastructure/migrations/
test_wheel_migrate_postgres.py`` (integration).
"""

from __future__ import annotations

import json
import subprocess
import venv
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"

PROBE = r"""
import json
from pathlib import Path

cwd = Path.cwd()
assert not (cwd / "pyproject.toml").exists(), "probe cwd must not be a checkout"

from shared.infrastructure.repositories.db.common import (
    REPO_ROOT, resolve_migration_assets,
)
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_sql import lint_migration_file

out = {"repo_root": REPO_ROOT}
assets = resolve_migration_assets()
out["origin"] = assets.origin
out["root_in_site_packages"] = "site-packages" in str(assets.root)
manifest = load_manifest(assets=assets)  # verify_disk against the bundle
out["entries"] = len(manifest.entries)
out["baselines"] = [b.tag for b in manifest.baselines]
out["linted"] = sum(
    1 for e in manifest.entries
    if lint_migration_file(manifest.sql_path(e.id, assets.root)).statements
)
out["schema_sql"] = assets.schema_sql_path.is_file()
out["schema_seed"] = "CORE-LEDGER-SEED-BEGIN" in assets.schema_sql_path.read_text()
print("PROBE_JSON=" + json.dumps(out))
"""


def _find_latest_wheel() -> Path | None:
    if not DIST_DIR.exists():
        return None
    wheels = sorted(DIST_DIR.glob("core_runtime-*.whl"))
    return wheels[-1] if wheels else None


@pytest.mark.e2e
@pytest.mark.slow
# ID: 16c8209d-8a5a-48b0-9f73-2b1ed035e249
def test_installed_wheel_resolves_bundled_migration_assets(tmp_path: Path) -> None:
    wheel = _find_latest_wheel()
    if wheel is None:
        pytest.skip("No core_runtime-*.whl in dist/. Run `poetry build` first.")

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    bin_dir = venv_dir / "bin"
    install = subprocess.run(
        [str(bin_dir / "pip"), "install", "--quiet", str(wheel)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, f"pip install failed: {install.stderr[-1500:]}"

    workspace = tmp_path / "not-a-checkout"
    workspace.mkdir()
    (workspace / "probe.py").write_text(PROBE, encoding="utf-8")
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp_path)}
    result = subprocess.run(
        [str(bin_dir / "python"), "probe.py"],
        cwd=str(workspace),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, (
        f"probe failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
    )
    payload = json.loads(result.stdout.split("PROBE_JSON=", 1)[1])
    expected_entries = len(
        __import__("yaml").safe_load(
            (REPO_ROOT / "infra/migrations/manifest.yaml").read_text("utf-8")
        )["migrations"]["order"]
    )
    assert payload["repo_root"] is None
    assert payload["origin"] == "bundled" and payload["root_in_site_packages"]
    assert payload["entries"] == expected_entries == payload["linted"]
    assert payload["baselines"][:2] == ["v2.9.1", "v2.10.1"]
    assert payload["schema_sql"] and payload["schema_seed"]

    # The commands are mounted in the installed CLI.
    helptext = subprocess.run(
        [str(bin_dir / "core-admin"), "database", "migrate", "--help"],
        cwd=str(workspace),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert helptext.returncode == 0, helptext.stderr[-1500:]
    assert "--adopt-baseline" in helptext.stdout and "--write" in helptext.stdout
    assert "--bootstrap" not in helptext.stdout
