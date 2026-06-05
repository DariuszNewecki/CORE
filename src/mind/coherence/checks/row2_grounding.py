# src/mind/coherence/checks/row2_grounding.py
"""ROW2_GROUNDING — every accepted ADR cites at least one grounding paper.

Per ADR-073 D6 / topology §10.2 row 2.

Mechanism: structural grep over ADR References / Relates / Supersedes blocks.
No LLM, no embeddings.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CoherenceCandidate


_PAPERS_CITE = re.compile(r"\.specs/papers/[\w\-./]+\.md", re.IGNORECASE)
_SUPERSEDES_FRONTMATTER = re.compile(r"^\*\*Supersedes", re.IGNORECASE | re.MULTILINE)
_STATUS_ACCEPTED = re.compile(
    r"^\*\*Status:\*\*\s*Accepted", re.IGNORECASE | re.MULTILINE
)


# ID: d89bcb64-5a44-42a9-af06-ba730a70cf10
class Row2GroundingCheck:
    """Emit ROW2_GROUNDING for accepted ADRs missing a grounding paper citation."""

    relation = "ROW2_GROUNDING"

    # ID: 21f65c05-2345-4135-a581-b68b8000de23
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)

    # ID: 460370e4-9d2d-479e-967c-df37f7e7ab9e
    async def run(self) -> list[CoherenceCandidate]:
        # F-42 ADR-091 D5 Phase 4: ADR discovery routes through the
        # spec_markdown artifact-type universe filtered to .specs/decisions/
        # with the ADR-N name pattern.
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        spec_md_globs = repo.get_artifact_type("spec_markdown").content["discovery"]
        decisions = self._repo_root / ".specs" / "decisions"
        if not decisions.is_dir():
            return []
        universe: set[Path] = set()
        for glob in spec_md_globs:
            universe.update(self._repo_root.glob(glob))
        adr_paths = sorted(
            p
            for p in universe
            if p.is_relative_to(decisions) and p.name.startswith("ADR-")
        )
        candidates: list[CoherenceCandidate] = []
        for adr_path in adr_paths:
            content = adr_path.read_text(encoding="utf-8", errors="replace")
            if not _STATUS_ACCEPTED.search(content):
                continue
            if _SUPERSEDES_FRONTMATTER.search(content):
                continue
            if _PAPERS_CITE.search(content):
                continue
            rel = str(adr_path.relative_to(self._repo_root))
            candidates.append(
                CoherenceCandidate(
                    relation=self.relation,
                    documents=[rel],
                    claim=(
                        f"ADR {adr_path.stem} cites no grounding paper "
                        "(.specs/papers/...) and carries no Supersedes: declaration."
                    ),
                    rationale=(
                        "Topology paper §3 row 2 requires every accepted ADR to "
                        "either cite at least one grounding paper or declare "
                        "supersession of a predecessor (which inherits its "
                        "predecessor's grounding). Neither was found in this "
                        "ADR's text. Either backfill the References block with "
                        "the operationalized paper, or — if no grounding paper "
                        "exists — author the missing paper first per §11.3."
                    ),
                )
            )
        return candidates
