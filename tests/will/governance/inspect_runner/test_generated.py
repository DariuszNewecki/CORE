from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.governance.inspect_runner import get_search_capabilities


@pytest.mark.asyncio
# ID: 35af6366-0dad-4a49-b8ac-f7d7b2e468ee
async def test_get_search_capabilities():
    context = MagicMock()
    context.cognitive_service = MagicMock()
    context.cognitive_service.search_capabilities = AsyncMock(
        return_value=[{"name": "cap_a"}, {"name": "cap_b"}]
    )

    result = await get_search_capabilities(context, q="search", limit=5)

    context.cognitive_service.search_capabilities.assert_awaited_once_with(
        "search", limit=5
    )
    assert result["query"] == "search"
    assert result["available"] is True
    assert result["count"] == 2
    assert result["results"] == [{"name": "cap_a"}, {"name": "cap_b"}]


from enum import Enum
from unittest.mock import patch

from will.governance.inspect_runner import get_components_list


# ID: ac4b00fd-c973-4768-bf41-8df91b3ce7c1
def test_get_components_list():
    class _Phase(Enum):
        BUILD = "build"

    def _make_component(description: str):
        inst = MagicMock()
        inst.phase = _Phase.BUILD
        inst.description = description
        return inst

    # ID: df40c164-158b-4f8d-af7d-24f7e74b577f
    class CompA:
        phase = _Phase.BUILD
        description = "component a"

    # ID: 6b103ab9-9e49-42e0-8432-f9793afda523
    class CompB:
        phase = _Phase.BUILD
        description = "component b"

    def _discover(package):
        if package == "will.interpreters":
            return {"comp_a": CompA, "comp_b": CompB}
        return {}

    with patch(
        "shared.component_primitive.discover_components",
        side_effect=_discover,
    ):
        result = get_components_list(filter_type="Interpreters")

    assert result["count"] == 2
    rows = result["components"]
    assert len(rows) == 2
    for row in rows:
        assert row["ok"] is True
        assert row["type"] == "Interpreters"
        assert row["phase"] == "BUILD"
    ids = {row["component_id"] for row in rows}
    assert ids == {"comp_a", "comp_b"}


from types import SimpleNamespace

from will.governance.inspect_runner import get_analysis_bridges


# ID: f20de2ae-4c07-4c8a-b672-599bb84495d1
def test_get_analysis_bridges():
    bridge_one = SimpleNamespace(
        id="b-002",
        title="Second",
        description="desc two",
        bridge_class="class2",
        bridge_layer="layer2",
        source_layer="src_layer2",
        source_context="src_ctx2",
        consuming_types=["typeA"],
        sink_target="sink2",
        sink_layer="sink_layer2",
        sink_via="via2",
        attribution_mechanism="mech2",
        attribution_field="field2",
        attribution_note="note2",
        authority_adrs=["ADR-002"],
    )
    bridge_two = SimpleNamespace(
        id="b-001",
        title="First",
        description="desc one",
        bridge_class="class1",
        bridge_layer="layer1",
        source_layer="src_layer1",
        source_context="src_ctx1",
        consuming_types=["typeB"],
        sink_target="sink1",
        sink_layer="sink_layer1",
        sink_via="via1",
        attribution_mechanism="mech1",
        attribution_field="field1",
        attribution_note="note1",
        authority_adrs=["ADR-001"],
    )

    mock_load_bridges = MagicMock(return_value=[bridge_one, bridge_two])
    mock_bridges_consuming = MagicMock(return_value=[bridge_two])

    with (
        patch(
            "shared.infrastructure.intent.architecture_bridges.load_bridges",
            mock_load_bridges,
        ),
        patch(
            "shared.infrastructure.intent.architecture_bridges.bridges_consuming",
            mock_bridges_consuming,
        ),
    ):
        result = get_analysis_bridges()

    assert result["available"] is True
    assert result["count"] == 2
    assert result["consuming"] is None
    assert [b["id"] for b in result["bridges"]] == ["b-001", "b-002"]
    assert result["bridges"][0]["title"] == "First"
    mock_load_bridges.assert_called_once_with()
    mock_bridges_consuming.assert_not_called()
