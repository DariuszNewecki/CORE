# src/body/analyzers/base_analyzer.py
"""Base Analyzer - PARSE phase base class.

All Body analyzers extract structural facts from code without making decisions.
They are pure functions: same input → same output.

Owning `phase` here eliminates AST duplication across:
    FileAnalyzer, KnowledgeGraphAnalyzer, PromptAnalyzer, SymbolExtractor.
"""

from __future__ import annotations

from shared.component_primitive import Component, ComponentPhase


# ID: df950b6c-f0b5-432d-b826-4355d5689300
class BaseAnalyzer(Component):
    """Base class for all PARSE phase analyzers.

    Subclasses must implement execute(). They inherit phase automatically.
    No side effects permitted — analyzers are read-only fact extractors.
    """

    @property
    # ID: b20233cb-b6cb-44f8-97f7-726d7c0df0c4
    def phase(self) -> ComponentPhase:
        """All analyzers operate in the PARSE phase."""
        return ComponentPhase.PARSE
