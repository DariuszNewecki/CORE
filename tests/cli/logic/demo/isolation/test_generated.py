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


from cli.logic.demo.isolation import prove_clone_isolation


# ID: 307d5660-dd99-4e09-a214-d5a4588a267c
def test_prove_clone_isolation() -> None:
    clone = MagicMock()
    clone.clone_has_no_remote.return_value = True
    clone.get_current_commit.return_value = "abc123"

    result = prove_clone_isolation(clone, "abc123")

    assert result is None
    clone.clone_has_no_remote.assert_called_once_with()
    clone.get_current_commit.assert_called_once_with()


from cli.logic.demo.isolation import create_isolated_clone


# ID: a3995498-d88f-4de2-bded-f08a4109ffc7
def test_create_isolated_clone() -> None:
    source = MagicMock()
    expected_clone = MagicMock()
    source.create_disposable_clone.return_value = expected_clone

    identity = MagicMock()
    identity.clone_dir = "/tmp/clone-dir"

    result = create_isolated_clone(source, "abc123", identity)

    source.create_disposable_clone.assert_called_once_with("abc123", "/tmp/clone-dir")
    assert result is expected_clone


import hashlib

from cli.logic.demo.isolation import hash_directory


# ID: 8253ffa0-89bd-4bd5-80f9-bbecb1653ab3
def test_hash_directory(tmp_path):
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta")

    result = hash_directory(tmp_path)

    assert isinstance(result, str)
    assert len(result) == len(hashlib.sha256().hexdigest())

    # Deterministic: same content yields same digest.
    assert hash_directory(tmp_path) == result

    # Changing content changes the digest.
    (tmp_path / "b.txt").write_text("gamma")
    assert hash_directory(tmp_path) != result


from cli.logic.demo.isolation import hash_file


# ID: 5fa3f927-3904-4e14-ad81-661cab27cd40
def test_hash_file(tmp_path: Path) -> None:
    """Test hash_file returns the sha256 hex digest of a file's contents."""
    content = b"hello world"
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(content)

    result = hash_file(test_file)

    expected = hashlib.sha256(content).hexdigest()
    assert result == expected
    assert isinstance(result, str)
    assert len(result) == 64



from cli.logic.demo.isolation import compose_down


# ID: 8b60b656-d56c-4821-b0d8-29a624aec8d3
def test_compose_down():
    result = MagicMock(name="SubprocessResult")
    project_name = "demo-proj"
    compose_file = Path("/tmp/demo/docker-compose.yml")
    env = {"FOO": "bar"}

    with (
        patch(
            "cli.logic.demo.isolation.compose_down_command",
            return_value=["docker", "compose", "down"],
        ) as mock_cmd,
        patch(
            "cli.logic.demo.isolation.run_compose_command",
            new=AsyncMock(return_value=MagicMock(name="coro_result")),
        ) as mock_run,
        patch(
            "cli.logic.demo.isolation._with_deadline",
            new=AsyncMock(return_value=result),
        ) as mock_deadline,
    ):
        out = asyncio.run(compose_down(project_name, compose_file, env))

    assert out is result
    mock_cmd.assert_called_once_with(project_name, compose_file)
    mock_run.assert_called_once_with(
        ["docker", "compose", "down"],
        cwd=compose_file.parent,
        env=env,
    )
    mock_deadline.assert_awaited_once()
    _called_coro, called_timeout = mock_deadline.await_args.args[:2]
    assert called_timeout == 60.0
    assert mock_deadline.await_args.kwargs.get("phase") == "compose down"
