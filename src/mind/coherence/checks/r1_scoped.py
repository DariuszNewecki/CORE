# src/mind/coherence/checks/r1_scoped.py
"""R1_SCOPED — same-concern contradiction over ADR pairs declared via `Relates:`.

Per ADR-073 D2. Subset of SAMECONCERN constrained at the pair-membership step.
One-directional citation is sufficient: if ADR-X cites ADR-Y, pair (X, Y) is
checked regardless of whether ADR-Y cites ADR-X.

Mechanism: parse `Relates:` frontmatter, for each declared pair run kNN with
filter restricting hits to the partner ADR, then LLM-judge with the same
tiered policy as SAMECONCERN.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger

from ..llm_judge import judge_contradiction_pair
from .base import CoherenceCandidate


if TYPE_CHECKING:
    from body.governance.coherence_harvester import NormativeMarkerRegister
    from body.services.governance_claims_service import GovernanceClaimsService


logger = getLogger(__name__)


_RELATES_FRONTMATTER = re.compile(
    r"^\*\*Relates:\*\*\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)
_ADR_TOKEN = re.compile(r"ADR-\d{3}")

_HIGH_CONFIDENCE_COSINE = 0.78
_AMBIGUOUS_COSINE = 0.74
_KNN_LIMIT = 10


# ID: 411d5a1f-0a88-4a34-b1bc-4a64143daf09
class R1ScopedCheck:
    """Emit R1_SCOPED candidates for contradicting claims across declared ADR pairs."""

    relation = "R1_SCOPED"

    # ID: f24bd798-1f30-461e-9038-b791751970bc
    def __init__(
        self,
        repo_root: Path,
        register: NormativeMarkerRegister,
        claims_service: GovernanceClaimsService,
        cognitive_service: Any,
    ) -> None:
        self._repo_root = Path(repo_root)
        self._register = register
        self._claims_service = claims_service
        self._cognitive_service = cognitive_service

    # ID: 9208e1dc-5108-45b7-a2e1-514cc9df6af9
    async def run(self) -> list[CoherenceCandidate]:
        from body.governance.coherence_harvester import GovernanceClaimHarvester
        from shared.infrastructure.vector.cognitive_adapter import (
            CognitiveEmbedderAdapter,
        )

        pairs = self._declared_pairs()
        if not pairs:
            logger.info(
                "R1_SCOPED: no ADRs declare `Relates:` frontmatter — emitting zero (expected per D2)"
            )
            return []

        if not await self._claims_service.is_seeded():
            logger.info("R1_SCOPED: governance_claims not seeded; skipping (D4)")
            return []

        harvester = GovernanceClaimHarvester(self._repo_root, self._register)
        claims_by_path: dict[str, list] = {}
        for claim in harvester.harvest():
            claims_by_path.setdefault(claim.source_path, []).append(claim)

        embedder = CognitiveEmbedderAdapter(self._cognitive_service)
        seen: set[frozenset[tuple[str, str]]] = set()
        candidates: list[CoherenceCandidate] = []

        for source_path, partner_path in pairs:
            source_claims = claims_by_path.get(source_path, [])
            if not source_claims:
                continue
            for claim in source_claims:
                try:
                    vector = await embedder.get_embedding(claim.text)
                except Exception as exc:
                    logger.warning("R1_SCOPED: embed failed: %s", exc)
                    continue
                hits = await self._claims_service.search(
                    query_vector=vector,
                    limit=_KNN_LIMIT,
                    score_threshold=_AMBIGUOUS_COSINE,
                    source_path_in=[partner_path],
                )
                for hit in hits:
                    if (
                        hit.source_path == claim.source_path
                        and hit.content_sha == claim.content_sha
                    ):
                        continue
                    tier = (
                        "high_confidence"
                        if hit.cosine >= _HIGH_CONFIDENCE_COSINE
                        else "ambiguous"
                    )
                    pair_key: frozenset[tuple[str, str]] = frozenset(
                        {
                            (claim.source_path, claim.content_sha),
                            (hit.source_path, hit.content_sha),
                        }
                    )
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)

                    verdict = await judge_contradiction_pair(
                        cognitive_service=self._cognitive_service,
                        text_a=claim.text,
                        source_a=claim.source_path,
                        text_b=hit.text,
                        source_b=hit.source_path,
                        tier=tier,
                        relation=self.relation,
                    )
                    if verdict is not None:
                        candidates.append(verdict)
        return candidates

    # ID: 7939908b-6686-4b35-b3e6-a74f6ae1fbaf
    def _declared_pairs(self) -> list[tuple[str, str]]:
        """Parse Relates: frontmatter across all accepted ADRs.

        Returns a list of (source_adr_path, partner_adr_path) tuples — one
        per declared link. One-directional sufficient per D2.
        """
        decisions = self._repo_root / ".specs" / "decisions"
        if not decisions.is_dir():
            return []
        # Map ADR-NNN → relative path, used to resolve cited tokens to files.
        adr_path_by_id: dict[str, str] = {}
        for path in sorted(decisions.glob("ADR-*.md")):
            m = _ADR_TOKEN.match(path.stem)
            if m:
                adr_path_by_id[m.group(0)] = str(path.relative_to(self._repo_root))

        pairs: list[tuple[str, str]] = []
        for source_id, source_rel in adr_path_by_id.items():
            content = (self._repo_root / source_rel).read_text(
                encoding="utf-8", errors="replace"
            )
            match = _RELATES_FRONTMATTER.search(content)
            if not match:
                continue
            for partner_id in _ADR_TOKEN.findall(match.group(1)):
                if partner_id == source_id:
                    continue
                partner_rel = adr_path_by_id.get(partner_id)
                if partner_rel is None:
                    continue
                pairs.append((source_rel, partner_rel))
        return pairs
