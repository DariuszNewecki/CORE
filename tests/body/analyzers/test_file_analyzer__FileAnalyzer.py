"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/analyzers/file_analyzer.py
- Symbol: FileAnalyzer
- Status: 8 tests passed, some failed
- Passing tests: test_fileanalyzer_file_not_found, test_fileanalyzer_syntax_error, test_fileanalyzer_empty_file, test_fileanalyzer_sqlalchemy_model, test_fileanalyzer_function_module, test_fileanalyzer_complexity_calculation, test_fileanalyzer_with_context, test_fileanalyzer_sqlalchemy_import_only
- Generated: 2026-01-10 23:43:17
"""

import os
import tempfile
from pathlib import Path

import pytest

from body.analyzers.file_analyzer import FileAnalyzer


@pytest.mark.asyncio
async def test_fileanalyzer_file_not_found():
    """Test handling of non-existent file."""
    analyzer = FileAnalyzer()
    result = await analyzer.execute("non_existent_file.py")
    assert not result.ok
    assert "error" in result.data
    assert "File not found" in result.data["error"]


@pytest.mark.asyncio
async def test_fileanalyzer_syntax_error():
    """Test handling of file with syntax errors."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def invalid python syntax")
        temp_path = f.name
    try:
        analyzer = FileAnalyzer()
        result = await analyzer.execute(temp_path)
        assert not result.ok
        assert "error" in result.data
        assert "Syntax error" in result.data["error"]
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_fileanalyzer_empty_file():
    """Test analysis of empty Python file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("")
        temp_path = f.name
    try:
        analyzer = FileAnalyzer()
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


@pytest.mark.asyncio
async def test_fileanalyzer_sqlalchemy_model():
    """Test detection of SQLAlchemy model file."""
    content = "\nfrom sqlalchemy import Column, Integer, String\nfrom sqlalchemy.orm import Mapped, mapped_column\nfrom sqlalchemy.ext.declarative import declarative_base\n\nBase = declarative_base()\n\nclass User(Base):\n    __tablename__ = 'users'\n    \n    id: Mapped[int] = mapped_column(Integer, primary_key=True)\n    name = Column(String(50))\n    \n    def __repr__(self):\n        return f\"<User(id={self.id}, name={self.name})>\"\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name
    try:
        analyzer = FileAnalyzer()
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["file_type"] == "sqlalchemy_model"
        assert result.data["has_sqlalchemy"]
        assert result.data["class_count"] == 1
        assert result.data["function_count"] == 1
        assert result.confidence == 0.95
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_fileanalyzer_function_module():
    """Test detection of function-only module."""
    content = '\ndef calculate_sum(a, b):\n    return a + b\n\ndef calculate_product(a, b):\n    return a * b\n\ndef format_result(value):\n    return f"Result: {value}"\n\ndef validate_input(value):\n    return isinstance(value, (int, float))\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name
    try:
        analyzer = FileAnalyzer()
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


@pytest.mark.asyncio
async def test_fileanalyzer_complexity_calculation():
    """Test complexity categorization based on total definitions."""
    content = "\ndef func1(): pass\ndef func2(): pass\ndef func3(): pass\ndef func4(): pass\ndef func5(): pass\ndef func6(): pass\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name
    try:
        analyzer = FileAnalyzer()
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["complexity"] == "medium"
        assert result.metadata["total_definitions"] == 6
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_fileanalyzer_with_context():
    """Test FileAnalyzer with context for path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
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


@pytest.mark.asyncio
async def test_fileanalyzer_sqlalchemy_import_only():
    """Test file with SQLAlchemy import but no Base class or Mapped (should not be sqlalchemy_model)."""
    content = '\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import sessionmaker\n\nengine = create_engine("sqlite:///:memory:")\nSession = sessionmaker(bind=engine)\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        temp_path = f.name
    try:
        analyzer = FileAnalyzer()
        result = await analyzer.execute(temp_path)
        assert result.ok
        assert result.data["has_sqlalchemy"]
        assert result.data["file_type"] != "sqlalchemy_model"
    finally:
        os.unlink(temp_path)
