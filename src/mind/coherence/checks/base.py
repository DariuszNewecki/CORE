# src/mind/coherence/checks/base.py
"""Shared types for CCC check classes per ADR-073 D3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
# ID: f65b81c3-fff5-41e2-9c9a-58db1d4eeb6b
class CoherenceCandidate:
    """One emitted candidate row, persisted via CoherenceService.add_candidate."""

    relation: str
    documents: list[str]
    claim: str
    rationale: str


# ID: 5641414f-99ba-42d9-bf53-d0e41d4d4291
class CheckClass(Protocol):
    """Common shape for every check class in the ADR-073 D3 taxonomy.

    Implementations are constructed by the CoherenceChecker orchestrator
    with the resources each class needs (repo_root, harvester, claims
    service, etc.) and yield CoherenceCandidate instances. Persistence
    and manifest book-keeping is the orchestrator's responsibility.
    """

    relation: str

    async def run(self) -> list[CoherenceCandidate]: ...
