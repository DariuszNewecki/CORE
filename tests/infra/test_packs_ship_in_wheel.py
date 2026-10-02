"""The open governance packs ship with the product, byte for byte.

``src/shared/_packs/`` is the wheel-side mirror of the repository's top-level
``packs/`` registry (ADR-149). It is package data, not a source of truth:
every governed pack change updates source and mirror in the same commit, and
this standing test enforces that -- there is no runtime synchronisation.
Same pattern as the prompt corpus (#909, ``test_prompts_ship_in_wheel.py``).

Regression (2026-10-02): the 2.10.2 wheel carried no packs, so
``core-admin project adopt-pack`` found nothing for every pip user.

When a built wheel is present in ``dist/``, its ``shared/_packs/`` payload
must carry the same manifest.
"""

from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

from shared.infrastructure.bundled_packs import is_package_marker


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "packs"
MIRROR_ROOT = REPO_ROOT / "src" / "shared" / "_packs"
WHEEL_PREFIX = "shared/_packs/"
_EXCLUDED_DIRS = frozenset({"__pycache__"})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tracked_source_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "packs"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return sorted(p[len("packs/") :] for p in out.split("\0") if p)


def source_manifest() -> dict[str, str]:
    return {
        rel: _sha256((SOURCE_ROOT / rel).read_bytes())
        for rel in _tracked_source_files()
    }


def mirror_manifest() -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(MIRROR_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(MIRROR_ROOT).as_posix()
        if _EXCLUDED_DIRS & set(Path(rel).parts) or is_package_marker(rel):
            continue
        manifest[rel] = _sha256(path.read_bytes())
    return manifest


def _wheel_manifest(wheel: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(wheel) as zf:
        for name in zf.namelist():
            if not name.startswith(WHEEL_PREFIX) or name.endswith("/"):
                continue
            rel = name[len(WHEEL_PREFIX) :]
            if is_package_marker(rel):
                continue
            manifest[rel] = _sha256(zf.read(name))
    return manifest


def _diff(
    source: dict[str, str], other: dict[str, str]
) -> tuple[list[str], list[str], list[str]]:
    missing = sorted(set(source) - set(other))
    extra = sorted(set(other) - set(source))
    changed = sorted(k for k in set(source) & set(other) if source[k] != other[k])
    return missing, extra, changed


RESYNC = (
    "rsync -a --delete --exclude='__init__.py' --exclude='__pycache__' "
    "packs/ src/shared/_packs/"
)


def test_source_registry_is_tracked_and_non_empty() -> None:
    files = _tracked_source_files()
    assert len(files) >= 3, f"expected the open pack registry, got {files}"


def test_mirror_matches_tracked_source_byte_for_byte() -> None:
    source = source_manifest()
    mirror = mirror_manifest()
    missing, extra, changed = _diff(source, mirror)
    assert not (missing or extra or changed), (
        "src/shared/_packs/ has drifted from the tracked pack registry.\n"
        f"  missing in mirror: {missing}\n"
        f"  extra in mirror:   {extra}\n"
        f"  changed:           {changed}\n"
        "Source and mirror must change in the same commit. Resync with:\n"
        f"  {RESYNC}"
    )


def test_mirror_is_importable_package() -> None:
    assert (MIRROR_ROOT / "__init__.py").is_file()


def test_built_wheel_carries_the_same_manifest() -> None:
    dist = REPO_ROOT / "dist"
    wheels = sorted(dist.glob("core_runtime-*.whl")) if dist.exists() else []
    if not wheels:
        pytest.skip("No core_runtime-*.whl in dist/. Run `poetry build` first.")
    wheel = wheels[-1]
    source = source_manifest()
    bundled = _wheel_manifest(wheel)
    missing, extra, changed = _diff(source, bundled)
    assert not (missing or extra or changed), (
        f"{wheel.name} does not carry the tracked pack registry byte-for-byte.\n"
        f"  missing: {missing}\n  extra: {extra}\n  changed: {changed}"
    )
