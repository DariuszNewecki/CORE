from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.logic.demo.scenario_runner import run_scenario


@pytest.mark.asyncio
# ID: 27720e09-7438-4dc5-96f8-6847020ce7c3
async def test_run_scenario():
    state_dir = Path("/tmp/state")

    mock_app = MagicMock()
    mock_lifespan = AsyncMock()
    mock_app.router.lifespan_context = MagicMock(return_value=mock_lifespan)
    mock_core_context = MagicMock()
    mock_app.state.core_context = mock_core_context

    mock_finding = MagicMock()
    mock_finding.entry_id = "entry-1"

    mock_proposal = MagicMock()
    mock_proposal.proposal_id = "proposal-1"

    mock_chain = MagicMock()
    mock_final_entry = {"status": "closed", "payload": {"proposal_id": "proposal-1"}}

    mock_bbqs = MagicMock()
    mock_bbqs.fetch_entry_by_id = AsyncMock(return_value=mock_final_entry)

    with (
        patch("api.main.create_app", return_value=mock_app),
        patch(
            "cli.logic.demo.scenario_runner._instantiate_and_run_worker",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "cli.logic.demo.scenario_runner._resolve_finding",
            new=AsyncMock(return_value=(mock_finding, 1)),
        ),
        patch(
            "cli.logic.demo.scenario_runner._resolve_proposal",
            new=AsyncMock(return_value=mock_proposal),
        ),
        patch(
            "cli.logic.demo.scenario_runner._execute_and_fetch_chain",
            new=AsyncMock(return_value=(None, mock_chain)),
        ),
        patch(
            "cli.logic.demo.scenario_runner._reaudit_is_clean",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "body.services.blackboard_service.blackboard_query_service.BlackboardQueryService",
            return_value=mock_bbqs,
        ),
        patch(
            "cli.logic.demo.scenario_runner.write_state_json",
        ) as mock_write,
    ):
        await run_scenario(state_dir, "seeds/foo.json", "run-1")

    mock_write.assert_called_once()
    written_path = mock_write.call_args[0][0]
    assert written_path == state_dir / "scenario_result.json"
    result_dict = mock_write.call_args[0][1]
    assert result_dict["run_id"] == "run-1"
    assert result_dict["error"] is None
    assert result_dict["reaudit_clean"] is True
    assert result_dict["finding_final_status"] == "closed"
    assert result_dict["finding_final_proposal_id"] == "proposal-1"
