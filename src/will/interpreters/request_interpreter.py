# src/will/interpreters/request_interpreter.py

"""
RequestInterpreter - Universal entry point for all CORE operations.

Converts heterogeneous inputs (natural language, CLI args, API requests) into
canonical task structures that can be routed to appropriate workflows.

This is the INTERPRET phase of the Universal Workflow Pattern:
    INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE

Constitutional alignment:
- Phase: INTERPRET (new in v2.2.0)
- Authority: CODE
- Purpose: Parse intent without making decisions
- Output: Canonical task structure for downstream components
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


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


# ID: base_interpreter
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
    async def execute(self, **inputs) -> ComponentResult:
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


# ID: natural_language_interpreter
# ID: a02b2fcf-dc54-4a50-b430-e9948d9bb359
class NaturalLanguageInterpreter(RequestInterpreter):
    """
    Interprets natural language requests into TaskStructure.

    This is what powers `core "natural language command"`.

    Examples:
        "refactor UserService for clarity"
          → TaskType.REFACTOR, targets=["src/services/user.py"]

        "what does ContextBuilder do?"
          → TaskType.QUERY, targets=["ContextBuilder"]

        "generate tests for models/user.py"
          → TaskType.TEST, targets=["src/models/user.py"]
    """

    # Intent patterns (simple keyword matching for now - future: use LLM)
    # Order matters: more specific patterns should come first
    PATTERNS: ClassVar[dict[TaskType, list[str]]] = {
        TaskType.TEST: [
            r"\btests?\b",  # Matches "test" or "tests"
            r"\bunit\s+tests?\b",
            r"\bintegration\s+tests?\b",
            r"\bcoverage\b",
            r"\bgenerate.*tests?\b",  # "generate tests/test" → TEST not GENERATE
        ],
        TaskType.REFACTOR: [
            r"\brefactor\b",
            r"\bimprove\b.*\bclarity\b",
            r"\bsimplify\b",
            r"\bclean\s+up\b",
        ],
        TaskType.FIX: [
            r"\bfix\b",
            r"\brepair\b",
            r"\bresolve\b.*\bissue\b",
            r"\bcorrect\b",
        ],
        TaskType.GENERATE: [
            r"\bcreate\b",
            r"\bgenerate\b",  # This will match AFTER test patterns
            r"\bbuild\b",
            r"\badd\b.*\bfeature\b",
            r"\bimplement\b",
        ],
        TaskType.ANALYZE: [
            r"\banalyze\b",
            r"\binspect\b",
            r"\bexamine\b",
            r"\bcheck\b",
        ],
        TaskType.QUERY: [
            r"\bwhat\b.*\bdo(?:es)?\b",
            r"\bhow\b.*\bwork\b",
            r"\bexplain\b",
            r"\btell\s+me\b",
            r"\bshow\s+me\b",
        ],
        TaskType.AUDIT: [
            r"\baudit\b",
            r"\bconstitutional\b.*\bcheck\b",
            r"\bgovernance\b",
            r"\bcompliance\b",
        ],
        TaskType.DEVELOP: [r"\bdevelop\b", r"\bfull\s+feature\b", r"\bend.*to.*end\b"],
    }

    # ID: ef8e3f99-dae6-456a-85c5-63f8144d0784
    async def execute(self, user_message: str, **kwargs) -> ComponentResult:
        """
        Parse natural language → TaskStructure.

        Args:
            user_message: Natural language request from user

        Returns:
            ComponentResult with parsed TaskStructure
        """
        import time

        start = time.time()

        # 1. Classify task type
        task_type = self._classify_intent(user_message)

        # 2. Extract targets (files, symbols, etc)
        targets = self._extract_targets(user_message)

        # 3. Extract constraints
        constraints = self._extract_constraints(user_message)

        # 4. Build task structure
        task = TaskStructure(
            task_type=task_type,
            intent=user_message,
            targets=targets,
            constraints=constraints,
            context={"source": "natural_language"},
            confidence=self._calculate_confidence(task_type, targets),
        )

        result = self._create_result(
            task,
            metadata={
                "original_message": user_message,
                "patterns_matched": self._get_matched_patterns(user_message, task_type),
            },
        )
        result.duration_sec = time.time() - start

        logger.info(
            "Interpreted: %r → %s (confidence: %.2f)",
            user_message,
            task_type.value,
            task.confidence,
        )

        return result

    def _classify_intent(self, message: str) -> TaskType:
        """
        Classify message into TaskType using pattern matching.

        Checks patterns in priority order (most specific first).
        """
        message_lower = message.lower()

        # Check patterns in priority order (most specific first)
        # Order matters! TEST before GENERATE, etc.
        priority_order = [
            TaskType.TEST,  # Check "test" before "generate"
            TaskType.REFACTOR,
            TaskType.FIX,
            TaskType.DEVELOP,
            TaskType.GENERATE,  # Check "generate" after "test"
            TaskType.ANALYZE,
            TaskType.QUERY,
            TaskType.AUDIT,
        ]

        for task_type in priority_order:
            if task_type not in self.PATTERNS:
                continue
            for pattern in self.PATTERNS[task_type]:
                if re.search(pattern, message_lower):
                    return task_type

        return TaskType.UNKNOWN

    def _extract_targets(self, message: str) -> list[str]:
        """
        Extract target files/symbols from message.

        Looks for:
        - File paths: "src/models/user.py"
        - Python symbols: "UserService", "ContextBuilder"
        - Directories: "src/services/"
        """
        targets = []

        # File paths (*.py, *.yaml, etc)
        file_pattern = r"[\w/]+\.[\w]+"
        targets.extend(re.findall(file_pattern, message))

        # Python class names (CamelCase)
        class_pattern = r"\b([A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]+)+)\b"
        targets.extend(re.findall(class_pattern, message))

        return list(set(targets))  # Deduplicate

    def _extract_constraints(self, message: str) -> dict[str, Any]:
        """
        Extract execution constraints from message.

        Examples:
        - "don't write files" → {"write": False}
        - "try 5 times" → {"max_attempts": 5}
        - "only unit tests" → {"strategy": "unit_tests"}
        """
        constraints = {}

        # Write mode
        if re.search(r"don't write|dry[- ]run|preview", message.lower()):
            constraints["write"] = False
        elif re.search(r"apply|write|execute", message.lower()):
            constraints["write"] = True

        # Max attempts
        attempts_match = re.search(r"(\d+)\s+(?:times|attempts)", message.lower())
        if attempts_match:
            constraints["max_attempts"] = int(attempts_match.group(1))

        # Strategy hints
        if "unit test" in message.lower():
            constraints["strategy_hint"] = "unit_tests"
        elif "integration test" in message.lower():
            constraints["strategy_hint"] = "integration_tests"

        return constraints

    def _calculate_confidence(self, task_type: TaskType, targets: list[str]) -> float:
        """
        Calculate interpretation confidence.

        High confidence: Clear task type + specific targets
        Low confidence: Unknown task type or no targets
        """
        confidence = 0.5  # Base

        # Task type clarity
        if task_type != TaskType.UNKNOWN:
            confidence += 0.3

        # Target specificity
        if targets:
            confidence += 0.2
            if len(targets) == 1:  # Single clear target
                confidence += 0.1

        return min(confidence, 1.0)

    def _get_matched_patterns(self, message: str, task_type: TaskType) -> list[str]:
        """Return which patterns matched for this task type."""
        if task_type not in self.PATTERNS:
            return []

        message_lower = message.lower()
        matched = []

        for pattern in self.PATTERNS[task_type]:
            if re.search(pattern, message_lower):
                matched.append(pattern)

        return matched


# ID: cli_args_interpreter
# ID: 94271d67-67b4-4b39-8020-b944cd99f657
class CLIArgsInterpreter(RequestInterpreter):
    """
    Interprets CLI arguments into TaskStructure.

    This is for explicit commands like:
        core-admin fix clarity src/models/user.py --write

    Already has structure, just needs normalization.
    """

    # ID: 77647948-e7ef-4b02-a014-1bfde2b25f91
    async def execute(
        self,
        command: str,
        subcommand: str | None = None,
        targets: list[str] | None = None,
        **flags,
    ) -> ComponentResult:
        """
        Parse CLI args → TaskStructure.

        Args:
            command: Main command (fix, check, generate, etc)
            subcommand: Optional subcommand (clarity, complexity, etc)
            targets: List of file paths
            **flags: CLI flags (write, verbose, etc)

        Returns:
            ComponentResult with TaskStructure
        """
        import time

        start = time.time()

        # Map command → TaskType
        task_type_map = {
            "fix": TaskType.FIX,
            "check": TaskType.AUDIT,
            "generate": TaskType.GENERATE,
            "coverage": TaskType.TEST,
            "develop": TaskType.DEVELOP,
            "sync": TaskType.SYNC,
        }

        task_type = task_type_map.get(command, TaskType.UNKNOWN)

        # Build intent from command structure
        intent_parts = [command]
        if subcommand:
            intent_parts.append(subcommand)
        if targets:
            intent_parts.extend(targets)
        intent = " ".join(intent_parts)

        task = TaskStructure(
            task_type=task_type,
            intent=intent,
            targets=targets or [],
            constraints=flags,
            context={
                "source": "cli_args",
                "command": command,
                "subcommand": subcommand,
            },
            confidence=1.0 if task_type != TaskType.UNKNOWN else 0.3,
        )

        result = self._create_result(
            task,
            metadata={"command": command, "subcommand": subcommand, "flags": flags},
        )
        result.duration_sec = time.time() - start

        return result
