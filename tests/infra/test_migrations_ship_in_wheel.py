"""ADR-162 D8 (U7) -- the migration assets ship with the product, byte for byte.

``src/shared/_migrations/`` is the wheel-side mirror of
``infra/migrations/manifest.yaml``, every ``.sql`` file the manifest lists
under ``infra/scripts/migrations/`` and the repository-root ``schema.sql``,
in the same relative layout. It is package data, not a source of truth:
every change updates source and mirror in the same commit, and this standing
test enforces that -- there is no runtime synchronisation (the pattern
``shared/_prompts/`` established in #909).

Parity is a SHA-256 manifest over relative path; missing, extra and changed
payload files all fail, and the failure message carries the deterministic
commands that resync the mirror.

When a built wheel is present in ``dist/`` (CI's hermetic job builds one for
its e2e step), the wheel's ``shared/_migrations/`` payload must carry the same
manifest. Resolution from the bundle is proven in-process here (the resolver
with no source tree) and from a clean install in
``test_migrations_installed_wheel.py``.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from shared.infrastructure.repositories.db import common
from shared.infrastructure.repositories.db.manifest import load_manifest
from shared.infrastructure.repositories.db.migration_sql import lint_migration_file


REPO_ROOT = Path(__file__).resolve().parents[2]
MIRROR_ROOT = REPO_ROOT / "src" / "shared" / "_migrations"
WHEEL_PREFIX = "shared/_migrations/"
_PACKAGE_MARKERS = frozenset({"__init__.py"})
_EXCLUDED_DIRS = frozenset({"__pycache__"})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_manifest() -> dict[str, str]:
    """{relative path: sha256} of every asset the bundle must carry."""
    manifest = load_manifest(verify_disk=False)
    rel_paths = ["infra/migrations/manifest.yaml", "schema.sql"] + [
        str(Path("infra/scripts/migrations") / mig) for mig in manifest.order
    ]
    return {rel: _sha256((REPO_ROOT / rel).read_bytes()) for rel in rel_paths}


def _mirror_manifest() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in MIRROR_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(MIRROR_ROOT)
        if rel.name in _PACKAGE_MARKERS or set(rel.parts) & _EXCLUDED_DIRS:
            continue
        out[str(rel)] = _sha256(path.read_bytes())
    return out


def _resync_hint(missing: list[str], extra: list[str], changed: list[str]) -> str:
    lines = ["mirror out of sync with source; resync with:"]
    for rel in missing + changed:
        lines.append(f"  cp {rel} src/shared/_migrations/{rel}")
    for rel in extra:
        lines.append(f"  git rm src/shared/_migrations/{rel}")
    return "\n".join(lines)


# ID: 8ae5f57f-9105-4c4a-bd8c-b3780ff9f234
def test_mirror_matches_source_byte_for_byte() -> None:
    source, mirror = _source_manifest(), _mirror_manifest()
    missing = sorted(set(source) - set(mirror))
    extra = sorted(set(mirror) - set(source))
    changed = sorted(k for k in set(source) & set(mirror) if source[k] != mirror[k])
    assert not (missing or extra or changed), _resync_hint(missing, extra, changed)


# ID: 67368111-b1ca-4476-96e0-aae1991ef522
def test_mirror_carries_exactly_the_manifest_sql_and_nothing_else() -> None:
    """Non-migration files in the migrations directory (Python scripts, the
    ROLLOUT runbook) are not assets; the mirror's directory must satisfy the
    manifest's own disk verification."""
    mirror_sql = sorted(
        p.name for p in (MIRROR_ROOT / "infra" / "scripts" / "migrations").iterdir()
    )
    assert mirror_sql == sorted(load_manifest(verify_disk=False).order)


# ID: 6a5cad97-4fe6-4777-8536-aefdb6862691
def test_resolver_uses_the_bundle_when_there_is_no_source_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common, "REPO_ROOT", None)
    assets = common.resolve_migration_assets()
    assert assets.origin == "bundled"
    assert assets.root == MIRROR_ROOT
    manifest = load_manifest(assets=assets)  # verify_disk against the bundle
    assert manifest.order == load_manifest().order
    for entry in manifest.entries:
        lint_migration_file(manifest.sql_path(entry.id, assets.root))
    assert (
        assets.schema_sql_path.read_bytes() == (REPO_ROOT / "schema.sql").read_bytes()
    )


# ID: a019bf3d-5569-43c8-8289-72535d4eb5a2
def test_resolver_prefers_the_source_tree_when_it_is_the_checkout() -> None:
    assets = common.resolve_migration_assets()
    assert assets.origin == "source" and assets.root == REPO_ROOT


def _wheel() -> Path | None:
    wheels = sorted((REPO_ROOT / "dist").glob("core_runtime-*.whl"))
    return wheels[-1] if wheels else None


# ID: 4154ac2a-5590-480b-b626-5c669b636e89
def test_built_wheel_carries_the_same_assets() -> None:
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
    assert in_wheel == _source_manifest()
