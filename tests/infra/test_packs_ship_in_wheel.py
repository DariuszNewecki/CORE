"""The open governance packs have one source and ship with the product.

``src/shared/_packs/`` is the only pack registry (ADR-149, #1387): CORE's own
checkout reads it through the bundled lookup, and the wheel carries it as
package data. Until #1387 a top-level ``packs/`` was copied here and this test
compared the two.

Regression (2026-10-02): the 2.10.2 wheel carried no packs, so
``core-admin project adopt-pack`` found nothing for every pip user. When a
built wheel is present in ``dist/``, its ``shared/_packs/`` payload must equal
the tracked registry byte for byte.
"""

from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

from shared.infrastructure.bundled_packs import is_package_marker, pack_registry_dir


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS = REPO_ROOT / "src" / "shared" / "_packs"
WHEEL_PREFIX = "shared/_packs/"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tracked(path: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", path],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return sorted(p for p in out.split("\0") if p)


def registry_manifest() -> dict[str, str]:
    prefix = "src/shared/_packs/"
    return {
        rel[len(prefix) :]: _sha256((REPO_ROOT / rel).read_bytes())
        for rel in _tracked(prefix)
        if not is_package_marker(rel[len(prefix) :])
    }


def test_the_registry_is_tracked_once_in_src() -> None:
    assert len(registry_manifest()) >= 3
    assert _tracked("packs") == [], "a second pack registry is back"


def test_cores_checkout_reads_the_packaged_registry() -> None:
    with pack_registry_dir(REPO_ROOT) as registry:
        assert sorted(p.name for p in registry.glob("*.yaml")) == sorted(
            registry_manifest()
        )


def test_built_wheel_carries_the_registry() -> None:
    dist = REPO_ROOT / "dist"
    wheels = sorted(dist.glob("core_runtime-*.whl")) if dist.exists() else []
    if not wheels:
        pytest.skip("No core_runtime-*.whl in dist/. Run `poetry build` first.")
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(wheels[-1]) as zf:
        for name in zf.namelist():
            rel = name[len(WHEEL_PREFIX) :]
            if name.startswith(WHEEL_PREFIX) and not name.endswith("/"):
                if not is_package_marker(rel):
                    manifest[rel] = _sha256(zf.read(name))
    assert manifest == registry_manifest()
