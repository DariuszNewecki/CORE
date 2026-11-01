from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from will.autonomy.violation_remediator_proposal import (
    get_active_proposal_id_by_action_file,
)


@pytest.mark.asyncio
# ID: 6edae55a-a5c9-4091-a740-e39d74558500
async def test_get_active_proposal_id_by_action_file():
    earlier = datetime(2024, 1, 1, 0, 0, 0)
    later = datetime(2024, 1, 2, 0, 0, 0)

    action_a = SimpleNamespace(ref_id="act-1", parameters={"file_path": "a.py"})
    action_b = SimpleNamespace(ref_id="act-2", parameters=None)
    proposal_one = SimpleNamespace(
        proposal_id="prop-1",
        created_at=earlier,
        actions=[action_a, action_b],
    )

    action_c = SimpleNamespace(ref_id="act-1", parameters={"file_path": "a.py"})
    action_d = SimpleNamespace(ref_id="flow-9", parameters={"file_path": "d.py"})
    proposal_two = SimpleNamespace(
        proposal_id="prop-2",
        created_at=later,
        actions=[action_c, action_d],
    )

    repo = MagicMock()
    repo.list_by_status = AsyncMock(return_value=[proposal_one, proposal_two])

    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    registry = MagicMock()
    registry.session = MagicMock(return_value=session_cm)

    original_registry_mod = None
    import body.services.service_registry as registry_mod

    original_registry_mod = registry_mod.service_registry
    registry_mod.service_registry = registry

    import will.autonomy.proposal_repository as repo_mod

    original_repo_cls = repo_mod.ProposalRepository
    repo_mod.ProposalRepository = MagicMock(return_value=repo)

    try:
        result = await get_active_proposal_id_by_action_file()
    finally:
        registry_mod.service_registry = original_registry_mod
        repo_mod.ProposalRepository = original_repo_cls

    assert result[("act-1", "a.py")] == "prop-1"
    assert result[("act-2", None)] == "prop-1"
    assert result[("flow-9", "d.py")] == "prop-2"
    assert len(result) == 3
