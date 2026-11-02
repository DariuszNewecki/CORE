from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from will.strategists.sync_strategist import SyncStrategist


# ID: b9fda340-12b3-4730-8de3-ace8cc144bb8
def test_SyncStrategist_execute():
    strategist = SyncStrategist()
    strategist.tracer = MagicMock()
    strategist.tracer.record = MagicMock()

    strategist._select_strategy = MagicMock(return_value="incremental")
    strategist._build_sequence = MagicMock(
        return_value=["domains", "symbols", "vectors"]
    )
    strategist._determine_execution_mode = MagicMock(return_value="sequential")
    strategist._configure_force_flags = MagicMock(
        return_value={"domains": False, "symbols": False, "vectors": False}
    )
    strategist._estimate_duration = MagicMock(return_value=12.5)

    result = asyncio.new_event_loop().run_until_complete(
        strategist.execute("symbols", force_refresh=False, include_dependencies=True)
    )

    assert result.ok is True
    assert result.data["strategy"] == "incremental"
    assert result.data["sync_sequence"] == ["domains", "symbols", "vectors"]
    assert result.data["execution_mode"] == "sequential"
    assert result.data["sync_target"] == "symbols"
    assert result.next_suggested == "sync_executor"
    assert result.metadata["sequence_length"] == 3
    strategist.tracer.record.assert_called_once()
    strategist._select_strategy.assert_called_once()
    strategist._build_sequence.assert_called_once()
