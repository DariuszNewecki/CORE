# src/will/agents/deduction_agent.py

"""
DeductionAgent: Advises on LLM resource selection for cognitive roles.

CONSTITUTIONAL COMPLIANCE:
- Uses PathResolver for all .intent/ path resolution
- No hardcoded directory paths
- Gracefully degrades when policy files not present (test/sandbox tolerance)
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: c594267d-fb40-447e-a885-00d1fb409119
class DeductionAgent:
    """
    Advises on LLM resource selection for a given role.

    Reads agent policy from .intent/ structure if present.
    Gracefully degrades when policy files are absent (common in tests/sandboxes).

    CONSTITUTIONAL COMPLIANCE:
    - Uses PathResolver for all path resolution
    - No hardcoded .intent/ subdirectory paths
    - Tolerates missing policies (test-friendly)
    """

    def __init__(self, path_resolver: PathResolver, repo_path: Path | str):
        self._paths = path_resolver
        self.repo_path = Path(repo_path)
        self._policy: dict | None = None
        self.tracer = DecisionTracer()
        self._load_policies()

    def _load_policies(self) -> None:
        """
        Load agent selection policy from .intent/ structure if present.

        Searches multiple possible locations in new structure:
        - .intent/phases/agent_policy.yaml
        - .intent/workflows/agent_policy.yaml
        - .intent/rules/will/agent_policy.yaml (as fallback)

        If not present (common in isolated test sandboxes), degrades gracefully.
        """
        # FIXED: Removed hardcoded 'charter/policies/' path
        # Search in new .intent/ structure locations
        possible_paths = [
            self._paths.intent_root / "phases" / "agent_policy.yaml",
            self._paths.intent_root / "workflows" / "agent_policy.yaml",
            self._paths.intent_root / "rules" / "will" / "agent_policy.yaml",
        ]

        for policy_path in possible_paths:
            if policy_path.exists():
                try:
                    self._policy = (
                        yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
                    )
                    if not isinstance(self._policy, dict):
                        logger.warning(
                            "Agent policy is not a mapping; ignoring: %s", policy_path
                        )
                        self._policy = {}
                        continue

                    logger.debug("Loaded agent policy from: %s", policy_path)
                    return
                except Exception as e:
                    logger.warning(
                        "Failed to load agent policy from %s (%s). Trying next location.",
                        policy_path,
                        e,
                    )
                    continue

        # No policy found in any location - degrade gracefully
        logger.debug(
            "Agent policy not found in any expected location — proceeding without it."
        )
        self._policy = {}

    # ID: ebb57053-2ee5-4f2b-8fd6-28b1300766e5
    def select_resource(
        self,
        role: CognitiveRole,
        candidates: Iterable[LlmResource],
        task_context: str | None = None,
    ) -> str | None:
        """
        Return a preferred resource name if policy can pick one, else None.

        Policy-light heuristic:
          - Prefer lower performance_metadata.cost_rating if present.
          - Otherwise return None and let the caller decide (e.g., cheapest).

        Args:
            role: Cognitive role requiring LLM resource
            candidates: Available LLM resources to choose from
            task_context: Optional context for decision-making

        Returns:
            Name of selected resource, or None if no preference
        """
        candidates = list(candidates)
        if not candidates:
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="task_execution",
                rationale="Executing goal based on input context",
                chosen_action="No candidate LLM resources provided; returning None",
                confidence=0.9,
            )
            return None

        best = None
        best_rating = None

        for r in candidates:
            md = getattr(r, "performance_metadata", None) or {}
            rating = md.get("cost_rating")
            if rating is None:
                continue
            try:
                rating = float(rating)
            except Exception:
                continue
            if best_rating is None or rating < best_rating:
                best_rating = rating
                best = r

        if best is None:
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="task_execution",
                rationale="Executing goal based on input context",
                chosen_action="No LLM resource selected after evaluating candidates; returning None",
                confidence=0.9,
            )
            return None

        self.tracer.record(
            agent=self.__class__.__name__,
            decision_type="task_execution",
            rationale="Executing goal based on input context",
            chosen_action=f"Selected LLM resource '{best.name}' for role {role}",
            confidence=0.9,
        )
        return best.name
