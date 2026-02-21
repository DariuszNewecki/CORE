# src/body/analyzers/base_analyzer.py
# ID: a3f1e2d4-b5c6-7890-abcd-ef1234567890
"""Base Analyzer - PARSE phase base class.

All Body analyzers extract structural facts from code without making decisions.
They are pure functions: same input → same output.

Owning `phase` here eliminates AST duplication across:
    FileAnalyzer, KnowledgeGraphAnalyzer, PromptAnalyzer, SymbolExtractor.
"""

from __future__ import annotations

from shared.component_primitive import Component, ComponentPhase


# ID: b4e2f3a5-c6d7-8901-bcde-f01234567891
class BaseAnalyzer(Component):
    """Base class for all PARSE phase analyzers.

    Subclasses must implement execute(). They inherit phase automatically.
    No side effects permitted — analyzers are read-only fact extractors.
    """

    @property
    # ID: c5f3a4b6-d7e8-9012-cdef-012345678912
    def phase(self) -> ComponentPhase:
        """All analyzers operate in the PARSE phase."""
        return ComponentPhase.PARSE
