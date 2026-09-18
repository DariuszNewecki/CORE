"""#909 -- the prompt corpus ships with the product, byte for byte.

``src/shared/_prompts/`` is the wheel-side mirror of the repository's prompt
root (``PathResolver.prompts_dir``, today ``var/prompts/``). It is package
data, not a source of truth (ADR-161 D1a): every governed prompt change
updates source and mirror in the same commit, and this standing test is what
enforces that -- there is no runtime synchronisation.

Parity is a SHA-256 manifest over relative path for every *tracked* source
prompt file (``git ls-files``), compared against the mirror's payload files
(package markers such as ``__init__.py`` and ``__pycache__`` excluded).
Missing, extra and changed payload files all fail, and the failure message
carries the one deterministic rsync line that resyncs the mirror.

When a built wheel is present in ``dist/`` (CI's hermetic job builds one
for its e2e step), the wheel's ``shared/_prompts/`` payload must carry the
same manifest -- the property ADR-161 D3a-3 names.
"""

from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

from shared.infrastructure.bundled_prompts import is_package_marker
from shared.path_resolver import PathResolver


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PathResolver(REPO_ROOT).prompts_dir
MIRROR_ROOT = REPO_ROOT / "src" / "shared" / "_prompts"
WHEEL_PREFIX = "shared/_prompts/"
_EXCLUDED_DIRS = frozenset({"__pycache__"})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tracked_source_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", str(SOURCE_ROOT.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    prefix = SOURCE_ROOT.relative_to(REPO_ROOT).as_posix() + "/"
    return sorted(p[len(prefix) :] for p in out.split("\0") if p)


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
    f"rsync -a --delete --exclude='__init__.py' --exclude='__pycache__' "
    f"{SOURCE_ROOT.relative_to(REPO_ROOT)}/ {MIRROR_ROOT.relative_to(REPO_ROOT)}/"
)


def test_source_corpus_is_tracked_and_non_empty() -> None:
    files = _tracked_source_files()
    assert len(files) >= 150, (
        f"expected the full prompt corpus, got {len(files)} tracked files"
    )


def test_mirror_matches_tracked_source_byte_for_byte() -> None:
    source = source_manifest()
    mirror = mirror_manifest()
    missing, extra, changed = _diff(source, mirror)
    assert not (missing or extra or changed), (
        "src/shared/_prompts/ has drifted from the tracked prompt source.\n"
        f"  missing in mirror: {missing}\n"
        f"  extra in mirror:   {extra}\n"
        f"  changed:           {changed}\n"
        "Source and mirror must change in the same commit. Resync with:\n"
        f"  {RESYNC}"
    )
    assert len(mirror) == len(source)


def test_mirror_carries_only_payload_plus_package_marker() -> None:
    """Nothing but prompt payload and the importable marker lives in the mirror."""
    stray = [
        p.relative_to(MIRROR_ROOT).as_posix()
        for p in MIRROR_ROOT.rglob("*")
        if p.is_file()
        and not (_EXCLUDED_DIRS & set(p.relative_to(MIRROR_ROOT).parts))
        and p.suffix == ".py"
        and not is_package_marker(p.name)
    ]
    assert stray == [], f"non-marker python files in the prompt mirror: {stray}"
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
        f"{wheel.name} does not carry the tracked prompt corpus byte-for-byte.\n"
        f"  missing: {missing}\n  extra: {extra}\n  changed: {changed}"
    )
    assert len(bundled) == len(source)
