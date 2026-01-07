# src/body/analyzers/__init__.py

"""
Analyzers - Parse/Load phase components.

Analyzers extract information from code without making decisions.
They are pure functions: same input → same output.

Available Analyzers:
- FileAnalyzer: Classify file type and complexity
- SymbolExtractor: Extract testable functions and classes

Constitutional Alignment:
- Phase: PARSE/LOAD (structural analysis only)
- No side effects (read-only)
- Returns structured ComponentResult

Usage:
    from body.analyzers import FileAnalyzer, SymbolExtractor

    analyzer = FileAnalyzer()
    result = await analyzer.execute(file_path="models.py")
"""

from __future__ import annotations

from .file_analyzer import FileAnalyzer
from .symbol_extractor import SymbolExtractor, SymbolInfo


__all__ = [
    "FileAnalyzer",
    "SymbolExtractor",
    "SymbolInfo",
    "SymbolMetadata",
]
