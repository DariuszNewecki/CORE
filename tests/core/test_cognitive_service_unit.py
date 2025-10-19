# tests/core/test_cognitive_service_unit.py
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
    from core.cognitive_service import CognitiveService


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


@patch("core.cognitive_service.ResourceSelector")
@patch("core.cognitive_service.get_session")
@pytest.mark.asyncio
async def test_initialize_success(mock_get_session, mock_ResourceSelector, tmp_service):
    """initialize() populates _resource_selector and sets _loaded=True."""
    # 1. Define the mock data
    mock_resources = [SimpleNamespace(name="res1")]
    mock_roles = [SimpleNamespace(name="role1")]

    # --- THE FIX IS HERE ---
    # The object returned by `session.execute` is SYNCHRONOUS.
    # We must use MagicMock, NOT AsyncMock, to represent the result objects.
    fake_res_result = MagicMock()
    fake_res_result.scalars.return_value.all.return_value = mock_resources

    fake_role_result = MagicMock()
    fake_role_result.scalars.return_value.all.return_value = mock_roles
    # --- END OF FIX ---

    # 3. Configure the session mock. `session.execute` is async, but its
    #    return value is the synchronous MagicMock we just created.
    fake_session = AsyncMock()
    fake_session.__aenter__.return_value = fake_session
    fake_session.execute.side_effect = [fake_res_result, fake_role_result]
    mock_get_session.return_value = fake_session

    # The ResourceSelector mock is handled by the decorator
    mock_selector_instance = mock_ResourceSelector.return_value

    # 4. Run the code under test
    await tmp_service.initialize()

    # 5. Assertions
    assert tmp_service._loaded is True  # This will now pass
    assert tmp_service._resource_selector is mock_selector_instance
    mock_ResourceSelector.assert_called_once_with(mock_resources, mock_roles)


@patch("core.cognitive_service.ResourceSelector")
@patch("core.cognitive_service.get_session")
@pytest.mark.asyncio
async def test_initialize_handles_exception(
    mock_get_session, mock_ResourceSelector, tmp_service
):
    """initialize() keeps going even if the DB lookup blows up."""
    mock_get_session.side_effect = RuntimeError("db fail")
    mock_selector_instance = mock_ResourceSelector.return_value
    await tmp_service.initialize()
    assert tmp_service._resource_selector is mock_selector_instance
    mock_ResourceSelector.assert_called_once_with([], [])


# ---------------------------------------------------------------------------
# _create_provider_for_resource() - NO CHANGES BELOW THIS LINE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_provider_openai(mocker, tmp_service):
    res = SimpleNamespace(name="OpenAIResource", env_prefix="OPENAI")
    mocker.patch(
        "services.config_service.config_service.get",
        AsyncMock(
            side_effect=lambda k, d=None: "dummy" if "URL" in k or "MODEL" in k else d
        ),
    )
    mocker.patch(
        "services.config_service.config_service.get_secret",
        AsyncMock(return_value="sek"),
    )
    from services.llm.providers.openai import OpenAIProvider

    provider = await tmp_service._create_provider_for_resource(res)
    assert isinstance(provider, OpenAIProvider)


@pytest.mark.asyncio
async def test_create_provider_ollama(mocker, tmp_service):
    res = SimpleNamespace(name="ollama-test", env_prefix="OLLAMA")
    mocker.patch(
        "services.config_service.config_service.get", AsyncMock(return_value=None)
    )
    mocker.patch(
        "services.config_service.config_service.get_secret",
        AsyncMock(return_value="sek"),
    )
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
    mocker.patch(
        "services.config_service.config_service.get", AsyncMock(return_value=None)
    )
    mocker.patch(
        "services.config_service.config_service.get_secret",
        AsyncMock(return_value="sek"),
    )
    mocker.patch("os.getenv", return_value=None)
    with pytest.raises(ValueError):
        await tmp_service._create_provider_for_resource(res)


@pytest.mark.asyncio
async def test_create_provider_secret_keyerror(mocker, tmp_service):
    res = SimpleNamespace(name="EnvBack", env_prefix="ENV")
    mocker.patch(
        "services.config_service.config_service.get", AsyncMock(return_value="x")
    )
    mocker.patch(
        "services.config_service.config_service.get_secret",
        AsyncMock(side_effect=KeyError),
    )
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
    tmp_service._resource_selector = MagicMock()
    tmp_service._resource_selector.select_resource_for_role.return_value = mock_resource

    mock_provider = MagicMock()
    mock_client = MagicMock()
    mocker.patch("core.cognitive_service.LLMClient", return_value=mock_client)
    mocker.patch(
        "services.config_service.config_service.get", AsyncMock(return_value="x")
    )
    mocker.patch(
        "services.config_service.config_service.get_secret", AsyncMock(return_value="y")
    )
    mocker.patch(
        "core.cognitive_service.CognitiveService._create_provider_for_resource",
        AsyncMock(return_value=mock_provider),
    )
    mock_LLMResourceConfig = MagicMock()
    mock_LLMResourceConfig.return_value.get_max_concurrent = AsyncMock(return_value=1)
    mocker.patch("services.config_service.LLMResourceConfig", mock_LLMResourceConfig)

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
async def test_aget_client_no_selector(tmp_service):
    tmp_service._loaded = True
    tmp_service._resource_selector = None
    with pytest.raises(RuntimeError):
        await tmp_service.aget_client_for_role("abc")


@pytest.mark.asyncio
async def test_aget_client_no_resource(tmp_service):
    tmp_service._loaded = True
    tmp_service._resource_selector = MagicMock()
    tmp_service._resource_selector.select_resource_for_role.return_value = None
    with pytest.raises(RuntimeError):
        await tmp_service.aget_client_for_role("missing")


@pytest.mark.asyncio
async def test_aget_client_create_provider_fails(tmp_service, mocker):
    tmp_service._loaded = True
    mock_selector = MagicMock()
    mock_selector.select_resource_for_role.return_value = SimpleNamespace(
        name="R", env_prefix="R"
    )
    tmp_service._resource_selector = mock_selector
    mocker.patch(
        "core.cognitive_service.CognitiveService._create_provider_for_resource",
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
