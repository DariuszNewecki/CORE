from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cli.logic.demo.isolation import cleanup_run


# ID: 0d3f8d57-58ae-4cde-bb0c-c167b1dec5e8
def test_cleanup_run():
    identity = MagicMock()
    identity.state_dir = Path("/tmp/demo/runs/run-1")
    identity.run_id = "run-1"
    demo_state_dir = Path("/tmp/demo/state")

    with patch(
        "cli.logic.demo.isolation.GitService.marker_checked_remove"
    ) as mock_remove:
        cleanup_run(identity, demo_state_dir)

    mock_remove.assert_called_once_with(
        identity.state_dir, identity.run_id, demo_state_dir
    )


import json

from cli.logic.demo.isolation import read_state_json


# ID: c3dd3d82-a891-4fa4-9382-1d8611f646bb
def test_read_state_json(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    expected = {"status": "ok", "value": 42}
    state_file.write_text(json.dumps(expected), encoding="utf-8")

    result = read_state_json(state_file)

    assert result == expected


from cli.logic.demo.isolation import write_state_json


# ID: 6d38d0d4-765f-471c-ae20-60f6c88a44e4
def test_write_state_json(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "state" / "result.json"
    payload = {"status": "ok", "value": 42}

    write_state_json(target, payload)

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == payload


import asyncio
from unittest.mock import AsyncMock

from cli.logic.demo.isolation import compose_up


# ID: c19f153b-34bd-43d4-93aa-9c45bfe7bb82
def test_compose_up():
    project_name = "demo-proj"
    compose_file = Path("/tmp/proj/compose.yaml")
    env = {"FOO": "bar"}
    expected_result = MagicMock(name="SubprocessResult")

    fake_args = ["docker", "compose", "up", "-d", "--wait"]
    fake_coro = AsyncMock(return_value=expected_result)()

    with (
        patch(
            "cli.logic.demo.isolation.compose_up_command",
            return_value=fake_args,
        ) as mock_cmd,
        patch(
            "cli.logic.demo.isolation.run_compose_command",
            return_value=fake_coro,
        ) as mock_run,
        patch(
            "cli.logic.demo.isolation._with_deadline",
            new=AsyncMock(return_value=expected_result),
        ) as mock_deadline,
    ):
        result = asyncio.run(compose_up(project_name, compose_file, env))

    assert result is expected_result

    mock_cmd.assert_called_once_with(project_name, compose_file)
    mock_run.assert_called_once_with(fake_args, cwd=compose_file.parent, env=env)
    mock_deadline.assert_awaited_once()
    await_args = mock_deadline.await_args
    assert await_args.args[1] == 120.0
    assert await_args.kwargs.get("phase") == "compose up"
