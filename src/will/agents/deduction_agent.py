# src/will/agents/deduction_agent.py

"""Provides functionality for the deduction_agent module."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

from shared.config import settings
from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: c594267d-fb40-447e-a885-00d1fb409119
class DeductionAgent:
    """
    Advises on LLM resource selection for a given role.
    In production it reads policy files; in tests/sandboxes it must be tolerant
    when those files aren't present.
    """

    def __init__(self, repo_path: Path | str):
        self.repo_path = Path(repo_path)
        self._policy: dict | None = None
        self.tracer = DecisionTracer()
        self._load_policies()

    def _load_policies(self) -> None:
        """
        Load selection policy from the Charter if present.
        If not present (common in isolated test sandboxes), degrade gracefully.
        """
        policy_path = (
            settings.MIND.parent / "charter" / "policies" / "agent_policy.yaml"
        )
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
                return
            except Exception as e:
                logger.warning(
                    "Failed to load agent policy (%s). Proceeding without it.", e
                )
                self._policy = {}
                return
        logger.warning(
            "Agent policy not found at %s — proceeding without it.", policy_path
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
