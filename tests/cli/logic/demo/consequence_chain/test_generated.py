from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli.logic.demo.consequence_chain import run_consequence_chain


@pytest.mark.asyncio
# ID: 8b4d2afd-059d-4642-bdca-82e92b15d448
async def test_run_consequence_chain() -> None:
    demo_state_dir = Path("/tmp/demo_state")

    source = MagicMock()
    fingerprint = MagicMock()
    fingerprint.matches.return_value = True
    source.get_current_commit.return_value = "abc123"

    identity = MagicMock()
    identity.run_id = "run1234567890"
    identity.state_dir = Path("/tmp/demo_state/run1234567890")

    clone = MagicMock()
    clone.repo_path = Path("/tmp/clone")
    clone.is_committed.return_value = False
    clone.get_current_commit.return_value = "def456"
    clone.diff_file_names = AsyncMock(return_value=["seed.py"])

    up_result = MagicMock()
    up_result.returncode = 0

    scenario_result = MagicMock()
    scenario_result_dict = {"run_id": identity.run_id}

    assertion = MagicMock()
    assertion.passed = True

    phase_result = MagicMock()

    with (
        patch(
            "cli.logic.demo.consequence_chain.capture_fingerprint",
            side_effect=[fingerprint, fingerprint],
        ),
        patch(
            "cli.logic.demo.consequence_chain.generate_run_identity",
            return_value=identity,
        ),
        patch(
            "cli.logic.demo.consequence_chain.create_isolated_clone",
            return_value=clone,
        ),
        patch(
            "cli.logic.demo.consequence_chain.prove_clone_isolation",
        ),
        patch(
            "cli.logic.demo.consequence_chain.hash_directory",
            return_value="hashvalue",
        ),
        patch(
            "cli.logic.demo.consequence_chain.seed_relative_path",
            return_value="seeds/run12345.py",
        ),
        patch(
            "cli.logic.demo.consequence_chain.write_and_commit_seed",
        ),
        patch(
            "cli.logic.demo.consequence_chain.compose_up",
            new=AsyncMock(return_value=up_result),
        ),
        patch(
            "cli.logic.demo.consequence_chain._container_host_port",
            new=AsyncMock(return_value=5555),
        ),
        patch(
            "cli.logic.demo.consequence_chain._write_child_env",
        ),
        patch(
            "cli.logic.demo.consequence_chain.run_child_process",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "cli.logic.demo.consequence_chain.read_state_json",
            return_value=scenario_result_dict,
        ),
        patch(
            "cli.logic.demo.consequence_chain.ChainScenarioResult"
        ) as mock_chain_result,
        patch(
            "cli.logic.demo.consequence_chain.compose_down",
            new=AsyncMock(),
        ),
        patch(
            "cli.logic.demo.consequence_chain._evaluate_assertions",
            return_value=[assertion],
        ),
        patch(
            "cli.logic.demo.consequence_chain.AssertionResult",
            return_value=assertion,
        ),
        patch(
            "cli.logic.demo.consequence_chain.cleanup_run",
        ),
        patch(
            "cli.logic.demo.consequence_chain.PhaseResult",
            return_value=phase_result,
        ),
    ):
        mock_chain_result.from_dict.return_value = scenario_result

        result = await run_consequence_chain(source, demo_state_dir)

    assert result is phase_result
