"""#909, #1387 -- the prompt corpus has one source and ships with the product.

``src/shared/_prompts/`` is the only prompt source: CORE's law points its
prompt root there (``prompts.root`` in governance_paths.yaml) and the wheel
carries it as package data. There is no second copy to keep in step; until
#1387 the source sat in ``var/prompts/`` and this test compared it with a
mirror.

When a built wheel is present in ``dist/`` (CI's hermetic job builds one
for its e2e step), the wheel's ``shared/_prompts/`` payload must equal the
tracked corpus byte for byte.
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
PROMPTS = REPO_ROOT / "src" / "shared" / "_prompts"
WHEEL_PREFIX = "shared/_prompts/"


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


def corpus_manifest() -> dict[str, str]:
    prefix = "src/shared/_prompts/"
    return {
        rel[len(prefix) :]: _sha256((REPO_ROOT / rel).read_bytes())
        for rel in _tracked(prefix)
        if not is_package_marker(rel[len(prefix) :])
    }


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


def test_the_corpus_is_tracked_once_in_src() -> None:
    assert len(corpus_manifest()) >= 150
    assert _tracked("var/prompts") == [], "a second prompt source is back"


def test_cores_prompt_root_is_the_packaged_source() -> None:
    assert PathResolver(REPO_ROOT).prompts_dir == PROMPTS


def test_the_corpus_carries_only_payload_plus_package_marker() -> None:
    stray = [
        p.relative_to(PROMPTS).as_posix()
        for p in PROMPTS.rglob("*.py")
        if "__pycache__" not in p.parts and not is_package_marker(p.name)
    ]
    assert stray == [], f"non-marker python files in the prompt corpus: {stray}"
    assert (PROMPTS / "__init__.py").is_file()


def test_built_wheel_carries_the_corpus() -> None:
    dist = REPO_ROOT / "dist"
    wheels = sorted(dist.glob("core_runtime-*.whl")) if dist.exists() else []
    if not wheels:
        pytest.skip("No core_runtime-*.whl in dist/. Run `poetry build` first.")
    wheel = wheels[-1]
    assert _wheel_manifest(wheel) == corpus_manifest(), (
        f"{wheel.name} does not carry src/shared/_prompts/ byte for byte"
    )
