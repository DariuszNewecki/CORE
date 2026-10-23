from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mind.coherence.checks.specgap import SpecGapCheck


@pytest.mark.asyncio
# ID: 486e35e8-be69-4e8b-9c50-8998d67d32a6
async def test_SpecGapCheck_run():
    repo_root = Path("/tmp/repo")
    register = MagicMock()
    register.action_verbs = ["halt", "stop"]

    check = SpecGapCheck(repo_root, register)
    check.relation = "spec_gap"

    phase = "implementation"
    ur_id = "UR-1"
    ur_rel = ".intent/northstar.md"
    paragraph = "The system should halt on invalid input."

    check._load_phase_failure_modes = MagicMock(
        return_value={phase: {"ClassA": "retry"}}
    )
    check._load_phase_responsibility = MagicMock(return_value={phase: [ur_id]})
    check._extract_ur_paragraphs = MagicMock(return_value=[(ur_id, ur_rel, paragraph)])
    check._action_verbs_in = MagicMock(return_value={"halt"})
    check._operationally_linked = MagicMock(return_value=True)
    check._verbs_covered_by = MagicMock(return_value=False)

    with patch(
        "mind.coherence.checks.specgap._phases",
        return_value=[phase],
    ):
        result = await check.run()

    assert len(result) == 1
    candidate = result[0]
    assert candidate.relation == "spec_gap"
    assert candidate.documents == [ur_rel, f".intent/phases/{phase}.yaml"]
    assert ur_id in candidate.claim
    assert phase in candidate.claim


# ID: 20b2234e-eac0-4246-af4c-8100afb67d9a
def test_SpecGapCheck(tmp_path: Path):
    register = MagicMock()
    register.action_verbs = ["halt", "block"]

    check = SpecGapCheck(repo_root=tmp_path, register=register)

    check._load_phase_failure_modes = MagicMock(
        return_value={"P1": {"contradiction": "review"}}
    )
    check._load_phase_responsibility = MagicMock(return_value={})
    check._extract_ur_paragraphs = MagicMock(
        return_value=[
            (
                "UR-01",
                "src/mind/coherence/data/CORE-USER-REQUIREMENTS.md",
                "The P1 phase must halt on error.",
            )
        ]
    )

    with patch("mind.coherence.checks.specgap._phases", return_value=["P1"]):
        import asyncio

        result = asyncio.run(check.run())

    assert isinstance(result, list)
    for candidate in result:
        assert candidate.relation == "SPECGAP"
        assert len(candidate.documents) == 2
