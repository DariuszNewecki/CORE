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


from pathlib import Path


# ID: 27d17d75-edae-40c6-a5ea-17ae91dc2d1a
def test_get_analysis_test_targets(tmp_path):
    from will.governance.inspect_runner import get_analysis_test_targets

    # Minimal repo tree with one python file under src/
    repo_root = tmp_path
    src_dir = repo_root / "src"
    src_dir.mkdir()
    py_file = src_dir / "example.py"
    py_file.write_text("def foo():\n    return 1\n")

    # Fake analyzer returning genuinely dataclass targets (asdict requires dataclasses)
    # ID: 5ffd426a-5312-41e4-bd04-0ccf97dc2208
    class FakeTarget:
        def __init__(self, name, file, classification, complexity):
            self.name = name
            self.file = file
            self.classification = classification
            self.complexity = complexity

        def __eq__(self, other):
            return (
                isinstance(other, FakeTarget)
                and self.name == other.name
                and self.file == other.file
                and self.classification == other.classification
                and self.complexity == other.complexity
            )

        def __repr__(self):
            return (
                f"FakeTarget(name={self.name!r}, file={self.file!r}, "
                f"classification={self.classification!r}, complexity={self.complexity!r})"
            )

    # Patch asdict in the dataclasses module (imported locally inside the function)
    # ID: 7f27e835-31c4-4009-ba4a-5dd23cc7cf4d
    def fake_asdict(obj):
        return {
            "name": obj.name,
            "file": obj.file,
            "classification": obj.classification,
            "complexity": obj.complexity,
        }

    fake_analyzer = MagicMock()
    fake_analyzer.analyze_file.return_value = [
        FakeTarget(
            name="foo",
            file="src/example.py",
            classification="SIMPLE",
            complexity=1,
        )
    ]

    mock_analyzer_cls = MagicMock(return_value=fake_analyzer)

    context = MagicMock()
    context.git_service.repo_path = str(repo_root)

    with (
        patch(
            "body.self_healing.test_target_analyzer.TestTargetAnalyzer",
            mock_analyzer_cls,
        ),
        patch(
            "dataclasses.asdict",
            fake_asdict,
        ),
    ):
        result = get_analysis_test_targets(context)

    assert result["available"] is True
    assert result["count"] == 1
    assert len(result["targets"]) == 1
    target = result["targets"][0]
    assert target["file"] == "src/example.py"
    assert target["name"] == "foo"
    assert target["classification"] == "SIMPLE"

    fake_analyzer.analyze_file.assert_called_once()
    analyzed_path = fake_analyzer.analyze_file.call_args[0][0]
    assert isinstance(analyzed_path, Path)


# ID: ab5cae4a-0fe0-41b0-a47f-da6a93476c41
def test_get_analysis_command_tree():
    """Walks the real core-admin Typer app (#1386: the backend it imported
    never existed, so the endpoint always answered available=False)."""
    import json

    from will.governance.inspect_runner import get_analysis_command_tree

    result = get_analysis_command_tree()

    assert result["available"] is True
    assert result["source"] == "cli"
    assert result["count"] == len(result["commands"]) > 0
    names = {row["name"] for row in result["commands"]}
    assert "code.audit" in names
    for row in result["commands"]:
        assert "callback" not in row
    json.dumps(result)  # the route returns it as JSON


import pytest

from will.governance.inspect_runner import get_search_commands


@pytest.mark.asyncio
# ID: 46d680a4-d112-4399-91f1-2a0fdcaa9a8e
async def test_get_search_commands():
    row = MagicMock()
    row.name = "hub_search_cmd"
    row.module = "will.governance"
    row.summary = "Search CLI commands"
    row.help_text = "Fuzzy search over CLI registry"

    result_mock = MagicMock()
    result_mock.all.return_value = [row]

    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)

    out = await get_search_commands(session, q="search", limit=10)

    assert session.execute.await_count == 1
    assert out["query"] == "search"
    assert out["available"] is True
    assert out["count"] == 1
    assert out["results"] == [
        {
            "command": "hub_search_cmd",
            "module": "will.governance",
            "description": "Search CLI commands",
        }
    ]


import asyncio

from will.governance.inspect_runner import get_analysis_duplicates


# ID: 856a9a5f-808f-4d22-90e6-a7e14b01dd68
def test_get_analysis_duplicates():
    context = MagicMock()
    threshold = 0.9

    mock_inspect = AsyncMock(return_value=None)

    with patch(
        "body.self_healing.duplicates_service.inspect_duplicates_async",
        mock_inspect,
    ):
        result = asyncio.run(get_analysis_duplicates(context, threshold=threshold))

    mock_inspect.assert_awaited_once_with(context, threshold)
    assert result["ok"] is True
    assert result["threshold"] == threshold
    assert result["note"] == "results emitted to logs"


import pytest

from will.governance.inspect_runner import get_refusals_stats


@pytest.mark.asyncio
# ID: 172b682a-7017-4961-bea1-e5af615f1eb6
async def test_get_refusals_stats():
    fake_repo = MagicMock()
    fake_repo.get_statistics = AsyncMock(return_value={"total": 5})
    fake_repo.count_by_type = AsyncMock(return_value={"policy": 3, "safety": 2})

    with patch(
        "will.governance.inspect_runner.RefusalRepository",
        return_value=fake_repo,
    ):
        result = await get_refusals_stats(days=7)

    assert result == {
        "days": 7,
        "stats": {"total": 5},
        "counts_by_type": {"policy": 3, "safety": 2},
    }
    fake_repo.get_statistics.assert_awaited_once_with(days=7)
    fake_repo.count_by_type.assert_awaited_once_with(days=7)


import pytest

