# tests/features/self_healing/test_header_service.py
"""
Complete constitutional test suite for HeaderService.
Works with tmp_path — no more subpath errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

from src.features.self_healing.header_service import HeaderService


@pytest.fixture
def header_service(tmp_path: Path, monkeypatch: MonkeyPatch) -> HeaderService:
    """Create HeaderService with fake repo root."""
    # Make the temporary directory act as the real repo root
    monkeypatch.setattr("shared.config.settings.REPO_PATH", tmp_path)
    monkeypatch.chdir(tmp_path)  # some tests use Path.cwd()
    return HeaderService()


@pytest.fixture
def src_file(tmp_path: Path) -> Path:
    """Create a Python file inside src/ subdirectory."""
    file = tmp_path / "src" / "module" / "example.py"
    file.parent.mkdir(parents=True, exist_ok=True)
    return file


def test_detect_missing_header(header_service: HeaderService, src_file: Path) -> None:
    src_file.write_text("def foo():\n    return 42\n")
    issues = header_service.analyze([str(src_file)])
    assert len(issues) == 1
    assert issues[0]["issue"] == "missing_header"
    assert issues[0]["expected_header"] == "# src/module/example.py"


def test_detect_incorrect_header(header_service: HeaderService, src_file: Path) -> None:
    src_file.write_text("# wrong/path.py\nx = 1\n")
    issues = header_service.analyze([str(src_file)])
    assert len(issues) == 1
    assert issues[0]["issue"] == "incorrect_header"
    assert issues[0]["expected_header"] == "# src/module/example.py"


def test_correct_header_no_issue(header_service: HeaderService, src_file: Path) -> None:
    src_file.write_text("# src/module/example.py\n\ndef main():\n    pass\n")
    issues = header_service.analyze([str(src_file)])
    assert issues == []


def test_fix_missing_header(header_service: HeaderService, src_file: Path) -> None:
    src_file.write_text("print('hello')\n")
    header_service._fix([str(src_file)])
    content = src_file.read_text()
    assert content.startswith("# src/module/example.py\n")


def test_fix_wrong_header(header_service: HeaderService, src_file: Path) -> None:
    src_file.write_text("# src/wrong.py\n\nimport os\n")
    header_service._fix([str(src_file)])
    assert src_file.read_text().startswith("# src/module/example.py\n")
    assert "import os" in src_file.read_text()


def test_fix_preserves_blank_lines(
    header_service: HeaderService, src_file: Path
) -> None:
    src_file.write_text("\n\n# wrong\n\ndef x():\n    pass\n")
    header_service._fix([str(src_file)])
    lines = src_file.read_text().splitlines()
    assert lines[0] == "# src/module/example.py"
    assert lines[1] == ""
    assert lines[2] == ""


def test_correct_header_untouched(
    header_service: HeaderService, src_file: Path
) -> None:
    original = "# src/module/example.py\n\nimport math\n\ndef foo():\n    return 42\n"
    src_file.write_text(original)
    header_service._fix([str(src_file)])
    assert src_file.read_text() == original


def test_analyze_all_finds_offenders(
    header_service: HeaderService, tmp_path: Path
) -> None:
    good = tmp_path / "src" / "good.py"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text("# src/good.py\npass\n")

    bad = tmp_path / "src" / "bad.py"
    bad.write_text("no header\n")

    issues = header_service.analyze_all()
    assert len(issues) == 1
    assert Path(issues[0]["file"]).name == "bad.py"


def test_fix_all_repairs_everything(
    header_service: HeaderService, tmp_path: Path
) -> None:
    f1 = tmp_path / "src" / "a.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("print('no header')\n")

    f2 = tmp_path / "src" / "b.py"
    f2.write_text("# wrong\n")

    header_service._fix_all()

    assert f1.read_text().startswith("# src/a.py\n")
    assert f2.read_text().startswith("# src/b.py\n")


def test_non_src_files_are_ignored(
    header_service: HeaderService, tmp_path: Path
) -> None:
    file = tmp_path / "tests" / "test_something.py"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("def test(): pass\n")
    issues = header_service.analyze_all()
    assert not any(str(f["file"]).endswith("test_something.py") for f in issues)
