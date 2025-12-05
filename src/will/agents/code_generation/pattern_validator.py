# src/will/agents/code_generation/pattern_validator.py
"""
Pattern validation and inference for code generation.
Determines which architectural pattern applies and validates compliance.

ENHANCED: Now includes intelligent function classification to prevent
false positives on pure utility functions.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from shared.logger import getLogger

if TYPE_CHECKING:
    from shared.models import ExecutionTask

    from will.orchestration.intent_guard import IntentGuard

logger = getLogger(__name__)


# ID: 59749c80-7e75-4609-8ecb-143e9200f503
class PatternValidator:
    """Infers and validates architectural patterns for generated code."""

    def __init__(self, intent_guard: IntentGuard):
        """
        Initialize pattern validator.

        Args:
            intent_guard: The constitutional pattern enforcement system
        """
        self.intent_guard = intent_guard

    # ID: 43fd6352-ac56-4a17-a516-d46a77dad54d
    def infer_pattern_id(self, task: ExecutionTask) -> str:
        """
        Infer which architectural pattern applies to this task.

        ENHANCED: Now classifies functions by their nature (pure vs stateful)
        to avoid forcing action_pattern on simple utilities.
        """
        if hasattr(task.params, "pattern_id") and task.params.pattern_id:
            return task.params.pattern_id

        file_path = task.params.file_path or ""
        task_description = task.step.lower()

        # CLASSIFICATION HIERARCHY: Check nature of function first
        function_type = self._classify_function_type(file_path, task_description)

        if function_type == "pure_function":
            logger.info("  -> Classified as pure_function (no write param needed)")
            return "pure_function"

        if function_type == "stateless_utility":
            logger.info("  -> Classified as stateless_utility (no state modification)")
            return "stateless_utility"

        # ARCHITECTURAL LOCATION: For stateful/command code
        if "cli/commands" in file_path:
            if "inspect" in file_path or "inspect" in task_description:
                return "inspect_pattern"
            elif "check" in file_path or "validate" in task_description:
                return "check_pattern"
            elif "run" in file_path or "execute" in task_description:
                return "run_pattern"
            elif "manage" in file_path or "admin" in task_description:
                return "manage_pattern"
            else:
                return "action_pattern"

        elif "services" in file_path:
            if "repository" in file_path.lower():
                return "repository_pattern"
            else:
                return "stateful_service"

        elif "agents" in file_path:
            return "cognitive_agent"

        elif "body/actions" in file_path:
            return "action_pattern"

        # === CRITICAL FIX ===
        # If it falls through here (e.g. src/test_hello.py), it is a generic script.
        # We must NOT enforce action_pattern (which requires write: bool).
        # Defaulting to stateless_utility applies minimal validation (syntax check).
        return "stateless_utility"

    def _classify_function_type(self, file_path: str, task_description: str) -> str:
        """
        Classify the nature of the function being created.
        """
        # PURE FUNCTION INDICATORS
        pure_indicators = [
            "utility function",
            "helper function",
            "pure function",
            "stateless",
            "converter",
            "parser",
            "formatter",
            "validator",
            "calculator",
            "transform",
            "return string",
            "returns",
        ]

        # Check if in shared/utils (strong signal for pure functions)
        if "shared/utils" in file_path or "shared/universal" in file_path:
            for indicator in pure_indicators:
                if indicator in task_description:
                    return "pure_function"
            return "stateless_utility"

        # STATEFUL INDICATORS (needs action_pattern)
        # Note: "Create" removed from here to avoid trapping "Create a function..." goals
        stateful_indicators = [
            "command",
            "action",
            "execute",
            "modify",
            "update",
            "delete",
            "write to",
            "save to",
            "persist",
            "database",
            "file system",
            "upsert",
        ]

        if any(indicator in task_description for indicator in stateful_indicators):
            return "stateful"

        # READ-ONLY INDICATORS (stateless utility)
        readonly_indicators = [
            "read",
            "fetch",
            "get",
            "retrieve",
            "search",
            "find",
            "list",
            "show",
            "display",
            "create",  # "Create a function" context is usually metadata, not DB op
        ]

        if any(indicator in task_description for indicator in readonly_indicators):
            return "stateless_utility"

        # Default: assume stateful if ambiguous
        return "stateful"

    # ID: 412ade61-2b7e-48de-8327-eaea101affbb
    def infer_component_type(self, task: ExecutionTask) -> str:
        """
        Infer the component type from task metadata.
        """
        file_path = task.params.file_path or ""

        if "shared/utils" in file_path or "shared/universal" in file_path:
            return "utility"

        if "cli/commands" in file_path:
            return "command"
        elif "services" in file_path:
            return "service"
        elif "agents" in file_path:
            return "agent"
        else:
            # Default to utility for generic scripts
            return "utility"

    # ID: 4d65d262-2cc0-4228-b12f-e45d1a341c14
    def get_pattern_requirements(self, pattern_id: str) -> str:
        """
        Get constitutional requirements for a specific pattern.
        """
        requirements = {
            "pure_function": """
