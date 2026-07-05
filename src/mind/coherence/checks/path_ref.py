# src/mind/coherence/checks/path_ref.py
"""PATH_REF — governance document references a filesystem path that does not exist.

Scans all .specs/**/*.md and .intent/**/*.yaml for backtick-quoted
repo-relative path references (starting with .specs/, .intent/, or src/)
and verifies each resolves to a real path on the filesystem.

No LLM. No vectors. Pure filesystem check.

Addresses CCC scope gap F-02 (within-document path reference validity).
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CoherenceCandidate


_BACKTICK_PATH = re.compile(r"`(\.(?:specs|intent|src)/[^`]+)`")


# ID: 2a23bd4c-81be-4af3-9391-aadfcad40a0d
class PathRefCheck:
    """Emit PATH_REF for backtick-quoted repo paths that do not exist on disk."""

    relation = "PATH_REF"

    # ID: 549b09aa-16fc-4cc1-a7f0-25901af81d2d
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)

    # ID: c0749863-f20d-4cb4-ac5e-9e7eb553fa7d
    async def run(self) -> list[CoherenceCandidate]:
        candidates: list[CoherenceCandidate] = []
        for doc_path in self._governance_docs():
            try:
                content = doc_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel_doc = str(doc_path.relative_to(self._repo_root))
            seen: set[str] = set()
            for match in _BACKTICK_PATH.finditer(content):
                ref = match.group(1).rstrip("/.,;:)")
                if ref in seen:
                    continue
                seen.add(ref)
                if (self._repo_root / ref).exists():
                    continue
                candidates.append(
                    CoherenceCandidate(
                        relation=self.relation,
                        documents=[rel_doc],
                        claim=(
                            f"`{rel_doc}` references `{ref}` which does not exist "
                            "on the filesystem."
                        ),
                        rationale=(
                            "Governance documents must not reference repo paths that "
                            "do not exist. Either the path has moved (update the "
                            "reference), the artifact was deleted (remove or update "
                            "the reference), or the section is historical/superseded "
                            "(add an explicit disclaimer per the CORE-CHARTER §0 "
                            "supersession-note pattern)."
                        ),
                    )
                )
        return candidates

    def _governance_docs(self) -> list[Path]:
        """All .specs/**/*.md and .intent/**/*.yaml governance documents."""
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        repo = get_intent_repository()
        spec_globs = repo.get_artifact_type("spec_markdown").content["discovery"]
        yaml_globs = repo.get_artifact_type("intent_yaml").content["discovery"]
        universe: set[Path] = set()
        for glob in (*spec_globs, *yaml_globs):
            universe.update(self._repo_root.glob(glob))
        return sorted(p for p in universe if p.is_file())
