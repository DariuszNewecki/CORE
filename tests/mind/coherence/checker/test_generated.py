from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from mind.coherence.checker import CoherenceChecker


# ID: f1a5d607-8a52-4804-8c27-4a7c5809ea90
async def test_CoherenceChecker_run():
    cognitive_service = MagicMock()
    coherence_service = MagicMock()
    coherence_service.create_run = AsyncMock(return_value="run-123")
    coherence_service.update_manifest = AsyncMock()
    coherence_service.close_run_if_empty = AsyncMock()

    checker = CoherenceChecker(
        cognitive_service=cognitive_service,
        coherence_service=coherence_service,
        repo_root=Path("/tmp/repo"),
    )

    checker._detect_trigger = AsyncMock(return_value="manual")
    checker._build_input_manifest = MagicMock(
        return_value=[{"domain": "x", "path": "p", "type": "t"}]
    )
    checker._dispatch_checks = AsyncMock(
        return_value={
            "CheckA": {"emitted": 2},
            "CheckB": {"emitted": 3},
        }
    )

    run_id = await checker.run()

    assert run_id == "run-123"
    checker._detect_trigger.assert_awaited_once_with(full=False)
    coherence_service.create_run.assert_awaited_once_with("manual")
    checker._dispatch_checks.assert_awaited_once_with("run-123")
    coherence_service.update_manifest.assert_awaited_once()
    coherence_service.close_run_if_empty.assert_awaited_once_with("run-123")





# ID: af84c03a-8294-4301-acfa-221b8b58fc02
def test_CoherenceChecker(tmp_path: Path):
    import asyncio

    cognitive_service = MagicMock()
    coherence_service = MagicMock()

    coherence_service.create_run = AsyncMock(return_value="run-123")
    coherence_service.get_latest_run = AsyncMock(return_value=None)
    coherence_service.update_manifest = AsyncMock()
    coherence_service.close_run_if_empty = AsyncMock()
    coherence_service.dismissed_and_unchanged = AsyncMock(return_value=False)
    coherence_service.add_candidate = AsyncMock()

    checker = CoherenceChecker(
        cognitive_service=cognitive_service,
        coherence_service=coherence_service,
        repo_root=tmp_path,
        claims_service=None,
    )

    fake_status = {
        "DISPATCH_PARITY": {"status": "ok", "emitted": 0, "carried_forward": 0}
    }
    checker._dispatch_checks = AsyncMock(return_value=fake_status)

    result = asyncio.run(checker.run(full=True))

    assert result == "run-123"
    coherence_service.create_run.assert_awaited_once_with("manual")
    coherence_service.update_manifest.assert_awaited_once()
    coherence_service.close_run_if_empty.assert_awaited_once_with("run-123")
    checker._dispatch_checks.assert_awaited_once_with("run-123")
