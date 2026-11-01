"""ADR-162 D8 (U7), #1387 -- the migration assets have one source and ship
with the product.

``src/shared/_migrations/`` is the only home of ``infra/migrations/
manifest.yaml``, every ``.sql`` file the manifest lists under
``infra/scripts/migrations/`` and ``schema.sql``, in that relative layout.
The resolver reads this package in a checkout and in an installed wheel
alike; there is no second copy to keep in step. Until #1387 the source sat at
the repository root and this test compared it with a mirror.

When a built wheel is present in ``dist/`` (CI's hermetic job builds one for
its e2e step), the wheel's ``shared/_migrations/`` payload must equal the
tracked assets byte for byte. Resolution from a clean install is proven in
``test_migrations_installed_wheel.py``.
"""

from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

from shared.infrastructure.repositories.db.common import resolve_migration_assets
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_sql import lint_migration_file


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS = REPO_ROOT / "src" / "shared" / "_migrations"
ASSETS_PREFIX = "src/shared/_migrations/"
WHEEL_PREFIX = "shared/_migrations/"
_PACKAGE_MARKERS = frozenset({"__init__.py"})
# The former root copies (#1387); none may be tracked again.
_ROOT_COPIES = ("schema.sql", "infra/migrations")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tracked(*paths: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return sorted(p for p in out.split("\0") if p)


def _assets_manifest() -> dict[str, str]:
    """{path relative to the package: sha256} of every tracked asset."""
    return {
        rel[len(ASSETS_PREFIX) :]: _sha256((REPO_ROOT / rel).read_bytes())
        for rel in _tracked(ASSETS_PREFIX)
        if Path(rel).name not in _PACKAGE_MARKERS
    }


def _expected_assets() -> list[str]:
    manifest = load_manifest(verify_disk=False)
    return sorted(
        ["infra/migrations/manifest.yaml", "schema.sql"]
        + [f"infra/scripts/migrations/{mig}" for mig in manifest.order]
    )


# ID: 8ae5f57f-9105-4c4a-bd8c-b3780ff9f234
def test_the_assets_are_tracked_once_in_src() -> None:
    assert sorted(_assets_manifest()) == _expected_assets()
    assert _tracked(*_ROOT_COPIES) == [], "a second migration source is back"
    root_sql = [p for p in _tracked("infra/scripts/migrations") if p.endswith(".sql")]
    assert root_sql == [], f"migration SQL outside src/shared/_migrations: {root_sql}"


# ID: 6a5cad97-4fe6-4777-8536-aefdb6862691
def test_the_resolver_reads_the_packaged_assets() -> None:
    assets = resolve_migration_assets()
    assert assets.origin == "bundled"
    assert assets.root == ASSETS
    manifest = load_manifest(assets=assets)  # verify_disk against the package
    for entry in manifest.entries:
        lint_migration_file(manifest.sql_path(entry.id, assets.root))
    assert assets.schema_sql_path == ASSETS / "schema.sql"


def _wheel() -> Path | None:
    wheels = sorted((REPO_ROOT / "dist").glob("core_runtime-*.whl"))
    return wheels[-1] if wheels else None


# ID: 4154ac2a-5590-480b-b626-5c669b636e89
def test_built_wheel_carries_the_assets() -> None:
    wheel = _wheel()
    if wheel is None:
        pytest.skip("no built wheel in dist/ (CI's hermetic job builds one)")
    with zipfile.ZipFile(wheel) as zf:
        in_wheel = {
            name[len(WHEEL_PREFIX) :]: _sha256(zf.read(name))
            for name in zf.namelist()
            if name.startswith(WHEEL_PREFIX)
            and not name.endswith("/")
            and Path(name).name not in _PACKAGE_MARKERS
        }
    assert in_wheel == _assets_manifest(), (
        f"{wheel.name} does not carry src/shared/_migrations/ byte for byte"
    )
