"""The public GRC catalogs ship with the product, byte for byte.

ADR-116 D6 (amended 2026-10-03): the public tier is part of the open product
and ships in the ``core-runtime`` wheel; licensed and internal catalogs never
do. ``src/shared/_grc_catalogs/`` is the wheel-side mirror of the repository's
``grc-catalogs/inventory.yaml`` and ``grc-catalogs/public/``. It is package
data, not a source of truth: every catalog change updates source and mirror
in the same commit, and this standing test enforces that. Same pattern as the
packs (``test_packs_ship_in_wheel.py``).

When a built wheel is present in ``dist/``, its ``shared/_grc_catalogs/``
payload must carry the same manifest.
"""

from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "grc-catalogs"
MIRROR_ROOT = REPO_ROOT / "src" / "shared" / "_grc_catalogs"
WHEEL_PREFIX = "shared/_grc_catalogs/"
RESYNC = (
    "rsync -a --delete --exclude='__init__.py' --exclude='__pycache__' "
    "--exclude='licensed' --exclude='internal' grc-catalogs/ src/shared/_grc_catalogs/"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _shipped(rel: str) -> bool:
    """The open part of the corpus: the inventory and the public tier."""
    return rel == "inventory.yaml" or rel.startswith("public/")


def source_manifest() -> dict[str, str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "grc-catalogs"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    rels = sorted(p[len("grc-catalogs/") :] for p in out.split("\0") if p)
    return {
        rel: _sha256((SOURCE_ROOT / rel).read_bytes()) for rel in rels if _shipped(rel)
    }


def mirror_manifest() -> dict[str, str]:
    return {
        path.relative_to(MIRROR_ROOT).as_posix(): _sha256(path.read_bytes())
        for path in sorted(MIRROR_ROOT.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != "__init__.py"
    }


def _wheel_manifest(wheel: Path) -> dict[str, str]:
    with zipfile.ZipFile(wheel) as zf:
        return {
            name[len(WHEEL_PREFIX) :]: _sha256(zf.read(name))
            for name in zf.namelist()
            if name.startswith(WHEEL_PREFIX)
            and not name.endswith("/")
            and not name.endswith("__init__.py")
        }


def test_source_corpus_is_tracked_and_non_empty() -> None:
    source = source_manifest()
    assert "inventory.yaml" in source
    assert any(rel.endswith("/catalog.yaml") for rel in source)


def test_mirror_matches_public_source_byte_for_byte() -> None:
    source, mirror = source_manifest(), mirror_manifest()
    assert mirror == source, (
        "src/shared/_grc_catalogs/ has drifted from grc-catalogs/ "
        "(inventory.yaml + public/).\n"
        f"  missing in mirror: {sorted(set(source) - set(mirror))}\n"
        f"  extra in mirror:   {sorted(set(mirror) - set(source))}\n"
        "Source and mirror must change in the same commit. Resync with:\n"
        f"  {RESYNC}"
    )


def test_mirror_carries_no_licensed_or_internal_tier() -> None:
    tiers = {Path(rel).parts[0] for rel in mirror_manifest() if "/" in rel}
    assert tiers == {"public"}


def test_mirror_is_importable_package() -> None:
    assert (MIRROR_ROOT / "__init__.py").is_file()


def test_built_wheel_carries_the_same_manifest() -> None:
    dist = REPO_ROOT / "dist"
    wheels = sorted(dist.glob("core_runtime-*.whl")) if dist.exists() else []
    if not wheels:
        pytest.skip("No core_runtime-*.whl in dist/. Run `poetry build` first.")
    wheel = wheels[-1]
    newest_mirror = max(
        p.stat().st_mtime for p in MIRROR_ROOT.rglob("*") if p.is_file()
    )
    if wheel.stat().st_mtime < newest_mirror:
        pytest.skip(f"{wheel.name} predates the current mirror. Run `poetry build`.")
    assert _wheel_manifest(wheel) == source_manifest()
