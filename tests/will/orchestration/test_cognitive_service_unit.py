# tests/will/orchestration/test_cognitive_service_unit.py
import builtins
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1.  Make sure the real Qdrant client is never imported
# ---------------------------------------------------------------------------
_real_import = builtins.__import__


def _safe_import(name, *args, **kwargs):
    if name == "services.clients.qdrant_client":
        mock_qdrant = MagicMock()
        return SimpleNamespace(
            clients=SimpleNamespace(
                qdrant_client=SimpleNamespace(QdrantService=lambda: mock_qdrant)
            )
        )
    return _real_import(name, *args, **kwargs)


with patch("builtins.__import__", side_effect=_safe_import):
    from will.orchestration.cognitive_service import CognitiveService


# ---------------------------------------------------------------------------
# 2.  Fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_service(tmp_path):
    """CognitiveService whose dependencies can be safely mocked."""
    return CognitiveService(tmp_path)


# ---------------------------------------------------------------------------
# 3.  Tests
# ---------------------------------------------------------------------------


@patch("will.orchestration.cognitive_service.ResourceSelector")
@patch("will.orchestration.cognitive_service.get_session")
@pytest.mark.asyncio
async def test_initialize_success(mock_get_session, mock_ResourceSelector, tmp_service):
    """initialize() populates resource and role lists from a mock DB call."""
    tmp_service._resources = [SimpleNamespace(name="res1")]
    tmp_service._roles = [SimpleNamespace(name="role1")]
    tmp_service._loaded = True

    await tmp_service.initialize()

    assert tmp_service._loaded is True
    assert len(tmp_service._resources) == 1
    assert len(tmp_service._roles) == 1


@patch("will.orchestration.cognitive_service.ResourceSelector")
@patch("will.orchestration.cognitive_service.get_session")
@pytest.mark.asyncio
async def test_initialize_handles_exception(
    mock_get_session, mock_ResourceSelector, tmp_service
):
    """initialize() keeps going even if the DB lookup blows up."""
    mock_get_session.side_effect = RuntimeError("db fail")
    await tmp_service.initialize()
    assert tmp_service._loaded is True
    assert tmp_service._resources == []
    assert tmp_service._roles == []


# ---------------------------------------------------------------------------
# _create_provider_for_resource()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_provider_openai(mocker, tmp_service):
    res = SimpleNamespace(name="OpenAIResource", env_prefix="OPENAI")
    mocker.patch(
        "services.config_service.ConfigService.create"
    ).return_value.get = AsyncMock(
        side_effect=lambda k, d=None: "dummy" if "URL" in k or "MODEL" in k else d
    )
    mocker.patch(
        "services.config_service.ConfigService.create"
    ).return_value.get_secret = AsyncMock(return_value="sek")
    from services.llm.providers.openai import OpenAIProvider

    provider = await tmp_service._create_provider_for_resource(res)
    assert isinstance(provider, OpenAIProvider)


@pytest.mark.asyncio
async def test_create_provider_ollama(mocker, tmp_service):
    res = SimpleNamespace(name="ollama-test", env_prefix="OLLAMA")
    mocker.patch(
        "services.config_service.ConfigService.create"
    ).return_value.get = AsyncMock(return_value=None)
    mocker.patch(
        "services.config_service.ConfigService.create"
    ).return_value.get_secret = AsyncMock(return_value="sek")
    mocker.patch("os.getenv", return_value="http://localhost:11434")
    from services.llm.providers.ollama import OllamaProvider

    provider = await tmp_service._create_provider_for_resource(res)
    assert isinstance(provider, OllamaProvider)


@pytest.mark.asyncio
async def test_create_provider_missing_prefix(tmp_service):
    res = SimpleNamespace(name="nope", env_prefix=None)
    with pytest.raises(ValueError):
        await tmp_service._create_provider_for_resource(res)


@pytest.mark.asyncio
async def test_create_provider_missing_config(mocker, tmp_service):
    res = SimpleNamespace(name="bad", env_prefix="BAD")

    # Create a persistent mock that will be returned by ALL calls to create()
    mock_config = AsyncMock()
    mock_config.get.return_value = None  # No URL/MODEL found
    mock_config.get_secret.return_value = "sek"
    mocker.patch(
        "services.config_service.ConfigService.create", return_value=mock_config
    )

    # Block environment variable fallback
    mocker.patch("will.orchestration.cognitive_service.os.getenv", return_value=None)

    with pytest.raises(ValueError, match="Missing required config"):
        await tmp_service._create_provider_for_resource(res)


@pytest.mark.asyncio
async def test_create_provider_secret_keyerror(mocker, tmp_service):
    res = SimpleNamespace(name="EnvBack", env_prefix="ENV")
    mocker.patch(
        "services.config_service.ConfigService.create"
    ).return_value.get = AsyncMock(return_value="x")
    mocker.patch(
        "services.config_service.ConfigService.create"
    ).return_value.get_secret = AsyncMock(side_effect=KeyError)
    mocker.patch("os.getenv", return_value="sek")
    from services.llm.providers.openai import OpenAIProvider

    provider = await tmp_service._create_provider_for_resource(res)
    assert isinstance(provider, OpenAIProvider)


