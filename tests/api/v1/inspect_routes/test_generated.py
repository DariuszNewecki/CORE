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


import inspect

from api.v1.inspect_routes import analysis_common_knowledge


# ID: 04e553e8-4492-42ec-983b-9f6bd5a5a6fa
def test_analysis_common_knowledge():
    assert inspect.iscoroutinefunction(analysis_common_knowledge)

    response = MagicMock()
    response.headers = {}

    with patch(
        "api.v1.inspect_routes._signal_deprecation", new=MagicMock()
    ) as mock_signal:
        import asyncio

        result = asyncio.run(analysis_common_knowledge(response=response, limit=25))

    mock_signal.assert_called_once_with(response)
    assert result == {"available": False, "candidates": []}


import pytest

from api.v1.inspect_routes import analysis_duplicates


@pytest.mark.asyncio
# ID: 47e032c8-be56-451a-b0b7-68dd708e03a3
async def test_analysis_duplicates() -> None:
    request = MagicMock()
    request.app.state.core_context = MagicMock()

    expected = {"duplicates": [{"a": "x", "b": "y", "score": 0.9}]}

    with patch(
        "api.v1.inspect_routes.get_analysis_duplicates",
        new=AsyncMock(return_value=expected),
    ) as mock_get:
        result = await analysis_duplicates(request, threshold=0.9)

    assert result == expected
    mock_get.assert_awaited_once_with(request.app.state.core_context, threshold=0.9)


from fastapi import Response

from api.v1.inspect_routes import analysis_clusters


# ID: 704c89c7-dbc8-4525-88c9-5404b18eaba0
async def test_analysis_clusters():
    response = Response()
    with patch("api.v1.inspect_routes._signal_deprecation") as mock_signal:
        result = await analysis_clusters(response=response, limit=25)

    mock_signal.assert_called_once_with(response)
    assert result == {"available": False, "clusters": []}


import pytest

from api.v1.inspect_routes import analysis_bridges


@pytest.mark.asyncio
# ID: 7a298c28-0f0f-49db-a905-15414a9b5092
async def test_analysis_bridges():
    with patch("api.v1.inspect_routes.get_analysis_bridges") as mock_get:
        mock_get.return_value = {"bridges": ["a", "b"]}
        result = await analysis_bridges(consuming="svc")
        mock_get.assert_called_once_with(consuming="svc")
        assert result == {"bridges": ["a", "b"]}


import pytest

from api.v1.inspect_routes import refusals_stats


@pytest.mark.asyncio
# ID: 9dfe6e87-6c68-4fe6-b4b6-a1bca66d37bf
async def test_refusals_stats():
    fake_stats = {"by_type": {"policy": 3, "safety": 1}, "total": 4}
    with patch(
        "api.v1.inspect_routes.get_refusals_stats",
        new=AsyncMock(return_value=fake_stats),
    ) as mock_get_stats:
        result = await refusals_stats(days=7)

    assert result == fake_stats
    mock_get_stats.assert_awaited_once_with(days=7)


import pytest

from api.v1.inspect_routes import refusals_list


@pytest.mark.asyncio
# ID: 53acc890-63d0-46ef-9ac3-4aa5120592d6
async def test_refusals_list():
    expected = {"refusals": [{"id": "r1", "type": "scope"}]}
    mock_get_refusals = AsyncMock(return_value=expected)

    with patch("api.v1.inspect_routes.get_refusals", mock_get_refusals):
        result = await refusals_list(
            refusal_type="scope",
            session_id="sess-123",
            limit=10,
        )

    assert result == expected
    mock_get_refusals.assert_awaited_once_with(
        refusal_type="scope",
        session_id="sess-123",
        limit=10,
    )


import pytest

from api.v1.inspect_routes import decisions_patterns


@pytest.mark.asyncio
# ID: 2dc2141a-e1ad-4064-bc5c-40be166699cf
async def test_decisions_patterns():
    expected = {"patterns": {"stable": 3}, "days": 7}
    with patch(
        "api.v1.inspect_routes.get_decisions_patterns",
        new=AsyncMock(return_value=expected),
    ) as mock_get:
        result = await decisions_patterns(days=7)

    mock_get.assert_awaited_once_with(days=7)
    assert result == expected


import pytest

from api.v1.inspect_routes import decisions_list


@pytest.mark.asyncio
# ID: 4c60c930-8ce9-4e14-accd-2610a95d70e9
async def test_decisions_list():
    expected = {"items": [], "next_cursor": None}

    mock_get_decisions = AsyncMock(return_value=expected)

    with patch("api.v1.inspect_routes.get_decisions", mock_get_decisions):
        result = await decisions_list(
            session_id="sess-1",
            agent="agent-a",
            pattern="pat-1",
            limit=10,
            after="cursor-abc",
        )

    assert result == expected
    mock_get_decisions.assert_awaited_once_with(
        session_id="sess-1",
        agent="agent-a",
        pattern="pat-1",
        limit=10,
        after_cursor="cursor-abc",
    )



from api.v1.inspect_routes import status_drift


# ID: 47f400de-a913-40ec-94c1-045f3edcfc41
async def test_status_drift() -> None:
    core_context = MagicMock()

    request = MagicMock()
    request.app.state.core_context = core_context

    expected = {"symbols": [], "vectors": []}

    with patch(
        "api.v1.inspect_routes.get_drift_status",
        new=AsyncMock(return_value=expected),
    ) as mock_get_drift_status:
        result = await status_drift(request, scope="all")

    assert result == expected
    mock_get_drift_status.assert_awaited_once_with(core_context, scope="all")
