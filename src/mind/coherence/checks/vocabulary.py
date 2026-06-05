# src/mind/coherence/checks/vocabulary.py
"""VOCABULARY — surface non-canonical alias usage in governance artifacts.

Per ADR-073 D8 / topology §6.2 vocabulary invariant.

Mechanism (v1):
  1. Load the canonical vocabulary projection at .intent/META/vocabulary.json.
  2. For each (canonical_term, alias) pair in the projection, scan governance
     artifacts (.specs/{decisions,papers,northstar}/*.md) for alias usage.
  3. Emit a candidate when an alias appears in an artifact but the canonical
     term does NOT also appear there — indicating non-canonical usage rather
     than mere co-mention.

False positives ride the standard CCC triage flow per D8.

No LLM, no embeddings.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import CoherenceCandidate


# ID: a80cdd43-f35e-4af0-b034-67f1e0b46753
class VocabularyCheck:
    """Emit VOCABULARY for governance artifacts using non-canonical aliases."""

    relation = "VOCABULARY"

    # ID: 72eb54d5-6cfe-4f8b-9fd7-8bea4580452a
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)

    # ID: 3c0a85ca-154f-43ac-bc25-9fc458ced200
    async def run(self) -> list[CoherenceCandidate]:
        vocab_path = self._repo_root / ".intent" / "META" / "vocabulary.json"
        if not vocab_path.exists():
            return []
        data = json.loads(vocab_path.read_text(encoding="utf-8"))
        alias_map = _expand_alias_map(data.get("terms", []))
        if not alias_map:
            return []

        artifacts = list(_iter_governance_markdown(self._repo_root))
        candidates: list[CoherenceCandidate] = []
        for path in artifacts:
            content = path.read_text(encoding="utf-8", errors="replace")
            rel = str(path.relative_to(self._repo_root))
            for alias, canonical in alias_map.items():
                if _whole_word(content, alias) and not _whole_word(content, canonical):
                    candidates.append(
                        CoherenceCandidate(
                            relation=self.relation,
                            documents=[rel],
                            claim=(
                                f"`{alias}` is used in {rel} but the canonical term "
                                f"`{canonical}` does not appear in the same artifact."
                            ),
                            rationale=(
                                "Topology §6.2 (vocabulary invariant) requires "
                                "consistent term usage across the governance graph. "
                                f"`{alias}` is registered as an alias of `{canonical}` "
                                "in `.intent/META/vocabulary.json`. Using the alias "
                                "without also mentioning the canonical term signals "
                                "non-canonical usage rather than legitimate cross-reference. "
                                "Replace the alias with the canonical term, or — if the "
                                "alias is intended in a different sense — disambiguate "
                                "explicitly. Governor triage may dismiss if context "
                                "makes the alternative sense unambiguous."
                            ),
                        )
                    )
        return candidates


# ID: 3aaf2f0a-616d-4247-a4f8-51fa3ee53204
def _expand_alias_map(terms: list[dict]) -> dict[str, str]:
    """Expand the alias projection into {alias_token: canonical_term}.

    The vocabulary store stores some aliases as pipe-separated strings inside
    a single list entry (`["Handler | Processor | Step"]`); this helper
    splits them. Empty aliases produce no entries.
    """
    result: dict[str, str] = {}
    for term in terms:
        canonical = term.get("term")
        if not canonical:
            continue
        for raw in term.get("aliases", []) or []:
            if not isinstance(raw, str):
                continue
            for piece in raw.split("|"):
                token = piece.strip()
                if token and token.lower() != canonical.lower():
                    result[token] = canonical
    return result


def _whole_word(content: str, token: str) -> bool:
    """True iff `token` appears as a whole word in `content` (case-sensitive)."""
    return re.search(rf"\b{re.escape(token)}\b", content) is not None


def _iter_governance_markdown(repo_root: Path):
    """Yield governance markdown from .specs/{decisions,papers,northstar}/.

    F-42 ADR-091 D5 Phase 4: discovery routes through the spec_markdown
    artifact-type universe filtered to the three governance subdirectories.
    """
    from shared.infrastructure.intent.intent_repository import (
        get_intent_repository,
    )

    repo = get_intent_repository()
    spec_md_globs = repo.get_artifact_type("spec_markdown").content["discovery"]
    universe: set[Path] = set()
    for glob in spec_md_globs:
        universe.update(repo_root.glob(glob))
    governance_dirs = [
        repo_root / ".specs" / sub for sub in ("decisions", "papers", "northstar")
    ]
    for path in sorted(universe):
        if any(path.is_relative_to(d) for d in governance_dirs):
            yield path
