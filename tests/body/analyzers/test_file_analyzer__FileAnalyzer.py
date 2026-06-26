"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/analyzers/file_analyzer.py
- Symbol: FileAnalyzer
- Generated: 2026-01-10 23:43:17
- 2026-06-07 (#572 Cat B batch 12): FileAnalyzer's execute() now requires
  a CoreContext with git_service.repo_path (source returns
  "FileAnalyzer requires CoreContext with git_service" otherwise — see
  file_analyzer.py:46-58). Replaced 7 bare FileAnalyzer() calls with an
  ``analyzer`` fixture wrapping a MagicMock CoreContext. The 8th test
  (test_fileanalyzer_with_context) was already constructing FileAnalyzer
  with a MockContext and is left untouched.

  Additionally, every NamedTemporaryFile call now passes
  ``dir=_REPO_TMP_DIR`` per CLAUDE.md — pytest's default temp paths leak
  into /tmp which is constitutionally forbidden in this repo.
- 2026-06-19 (#675 smoke fix): _REPO_TMP_DIR was hardcoded to the server's
  ``/opt/dev/CORE/var/tmp`` and broke on any other checkout (CI runs at
  ``/home/runner/work/CORE/CORE``). Now resolved relative to this file's
  location, and the dir is created on demand (``var/tmp`` is gitignored, so
  it is absent on a fresh checkout).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from body.analyzers.file_analyzer import FileAnalyzer


# Repo root resolved from this file: tests/body/analyzers/<this> → parents[3].
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_TMP_DIR = str(_REPO_ROOT / "var" / "tmp")
# var/tmp is gitignored, so it does not exist on a fresh checkout (e.g. CI).
os.makedirs(_REPO_TMP_DIR, exist_ok=True)


@pytest.fixture
def analyzer():
    """FileAnalyzer backed by a minimal MagicMock CoreContext.

    Source's execute() reads ``context.git_service.repo_path`` to compute
    rel_path for the result metadata; that's the only attribute the
    tests below exercise. Pointing at the repo root means tempfiles
    written under ``var/tmp/`` resolve to a clean rel_path."""
    ctx = MagicMock()
    ctx.git_service.repo_path = _REPO_ROOT
    return FileAnalyzer(context=ctx)


async def test_fileanalyzer_file_not_found(analyzer):
    """Test handling of non-existent file."""
    result = await analyzer.execute("non_existent_file.py")
    assert not result.ok
    assert "error" in result.data
    assert "File not found" in result.data["error"]


async def test_fileanalyzer_syntax_error(analyzer):
    """Test handling of file with syntax errors."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=_REPO_TMP_DIR
    ) as f:
        f.write("def invalid python syntax")
        temp_path = f.name
    try:
        result = await analyzer.execute(temp_path)
        assert not result.ok
        assert "error" in result.data
        assert "Syntax error" in result.data["error"]
    finally:
        os.unlink(temp_path)


async def test_fileanalyzer_empty_file(analyzer):
    """Test analysis of empty Python file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=_REPO_TMP_DIR
    ) as f:
        f.write("")
        temp_path = f.name
    try:
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["file_type"] == "mixed_module"
        assert not result.data["has_sqlalchemy"]
        assert not result.data["has_async"]
        assert result.data["class_count"] == 0
        assert result.data["function_count"] == 0
        assert result.data["complexity"] == "low"
        assert result.metadata["line_count"] == 0
        assert result.metadata["total_definitions"] == 0
    finally:
        os.unlink(temp_path)


async def test_fileanalyzer_sqlalchemy_model(analyzer):
    """Test detection of SQLAlchemy model file."""
    content = "\nfrom sqlalchemy import Column, Integer, String\nfrom sqlalchemy.orm import Mapped, mapped_column\nfrom sqlalchemy.ext.declarative import declarative_base\n\nBase = declarative_base()\n\nclass User(Base):\n    __tablename__ = 'users'\n    \n    id: Mapped[int] = mapped_column(Integer, primary_key=True)\n    name = Column(String(50))\n    \n    def __repr__(self):\n        return f\"<User(id={self.id}, name={self.name})>\"\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=_REPO_TMP_DIR
    ) as f:
        f.write(content)
        temp_path = f.name
    try:
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["file_type"] == "sqlalchemy_model"
        assert result.data["has_sqlalchemy"]
        assert result.data["class_count"] == 1
        assert result.data["function_count"] == 1
        assert result.confidence == 0.95
    finally:
        os.unlink(temp_path)


async def test_fileanalyzer_function_module(analyzer):
    """Test detection of function-only module."""
    content = '\ndef calculate_sum(a, b):\n    return a + b\n\ndef calculate_product(a, b):\n    return a * b\n\ndef format_result(value):\n    return f"Result: {value}"\n\ndef validate_input(value):\n    return isinstance(value, (int, float))\n'
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=_REPO_TMP_DIR
    ) as f:
        f.write(content)
        temp_path = f.name
    try:
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["file_type"] == "function_module"
        assert result.data["function_count"] == 4
        assert result.data["class_count"] == 0
        assert not result.data["has_async"]
        assert not result.data["has_sqlalchemy"]
        assert result.confidence == 0.85
    finally:
        os.unlink(temp_path)


async def test_fileanalyzer_complexity_calculation(analyzer):
    """Test complexity categorization based on total definitions."""
    content = "\ndef func1(): pass\ndef func2(): pass\ndef func3(): pass\ndef func4(): pass\ndef func5(): pass\ndef func6(): pass\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=_REPO_TMP_DIR
    ) as f:
        f.write(content)
        temp_path = f.name
    try:
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["complexity"] == "medium"
        assert result.metadata["total_definitions"] == 6
    finally:
        os.unlink(temp_path)


async def test_fileanalyzer_with_context():
    """Test FileAnalyzer with context for path resolution.

    Pre-existing pass — keeps the MockContext construction shape since
    this test specifically asserts on rel_path semantics that depend on
    context.git_service.repo_path matching the file's parent."""
    with tempfile.TemporaryDirectory(dir=_REPO_TMP_DIR) as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("def test(): pass")

        class MockGitService:
            def __init__(self, repo_path):
                self.repo_path = Path(repo_path)

        class MockContext:
            def __init__(self, repo_path):
                self.git_service = MockGitService(repo_path)

        context = MockContext(tmpdir)
        analyzer = FileAnalyzer(context=context)
        result = await analyzer.execute("test.py")
        assert result.ok
        assert result.data["file_type"] == "function_module"
        assert result.metadata["file_path"] == "test.py"


async def test_fileanalyzer_sqlalchemy_import_only(analyzer):
    """Test file with SQLAlchemy import but no Base class or Mapped (should not be sqlalchemy_model)."""
    content = '\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import sessionmaker\n\nengine = create_engine("sqlite:///:memory:")\nSession = sessionmaker(bind=engine)\n'
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=_REPO_TMP_DIR
    ) as f:
        f.write(content)
        temp_path = f.name
    try:
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["has_sqlalchemy"]
        assert result.data["file_type"] != "sqlalchemy_model"
    finally:
        os.unlink(temp_path)