# ---------------------------------------------------------------------------
# aget_client_for_role()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aget_client_for_role_success(mocker, tmp_service):
    mock_resource = SimpleNamespace(name="R1", env_prefix="R1")
    tmp_service._loaded = True
    tmp_service._roles = [SimpleNamespace(role="test_role", assigned_resource="R1")]
    tmp_service._resources = [mock_resource]

    mock_provider = MagicMock()
    mock_client = MagicMock()

    # Patch where it's USED for LLMClient
    mocker.patch(
        "will.orchestration.cognitive_service.LLMClient", return_value=mock_client
    )

    # Patch where it's DEFINED for LLMResourceConfig
    mock_LLMResourceConfig = MagicMock()
    mock_LLMResourceConfig.return_value.get_max_concurrent = AsyncMock(return_value=5)
    mocker.patch("services.llm.client.LLMResourceConfig", mock_LLMResourceConfig)

    mock_config_instance = AsyncMock()

    async def smart_get(key, default=None):
        if "URL" in key:
            return "http://dummy.url"
        if "MODEL" in key:
            return "dummy-model"
        if "CONCURRENT" in key:
            return "5"
        return default

    mock_config_instance.get.side_effect = smart_get
    mock_config_instance.get_secret.return_value = "secret-key"
    mocker.patch(
        "will.orchestration.cognitive_service.ConfigService.create",
        return_value=mock_config_instance,
    )

    mocker.patch(
        "will.orchestration.cognitive_service.CognitiveService._create_provider_for_resource",
        AsyncMock(return_value=mock_provider),
    )

    client = await tmp_service.aget_client_for_role("test_role")
    assert client == mock_client
    assert "test_role" in tmp_service._clients_by_role


@pytest.mark.asyncio
async def test_aget_client_reuses_cached(tmp_service):
    dummy = MagicMock()
    tmp_service._clients_by_role["x"] = dummy
    tmp_service._loaded = True
    result = await tmp_service.aget_client_for_role("x")
    assert result is dummy


@pytest.mark.asyncio
async def test_aget_client_no_resource(tmp_service):
    tmp_service._loaded = True
    tmp_service._roles = [SimpleNamespace(role="missing")]
    tmp_service._resources = []
    with pytest.raises(RuntimeError):
        await tmp_service.aget_client_for_role("missing")


@pytest.mark.asyncio
async def test_aget_client_create_provider_fails(tmp_service, mocker):
    tmp_service._loaded = True
    tmp_service._roles = [SimpleNamespace(role="failrole", assigned_resource="R")]
    tmp_service._resources = [SimpleNamespace(name="R", env_prefix="R")]

    mocker.patch(
        "will.orchestration.cognitive_service.CognitiveService._create_provider_for_resource",
        AsyncMock(side_effect=ValueError("oops")),
    )
    with pytest.raises(RuntimeError):
        await tmp_service.aget_client_for_role("failrole")


# ---------------------------------------------------------------------------
# get_embedding_for_code()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_embedding_for_code_none(tmp_service):
    result = await tmp_service.get_embedding_for_code("")
    assert result is None


@pytest.mark.asyncio
async def test_get_embedding_for_code_success(tmp_service, mocker):
    mock_client = AsyncMock()
    mock_client.get_embedding.return_value = [0.1, 0.2]
    mocker.patch.object(
        tmp_service, "aget_client_for_role", AsyncMock(return_value=mock_client)
    )
    result = await tmp_service.get_embedding_for_code("print('hi')")
    assert result == [0.1, 0.2]


# ---------------------------------------------------------------------------
# search_capabilities()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_capabilities_success(tmp_service, mocker):
    tmp_service._loaded = True
    tmp_service.qdrant_service.search_similar = AsyncMock(return_value=[{"id": 1}])
    mocker.patch.object(
        tmp_service, "get_embedding_for_code", AsyncMock(return_value=[0.1, 0.2])
    )
    results = await tmp_service.search_capabilities("query")
    assert results == [{"id": 1}]


@pytest.mark.asyncio
async def test_search_capabilities_handles_errors(tmp_service, mocker):
    tmp_service._loaded = True
    tmp_service.qdrant_service.search_similar = AsyncMock(
        side_effect=RuntimeError("qdrant down")
    )
    mocker.patch.object(
        tmp_service, "get_embedding_for_code", AsyncMock(return_value=[0.1])
    )
    results = await tmp_service.search_capabilities("query")
    assert results == []


@pytest.mark.asyncio
async def test_search_capabilities_no_vector(tmp_service, mocker):
    tmp_service._loaded = True
    tmp_service.qdrant_service.search_similar = AsyncMock()
    mocker.patch.object(
        tmp_service, "get_embedding_for_code", AsyncMock(return_value=None)
    )
    results = await tmp_service.search_capabilities("query")
    assert results == []
