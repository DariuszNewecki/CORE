"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/utils/import_scanner.py
- Symbol: scan_imports_for_file
- Status: verified_in_sandbox
- Generated: 2026-01-07 21:55:04
"""

from pathlib import Path

from shared.utils.import_scanner import scan_imports_for_file


# Detected return type: list[str]


def test_scan_imports_for_file_import():
    """Test scanning a file with a simple import statement."""
    source = "import os"
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == ["os"]
    finally:
        file_path.unlink()


def test_scan_imports_for_file_import_from():
    """Test scanning a file with a 'from x import y' statement."""
    source = "from collections import defaultdict"
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == ["collections"]
    finally:
        file_path.unlink()


def test_scan_imports_for_file_import_from_without_module():
    """Test scanning a file with a 'from . import y' statement (module is None)."""
    source = "from . import sibling"
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == []
    finally:
        file_path.unlink()


def test_scan_imports_for_file_multiple_imports():
    """Test scanning a file with multiple import statements."""
    source = """
import sys
import os.path
from typing import List, Dict
from django.conf import settings
"""
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        # Order is depth-first from ast.walk, which follows the source order for top-level nodes.
        assert result == ["sys", "os.path", "typing", "django.conf"]
    finally:
        file_path.unlink()


def test_scan_imports_for_file_nested_import_in_function():
    """Test that imports inside function definitions are also captured."""
    source = """
def my_func():
    import json
"""
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == ["json"]
    finally:
        file_path.unlink()


def test_scan_imports_for_file_relative_import_with_level():
    """Test that relative imports with a module are captured."""
    source = "from ..package import module"
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == ["package"]
    finally:
        file_path.unlink()


def test_scan_imports_for_file_empty_file():
    """Test scanning an empty Python file."""
    source = ""
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == []
    finally:
        file_path.unlink()


def test_scan_imports_for_file_syntax_error_handled_gracefully():
    """Test that a syntax error in the file returns an empty list (exception is logged)."""
    source = "def invalid python syntax"
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        # The function catches Exception and returns an empty list.
        assert result == []
    finally:
        file_path.unlink()


def test_scan_imports_for_file_aliases_ignored():
    """Test that import aliases (as) do not affect the extracted module path."""
    source = "import pandas as pd"
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == ["pandas"]
    finally:
        file_path.unlink()


def test_scan_imports_for_file_import_from_with_multiple_modules():
    """Test 'from x import a, b, c' only records module 'x' once."""
    source = "from django.http import HttpResponse, JsonResponse"
    file_path = Path("test_file.py")
    file_path.write_text(source, encoding="utf-8")
    try:
        result = scan_imports_for_file(file_path)
        assert result == ["django.http"]
    finally:
        file_path.unlink()