from will.governance.inspect_runner import get_refusals


@pytest.mark.asyncio
# ID: 1cf538d5-8a5d-46d7-813f-bc39c18db0b0
async def test_get_refusals():
    mock_repo = MagicMock()
    mock_repo.get_recent = AsyncMock(return_value=[])
    mock_repo.get_by_session = AsyncMock(return_value=[])
    mock_repo.get_by_type = AsyncMock(return_value=[])

    with patch(
        "will.governance.inspect_runner.RefusalRepository",
        return_value=mock_repo,
    ):
        result = await get_refusals(limit=10)

    mock_repo.get_recent.assert_awaited_once_with(limit=10, refusal_type=None)
    assert result == {"count": 0, "refusals": []}


# ID: b20bc0cc-ff5b-4ac8-a811-c4bbf9f2b2da
def test_get_decisions_patterns():
    from will.governance.inspect_runner import get_decisions_patterns

    summary = {
        "some_pattern": {
            "count": 3,
            "violations": 1,
            "success_rate": 0.66,
            "decisions": ["d1", "d2"],
        }
    }

    mock_repo = MagicMock()
    mock_repo.get_pattern_summary = AsyncMock(return_value=summary)

    mock_open = MagicMock()
    mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_repo)
    mock_open.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "will.governance.inspect_runner.DecisionTraceRepository.open",
        mock_open,
    ):
        result = asyncio.run(get_decisions_patterns(days=7))

    assert result == {"days": 7, "patterns": summary}
    mock_repo.get_pattern_summary.assert_awaited_once_with(7)


import pytest


# ID: e3fbbcc7-4cef-4bc3-a189-98aa1041d40a
async def test_get_decisions():
    from will.governance.inspect_runner import get_decisions

    fake_trace = MagicMock()

    mock_repo = MagicMock()
    mock_repo.get_recent_paginated = AsyncMock(return_value=([fake_trace], False, None))

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_repo)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "will.governance.inspect_runner.DecisionTraceRepository.open",
            return_value=mock_ctx,
        ),
        patch(
            "will.governance.inspect_runner._trace_to_dict",
            return_value={"pattern": "do-thing"},
        ),
    ):
        result = await get_decisions(limit=10)

    assert result["count"] == 1
    assert result["has_more"] is False
    assert result["next_cursor"] is None
    assert result["traces"] == [{"pattern": "do-thing"}]
    mock_repo.get_recent_paginated.assert_awaited_once_with(
        limit=10,
        after_cursor=None,
        agent_name=None,
    )


import pytest

from will.governance.inspect_runner import get_drift_status


@pytest.mark.asyncio
# ID: 585e6d42-03e6-49a1-8c15-9724048449b0
async def test_get_drift_status() -> None:
    context = MagicMock()
    context.qdrant_service = MagicMock()
    context.qdrant_service.list_collections = AsyncMock(
        return_value=["coll_a", "coll_b"]
    )

    drift_result = {"total_violations": 0, "drifted": []}
    mock_run_drift = AsyncMock(return_value=drift_result)

    with patch(
        "body.introspection.drift_service.run_drift_analysis_async",
        mock_run_drift,
    ):
        result = await get_drift_status(context, scope="all")

    assert result["scope"] == "all"
    assert result["symbols"] == drift_result
    assert result["vectors"]["available"] is True
    assert result["vectors"]["collections"] == ["coll_a", "coll_b"]
    assert result["vectors"]["count"] == 2
    assert result["guard"]["available"] is False
    mock_run_drift.assert_awaited_once()
    context.qdrant_service.list_collections.assert_awaited_once()


import pytest

from will.governance.inspect_runner import get_db_status


@pytest.mark.asyncio
# ID: 081ab475-0898-437a-b724-1d54b39111e6
async def test_get_db_status():
    session = MagicMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one = MagicMock(return_value=7)
    session.execute = AsyncMock(side_effect=[MagicMock(), scalar_result])

    result = await get_db_status(session)

    assert result == {
        "ok": True,
        "connected": True,
        "core_schema_tables": 7,
    }
    assert session.execute.await_count == 2


import datetime

import pytest

from will.governance.inspect_runner import get_spend


@pytest.mark.asyncio
# ID: 69a6c97e-c1b9-4589-99cf-d1456c636462
async def test_get_spend():
    by_role_rows = [
        ("planner", "gpt-4o", 3, 100, 50, 0.30, 0),
        ("executor", "gpt-4o-mini", 2, 20, 10, 0.02, 1),
    ]
    by_day_rows = [
        (datetime.date(2024, 1, 2), 4, 0.25, 0),
        (datetime.date(2024, 1, 1), 1, 0.07, 1),
    ]

    role_result = MagicMock()
    role_result.fetchall.return_value = by_role_rows
    day_result = MagicMock()
    day_result.fetchall.return_value = by_day_rows

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[role_result, day_result])

    result = await get_spend(session, days=7)

    assert result["days"] == 7
    assert result["calls"] == 5
    assert result["unpriced"] == 1
    assert result["usd"] == pytest.approx(0.32)

    assert result["by_role_model"][0] == {
        "role": "planner",
        "model": "gpt-4o",
        "calls": 3,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "usd": pytest.approx(0.30),
        "usd_per_call": pytest.approx(0.10),
        "unpriced": 0,
    }
    assert result["by_role_model"][1]["usd_per_call"] == pytest.approx(0.01)

    assert result["by_day"] == [
        {"day": "2024-01-02", "calls": 4, "usd": pytest.approx(0.25), "unpriced": 0},
        {"day": "2024-01-01", "calls": 1, "usd": pytest.approx(0.07), "unpriced": 1},
    ]

    assert session.execute.await_count == 2
