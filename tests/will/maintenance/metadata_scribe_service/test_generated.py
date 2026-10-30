from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.maintenance.metadata_scribe_service import MetadataScribeService


@pytest.mark.asyncio
# ID: ff6a0156-5c77-466e-b07a-89eec9ade070
async def test_MetadataScribeService_draft_metadata():
    cognitive = MagicMock()
    agent = MagicMock()
    cognitive.aget_client_for_role = AsyncMock(return_value=agent)

    with patch(
        "will.maintenance.metadata_scribe_service.PromptModel"
    ) as mock_prompt_model_cls:
        mock_model = MagicMock()
        mock_model.manifest = MagicMock()
        mock_model.manifest.role = "architect"
        mock_model.invoke = AsyncMock(return_value='{"canonical_name": "do_thing"}')
        mock_prompt_model_cls.load.return_value = mock_model

        with patch(
            "will.maintenance.metadata_scribe_service.extract_json_from_response"
        ) as mock_extract:
            mock_extract.return_value = {"canonical_name": "do_thing"}

            service = MetadataScribeService(cognitive)

            result = await service.draft_metadata(
                function_name="do_thing",
                docstring="Does a thing.",
                file_path="src/thing.py",
                source_code="def do_thing(): ...",
            )

    assert result == {"canonical_name": "do_thing"}
    cognitive.aget_client_for_role.assert_awaited_once_with("architect")
    mock_model.invoke.assert_awaited_once()


import pytest


@pytest.mark.asyncio
# ID: 81237a08-6585-49de-87d3-46792a5eed87
async def test_MetadataScribeService():
    cognitive_service = MagicMock()

    with patch(
        "will.maintenance.metadata_scribe_service.PromptModel"
    ) as mock_prompt_model_cls:
        mock_model = MagicMock()
        mock_model.manifest = MagicMock()
        mock_model.manifest.role = "architect"
        mock_model.invoke = AsyncMock(
            return_value='{"canonical_name": "do-thing", "description": "Does a thing"}'
        )
        mock_prompt_model_cls.load.return_value = mock_model

        cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())

        service = MetadataScribeService(cognitive_service=cognitive_service)

    with patch(
        "will.maintenance.metadata_scribe_service.extract_json_from_response"
    ) as mock_extract:
        mock_extract.return_value = {
            "canonical_name": "do-thing",
            "description": "Does a thing",
        }

        result = await service.draft_metadata(
            function_name="do_thing",
            docstring="Does a thing.",
            file_path="src/pkg/mod.py",
            source_code="def do_thing():\n    pass\n",
        )

    assert result == {"canonical_name": "do-thing", "description": "Does a thing"}
    cognitive_service.aget_client_for_role.assert_awaited_once_with("architect")
    mock_model.invoke.assert_awaited_once()
    _, kwargs = mock_model.invoke.await_args
    assert kwargs["user_id"] == "metascribe_draft"
    assert kwargs["context"]["function_name"] == "do_thing"
    assert kwargs["context"]["file_path"] == "src/pkg/mod.py"
    assert kwargs["context"]["docstring"] == "Does a thing."
    assert kwargs["context"]["source_code"] == "def do_thing():\n    pass\n"
