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

from shared.governance.coherence_harvester import (
    NOT_IN_FORCE_STATUSES,
    document_status,
)

from .base import CoherenceCandidate


_BACKTICK_PATH = re.compile(r"`(\.(?:specs|intent|src)/[^`]+)`")

# Glob wildcards and template placeholders: a match containing any of these
# documents a *convention* or *family of files* ("every worker declares
# itself at `.intent/workers/*.yaml`"), not a specific file — it can never
# "exist on the filesystem" by definition, so it can never be a real
# PATH_REF finding (#832).
_GLOB_OR_PLACEHOLDER_CHARS = frozenset("*<>{}")

# Locators that follow a path but are not part of it: `#anchor`, `:195-204`
# (hyphen or en dash), `:L12`, `:§5`, ` §4a`. Run 6558a043 reported 41 existing paths as missing
# because these were kept in the path.
_LOCATOR_SUFFIX = re.compile(
    r"(?:#.*|\s*:?\s*§.*|:L?\d+(?:\s*[\u2013-]\s*\d+)?(?:\s*,.*)?)$"
)
_BARE_ADR_ID = re.compile(r"^\.specs/decisions/ADR-\d+$")


def _normalize_ref(raw: str) -> str | None:
    """The path a backtick reference names, or None when it names no path.

    Markdown line-wrapping is joined; locator suffixes are dropped; an
    ellipsis or remaining whitespace means prose ("`.intent/ <-> Qdrant`"),
    not a path.
    """
    ref = re.sub(r"\s*\n\s*", "", raw)
    ref = _LOCATOR_SUFFIX.sub("", ref).rstrip("/.,;:)")
    if "…" in ref or "..." in ref or re.search(r"\s", ref):
        return None
    return ref or None


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
            # A superseded or retired document is history: its paths are the
            # paths of its time (ADR-105 D5 terminal states).
            if document_status(content) in NOT_IN_FORCE_STATUSES:
                continue
            rel_doc = str(doc_path.relative_to(self._repo_root))
            seen: set[str] = set()
            for match in _BACKTICK_PATH.finditer(content):
                ref = _normalize_ref(match.group(1))
                if ref is None or ref in seen:
                    continue
                seen.add(ref)
                if _GLOB_OR_PLACEHOLDER_CHARS.intersection(ref):
                    continue
                if self._resolves(ref):
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

    def _resolves(self, ref: str) -> bool:
        """True when *ref* exists; a bare ``ADR-NNN`` resolves to its file."""
        if (self._repo_root / ref).exists():
            return True
        if _BARE_ADR_ID.match(ref):
            parent = (self._repo_root / ref).parent
            return any(parent.glob(Path(ref).name + "-*.md"))
        return False

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
