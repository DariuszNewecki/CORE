from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.v1.inspect_routes import search_commands


@pytest.mark.asyncio
# ID: cc780f26-5728-4e9c-b559-acfca54f204e
async def test_search_commands():
    mock_session = AsyncMock()
    mock_get_search_commands = AsyncMock(return_value={"commands": ["deploy", "merge"]})

    with patch("api.v1.inspect_routes.get_search_commands", mock_get_search_commands):
        result = await search_commands(q="deploy", limit=10, session=mock_session)

    assert result == {"commands": ["deploy", "merge"]}
    mock_get_search_commands.assert_awaited_once_with(
        mock_session, q="deploy", limit=10
    )


from unittest.mock import MagicMock

import pytest

from api.v1.inspect_routes import search_capabilities


@pytest.mark.asyncio
# ID: c014f8aa-84dd-4b39-b135-ef50b7f80b5a
async def test_search_capabilities():
    core_context = MagicMock()
    request = MagicMock()
    request.app.state.core_context = core_context

    expected = {"results": [{"id": "cap-1"}]}

    with patch(
        "api.v1.inspect_routes.get_search_capabilities",
        new=AsyncMock(return_value=expected),
    ) as mock_get:
        result = await search_capabilities(request=request, q="foo", limit=5)

    assert result == expected
    mock_get.assert_awaited_once_with(core_context, q="foo", limit=5)


import pytest

from api.v1.inspect_routes import components_list


@pytest.mark.asyncio
# ID: c9b6f392-2e83-4cda-bfbc-ef587ffd7a7d
async def test_components_list():
    expected = {"components": [{"name": "alpha", "layer": "Mind"}]}
    with patch(
        "api.v1.inspect_routes.get_components_list",
        return_value=expected,
    ) as mock_get:
        result = await components_list(filter_type="tool")
    assert result == expected
    mock_get.assert_called_once_with(filter_type="tool")


from api.v1.inspect_routes import analysis_test_targets


# ID: cbb54c4d-ce90-4596-b7b9-dd5d7aafe3e2
async def test_analysis_test_targets():
    expected_result = {"SIMPLE": ["a.py"], "COMPLEX": ["b.py"]}
    core_context = MagicMock()

    request = MagicMock()
    request.app.state.core_context = core_context

    with (
        patch(
            "api.v1.inspect_routes.get_analysis_test_targets",
            new=MagicMock(return_value=expected_result),
        ) as mock_get_targets,
        patch(
            "api.v1.inspect_routes.asyncio.to_thread",
            new=AsyncMock(return_value=expected_result),
        ) as mock_to_thread,
    ):
        result = await analysis_test_targets(request)

    mock_to_thread.assert_awaited_once()
    called_fn, called_arg = mock_to_thread.await_args.args
    assert called_fn is mock_get_targets
    assert called_arg is core_context
    assert result == expected_result


import pytest

from api.v1.inspect_routes import analysis_command_tree


@pytest.mark.asyncio
# ID: bb82eae8-7d87-4968-834f-2b710594f35a
async def test_analysis_command_tree():
    mock_core_context = MagicMock()
    mock_request = MagicMock()
    mock_request.app.state.core_context = mock_core_context
    mock_request.app.state.__dict__ = {"core_context": mock_core_context}

    expected_tree = {"commands": ["foo", "bar"]}

    with patch(
        "api.v1.inspect_routes.get_analysis_command_tree",
        return_value=expected_tree,
    ) as mock_get_tree:
        result = await analysis_command_tree(mock_request)

    assert result == expected_tree
    mock_get_tree.assert_called_once_with(mock_core_context)
