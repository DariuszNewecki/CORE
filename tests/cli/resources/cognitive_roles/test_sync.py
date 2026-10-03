"""core-admin cognitive-roles sync and its deprecated aliases (2026-10-02 rename)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from cli.resources.cognitive_roles import project as mod


def _client(in_sync: bool) -> MagicMock:
    client = MagicMock()
    client.cognitive_roles.project = AsyncMock(
        return_value={"data": {"in_sync": in_sync, "applied": ["Coder"]}}
    )
    return client


async def _run(func, client, **kwargs):
    with patch.object(mod, "CoreApiClient", return_value=client):
        await func(MagicMock(spec=typer.Context), **kwargs)


async def test_sync_without_write_passes_when_in_sync() -> None:
    client = _client(in_sync=True)
    await _run(mod.cognitive_roles_sync, client, write=False, yes=False)
    client.cognitive_roles.project.assert_awaited_once_with(write=False)


async def test_sync_without_write_exits_1_on_drift() -> None:
    with pytest.raises(typer.Exit) as exc:
        await _run(
            mod.cognitive_roles_sync, _client(in_sync=False), write=False, yes=False
        )
    assert exc.value.exit_code == 1


async def test_sync_with_write_applies() -> None:
    client = _client(in_sync=False)
    await _run(mod.cognitive_roles_sync, client, write=True, yes=True)
    client.cognitive_roles.project.assert_awaited_once_with(write=True)


async def test_diff_alias_keeps_ci_behaviour() -> None:
    with pytest.raises(typer.Exit):
        await _run(mod.cognitive_roles_diff, _client(in_sync=False))


async def test_project_alias_keeps_pre_rename_behaviour() -> None:
    """Old `project` without --apply showed drift and exited 0."""
    client = _client(in_sync=False)
    await _run(mod.cognitive_roles_project, client, apply=False)
    client.cognitive_roles.project.assert_awaited_once_with(write=False)
    client2 = _client(in_sync=False)
    await _run(mod.cognitive_roles_project, client2, apply=True)
    client2.cognitive_roles.project.assert_awaited_once_with(write=True)


def test_only_sync_is_visible_and_aliases_are_hidden() -> None:
    from cli.admin_cli import app
    from shared.cli.app_introspection import walk_typer_app

    cmds = {
        c["name"]: c["hidden"]
        for c in walk_typer_app(app)
        if c["name"].startswith("cognitive-roles.")
    }
    assert cmds == {
        "cognitive-roles.sync": False,
        "cognitive-roles.diff": True,
        "cognitive-roles.project": True,
    }
