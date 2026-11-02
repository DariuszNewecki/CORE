from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.self_healing.capability_tagging_service import main_async


# ID: 79e7bb32-7790-41e1-80c6-57a004f368d7
async def test_main_async():
    session_factory = MagicMock()
    cognitive_service = MagicMock()
    knowledge_service = MagicMock()

    with patch(
        "will.self_healing.capability_tagging_service._async_tag_capabilities",
        new=AsyncMock(),
    ) as mock_tag:
        await main_async(
            session_factory=session_factory,
            cognitive_service=cognitive_service,
            knowledge_service=knowledge_service,
            write=True,
            dry_run=False,
            limit=5,
        )

    mock_tag.assert_awaited_once_with(
        cognitive_service=cognitive_service,
        knowledge_service=knowledge_service,
        session_factory=session_factory,
        file_path=None,
        dry_run=False,
        limit=5,
    )
