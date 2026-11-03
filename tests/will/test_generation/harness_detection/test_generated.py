from __future__ import annotations

from pathlib import Path

from will.test_generation.harness_detection import HarnessDetector


# ID: 1022aee0-5b75-40fd-afc3-016bc9cf5d5a
def test_HarnessDetector_detect(tmp_path):
    repo_root = tmp_path
    tests_dir = repo_root / "tests"
    tests_dir.mkdir()
    conftest = tests_dir / "conftest.py"
    conftest.write_text(
        "import sqlalchemy\n"
        "def session():\n"
        "    pass\n"
        "def engine():\n"
        "    pass\n"
        "from pytest_postgresql import postgresql_proc\n"
    )

    detector = HarnessDetector(repo_root=Path(repo_root))
    result = detector.detect()

    assert result.has_tests_conftest is True
    assert result.has_pytest_postgresql_signals is True
    assert result.has_sqlalchemy_fixture_signals is True
    assert any("tests/conftest.py" in note for note in result.notes)


import tempfile


# ID: dcba9375-bfb0-42ff-9d19-2c9ebb8825ee
def test_HarnessDetector() -> None:
    repo_root = Path(tempfile.mkdtemp())
    tests_dir = repo_root / "tests"
    tests_dir.mkdir()
    conftest = tests_dir / "conftest.py"
    conftest.write_text(
        "import pytest\n"
        "from sqlalchemy import create_engine\n"
        "from sqlalchemy.orm import sessionmaker, Session\n"
        "postgresql_proc = None\n",
        encoding="utf-8",
    )

    detector = HarnessDetector(repo_root)
    signals = detector.detect()

    assert signals.has_tests_conftest is True
    assert signals.has_pytest_postgresql_signals is True
    assert signals.has_sqlalchemy_fixture_signals is True
    assert any("tests/conftest.py" in note for note in signals.notes)
