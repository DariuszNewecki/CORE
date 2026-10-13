"""The claim harvester reads the collapsed decision record.

Phase 4 of the governance-text reduction folds the accepted ADRs into
.specs/DECISIONS.md; without reading it the coherence checker would see no
decisions at all.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from shared.governance.coherence_harvester import (
    GovernanceClaimHarvester,
    NormativeMarkerRegister,
)


def test_decisions_record_yields_adr_claims(tmp_path: Path) -> None:
    specs = tmp_path / ".specs"
    specs.mkdir()
    (specs / "DECISIONS.md").write_text(
        "# CORE decisions\n\n## ADR-012 — Example\n\n"
        "The executor MUST record a consequence for every completed proposal.\n"
    )
    intent_repo = MagicMock()
    intent_repo.iter_documents.return_value = iter([])
    register = NormativeMarkerRegister._from_data({"markers": ["MUST"]}, source="t")

    claims = list(GovernanceClaimHarvester(tmp_path, register, intent_repo).harvest())

    assert [Path(c.source_path).name for c in claims] == ["DECISIONS.md"]
    assert all(c.category == "adr" for c in claims)
