"""write_runtime_text normalizes trailing newlines.

Pins that content lacking a final newline is written with one. The
normalization happens after all validation (syntax gate, ID anchors)
and before the atomic write, so the bytes on disk always end with
exactly one '\\n'. Keeps diffs minimal and POSIX-friendly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.storage.file_handler import FileHandler


# ID: f3a17b9c-4d2e-4c81-b5e9-7a3f2c8e4a90
def test_write_runtime_text_appends_trailing_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fh = FileHandler(str(tmp_path))
    monkeypatch.setattr(fh, "_guard_paths", lambda *args, **kwargs: None)

    fh.write_runtime_text("note.txt", "hello world")

    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "hello world\n"
