# src/mind/coherence/checks/row4_naming.py
"""ROW4_NAMING — every `.intent/` artifact is named in at least one accepted
ADR's D-text, or predates topology paper acceptance (grandfathered).

Per ADR-073 D6 / topology §10.2 row 4 + §11.1 backfill-on-touch posture.

Grandfather signal is git-history first-appearance date
(`git log --diff-filter=A`) compared against the topology paper's acceptance
date (2026-05-26). Filesystem mtime is not used — it does not survive clone
or touch.

Mechanism: structural grep over ADR D-text for the artifact's path. No LLM.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

from .base import CoherenceCandidate


_TOPOLOGY_ACCEPTANCE = date(2026, 5, 26)
_STATUS_ACCEPTED = re.compile(
    r"^\*\*Status:\*\*\s*Accepted", re.IGNORECASE | re.MULTILINE
)
_META_PARTS = {"META"}


# ID: a7968f92-b6b9-4d0d-bb5d-6e6a7a6a4d43
class Row4NamingCheck:
    """Emit ROW4_NAMING for post-topology artifacts not named in any accepted ADR."""

    relation = "ROW4_NAMING"

    # ID: 99603b79-9830-4568-98bc-c59d9f5eb676
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)

    # ID: 809cc4b0-5fd8-47f0-a29d-930848b6e279
    async def run(self) -> list[CoherenceCandidate]:
        intent = self._repo_root / ".intent"
        if not intent.is_dir():
            return []
        accepted_adr_texts = self._collect_accepted_adr_text()
        candidates: list[CoherenceCandidate] = []
        for path in _iter_intent_artifacts(self._repo_root):
            rel = str(path.relative_to(self._repo_root))
            if any(rel in text for text in accepted_adr_texts):
                continue
            first_seen = self._git_first_seen(rel)
            if first_seen is not None and first_seen < _TOPOLOGY_ACCEPTANCE:
                continue
            candidates.append(
                CoherenceCandidate(
                    relation=self.relation,
                    documents=[rel],
                    claim=(
                        f"`.intent/` artifact `{rel}` is not named in any accepted "
                        "ADR's D-text and post-dates topology paper acceptance "
                        "(2026-05-26)."
                    ),
                    rationale=(
                        "Topology paper §3 row 4 strict requires every governance "
                        "change in `.intent/` to be named in its governing ADR's "
                        "D-text at acceptance. Grandfather exemption applies only "
                        "to artifacts whose git first-appearance precedes topology "
                        "acceptance. Either author the governing ADR (or amend an "
                        "existing one) to reference this path, or — if the artifact "
                        "is in fact pre-acceptance — verify the git history claim."
                    ),
                )
            )
        return candidates

    def _collect_accepted_adr_text(self) -> list[str]:
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
        texts: list[str] = []
        for adr in adr_paths:
            content = adr.read_text(encoding="utf-8", errors="replace")
            if _STATUS_ACCEPTED.search(content):
                texts.append(content)
        return texts

    def _git_first_seen(self, rel_path: str) -> date | None:
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self._repo_root),
                    "log",
                    "--diff-filter=A",
                    "--format=%aI",
                    "--",
                    rel_path,
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not result.stdout.strip():
            return None
        last_line = result.stdout.strip().splitlines()[-1]
        try:
            return date.fromisoformat(last_line[:10])
        except ValueError:
            return None


def _iter_intent_artifacts(repo_root: Path):
    """Yield `.intent/` governance artifacts (yaml, yml, json), excluding META.

    F-42 ADR-091 D5 Phase 4: discovery routes through the intent_yaml +
    intent_json artifact-type universes. The META exclusion preserves the
    original semantic — META-tree files are governance infrastructure
    (schemas, enums, global meta-schema), not governance artifacts subject
    to row4_naming ADR-citation requirements.
    """
    from shared.infrastructure.intent.intent_repository import (
        get_intent_repository,
    )

    repo = get_intent_repository()
    yaml_globs = repo.get_artifact_type("intent_yaml").content["discovery"]
    json_globs = repo.get_artifact_type("intent_json").content["discovery"]
    universe: set[Path] = set()
    for glob in (*yaml_globs, *json_globs):
        universe.update(repo_root.glob(glob))
    for path in sorted(universe):
        if not path.is_file():
            continue
        if _META_PARTS.intersection(path.parts):
            continue
        yield path
