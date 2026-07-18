# src/will/agents/code_generation/pattern_validator.py

"""
Pattern validation and inference for code generation.
Determines which architectural pattern applies and validates compliance.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'reason_with_purpose': Classification depends on intent, not just path.
- FIXED: Added 'Test File Sanctuary' to prevent misclassification of tests as services.
- FIXED: Allows stateless logic to exist in service layers.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from shared.logger import getLogger


if TYPE_CHECKING:
    from body.governance.intent_guard import IntentGuard
    from shared.models import ExecutionTask

logger = getLogger(__name__)


# ID: 4a0b41ed-d43e-4f28-bff3-1e807b24cfca
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

        Logic order:
        1. Explicit overrides in task params.
        2. THE SANCTUARY: Test files are always treated as stateless utilities.
        3. Nature of function (Pure/Stateless logic overrides folder location).
        4. Architectural location (Folder-based defaults).
        """
        if hasattr(task.params, "pattern_id") and task.params.pattern_id:
            return task.params.pattern_id

        file_path = task.params.file_path or ""
        task_description = task.step.lower()

        # 1. THE SANCTUARY: Test Files
        # Prevents "test_logic" from being arrested by "service" folder rules.
        # Routes to `test_file` so the LLM receives pytest-shaped requirements,
        # not generic stateless-utility guidance (which produced #429 defect 4).
        if "test_" in file_path or "/tests/" in file_path or "test" in task_description:
            logger.debug("  -> Identified as test logic. Mapping to 'test_file'.")
            return "test_file"

        # 2. CLASSIFICATION HIERARCHY: Check nature of function next
        function_type = self._classify_function_type(file_path, task_description)

        if function_type == "pure_function":
            logger.debug("  -> Inferring 'pure_function' based on task nature.")
            return "pure_function"

        if function_type == "stateless_utility":
            logger.debug("  -> Inferring 'stateless_utility' based on task nature.")
            return "stateless_utility"

        # 3. ARCHITECTURAL LOCATION: For stateful/command code
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

        # Point to the new canonical substrate
        elif "body/atomic" in file_path:
            return "action_pattern"

        # Default for unknown locations
        return "stateless_utility"

    def _classify_function_type(self, file_path: str, task_description: str) -> str:
        """
        Classify the nature of the function being created using semantic indicators.
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

        # Check description for pure/stateless intent
        for indicator in pure_indicators:
            if indicator in task_description:
                # Distinguish between high-purity (pure_function) and general utility
                if any(
                    x in task_description for x in ["pure", "mathematical", "stateless"]
                ):
                    return "pure_function"
                return "stateless_utility"

        # READ-ONLY INDICATORS
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
        ]
        if any(indicator in task_description for indicator in readonly_indicators):
            return "stateless_utility"

        # STATEFUL INDICATORS (needs action_pattern or stateful_service)
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

        return "unknown"

    # ID: 412ade61-2b7e-48de-8327-eaea101affbb
    def infer_component_type(self, task: ExecutionTask) -> str:
        """
        Infer the component type from task metadata.
        """
        file_path = task.params.file_path or ""

        if "test_" in file_path or "/tests/" in file_path:
            return "utility"

        if "shared/utils" in file_path or "shared/universal" in file_path:
            return "utility"

        if "cli/commands" in file_path:
            return "command"
        elif "services" in file_path:
            return "service"
        elif "agents" in file_path:
            return "agent"
        elif "body/atomic" in file_path:
            return "action"
        else:
            return "utility"

    # ID: 4d65d262-2cc0-4228-b12f-e45d1a341c14
    def get_pattern_requirements(self, pattern_id: str) -> str:
        """
        Get constitutional requirements for a specific pattern.
        """
        requirements = {
            "pure_function": """
## Pattern Requirements: pure_function
- Must have NO side effects (no I/O, no global state modification).
- Must be deterministic (same input -> same output).
- Should use type hints for all parameters and return value.
- Should have comprehensive docstring with examples.
""",
            "stateless_utility": """
## Pattern Requirements: stateless_utility
- Module should provide reusable, stateless logic.
- Should use type hints and clear docstrings.
- NO 'write' parameter needed.
""",
            "test_file": """
## Pattern Requirements: test_file
- You are generating a pytest TEST MODULE for an existing source file. The source is shown in the "Target File to Test" section of the architectural context above.
- Use pytest conventions: `def test_*()` functions, fixtures via `@pytest.fixture`, parametrization via `@pytest.mark.parametrize`, mocks via `unittest.mock` where needed.
- Import the module under test using its PACKAGE PATH, e.g. `from shared.infrastructure.storage.file_classifier import get_file_classification`. DO NOT use `from src.shared...` — `src` is a `pythonpath` root, not an importable package.
- Use ONLY symbols (functions, classes, constants) that actually exist in the target file's source. If a symbol is not present in the "Target File to Test" section, do NOT import or reference it.
- Cover the public surface: every public function/class, happy paths, error paths, and edge cases observable from the public interface.
""",
            "action_pattern": """
## Pattern Requirements: action_pattern (Atomic Action)
- MUST use @atomic_action decorator from shared.atomic_action.
- MUST have a 'write' parameter with type: bool, defaulting to False.
- MUST return an ActionResult object.
""",
            "stateful_service": """
## Pattern Requirements: stateful_service
- MUST be a class that maintains or manages state.
- MUST have an __init__ method for dependency injection.
""",
            "repository_pattern": """
## Pattern Requirements: repository_pattern
- MUST encapsulate database access logic.
- Should implement standard CRUD methods (save, find, delete).
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
        # Purity check: pure_function and stateless_utility have no per-pattern
        # validator on the body side and only need syntax validation here. Note:
        # test_file USED to short-circuit too, but post-#574 (7404ace5) the body
        # side has a real validator (PatternValidators.validate_test_file_pattern
        # — import resolution + absolute-import discipline). Short-circuiting
        # test_file from this code path bypassed that gate (issue #583); the
        # delegation below is now the canonical path for test_file.
        if pattern_id in ("pure_function", "stateless_utility"):
            try:
                ast.parse(code)
                return (True, [])
            except SyntaxError as e:
                return (False, [{"message": f"Syntax error: {e}", "severity": "error"}])

        # Complex patterns are delegated to the IntentGuard (The Law)
        return await self.intent_guard.validate_generated_code(  # type: ignore[misc]
            code=code,
            pattern_id=pattern_id,
            component_type=component_type,
            target_path=target_path,
        )
