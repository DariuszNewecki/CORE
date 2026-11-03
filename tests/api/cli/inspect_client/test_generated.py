from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from api.cli.inspect_client import InspectClient


@pytest.mark.asyncio
# ID: ab0443ce-f209-4fea-9aed-f85785b0f712
async def test_InspectClient_analysis_bridges() -> None:
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"bridges": [{"name": "b1"}]})

    client = InspectClient(facade)

    result = await client.analysis_bridges(consuming="service_a")

    assert result == {"bridges": [{"name": "b1"}]}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/analysis/bridges", params={"consuming": "service_a"}
    )


import pytest


@pytest.mark.asyncio
# ID: 8a1b856a-cc21-45a8-89e2-4abaa8723e3f
async def test_InspectClient_refusals_stats():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"total": 5, "by_type": {"x": 5}})
    client = InspectClient(facade)

    result = await client.refusals_stats(days=14)

    assert result == {"total": 5, "by_type": {"x": 5}}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/refusals/stats", params={"days": 14}
    )


import pytest


@pytest.mark.asyncio
# ID: 4a24d1f4-3bc6-4136-b7f8-9f97152c748f
async def test_InspectClient_refusals_list():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"items": []})

    client = InspectClient(facade)

    result = await client.refusals_list()

    facade._request.assert_awaited_once_with(
        "GET", "/v1/refusals", params={"limit": 50}
    )
    assert result == {"items": []}


import pytest


@pytest.mark.asyncio
# ID: 3f617293-b8e5-4b57-8279-07f68bf15cc7
async def test_InspectClient_decisions_patterns():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"patterns": []})

    client = InspectClient(facade)

    result = await client.decisions_patterns(days=14)

    assert result == {"patterns": []}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/decisions/patterns", params={"days": 14}
    )


import pytest


@pytest.mark.asyncio
# ID: 92197b20-7d91-489c-b86b-f12c3dfc869c
async def test_InspectClient_analysis_common_knowledge():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"items": [{"id": "ck-1"}]})

    client = InspectClient(facade)

    result = await client.analysis_common_knowledge()

    facade._request.assert_awaited_once_with(
        "GET", "/v1/analysis/common-knowledge", params={"limit": 25}
    )
    assert result == {"items": [{"id": "ck-1"}]}


import pytest


@pytest.mark.asyncio
# ID: 7d674402-6433-473c-932e-5fb133bdc540
async def test_InspectClient_analysis_duplicates():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"duplicates": []})
    client = InspectClient(facade)

    result = await client.analysis_duplicates(threshold=0.9)

    facade._request.assert_awaited_once_with(
        "GET",
        "/v1/analysis/duplicates",
        params={"threshold": 0.9},
        timeout=300.0,
    )
    assert result == {"duplicates": []}


# ID: 84ea26cd-d1a2-438a-88bd-9b143ea91f49
async def test_InspectClient_analysis_clusters():
    facade = MagicMock()
    expected = {"clusters": [{"id": "c1", "label": "semantic"}]}
    facade._request = AsyncMock(return_value=expected)

    client = InspectClient(facade)

    result = await client.analysis_clusters(limit=10)

    assert result == expected
    facade._request.assert_awaited_once_with(
        "GET", "/v1/analysis/clusters", params={"limit": 10}
    )


import pytest


@pytest.mark.asyncio
# ID: 8ca6e0b0-ec5d-45b7-b32b-821c5dab014d
async def test_InspectClient_inspect_search_commands():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"results": [{"name": "build"}]})
    client = InspectClient(facade)

    result = await client.inspect_search_commands("buil", limit=10)

    facade._request.assert_awaited_once_with(
        "GET", "/v1/search/commands", params={"q": "buil", "limit": 10}
    )
    assert result == {"results": [{"name": "build"}]}


import asyncio


# ID: 7b807695-b31a-4b94-a83c-a3ebd8f8e7de
def test_InspectClient_inspect_search_capabilities():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"results": [{"id": "cap-1"}]})

    client = InspectClient(facade)

    result = asyncio.run(client.inspect_search_capabilities("auth", limit=5))

    assert result == {"results": [{"id": "cap-1"}]}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/search/capabilities", params={"q": "auth", "limit": 5}
    )


import pytest


@pytest.mark.asyncio
# ID: 44aa0522-f3a5-4f57-98a2-9690d2a1ceb0
async def test_InspectClient_inspect_components():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"components": []})
    client = InspectClient(facade)

    result = await client.inspect_components(filter_type="service")

    facade._request.assert_awaited_once_with(
        "GET", "/v1/components", params={"type": "service"}
    )
    assert result == {"components": []}


import pytest


@pytest.mark.asyncio
# ID: d6d3fee4-c447-4dd0-b8db-c8084454fc2a
async def test_InspectClient_analysis_test_targets() -> None:
    facade = AsyncMock()
    expected = {"SIMPLE": ["a", "b"], "COMPLEX": ["c"]}
    facade._request = AsyncMock(return_value=expected)

    client = InspectClient(facade)

    result = await client.analysis_test_targets()

    facade._request.assert_awaited_once_with("GET", "/v1/analysis/test-targets")
    assert result == expected


import pytest


# ID: 7d40a540-48ea-4765-ad5e-b718be173c7a
async def test_InspectClient_analysis_command_tree() -> None:
    expected = {"commands": [{"name": "build"}, {"name": "test"}]}
    facade = MagicMock()
    facade._request = AsyncMock(return_value=expected)

    client = InspectClient(facade)

    result = await client.analysis_command_tree()

    assert result == expected
    facade._request.assert_awaited_once_with("GET", "/v1/analysis/command-tree")


import pytest


@pytest.mark.asyncio
# ID: c4972857-8f76-459b-8dda-7b04a999029a
async def test_InspectClient_decisions_list():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"decisions": []})

    client = InspectClient(facade)

    result = await client.decisions_list(
        session_id="sess-123",
        agent="agent-x",
        pattern="foo",
        limit=10,
    )

    assert result == {"decisions": []}
    facade._request.assert_awaited_once_with(
        "GET",
        "/v1/decisions",
        params={
            "limit": 10,
            "session_id": "sess-123",
            "agent": "agent-x",
            "pattern": "foo",
        },
    )



import pytest


@pytest.mark.asyncio
# ID: 2749fa7c-584d-41c3-8839-3bfa7bd856e8
async def test_InspectClient_status_drift():
    facade = MagicMock()
    facade._request = AsyncMock(return_value={"drift": []})

    client = InspectClient(facade)
    result = await client.status_drift()

    assert result == {"drift": []}
    facade._request.assert_awaited_once_with(
        "GET", "/v1/status/drift", params={"scope": "all"}
    )
