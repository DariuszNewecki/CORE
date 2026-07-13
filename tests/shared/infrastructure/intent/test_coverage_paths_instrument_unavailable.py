"""uncovered_source_files must raise InstrumentUnavailable — not return [] —
when the coverage source root is missing (#765/T1.3).

An empty list previously read as "all files covered"; the raise lets callers
post an instrument-unavailable observation instead of a false all-clear.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.test_coverage_paths import (
    InstrumentUnavailable,
    uncovered_source_files,
)


def test_missing_source_root_raises_instrument_unavailable(tmp_path: Path) -> None:
    """tmp_path has no src/ — the scan cannot run, so it must raise."""
    with pytest.raises(InstrumentUnavailable) as exc_info:
        uncovered_source_files(tmp_path, {"source_root": "src"})
    assert "source root not found" in str(exc_info.value)


def test_present_source_root_scans_normally(tmp_path: Path) -> None:
    """A present (even if empty) source root scans without raising —
    an empty result here is genuinely 'nothing uncovered', not 'couldn't
    look'."""
    (tmp_path / "src").mkdir()
    result = uncovered_source_files(tmp_path, {"source_root": "src"})
    assert result == []


def test_uncovered_file_detected(tmp_path: Path) -> None:
    """A source file with no matching test is reported as uncovered."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "module.py").write_text("x = 1\n", encoding="utf-8")
    result = uncovered_source_files(
        tmp_path,
        {
            "source_root": "src",
            "test_root": "tests",
            "test_file_suffix": "/test_generated.py",
            "excluded_filenames": ["__init__.py"],
        },
    )
    assert "src/pkg/module.py" in result
