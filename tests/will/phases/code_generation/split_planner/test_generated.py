from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from will.phases.code_generation.split_planner import DeterministicSplitPlanner


# ID: 81f5ff2d-5081-4fa8-b736-6401fcd45983
def test_DeterministicSplitPlanner_execute(tmp_path: Path) -> None:
    import asyncio

    source_file = tmp_path / "mod.py"
    source_file.write_text(
        "def foo():\n    return 1\n\nclass Bar:\n    pass\n", encoding="utf-8"
    )

    task = SimpleNamespace(params=SimpleNamespace(file_path="mod.py"))
    context = SimpleNamespace(
        results={
            "planning": {
                "execution_plan": [task],
                "clusters": [],
            }
        }
    )

    core_context = SimpleNamespace(git_service=SimpleNamespace(repo_path=tmp_path))
    planner = DeterministicSplitPlanner(core_context)

    fake_plan = MagicMock(name="SplitPlan")
    fake_result = MagicMock(name="SplitResult")

    fake_splitter = MagicMock()
    fake_splitter.split.return_value = fake_result

    with (
        patch(
            "will.phases.code_generation.split_planner.DeterministicSplitPlanner._request_split_plan",
            new=AsyncMock(return_value=fake_plan),
        ) as mock_request,
        patch(
            "will.phases.code_generation.split_planner.ModularitySplitter",
            return_value=fake_splitter,
        ) as mock_splitter_cls,
    ):
        result = asyncio.run(planner.execute(context, start_time=0.0))

    mock_request.assert_awaited_once()
    call_kwargs = mock_request.await_args.kwargs
    assert call_kwargs["source_file"] == "mod.py"
    assert "def foo" in call_kwargs["source_code"]
    assert call_kwargs["actual_symbols"] == ["foo", "Bar"]

    mock_splitter_cls.assert_called_once_with()
    fake_splitter.split.assert_called_once_with(source_file, fake_plan)

    assert result.name == "code_generation"
    assert result.ok is True
    data = result.data
    assert data["deterministic_split"] is True
    assert len(data["split_results"]) == 1
    entry = data["split_results"][0]
    assert entry["file"] == "mod.py"
    assert entry["ok"] is True
    assert entry["split_result"] is fake_result
    assert entry["plan"] is fake_plan





# ID: a34d4c29-5a03-4aa6-94f2-3cc6d9d5648b
def test_DeterministicSplitPlanner():
    from will.phases.code_generation.split_planner import (
        DeterministicSplitPlanner as DSP,
    )

    core_context = MagicMock()
    planner = DSP(core_context)

    fake_plan = MagicMock()
    fake_plan.modules = [MagicMock(), MagicMock()]

    with patch.object(
        planner, "_request_split_plan", new=AsyncMock(return_value=fake_plan)
    ) as mock_request:
        import asyncio

        result = asyncio.run(
            planner._request_split_plan(
                source_file="foo.py",
                source_code="class A: pass\n",
                clusters_text="none",
                actual_symbols=["A"],
            )
        )

    assert result is fake_plan
    mock_request.assert_awaited_once()
