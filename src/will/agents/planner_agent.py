# src/will/agents/planner_agent.py
# ID: ad85dc18-646b-4bb9-95df-2d9a63873d26

"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan.

CONSTITUTIONAL ENHANCEMENT (V2.5.0):
"Legal Counsel": Now performs RAG (Retrieval Augmented Generation) against
the Constitution before planning.
The Planner searches the 'core_policies' vector collection for rules relevant
to the specific user goal and injects them into the prompt.
Prevents "Trial by Fire" (proposing illegal plans that get blocked by the Body).

HARDENING (V2.6):
Removed non-deterministic random cleanup to satisfy P1.2.
Cleaned imports to reduce layer leakage.
"""

from __future__ import annotations

import json
from pathlib import Path

from body.atomic.registry import action_registry
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError
from shared.path_resolver import PathResolver
from will.agents.action_introspection import get_all_action_schemas
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
        """
        self.cognitive_service = cognitive_service
        self.tracer = DecisionTracer()
        self.repo_path = repo_path
        self._paths = PathResolver(repo_path)
        self.max_retries = max_retries

        # Initialize the Legal Counsel (Policy Vectorizer)
        self.legal_counsel = PolicyVectorizer(
            repo_root=repo_path,
            cognitive_service=cognitive_service,
            qdrant_service=cognitive_service.qdrant_service,
        )

        # Load Prompt Template
        prompt_path = self._paths.prompt("planner_agent")
        try:
            self.prompt_template = prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(
                "Constitutional prompt 'planner_agent.prompt' missing from %s",
                prompt_path,
            )
            raise

    # ID: 2d8e41a4-423b-4381-8f35-fce3dc238ab2
    async def create_execution_plan(
        self,
        goal: str,
        reconnaissance_report: str = "",
    ) -> list[ExecutionTask]:
        """
        Creates an execution plan, informed by relevant constitutional laws.
        """

        # 1. LEGAL COUNSEL: Consult the Constitution (RAG)
        logger.info("⚖️  Planner requesting legal counsel for goal: '%s'", goal)
        relevant_policies = await self.legal_counsel.search_policies(
            query=goal,
            limit=5,
        )

        # Format legal advice for the LLM
        legal_brief: list[str] = []

        if relevant_policies:
            legal_brief.append("### RELEVANT CONSTITUTIONAL LAWS")
            legal_brief.append(
                "You MUST adhere to the following laws found in the Constitution:"
            )

            for hit in relevant_policies:
                payload = hit.get("payload", {})
                rule_id = payload.get("section_path") or "unknown_rule"
                content = payload.get("content", "").replace("\n", " ").strip()
                severity = payload.get("severity", "error")

                prefix = "⛔ CRITICAL" if severity == "error" else "⚠️  WARNING"
                legal_brief.append(f"- {prefix} ({rule_id}): {content[:300]}")
        else:
            legal_brief.append("### CONSTITUTIONAL CHECK")
            legal_brief.append(
                "No specific specific policies found for this topic. "
                "Proceed with standard caution."
            )

        constitutional_context = "\n".join(legal_brief)

        # 2. Context Integration
        enriched_recon = f"{reconnaissance_report}\n\n{constitutional_context}"

        actions = action_registry.list_all()
        action_schemas = get_all_action_schemas(actions)
        action_descriptions = json.dumps(action_schemas, indent=2)

        prompt = build_planning_prompt(
            self._paths,
            goal,
            action_descriptions,
            enriched_recon,
            self.prompt_template,
        )

        # 3. Strategic Planning Loop
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

                    self.tracer.record(
                        agent="PlannerAgent",
                        decision_type="plan_creation",
                        rationale="Decomposed goal into actionable steps",
                        chosen_action=f"Generated plan with {len(plan)} steps",
                        context={
                            "goal": goal,
                            "laws_consulted": len(relevant_policies),
                            "steps": len(plan),
                        },
                        confidence=0.9,
                    )

                    return plan

                except PlanExecutionError as e:
                    logger.warning(
                        "Plan validation failed on attempt %d: %s",
                        attempt + 1,
                        e,
                    )
                    if attempt == self.max_retries - 1:
                        raise

        return []
