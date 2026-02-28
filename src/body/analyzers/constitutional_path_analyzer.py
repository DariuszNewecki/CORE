# ID: a2b3c4d5-e6f7-8901-abcd-ef1234567812
# src/body/analyzers/constitutional_path_analyzer.py

from __future__ import annotations

import time
from typing import Any

from body.analyzers.base_analyzer import BaseAnalyzer
from shared.component_primitive import ComponentResult
from shared.infrastructure.intent.intent_repository import get_intent_repository


# ID: 9666577f-5e1f-4dea-a104-59c72bfffe82
class ConstitutionalPathAnalyzer(BaseAnalyzer):
    """
    PARSE Phase Component.
    Authoritatively discovers all artifacts indexed in the Mind (.intent/).

    CONSTITUTIONAL ALIGNMENT:
    - Authority: IntentRepository (The sole gateway to the Mind).
    - Boundary: Read-only access to indexed policies and META contracts.
    """

    # ID: ba8e4735-0988-479a-92ad-5aeeba2ba4c6
    async def execute(self, **kwargs: Any) -> ComponentResult:
        start_time = time.time()

        # 1. Access the Mind through the sanctioned gateway
        # This automatically triggers validate_intent_tree (Bootstrap Contract v0)
        repo = get_intent_repository()
        repo.initialize()  # Builds the in-memory index

        # 2. Sensation: Retrieve only what the Repository has indexed as "Law"
        # This prevents the Body from 'hallucinating' or crawling unindexed files.
        policy_paths = [str(ref.path) for ref in repo.list_policies()]

        # 3. Add the "Contractual Primitives" (META files required for system operation)
        # These are derived from the repo.root provided by the PathResolver.
        core_structure = [
            repo.root / "META" / "intent_tree.schema.json",
            repo.root / "META" / "rule_document.schema.json",
            repo.root / "META" / "enums.json",
            repo.root / "constitution" / "precedence_rules.yaml",
        ]

        artifacts = policy_paths + [str(p) for p in core_structure if p.exists()]
        unique_artifacts = sorted(list(set(artifacts)))

        duration = time.time() - start_time

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            data={"paths": unique_artifacts, "count": len(unique_artifacts)},
            phase=self.phase,
            confidence=1.0,
            duration_sec=duration,
            metadata={
                "intent_root": str(repo.root),
                "rationale": "Collected indexed policy refs and META contracts from IntentRepository.",
            },
        )
