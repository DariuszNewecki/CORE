# tests/body/infrastructure/storage/test_file_handler__orphan_shadow_preserved.py

"""FileHandler's write-time anchor injection (ADR-097 D4) must not regenerate
an identity that an orphaned anchor still carries (linkage.no_orphan_ids).

This is the layer the e2e fix.ids test exposed: fix.ids correctly skipped the
shadowed symbol, then the write of the same file for an unrelated symbol
re-injected a fresh anchor one layer down. Real writes under var/tmp/; the
IntentGuard call is stubbed exactly as in test_file_handler__regression_matrix.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

import pytest

from body.infrastructure.storage.file_handler import FileHandler


_ORPHAN_LINE = "# ID: a1fb17c6-a4a7-4503-9103-491b28305c2d"
_FRESH = re.compile(r"^# ID: [0-9a-f-]{36}$", re.MULTILINE)

_SOURCE = (
    f"{_ORPHAN_LINE}\n"
    "\n"
    "def shadowed():\n"
    "    return 1\n"
    "\n"
    "\n"
    "def unrelated():\n"
    "    return 2\n"
)


@pytest.fixture
def repo_root() -> Path:
    here = Path(__file__).resolve()
    var_tmp = here.parents[3] / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="fh_orphan_", dir=str(var_tmp)))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fh(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> FileHandler:
    handler = FileHandler(str(repo_root))
    monkeypatch.setattr(handler, "_guard_paths", lambda *a, **kw: None)
    return handler


def test_write_preserves_orphan_and_does_not_regenerate_shadowed_symbol(
    fh: FileHandler, repo_root: Path
) -> None:
    fh.write_runtime_text("src/probe.py", _SOURCE)
    written = (repo_root / "src" / "probe.py").read_text(encoding="utf-8")

    # orphan bytes untouched: anchor, blank line, def -- exactly as given
    assert f"{_ORPHAN_LINE}\n\ndef shadowed" in written
    assert written.count(_ORPHAN_LINE) == 1
    # the shadowed symbol got no fresh anchor
    assert not re.search(r"^# ID: [0-9a-f-]{36}\ndef shadowed", written, re.MULTILINE)
    # the unrelated symbol did
    assert re.search(r"^# ID: [0-9a-f-]{36}\ndef unrelated", written, re.MULTILINE)
    # exactly one line was added in total
    assert len(written.splitlines()) == len(_SOURCE.splitlines()) + 1
    assert len(_FRESH.findall(written)) == 2  # the orphan + the one fresh anchor


def test_write_without_orphans_still_injects(fh: FileHandler, repo_root: Path) -> None:
    fh.write_runtime_text("src/plain.py", "def hello():\n    return 1\n")
    written = (repo_root / "src" / "plain.py").read_text(encoding="utf-8")
    assert re.search(r"^# ID: [0-9a-f-]{36}\ndef hello", written, re.MULTILINE)
