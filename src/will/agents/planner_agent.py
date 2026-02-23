# src/will/agents/planner_agent.py
# ID: ad85dc18-646b-4bb9-95df-2d9a63873d26

"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan.

CONSTITUTIONAL ENHANCEMENT (V2.3.0):
"Legal Counsel": Now performs RAG (Retrieval Augmented Generation) against
the Constitution before planning.
The Planner searches the 'core_policies' vector collection for rules relevant
to the specific user goal and injects them into the prompt.
Prevents "Trial by Fire" (proposing illegal plans that get blocked by the Body).

HARDENING (V2.3.0):
- Removed non-deterministic random cleanup to satisfy P1.2.
- Cleaned imports to reduce layer leakage.
- Memory cleanup is now an explicit CLI command only (core-admin cleanup memory).
"""

from __future__ import annotations

import json
from pathlib import Path

from body.atomic.registry import action_registry
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError
from shared.path_resolver import PathResolver
from will.agents.base_planner import build_planning_prompt, parse_and_validate_plan
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.decision_tracer import DecisionTracer
from will.tools.policy_vectorizer import PolicyVectorizer


logger = getLogger(__name__)


# ID: c0bf833c-f3a2-4508-8cd0-1d6474eebb4d
class PlannerAgent:
    """Decomposes goals into constitutionally-aligned executable plans."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        repo_path: Path,
        max_retries: int = 3,
    ):
        """
        Initializes the PlannerAgent with Legal Counsel capabilities.

        Args:
            cognitive_service: LLM orchestration service
            repo_path: Repository root path for policy lookup
            max_retries: Maximum planning attempts on validation failure
        """
        self.cognitive_service = cognitive_service
        self.repo_path = repo_path
        self.max_retries = max_retries
        self.tracer = DecisionTracer()
        self.policy_vectorizer = PolicyVectorizer(cognitive_service)

    # ID: 1ea9ec86-10a3-4356-9c31-c14e53c8fd0
    # ID: 52208224-fea7-4d79-baee-d3b07d634624
    async def create_execution_plan(
        self, goal: str, reconnaissance_report: str = ""
    ) -> list[ExecutionTask]:
        """
        Creates an execution plan from a user goal and a reconnaissance report.

        CONSTITUTIONAL COMPLIANCE:
        - P1.2: Pure planning — no side effects, no random, no cleanup calls.
        - Legal Counsel: Fetches relevant constitutional rules via RAG before planning.
        - Tracing: Records decision for every plan created (planning.trace_mandatory).

        Args:
            goal: High-level user goal
            reconnaissance_report: Optional context from ReconnaissanceAgent

        Returns:
            List of ExecutionTask objects representing the plan
        """
        # LEGAL COUNSEL: Fetch relevant constitutional rules for this goal
        constitutional_context = await self._fetch_constitutional_context(goal)

        # Load QA constraints from policy files
        qa_constraints = self._load_qa_constraints()

        # Enrich the reconnaissance report with constitutional rules and QA requirements
        enriched_recon = (
            f"{reconnaissance_report}\n{constitutional_context}\n{qa_constraints}"
        )

        # Build action descriptions from the live Registry
        actions = action_registry.list_all()
        action_descriptions = json.dumps(
            [
                {
                    "action_id": a.action_id,
                    "description": a.description,
                    "impact": a.impact_level,
                }
                for a in actions
            ],
            indent=2,
        )

        # Load the planning prompt template
        path_resolver = PathResolver(self.repo_path)
        try:
            prompt_template = path_resolver.prompt("planner_agent").read_text(
                encoding="utf-8"
            )
        except FileNotFoundError:
            logger.error(
                "Constitutional prompt 'planner_agent.prompt' missing from var/prompts/"
            )
            raise

        prompt = build_planning_prompt(
            goal, action_descriptions, enriched_recon, prompt_template
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

                    # MANDATORY TRACING: Record the final plan decision (planning.trace_mandatory)
                    self.tracer.record(
                        agent=self.__class__.__name__,
                        decision_type="task_execution",
                        rationale=(
                            "Decomposed goal into actionable steps "
                            "based on Constitution and QA standards"
                        ),
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

    # ID: b3e7f1a2-5c9d-4e8f-a2b6-c8d1e4f7a3b9
    async def _fetch_constitutional_context(self, goal: str) -> str:
        """
        Performs RAG against the Constitution for rules relevant to this goal.

        This is the "Legal Counsel" step: the planner consults constitutional
        rules before proposing a plan, preventing illegal proposals.

        Args:
            goal: The planning goal to search against

        Returns:
            Formatted string of relevant constitutional rules, or empty string
        """
        try:
            policy_hits = await self.policy_vectorizer.search_policies(
                query=goal, limit=5
            )
            if not policy_hits:
                return ""

            rules_text = "\n### Relevant Constitutional Rules\n"
            for hit in policy_hits:
                payload = hit.get("payload", {})
                rule_id = payload.get("rule_id", "unknown")
                statement = payload.get("statement", "")
                enforcement = payload.get("enforcement", "reporting")
                rules_text += f"- [{enforcement.upper()}] {rule_id}: {statement}\n"

            return rules_text

        except Exception as e:
            # Legal Counsel failure is non-fatal — plan without it, log the gap
            logger.warning(
                "Constitutional context fetch failed (planning without RAG): %s", e
            )
            return ""

    # ID: d4f8e2c1-b7a5-9e3f-c6d2-a1f4e7b9c3d5
    def _load_qa_constraints(self) -> str:
        """
        Loads QA constraints from constitutional policy files.

        Uses PathResolver (injected via repo_path) instead of importing
        settings directly, to comply with architecture.boundary.settings_access.
        """
        import json

        import yaml

        path_resolver = PathResolver(self.repo_path)

        for policy_name in ["purity", "quality_assurance"]:
            try:
                qa_path = path_resolver.policy(policy_name)
                if qa_path.exists():
                    content = qa_path.read_text(encoding="utf-8")
                    data = (
                        json.loads(content)
                        if qa_path.suffix == ".json"
                        else yaml.safe_load(content)
                    )
                    rules = data.get("rules", [])
                    return (
                        f"\n### Quality Assurance Targets\n"
                        f"{json.dumps(rules, indent=2)}"
                    )
            except Exception:
                continue

        return "\n### Quality Assurance Targets\n- Ensure 75%+ test coverage."
