"""The claim harvester skips documents that are no longer in force.

CCC run 6558a043 (2026-10-10) reported withdrawn ADR-112 (`status: retired`)
as conflicting with ADR-159: the harvester judged dead law as live.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from shared.governance.coherence_harvester import (
    _NOT_IN_FORCE_STATUSES,
    GovernanceClaimHarvester,
    NormativeMarkerRegister,
)


_BODY = "The executor MUST record a consequence for every completed proposal.\n"


def _adr(status: str) -> str:
    return f"---\nkind: adr\nstatus: {status}\n---\n\n# ADR\n\n{_BODY}"


# ID: 1a9b6dc3-5828-4807-93af-2d84a9bb6ad3
def test_retired_and_superseded_documents_yield_no_claims(tmp_path: Path) -> None:
    decisions = tmp_path / ".specs" / "decisions"
    decisions.mkdir(parents=True)
    for status in ("accepted", "proposed", "retired", "superseded"):
        (decisions / f"ADR-{status}.md").write_text(_adr(status))
    (decisions / "ADR-nofrontmatter.md").write_text(f"# ADR\n\n{_BODY}")

    intent_repo = MagicMock()
    intent_repo.iter_documents.return_value = iter([])
    register = NormativeMarkerRegister._from_data({"markers": ["MUST"]}, source="t")
    harvester = GovernanceClaimHarvester(tmp_path, register, intent_repo)

    sources = {Path(c.source_path).stem for c in harvester.harvest()}

    assert sources == {"ADR-accepted", "ADR-proposed", "ADR-nofrontmatter"}


# ID: dd56e253-9ab5-4f59-9fcf-4253abcb3c0c
def test_not_in_force_statuses_are_the_governed_terminal_states() -> None:
    """Drift guard: the skipped statuses must exist in the governed
    document_status vocabulary, and be terminal for both ADRs and papers."""
    repo_root = Path(__file__).resolve().parents[3]
    enums = json.loads((repo_root / ".intent" / "META" / "enums.json").read_text())
    defs = enums.get("enums", enums.get("definitions", enums))

    assert _NOT_IN_FORCE_STATUSES <= set(defs["document_status"]["enum"])
    assert _NOT_IN_FORCE_STATUSES <= set(defs["adr_status"]["enum"])
    assert _NOT_IN_FORCE_STATUSES <= set(defs["paper_status"]["enum"])
