"""CognitiveService._create_provider_for_resource: a `locality: local` resource
never consults the secret store (#894 seeding unit).

An isolated external run carries no CORE_MASTER_KEY; SecretsService raises
RuntimeError when asked for one, and the provider factory only tolerated
KeyError/SecretNotFoundError -- so a local Ollama model could not be reached
from a bound copy. Local resources have no api key by definition (ADR-052
locality); remote resources keep the lookup.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from will.orchestration.cognitive_service import CognitiveService


def _service_with_config(get_secret: AsyncMock) -> CognitiveService:
    svc = CognitiveService(repo_path=Path("/nonexistent-repo"))
    config = MagicMock()

    async def _get(key: str, default=None, required=False):
        return {
            "ollama_trial.api_url": "http://127.0.0.1:11434",
            "ollama_trial.model_name": "qwen2.5-coder:3b",
            "remote_trial.api_url": "https://api.example/v1",
            "remote_trial.model_name": "m",
        }.get(key, default)

    config.get = _get
    config.get_secret = get_secret
    svc._config = config
    svc._loaded = True
    svc._orch = MagicMock()
    return svc


async def test_local_resource_never_touches_the_secret_store() -> None:
    get_secret = AsyncMock(
        side_effect=RuntimeError("CORE_MASTER_KEY not found in configuration")
    )
    svc = _service_with_config(get_secret)
    resource = SimpleNamespace(
        name="ollama_trial", env_prefix="OLLAMA_TRIAL", locality="local"
    )
    provider = await svc._create_provider_for_resource(resource)
    assert type(provider).__name__ == "OllamaProvider"
    get_secret.assert_not_awaited()


async def test_remote_resource_still_looks_up_its_key() -> None:
    get_secret = AsyncMock(return_value="sk-test")
    svc = _service_with_config(get_secret)
    resource = SimpleNamespace(
        name="remote_trial", env_prefix="REMOTE_TRIAL", locality="remote"
    )
    provider = await svc._create_provider_for_resource(resource)
    assert type(provider).__name__ == "OpenAIProvider"
    get_secret.assert_awaited_once()


async def test_remote_resource_without_master_key_still_raises() -> None:
    """The isolation posture is preserved for remote resources: no master key,
    no key -- and that stays a loud RuntimeError, not a silent None."""
    get_secret = AsyncMock(
        side_effect=RuntimeError("CORE_MASTER_KEY not found in configuration")
    )
    svc = _service_with_config(get_secret)
    resource = SimpleNamespace(
        name="remote_trial", env_prefix="REMOTE_TRIAL", locality="remote"
    )
    with pytest.raises(RuntimeError, match="CORE_MASTER_KEY"):
        await svc._create_provider_for_resource(resource)
