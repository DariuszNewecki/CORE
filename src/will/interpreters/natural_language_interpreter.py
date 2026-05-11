# src/will/interpreters/natural_language_interpreter.py

"""
NaturalLanguageInterpreter — free-form English → TaskStructure.

INTERPRET-phase implementation that powers natural-language entry points
like `core "natural language command"`. Uses priority-ordered regex
patterns to classify the user's intent into a TaskType, then extracts
target files/symbols and execution constraints from the same message.

This module owns the natural-language vocabulary: which regex patterns
map to which TaskType, how targets are recognised (file paths, CamelCase
class names), how constraint hints ("dry run", "5 times", "unit tests")
are surfaced. When the natural-language surface evolves, this is the
module that changes.

The contract (RequestInterpreter base, TaskType, TaskStructure) lives in
request_interpreter.py.

LAYER: will/interpreters — sibling of cli_args_interpreter.py. No DB
access, no file writes, no LLM calls.
"""

from __future__ import annotations

import re
from typing import ClassVar

from shared.component_primitive import ComponentResult
from shared.logger import getLogger
from will.interpreters.request_interpreter import (
    RequestInterpreter,
    TaskStructure,
    TaskType,
)


logger = getLogger(__name__)


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
        class_pattern = r"\b([A-Z][a-z0-9]{1,40}(?:[A-Z][a-z0-9]{1,40})+)\b"
        targets.extend(re.findall(class_pattern, message))

        return list(set(targets))  # Deduplicate

    def _extract_constraints(self, message: str) -> dict:
        """
        Extract execution constraints from message.

        Examples:
        - "don't write files" → {"write": False}
        - "try 5 times" → {"max_attempts": 5}
        - "only unit tests" → {"strategy": "unit_tests"}
        """
        constraints: dict = {}

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
