# src/core/agents/deduction_agent.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import yaml

from services.database.models import CognitiveRole, LlmResource
from shared.config import settings
from shared.logger import getLogger

log = getLogger(__name__)


# ID: 6cdae3a9-a62c-4558-aff2-b51d953dfde8
class DeductionAgent:
    """
    Advises on LLM resource selection for a given role.
    In production it reads policy files; in tests/sandboxes it must be tolerant
    when those files aren’t present.
    """

    def __init__(self, repo_path: Path | str):
        self.repo_path = Path(repo_path)
        self._policy: dict | None = None
        self._load_policies()

    def _load_policies(self) -> None:
        """
        Load selection policy from the Charter if present.
        If not present (common in isolated test sandboxes), degrade gracefully.
        """
        # Preferred constitutional location
        policy_path = (
            settings.MIND.parent / "charter" / "policies" / "agent_policy.yaml"
        )
        if policy_path.exists():
            try:
                self._policy = (
                    yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
                )
                if not isinstance(self._policy, dict):
                    log.warning(
                        "Agent policy is not a mapping; ignoring: %s", policy_path
                    )
                    self._policy = {}
                return
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "Failed to load agent policy (%s). Proceeding without it.", e
                )
                self._policy = {}
                return

        # Fallback: don’t crash in tests; proceed without policy
        log.warning(
            "Agent policy not found at %s — proceeding without it.", policy_path
        )
        self._policy = {}

    # ID: d25e3279-3af2-4ded-ae84-787683807c23
    def select_resource(
        self,
        role: CognitiveRole,
        candidates: Iterable[LlmResource],
        task_context: str | None = None,
    ) -> Optional[str]:
        """
        Return a preferred resource name if policy can pick one, else None.
        Policy-light heuristic:
          - Prefer lower performance_metadata.cost_rating if present.
          - Otherwise return None and let the caller decide (e.g., cheapest).
        """
        candidates = list(candidates)
        if not candidates:
            return None

        # If policy defines something more advanced, you can add it here later.

        # Heuristic: prefer lowest cost_rating if available
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

        return best.name if best is not None else None
