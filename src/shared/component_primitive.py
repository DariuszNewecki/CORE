# src/shared/component_primitive.py

"""
Component Primitive - Base interface for CORE components.

Constitutional Alignment:
- Article IV: All components MUST return evaluable results
- Phase separation: Components declare which phase they operate in
- UNIX philosophy: Each component does ONE thing well

Three new component types:
- Analyzers (Parse/Load phase): Extract information
- Evaluators (Audit phase): Assess quality/patterns
- Strategists (Runtime phase): Make rule-based decisions

Usage:
    # Standalone
    analyzer = FileAnalyzer()
    result = await analyzer.execute(file_path="...")

    # In workflow
    orchestrator = ProcessOrchestrator()
    results = await orchestrator.run_sequence([
        (FileAnalyzer(), {"file_path": path}),
        (SymbolExtractor(), {"file_path": path}),
    ])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 9ac2d7c5-0bb6-421f-a441-9e3ef24ca1f8
class ComponentPhase(str, Enum):
    """Constitutional phases where components operate."""

    PARSE = "parse"
    LOAD = "load"
    AUDIT = "audit"
    RUNTIME = "runtime"
    EXECUTION = "execution"


@dataclass
# ID: f1fce892-e62b-49a2-94cb-c78aec646928
class ComponentResult:
    """
    Universal result structure for all components.

    Constitutional requirement (Article IV): All components MUST return
    evaluable results with explicit success status.

    This structure is the single source of truth for component outputs.
    """

    component_id: str
    "Unique identifier for the component that produced this result"
    ok: bool
    "Binary success indicator. True = component achieved its goal."
    data: dict[str, Any]
    "Component-specific output data"
    phase: ComponentPhase
    "Constitutional phase this component operates in"
    confidence: float = 1.0
    "Confidence in result (0.0-1.0). Used for workflow decisions."
    next_suggested: str = ""
    "\n    Optional suggestion for next component to run.\n    This is a hint, not a requirement - orchestrators may ignore it.\n    "
    metadata: dict[str, Any] = field(default_factory=dict)
    "\n    Additional context that may be useful for subsequent components.\n    Examples: error details, pattern history, accumulated state.\n    "
    duration_sec: float = 0.0
    "Execution time in seconds"

    def __post_init__(self):
        """Validate constitutional requirements."""
        if not isinstance(self.component_id, str) or not self.component_id:
            raise ValueError("ComponentResult.component_id must be non-empty string")
        if not isinstance(self.data, dict):
            raise ValueError("ComponentResult.data must be dict")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("ComponentResult.confidence must be in [0.0, 1.0]")


# ID: 16b01920-ad6f-4516-900c-af2f7e9eefc7
class Component:
    """
    Base class for all CORE components.

    This is OPTIONAL - components can implement the interface without inheritance.
    Provided for consistency and convenience.

    Constitutional principles:
    - Explicitness: Component declares its phase
    - Evaluation: Returns structured, evaluable result
    - UNIX philosophy: Does ONE thing well
    - No side effects (except Execution phase)
    """

    @property
    # ID: af524c7e-009a-4e0d-b747-eead8d9b26c1
    def component_id(self) -> str:
        """
        Unique identifier for this component.

        Default implementation uses class name in lowercase.
        Override if you need custom naming.
        """
        return self.__class__.__name__.lower()

    @property
    # ID: 15bfa206-731f-4b69-8cc0-f9424ffcd895
    def phase(self) -> ComponentPhase:
        """
        Constitutional phase this component operates in.

        Must be overridden by subclasses.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must declare its phase")

    @property
    # ID: 4b938b8d-5161-4d16-8e30-91e8f8eec743
    def description(self) -> str:
        """
        Human-readable description of what this component does.

        Should be a single sentence describing the component's purpose.
        """
        return self.__doc__.split("\n")[0] if self.__doc__ else "No description"

    # ID: 2f422a72-23bc-4a64-a8c7-61903576c911
    async def execute(self, **inputs) -> ComponentResult:
        """
        Execute the component.

        Constitutional contract:
        - MUST return ComponentResult
        - MUST be idempotent (same inputs → same outputs)
        - MUST NOT have side effects (except Execution phase)
        - MUST complete in bounded time

        Args:
            **inputs: Component-specific input parameters

        Returns:
            ComponentResult with execution outcome
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")

    def __repr__(self) -> str:
        """String representation for logging."""
        return f"{self.__class__.__name__}(phase={self.phase.value})"


# ID: 3a850ac3-0fcf-41d6-939f-8796664a94ce
def discover_components(package_name: str) -> dict[str, type[Component]]:
    """
    Discover all Component subclasses in a package.

    This enables dynamic discovery without file-based registries.

    Args:
        package_name: Python package to search (e.g., 'body.analyzers')

    Returns:
        Dict mapping component_id to component class

    Example:
        analyzers = discover_components('body.analyzers')
        file_analyzer = analyzers['fileanalyzer']()
        result = await file_analyzer.execute(file_path="...")
    """
    import importlib
    import inspect
    import pkgutil

    try:
        package = importlib.import_module(package_name)
    except ImportError as e:
        logger.warning("Could not import package %s: %s", package_name, e)
        return {}
    components = {}
    for _, module_name, _ in pkgutil.walk_packages(
        package.__path__, package.__name__ + "."
    ):
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Component) and obj is not Component:
                    instance = obj()
                    components[instance.component_id] = obj
                    logger.debug("Discovered component: %s", instance.component_id)
        except Exception as e:
            logger.debug("Could not inspect module %s: %s", module_name, e)
            continue
    return components
