# src/body/analyzers/base_analyzer.py
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
    """
        BaseAnalyzer is an abstract base class for parse-phase fact extraction analyzers requiring subclasses to implement execute().
    Args:
    Returns:
    """

    """
    BaseAnalyzer is an abstract base class for parse-phase analyzers that extract facts, inheriting the phase attribute from its parent class and ensuring no side effects. It requires subclasses to implement the execute() method to perform fact extraction.
    """

    """
    The BaseAnalyzer class in the given Python code is an abstract base class designed as a foundation for parse-phase analyzers that extract facts. It requires subclasses to implement the execute() method, ensuring no side effects and inheriting the phase attribute from its parent class.
    """

    """
    The BaseAnalyzer class is a base class for parse-phase analyzers that extract facts, inheriting the phase attribute automatically and ensuring no side effects. It requires subclasses to implement the execute() method to perform fact extraction.
    """

    """
    The BaseAnalyzer class is a base class for parse-phase fact extractors with a read-only interface, requiring subclasses to implement the execute() method to perform fact extraction.
    """

    """
    The BaseAnalyzer class is a base class for parse-phase analyzers that extract facts. It inherits the phase attribute automatically and ensures that no side effects are permitted, making it read-only fact extractors. The execute() method must be implemented by subclasses to perform fact extraction.
    """

    """
    Base class for analyzers that extract facts during the PARSE phase.
    """

    """
    Base class for analyzers that extract facts during the PARSE phase.
    """

    """
    Base class for analyzers that extract facts during the PARSE phase.
    """

    """
    Base class for analyzers that extract facts during the PARSE phase.
    """

    """Base class for all PARSE phase analyzers.

    Subclasses must implement execute(). They inherit phase automatically.
    No side effects permitted — analyzers are read-only fact extractors.
    """

    @property
    # ID: c5f3a4b6-d7e8-9012-cdef-012345678912
    def phase(self) -> ComponentPhase:
        """All analyzers operate in the PARSE phase."""
        return ComponentPhase.PARSE
