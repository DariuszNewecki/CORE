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


# ID: e518aa0c-3135-4154-913f-a1aa8f95212e
class CheckSkipped(Exception):
    """Raised by a check class that cannot run due to a known precondition gap.

    Distinct from a generic exception: the orchestrator records
    ``status="skipped"`` (not ``status="error"``) so governors can
    distinguish a deliberate skip from an unexpected failure.

    ``str(exc)`` is used as the ``reason`` in the check manifest, so
    keep the message short and machine-readable (e.g. ``"seed_gap"``).
    """


# ID: dabe3174-e170-43f1-8da4-39fd68fec3a6
class JudgeUnavailable(Exception):
    """The LLM judge could not judge a pair (call failed or timed out).

    Distinct from a "no contradiction" verdict: a pair that was never
    judged is unchecked, not clear.
    """


# ID: f3f7d3f0-caa2-44cb-b92c-88f2730bee3f
class CheckIncomplete(Exception):
    """Raised by a check class when some of its pairs could not be judged.

    Carries the candidates it did produce so they are kept; the orchestrator
    records ``status="partial"`` with the unjudged count, so a run whose
    judge was unreachable can never read as "0 contradictions".
    """

    def __init__(
        self,
        candidates: list[CoherenceCandidate],
        judged: int,
        unjudged: int,
        first_error: str,
    ) -> None:
        super().__init__(
            f"{unjudged} of {judged + unjudged} pairs unjudged: {first_error}"
        )
        self.candidates = candidates
        self.judged = judged
        self.unjudged = unjudged


# ID: 5641414f-99ba-42d9-bf53-d0e41d4d4291
class CheckClass(Protocol):
    """Common shape for every check class in the ADR-073 D3 taxonomy.

    Implementations are constructed by the CoherenceChecker orchestrator
    with the resources each class needs (repo_root, harvester, claims
    service, etc.) and yield CoherenceCandidate instances. Persistence
    and manifest book-keeping is the orchestrator's responsibility.
    """

    relation: str

    # ID: a8967c42-38a3-4161-bb66-bf03f1fe5a35
    async def run(self) -> list[CoherenceCandidate]: ...
