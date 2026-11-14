"""A fake installed plug-in for tests (ADR-177): a package and its
``.dist-info`` written to a temporary directory on ``sys.path``, so
``importlib.metadata`` finds it as if it were pip-installed."""

from __future__ import annotations

import importlib
import sys
import textwrap
from pathlib import Path

import pytest


ENGINE_SOURCE = """
from pathlib import Path
from typing import Any

from mind.engine_api import BaseEngine, EngineResult, EvidenceClass


class {class_name}(BaseEngine):
    engine_id = "{engine_id}"
    evidence_class = EvidenceClass.PROVEN

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        return EngineResult(ok=True, message="ok", violations=[], engine_id=self.engine_id)
"""


def install_fake_plugin(
    monkeypatch: pytest.MonkeyPatch,
    site: Path,
    *,
    dist_name: str,
    package: str,
    manifest: str,
    files: dict[str, str] | None = None,
    version: str = "0.1.0",
) -> Path:
    """Write ``package`` (with ``MANIFEST = <manifest>`` in ``__init__``) and
    its dist-info under ``site``; put ``site`` on ``sys.path``. Returns the
    package directory. ``files`` adds files relative to the package."""
    package_dir = site / package
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text(f"MANIFEST = {manifest}\n")
    written = [f"{package}/__init__.py"]
    for rel, content in (files or {}).items():
        target = package_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content))
        written.append(f"{package}/{rel}")
    dist_info = site / f"{dist_name.replace('-', '_')}-{version}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {dist_name}\nVersion: {version}\n"
    )
    (dist_info / "entry_points.txt").write_text(
        f"[core.plugins]\n{dist_name} = {package}:MANIFEST\n"
    )
    record = [f"{path},," for path in written]
    record += [
        f"{dist_info.name}/{n},," for n in ("METADATA", "entry_points.txt", "RECORD")
    ]
    (dist_info / "RECORD").write_text("\n".join(record) + "\n")
    monkeypatch.syspath_prepend(str(site))
    importlib.invalidate_caches()
    for name in [m for m in sys.modules if m == package or m.startswith(f"{package}.")]:
        monkeypatch.delitem(sys.modules, name)
    return package_dir