## Pattern Requirements: pure_function
CRITICAL: This is a PURE, STATELESS function.
- Must have NO side effects (no I/O, no global state modification)
- Must be deterministic (same input → same output)
- Should use type hints for all parameters and return value
- Should have comprehensive docstring with examples
- NO 'write' parameter needed (this is not a command)
- NO database access, file writes, or network calls
""",
            "stateless_utility": """
## Pattern Requirements: stateless_utility
CRITICAL: This is a general utility or script.
- Should use type hints for all parameters and return value
- Should have comprehensive docstring
- NO 'write' parameter needed (this is not a command)
""",
            "inspect_pattern": """
## Pattern Requirements: inspect_pattern
CRITICAL: This is a READ-ONLY command that must NEVER modify state.
- Must NOT have --write, --apply, or --force parameters
- Should return data for inspection only
- Exit code: 0 for success, 1 for error
""",
            "action_pattern": """
## Pattern Requirements: action_pattern
CRITICAL: This command modifies state and must follow safety guarantees.
- MUST have a 'write' parameter with type: bool
- MUST default to False (dry-run by default)
- In dry-run mode, show what WOULD change without changing it
- Only execute when write=True
- Must be atomic (all or nothing)
""",
            "check_pattern": """
## Pattern Requirements: check_pattern
CRITICAL: This is a VALIDATION command.
- Must NOT modify state (no --write parameter)
- Must return clear pass/fail status
- Exit code: 0 for pass, 1 for fail, 2 for warnings
- Provide actionable error messages
""",
            "run_pattern": """
## Pattern Requirements: run_pattern
CRITICAL: This executes autonomous operations.
- MUST have 'write' parameter (bool, default=False)
- Must operate within autonomy lane boundaries
- Must log all autonomous decisions
- Respects constitutional constraints
""",
        }
        return requirements.get(pattern_id, requirements["stateless_utility"])

    # ID: c4f9561f-2d24-409a-99b7-a9cb5a487ddf
    async def validate_code(
        self, code: str, pattern_id: str, component_type: str, target_path: str
    ) -> tuple[bool, list]:
        """
        Validate generated code against pattern requirements.
        """
        # OPTIMIZATION: Skip pattern validation for pure functions
        if pattern_id in ("pure_function", "stateless_utility"):
            # Just check basic Python validity
            try:
                ast.parse(code)
                logger.info(f"  -> {pattern_id} validated (basic syntax check only)")
                return (True, [])
            except SyntaxError as e:
                logger.warning(f"  -> Syntax error in {pattern_id}: {e}")
                return (False, [{"message": f"Syntax error: {e}", "severity": "error"}])

        # Full pattern validation for stateful code
        return await self.intent_guard.validate_generated_code(
            code=code,
            pattern_id=pattern_id,
            component_type=component_type,
            target_path=target_path,
        )
