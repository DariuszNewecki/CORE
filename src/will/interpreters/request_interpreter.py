# src/will/interpreters/request_interpreter.py

"""
RequestInterpreter - Universal entry point for all CORE operations.

Defines the INTERPRET-phase contract: canonical TaskType vocabulary, the
TaskStructure shape every interpretation produces, and the
RequestInterpreter abstract base every concrete interpreter inherits.

Concrete implementations live in sibling modules:
- natural_language_interpreter.py — free-form English parsing
- cli_args_interpreter.py — explicit CLI args normalisation

This is the INTERPRET phase of the Universal Workflow Pattern:
    INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE

Constitutional alignment:
- Phase: INTERPRET (new in v2.2.0)
- Authority: CODE
- Purpose: Parse intent without making decisions
- Output: Canonical task structure for downstream components
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from shared.component_primitive import Component, ComponentPhase, ComponentResult


# ID: ee7cac1a-6ab9-42a3-8068-a3e793fa6cb9
class TaskType(str, Enum):
    """Canonical task types that CORE can handle."""

    # Information retrieval
    QUERY = "query"  # "what does X do?"
    ANALYZE = "analyze"  # "analyze this file"
    EXPLAIN = "explain"  # "explain how X works"

    # Code modification
    REFACTOR = "refactor"  # "refactor for clarity"
    FIX = "fix"  # "fix the bug", "fix complexity"
    GENERATE = "generate"  # "create a new feature"
    TEST = "test"  # "generate tests"

    # System operations
    AUDIT = "audit"  # "check constitutional compliance"
    SYNC = "sync"  # "sync knowledge graph"
    VALIDATE = "validate"  # "validate policies"

    # Development workflows
    DEVELOP = "develop"  # "build feature X"

    # Unknown/ambiguous
    UNKNOWN = "unknown"


@dataclass
# ID: c1d04f7c-d810-42c8-96ec-48a98e93e63d
class TaskStructure:
    """
    Canonical task structure - output of INTERPRET phase.

    This is what every operation in CORE becomes after interpretation.
    """

    task_type: TaskType
    intent: str  # Human-readable goal
    targets: list[str]  # Files, symbols, or scope indicators
    constraints: dict[str, Any]  # Execution constraints (write mode, max attempts, etc)
    context: dict[str, Any]  # Additional context for routing
    confidence: float  # 0.0-1.0 - How confident is the interpretation?


# ID: ccfdfcd1-fa37-434e-b9fe-9b094ab215b9
class RequestInterpreter(Component):
    """
    Base class for all request interpreters.

    Interpreters convert inputs → TaskStructure without making decisions
    about HOW to execute the task (that's the strategist's job).

    Subclasses:
    - NaturalLanguageInterpreter: "refactor this file" → TaskStructure
    - CLIArgsInterpreter: Typer args → TaskStructure
    - APIRequestInterpreter: JSON payload → TaskStructure
    """

    @property
    # ID: edce7891-4f69-4b92-a0c7-6151eac1326d
    def phase(self) -> ComponentPhase:
        """Interpreters operate in INTERPRET phase."""
        return ComponentPhase.INTERPRET

    # ID: b5008a8d-629d-4c07-b1bf-b6f3ba667e0b
    async def execute(self, *args: Any, **kwargs: Any) -> ComponentResult:
        """
        Parse input → TaskStructure.

        Args:
            **inputs: Varies by subclass (user_message, cli_args, api_payload, etc)

        Returns:
            ComponentResult with TaskStructure in data["task"]
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def _create_result(
        self,
        task: TaskStructure,
        ok: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ComponentResult:
        """Helper to create consistent ComponentResult from TaskStructure."""
        return ComponentResult(
            component_id=self.component_id,
            ok=ok,
            data={"task": task},
            phase=self.phase,
            confidence=task.confidence,
            next_suggested="analyzer" if ok else None,
            metadata=metadata or {},
            duration_sec=0.0,  # Filled by caller
        )
