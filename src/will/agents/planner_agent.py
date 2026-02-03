# src/will/agents/planner_agent.py
# ID: 31bb8dba-f4d2-426a-8783-d09614085258
"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan that can be carried out
by the ExecutionAgent.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'autonomy.reasoning.policy_alignment'.
- MODERNIZATION: Uses PathResolver standard instead of settings.load().
- FIXED: Correctly handles session acquisition for memory cleanup.
- ENHANCED: Uses action introspection to provide LLM with parameter requirements.
- UPDATED: Searches new .intent/ structure (no charter/ subdirectory).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import yaml

from body.atomic.registry import action_registry  # FIXED: Use registry directly
from body.services.service_registry import service_registry
from features.self_healing import MemoryCleanupService
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError
from shared.path_resolver import PathResolver
from will.agents.action_introspection import get_all_action_schemas
from will.agents.base_planner import build_planning_prompt, parse_and_validate_plan
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: 31bb8dba-f4d2-426a-8783-d09614085258
class PlannerAgent:
    """Decomposes goals into executable plans."""

    def __init__(
        self, cognitive_service: CognitiveService, repo_path: Path, max_retries: int = 3
    ):
        """
        Initializes the PlannerAgent.

        Args:
            cognitive_service: Service for LLM interaction.
            repo_path: Root path of the repository (for loading prompts/policies).
            max_retries: Number of retry attempts for planning.
        """
        self.cognitive_service = cognitive_service
        self.tracer = DecisionTracer()
        self.repo_path = repo_path
        self._paths = PathResolver(repo_path)
        self.max_retries = max_retries

        # ALIGNED: Using PathResolver pattern relative to repo root
        # var/prompts is the canonical location for runtime prompts
        prompt_path = self._paths.prompt("planner_agent")

        try:
            self.prompt_template = prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(
                "Constitutional prompt 'planner_agent.prompt' missing from %s",
                prompt_path,
            )
            raise

    # ID: 1ea9ec86-10a3-4356-9c31-c14e53c8fed0
    async def create_execution_plan(
        self, goal: str, reconnaissance_report: str = ""
    ) -> list[ExecutionTask]:
        """
        Creates an execution plan from a user goal and a reconnaissance report.

        Args:
            goal: High-level user goal to decompose
            reconnaissance_report: Context from reconnaissance phase

        Returns:
            List of ExecutionTask objects representing the plan
        """
        # SAFE AUTO-CLEANUP: Triggered occasionally to manage system memory
        if random.random() < 0.1:
            try:
                # Use registry to acquire session without hardcoded imports
                async with service_registry.session() as session:
                    cleanup_service = MemoryCleanupService(session=session)
                    await cleanup_service.cleanup_old_memories(dry_run=False)
            except Exception as e:
                logger.debug("Memory cleanup deferred: %s", e)

        # FIXED: Search new .intent/ structure for quality/purity rules
        qa_constraints = ""

        # Search in new structure: .intent/rules/code/
        policy_candidates = [
            self._paths.intent_root / "rules" / "code" / "purity.json",
            self._paths.intent_root / "rules" / "code" / "purity.yaml",
            self._paths.intent_root / "rules" / "code" / "linkage.json",
            self._paths.intent_root / "rules" / "code" / "linkage.yaml",
        ]

        for qa_path in policy_candidates:
            try:
                if qa_path.exists():
                    content = qa_path.read_text(encoding="utf-8")
                    # Handle both JSON and YAML rules
                    data = (
                        json.loads(content)
                        if qa_path.suffix == ".json"
                        else yaml.safe_load(content)
                    )
                    rules = data.get("rules", [])
                    qa_constraints = f"\n### Quality Assurance Targets\n{json.dumps(rules, indent=2)}"
                    logger.debug("Loaded QA constraints from: %s", qa_path)
                    break
            except Exception as e:
                logger.debug("Could not load QA policy from %s: %s", qa_path, e)
                continue

        if not qa_constraints:
            # Fallback to minimal default
            qa_constraints = (
                "\n### Quality Assurance Targets\n- Ensure 75%+ test coverage."
            )
            logger.debug("Using default QA constraints (no policy file found)")

        # Enrich the reconnaissance report with QA requirements
        enriched_recon = f"{reconnaissance_report}\n{qa_constraints}"

        # ENHANCED: Build complete action schemas with parameter requirements
        # This tells the LLM exactly what parameters each action needs
        actions = action_registry.list_all()
        action_schemas = get_all_action_schemas(actions)
        action_descriptions = json.dumps(action_schemas, indent=2)

        # Build planning prompt with all required context
        prompt = build_planning_prompt(
            self._paths, goal, action_descriptions, enriched_recon, self.prompt_template
        )

        client = await self.cognitive_service.aget_client_for_role("Planner")

        for attempt in range(self.max_retries):
            logger.info(
                "🧠 Planning execution steps (Attempt %d/%d)...",
                attempt + 1,
                self.max_retries,
            )

            response_text = await client.make_request_async(prompt)
            if response_text:
                try:
                    plan = parse_and_validate_plan(response_text)

                    # MANDATORY TRACING: Record the final plan decision
                    self.tracer.record(
                        agent=self.__class__.__name__,
                        decision_type="task_execution",
                        rationale="Decomposed goal into actionable steps based on Constitution and QA standards",
                        chosen_action=f"Generated plan with {len(plan)} steps",
                        context={"goal": goal, "steps": len(plan)},
                        confidence=0.9,
                    )
                    return plan
                except PlanExecutionError as e:
                    logger.warning(
                        "Plan validation failed on attempt %d: %s", attempt + 1, e
                    )
                    if attempt == self.max_retries - 1:
                        raise

        return []
