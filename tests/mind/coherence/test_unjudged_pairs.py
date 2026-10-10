"""A pair the LLM judge could not judge is unchecked, not clear.

Run ce1a1190 (2026-10-10): all 930 judge calls in SAMECONCERN / R1_SCOPED
failed ("CORE_MASTER_KEY not found"); each returned None, which the checks
read as "no contradiction" — the run reported "0 candidates, 11 ran".
The judge now raises JudgeUnavailable, a check with unjudged pairs raises
CheckIncomplete (keeping what it found), and the run records "partial".
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.coherence.checks.base import (
    CheckIncomplete,
    CoherenceCandidate,
    JudgeUnavailable,
)
from shared.governance.coherence_harvester import Claim


def _claim(text: str, path: str, sha: str) -> Claim:
    return Claim(
        text=text,
        source_path=path,
        line=1,
        paragraph_index=0,
        category="rule",
        content_sha=sha,
    )


# ID: 82aa8cb7-2676-4ee7-b317-15daf49d6998
async def test_judge_raises_when_the_call_fails() -> None:
    from mind.coherence.llm_judge import judge_contradiction_pair

    cognitive = MagicMock()
    cognitive.aget_client_for_role = AsyncMock(
        side_effect=RuntimeError("CORE_MASTER_KEY not found in configuration")
    )

    with pytest.raises(JudgeUnavailable, match="CORE_MASTER_KEY"):
        await judge_contradiction_pair(
            cognitive_service=cognitive,
            text_a="a",
            source_a="x.md",
            text_b="b",
            source_b="y.md",
            tier="ambiguous",
        )


# ID: ef70a4ee-5d64-4143-ae57-2b19da01f645
async def test_sameconcern_with_unjudged_pairs_is_incomplete() -> None:
    from mind.coherence.checks.sameconcern import SameConcernCheck

    claims = [_claim("A must", "a.md", "1"), _claim("B must", "b.md", "2")]
    claims_service = AsyncMock()
    claims_service.is_seeded.return_value = True
    claims_service.search.return_value = [
        SimpleNamespace(
            source_path="z.md", content_sha="9", cosine=0.9, text="Z", category="rule"
        )
    ]
    check = SameConcernCheck(
        repo_root=Path("var/tmp"),
        register=MagicMock(),
        claims_service=claims_service,
        cognitive_service=MagicMock(),
        max_queries=None,
    )
    found = CoherenceCandidate(
        relation="SAMECONCERN", documents=["a.md", "z.md"], claim="c", rationale="r"
    )

    with (
        patch("shared.governance.coherence_harvester.GovernanceClaimHarvester") as mh,
        patch(
            "shared.infrastructure.vector.cognitive_adapter.CognitiveEmbedderAdapter"
        ) as ma,
        patch(
            "mind.coherence.checks.sameconcern.judge_contradiction_pair",
            AsyncMock(side_effect=[found, JudgeUnavailable("CORE_MASTER_KEY")]),
        ),
    ):
        mh.return_value.harvest.return_value = iter(claims)
        ma.return_value = AsyncMock(
            get_embeddings_batch=AsyncMock(return_value=[[1.0], [2.0]])
        )
        with pytest.raises(CheckIncomplete) as exc_info:
            await check.run()

    assert exc_info.value.candidates == [found]
    assert (exc_info.value.judged, exc_info.value.unjudged) == (1, 1)
    assert "CORE_MASTER_KEY" in str(exc_info.value)


# ID: 166d1af3-377b-4826-97f1-c7a59ce9805f
async def test_checker_records_partial_and_keeps_candidates() -> None:
    from mind.coherence.checker import CoherenceChecker

    coherence_service = AsyncMock()
    # Nothing was dismissed before (triage carry-forward, proposal 0012); a bare
    # AsyncMock would answer with a truthy mock and carry the candidate forward.
    coherence_service.dismissed_and_unchanged = AsyncMock(return_value=False)
    checker = CoherenceChecker(
        cognitive_service=MagicMock(),
        coherence_service=coherence_service,
        repo_root=Path("var/tmp"),
        claims_service=AsyncMock(),
    )
    found = CoherenceCandidate(
        relation="SAMECONCERN", documents=["a.md", "z.md"], claim="c", rationale="r"
    )
    none = AsyncMock(return_value=[])
    structural = [
        "dispatch_parity.DispatchParityCheck",
        "row2_grounding.Row2GroundingCheck",
        "row3_citation.Row3CitationCheck",
        "row4_naming.Row4NamingCheck",
        "vocabulary.VocabularyCheck",
        "specgap.SpecGapCheck",
        "path_ref.PathRefCheck",
        "intent_binding.IntentBindingCheck",
        "cross_ns_direction.CrossNsDirectionCheck",
        "r1_scoped.R1ScopedCheck",
    ]
    patches = [patch(f"mind.coherence.checks.{p}.run", new=none) for p in structural]
    patches += [
        patch(
            "mind.coherence.checks.sameconcern.SameConcernCheck.run",
            new=AsyncMock(side_effect=CheckIncomplete([found], 5, 3, "no key")),
        ),
        patch(
            "shared.infrastructure.intent.intent_repository.get_intent_repository",
            return_value=MagicMock(),
        ),
        patch(
            "shared.governance.coherence_harvester.NormativeMarkerRegister.from_intent",
            return_value=MagicMock(),
        ),
    ]
    for p in patches:
        p.start()
    try:
        status = await checker._dispatch_checks(run_id="run-1")
    finally:
        for p in patches:
            p.stop()

    assert status["SAMECONCERN"]["status"] == "partial"
    assert status["SAMECONCERN"]["unjudged"] == 3
    assert status["SAMECONCERN"]["emitted"] == 1
    coherence_service.add_candidate.assert_awaited_once()


# ID: ba5bbbd3-4bf3-4590-8cb2-bb72e6c87dfb
def test_partial_check_class_makes_the_run_partial() -> None:
    from cli.logic.coherence_coverage import check_class_coverage

    coverage = check_class_coverage(
        [
            {
                "domain": "_meta",
                "type": "check_classes_run",
                "check_status": {
                    "SAMECONCERN": {
                        "status": "partial",
                        "error": "930 of 930 pairs unjudged: no key",
                    }
                },
            }
        ]
    )

    assert coverage.partial is True
    assert coverage.failed[0][0] == "SAMECONCERN"
    assert "unjudged" in coverage.failed[0][1]
