# src/mind/coherence/checks/row2_grounding.py
"""ROW2_GROUNDING — every accepted ADR cites at least one grounding paper.

Per ADR-073 D6 / topology §10.2 row 2.

Two sub-checks run in sequence:

1. Basic grounding absence: an accepted ADR with no paper citation and no
   supersedes declaration emits ROW2_GROUNDING.

2. Inherited bind verification (#615): when an ADR does declare supersession
   of a specific predecessor (e.g. "Supersedes: ADR-042"), the inherited bind
   is only valid if the predecessor itself carries a grounding paper citation
   or its own supersedes declaration. A broken chain — where neither the ADR
   nor any of its declared predecessors has grounding — also emits
   ROW2_GROUNDING with a rationale describing the break point.

   Verification is one level deep. If the predecessor itself has a supersedes
   declaration, that predecessor's own chain is governed by its own
   ROW2_GROUNDING pass; breaking the chain there will produce a separate
   finding rather than requiring full transitive resolution here.

Mechanism: structural grep over ADR References / Relates / Supersedes blocks.
No LLM, no embeddings.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CoherenceCandidate


_PAPERS_CITE = re.compile(r"\.specs/papers/[\w\-./]+\.md", re.IGNORECASE)
_SUPERSEDES_LINE = re.compile(r"^\*\*Supersedes", re.IGNORECASE | re.MULTILINE)
_SUPERSEDES_ADR_ID = re.compile(r"\bADR-(\d+)\b")
_STATUS_ACCEPTED = re.compile(
    r"^\*\*Status:\*\*\s*Accepted", re.IGNORECASE | re.MULTILINE
)


# ID: ca1e4a12-5d3f-4f8a-b8e9-f2a7c3d1e094
def _extract_supersedes_adr_ids(content: str) -> list[str]:
    """Return the ADR-N ids named on any Supersedes line in the prose.

    Ignores "Supersedes: none / nothing" lines (no ADR id present).
    """
    ids: list[str] = []
    for match in _SUPERSEDES_LINE.finditer(content):
        # Grab the rest of the line from the match start
        line_start = match.start()
        line_end = content.find("\n", line_start)
        line = content[line_start:line_end] if line_end != -1 else content[line_start:]
        for id_match in _SUPERSEDES_ADR_ID.finditer(line):
            ids.append(f"ADR-{id_match.group(1)}")
    return ids


# ID: 7b4e2c9a-1d3f-4a6b-9e8d-c5f2b0a3d7e1
def _find_adr_file(adr_id: str, decisions_dir: Path) -> Path | None:
    """Locate the .md file for adr_id (e.g. 'ADR-42' or 'ADR-042') in decisions_dir."""
    raw = adr_id.split("-", 1)[1].lstrip("0") or "0"
    num = int(raw)
    for pattern in (f"ADR-{num:03d}-*.md", f"ADR-{num}-*.md"):
        hits = sorted(decisions_dir.glob(pattern))
        if hits:
            return hits[0]
    return None


# ID: 3f8d1b7e-6c4a-4e2d-a9f5-b7c3d2e1f0a8
def adr_has_grounding_or_supersedes(content: str) -> bool:
    """True if the ADR text has a grounding paper citation OR a Supersedes declaration.

    Used to validate an inherited bind: a predecessor that satisfies either
    condition is considered to have valid grounding to pass forward.
    """
    return bool(_PAPERS_CITE.search(content) or _SUPERSEDES_LINE.search(content))


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
            if _PAPERS_CITE.search(content):
                continue

            rel = str(adr_path.relative_to(self._repo_root))

            # Does this ADR declare supersession?
            supersedes_ids = _extract_supersedes_adr_ids(content)
            if supersedes_ids:
                # Verify each inherited bind: the predecessor must have either
                # a grounding paper citation or its own supersedes declaration.
                broken: list[str] = []
                for sid in supersedes_ids:
                    pred_file = _find_adr_file(sid, decisions)
                    if pred_file is None:
                        broken.append(f"{sid} (file not found)")
                        continue
                    pred_content = pred_file.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    if not adr_has_grounding_or_supersedes(pred_content):
                        broken.append(sid)
                if not broken:
                    continue  # All declared predecessors have valid grounding
                candidates.append(
                    CoherenceCandidate(
                        relation=self.relation,
                        documents=[rel],
                        claim=(
                            f"ADR {adr_path.stem} inherits grounding from "
                            f"{', '.join(supersedes_ids)} but "
                            f"{', '.join(broken)} "
                            "carry neither a grounding paper citation nor a "
                            "Supersedes declaration. The inherited bind is broken."
                        ),
                        rationale=(
                            "ADR-073 D6 ROW2_GROUNDING requires that when an ADR "
                            "claims grounding by supersession, the predecessor must "
                            "itself carry valid grounding to pass forward. A broken "
                            "chain — where the predecessor has neither a paper "
                            "citation nor its own supersedes — means no grounding "
                            "exists in the inheritance line. Either backfill the "
                            "predecessor with a grounding paper citation, or verify "
                            "the supersedes declaration is correct."
                        ),
                    )
                )
                continue

            # No paper citation and no supersedes declaration at all.
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
