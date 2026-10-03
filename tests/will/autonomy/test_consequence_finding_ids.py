"""Every completed proposal's consequence names the findings it addressed (D5).

Measured 2026-10-03: 0 of 262 test-generation consequences recorded
``findings_resolved`` (the violation side: 7 of 9). The test remediator never
put its findings on the proposal: it cannot use ``finding_ids``, the deferral
contract (supervision re-defers listed findings that drift back to open, and
the test remediator deliberately releases a file's findings for its other
per-symbol proposals). It now records them as ``addressed_finding_ids`` — an
evidence link the consequence carries and supervision ignores.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.autonomy.proposal_execution_pipeline import consequence_finding_ids


def test_union_of_deferred_and_addressed_without_duplicates() -> None:
    assert consequence_finding_ids(
        {"finding_ids": ["a", "b"], "addressed_finding_ids": ["b", "c"]}
    ) == ["a", "b", "c"]


def test_addressed_only_and_empty_cases() -> None:
    assert consequence_finding_ids({"addressed_finding_ids": ["x"]}) == ["x"]
    assert consequence_finding_ids({}) == []
    assert consequence_finding_ids(None) == []


@pytest.mark.asyncio
async def test_symbol_proposal_links_findings_as_evidence_not_deferral() -> None:
    from will.workers.test_remediator import _operations as ops

    captured: dict[str, object] = {}

    class _Repo:
        def __init__(self, session: object) -> None:
            pass

        async def create(self, proposal):  # type: ignore[no-untyped-def]
            captured["constraints"] = proposal.constitutional_constraints
            return "pid-1"

    @asynccontextmanager
    async def _session():  # type: ignore[no-untyped-def]
        yield MagicMock(commit=AsyncMock())

    registry = MagicMock(session=_session)
    with (
        patch("body.services.service_registry.service_registry", registry),
        patch("will.autonomy.proposal_repository.ProposalRepository", _Repo),
        patch(
            "will.autonomy.proposal_state_manager.ProposalStateManager",
            MagicMock(return_value=MagicMock(approve=AsyncMock())),
        ),
    ):
        pid = await ops._create_symbol_proposal(
            source_file="src/a.py",
            symbol_name="f",
            symbol_kind="function",
            signature="def f()",
            test_file="tests/test_a.py",
            findings=[{"id": "e1"}, {"id": "e2"}],
        )

    assert pid == "pid-1"
    constraints = captured["constraints"]
    assert constraints["addressed_finding_ids"] == ["e1", "e2"]  # type: ignore[index]
    assert "finding_ids" not in constraints  # type: ignore[operator]
