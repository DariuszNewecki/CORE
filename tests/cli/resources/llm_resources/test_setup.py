"""#1374: `core-admin llm-resources setup` / `check`."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from cli.resources.llm_resources import setup as mod


GOOD_CHECK = {
    "ok": True,
    "data": {
        "ok": True,
        "embedding": {"ok": True, "dimensions": 768},
        "chat": {"ok": True, "reply": "OK"},
    },
}


def _client(
    check: dict | None = None,
    remote_prefixes: tuple[str, ...] = ("setup_embedding", "setup_chat"),
) -> MagicMock:
    client = MagicMock()
    client.cognitive_roles.project = AsyncMock(return_value={"ok": True, "data": {}})
    client.llm_resources.setup = AsyncMock(
        return_value={
            "ok": True,
            "data": {
                "system_config": "created (local_only, llm enabled)",
                "remote_env_prefixes": list(remote_prefixes),
            },
        }
    )
    client.llm_resources.check = AsyncMock(return_value=check or GOOD_CHECK)
    client.secrets.set_secret = AsyncMock(return_value={"ok": True})
    return client


async def _setup(client: MagicMock, **kwargs) -> None:
    args = {
        "url": mod.DEFAULT_URL,
        "embedding_url": None,
        "embedding_model": mod.DEFAULT_EMBEDDING_MODEL,
        "chat_model": mod.DEFAULT_CHAT_MODEL,
        "api_key_env": None,
        "write": True,
    }
    args.update(kwargs)
    with patch.object(mod, "CoreApiClient", return_value=client):
        await mod.llm_resources_setup(MagicMock(spec=typer.Context), **args)


async def test_local_setup_syncs_roles_writes_models_and_checks() -> None:
    client = _client()
    await _setup(client)
    client.cognitive_roles.project.assert_awaited_once_with(write=True)
    client.llm_resources.setup.assert_awaited_once_with(
        api_url="http://localhost:11434",
        embedding_model="nomic-embed-text",
        chat_model="qwen2.5-coder:7b",
        locality="local",
        embedding_api_url="",
        embedding_locality="local",
        write=True,
    )
    client.secrets.set_secret.assert_not_awaited()
    client.llm_resources.check.assert_awaited_once()
    assert client.timeout == mod.CHECK_TIMEOUT_SECONDS


async def test_dry_run_writes_nothing_and_does_not_check() -> None:
    client = _client()
    await _setup(client, write=False)
    client.cognitive_roles.project.assert_not_awaited()
    assert client.llm_resources.setup.await_args.kwargs["write"] is False
    client.llm_resources.check.assert_not_awaited()


async def test_a_key_makes_the_models_remote_and_is_stored_for_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MY_KEY", "sk-test")
    client = _client()
    await _setup(client, url="https://models.example/v1", api_key_env="MY_KEY")
    assert client.llm_resources.setup.await_args.kwargs["locality"] == "remote"
    stored = [c.kwargs["key"] for c in client.secrets.set_secret.await_args_list]
    assert stored == ["setup_embedding.api_key", "setup_chat.api_key"]
    assert {c.kwargs["value"] for c in client.secrets.set_secret.await_args_list} == {
        "sk-test"
    }


async def test_hosted_chat_with_local_embeddings_keys_only_the_chat_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MY_KEY", "sk-test")
    client = _client(remote_prefixes=("setup_chat",))
    await _setup(
        client,
        url="https://api.anthropic.com/v1",
        embedding_url="http://localhost:11434",
        api_key_env="MY_KEY",
    )
    kwargs = client.llm_resources.setup.await_args.kwargs
    assert (kwargs["locality"], kwargs["embedding_locality"]) == ("remote", "local")
    assert kwargs["embedding_api_url"] == "http://localhost:11434"
    stored = [c.kwargs["key"] for c in client.secrets.set_secret.await_args_list]
    assert stored == ["setup_chat.api_key"]


async def test_an_unset_key_variable_stops_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MY_KEY", raising=False)
    client = _client()
    with pytest.raises(typer.Exit) as exc:
        await _setup(client, api_key_env="MY_KEY")
    assert exc.value.exit_code == 1
    client.llm_resources.setup.assert_not_awaited()


async def test_a_failing_model_exits_1() -> None:
    bad = {
        "ok": False,
        "data": {
            "ok": False,
            "embedding": {"ok": True, "dimensions": 768},
            "chat": {"ok": False, "error": "model 'qwen2.5-coder:7b' not found"},
        },
    }
    with pytest.raises(typer.Exit) as exc:
        await _setup(_client(check=bad))
    assert exc.value.exit_code == 1


async def test_check_exits_1_on_wrong_embedding_size() -> None:
    bad = {
        "data": {
            "ok": False,
            "embedding": {"ok": False, "error": "returns 1536 dimensions"},
            "chat": {"ok": True},
        }
    }
    client = _client(check=bad)
    with patch.object(mod, "CoreApiClient", return_value=client):
        with pytest.raises(typer.Exit) as exc:
            await mod.llm_resources_check(MagicMock(spec=typer.Context))
    assert exc.value.exit_code == 1
