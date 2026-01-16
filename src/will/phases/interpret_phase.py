# src/will/phases/interpret_phase.py
# ID: will.phases.interpret_phase

"""
INTERPRET Phase - Convert natural language intent into canonical task structure

Constitutional Entry Point:
This is the first phase in CORE's governance pipeline, bridging ungoverned
(human communication) with governed (system execution).

IMPLEMENTATION EVOLUTION:
Current (v1): Deterministic pattern matching
- Fast, testable, deterministic (same input → same output)
- Sufficient for common workflow patterns
- No LLM dependency = no cost, no latency

Future (v2): LLM-assisted interpretation
- Handle complex, ambiguous requests
- Multi-intent detection
- Context-aware clarification
- Constitutional constraint: Must remain deterministic for given context

The transition from v1 → v2 is a quality improvement, not a constitutional change.
Both versions must produce canonical task structures that pass Parse phase validation.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
class InterpretPhase:
    """
    INTERPRET Phase Implementation (v1 - Deterministic)

    Converts natural language user goals into canonical task structures
    using pattern matching and heuristics.

    Constitutional Properties:
    - Phase: interpret (first in pipeline)
    - Authority: policy
    - Failure Mode: clarify (ask user, don't block)
    """

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
    async def execute(self, workflow_context: WorkflowContext) -> PhaseResult:
        """
        Execute INTERPRET phase.

        Takes user's natural language goal and produces canonical task structure.

        Returns:
            PhaseResult with:
                - task_structure: Canonical task definition
                - workflow_type: Inferred workflow
                - clarification_needed: Boolean
        """
        goal = workflow_context.goal

        logger.info("🎯 INTERPRET Phase: Parsing goal: '%s'", goal)

        try:
            # Infer workflow type from goal
            workflow_type = self._infer_workflow_type(goal)

            # Extract target information
            target_info = self._extract_target_info(goal)

            # Build canonical task structure
            task_structure = {
                "goal": goal,
                "workflow_type": workflow_type,
                "targets": target_info.get("targets", []),
                "constraints": target_info.get("constraints", {}),
                "clarification_needed": False,
            }

            logger.info("✅ INTERPRET: Mapped to workflow '%s'", workflow_type)

            # Add metadata to data dict (PhaseResult doesn't have separate metadata field)
            task_structure["_metadata"] = {
                "interpretation_method": "deterministic_v1",
                "confidence": (
                    "high" if self._is_confident(goal, workflow_type) else "medium"
                ),
            }

            return PhaseResult(name="interpret", ok=True, data=task_structure)

        except Exception as e:
            logger.error("❌ INTERPRET Phase failed: %s", e, exc_info=True)
            return PhaseResult(
                name="interpret",
                ok=False,
                error=str(e),
                data={"clarification_needed": True},
            )

    def _infer_workflow_type(self, goal: str) -> str:
        """
        Infer workflow type from goal text using deterministic patterns.

        v1 Implementation: Pattern matching on keywords
        v2 Evolution: LLM-based classification with confidence scores

        This is constitutionally acceptable because:
        1. Deterministic for given input
        2. Output is validated by Parse phase
        3. Wrong inference = workflow fails early (safe)
        """
        goal_lower = goal.lower()

        # Refactoring signals
        refactor_patterns = [
            r"\brefactor\b",
            r"\bmodularity\b",
            r"\bsplit\b",
            r"\bextract\b",
            r"\breorganize\b",
            r"\bimprove\s+structure\b",
        ]

        if any(re.search(pattern, goal_lower) for pattern in refactor_patterns):
            return "refactor_modularity"

        # Test generation signals
        test_patterns = [
            r"\btest\b",
            r"\bcoverage\b",
            r"\bgenerate\s+tests\b",
            r"\badd\s+tests\b",
            r"\btest\s+generation\b",
        ]

        if any(re.search(pattern, goal_lower) for pattern in test_patterns):
            return "coverage_remediation"

        # Feature development signals
        feature_patterns = [
            r"\bimplement\b",
            r"\badd\s+feature\b",
            r"\bcreate\b",
            r"\bbuild\b",
            r"\bdevelop\b",
            r"\bnew\s+feature\b",
        ]

        if any(re.search(pattern, goal_lower) for pattern in feature_patterns):
            return "full_feature_development"

        # Default: full feature development
        logger.warning(
            "⚠️  Could not confidently infer workflow type, defaulting to full_feature_development"
        )
        return "full_feature_development"

    def _extract_target_info(self, goal: str) -> dict:
        """
        Extract target files/modules from goal text.

        v1 Implementation: Basic pattern matching
        v2 Evolution: LLM-based entity extraction

        Returns:
            {
                "targets": [list of file paths or module names],
                "constraints": {additional constraints}
            }
        """
        targets = []
        constraints = {}

        # Look for file paths (simple pattern)
        # Matches: src/module/file.py, path/to/module.py, etc.
        file_pattern = r"\b[\w/]+\.py\b"
        matches = re.findall(file_pattern, goal)
        if matches:
            targets.extend(matches)

        # Look for module names (simple pattern)
        # Matches: user_service, payment_processor, etc.
        module_pattern = r"\b[a-z_]+_[a-z_]+\b"
        matches = re.findall(module_pattern, goal.lower())
        if matches and not targets:  # Only if no file paths found
            targets.extend(matches)

        return {
            "targets": targets,
            "constraints": constraints,
        }

    def _is_confident(self, goal: str, workflow_type: str) -> bool:
        """
        Determine if interpretation confidence is high.

        Used for metadata and potential future clarification logic.
        """
        goal_lower = goal.lower()

        # High confidence if goal contains explicit workflow-related keywords
        confidence_keywords = {
            "refactor_modularity": ["refactor", "modularity", "split"],
            "coverage_remediation": ["test", "coverage"],
            "full_feature_development": ["implement", "feature", "create"],
        }

        keywords = confidence_keywords.get(workflow_type, [])
        return any(keyword in goal_lower for keyword in keywords)
