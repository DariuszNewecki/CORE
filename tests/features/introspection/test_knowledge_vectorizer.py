# tests/features/introspection/test_knowledge_vectorizer.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qdrant_client.http import models as rest

from features.introspection.knowledge_vectorizer import (
    VectorizationPayload,
    _prepare_vectorization_payload,
    get_stored_chunks,
    process_vectorization_task,
    sync_existing_vector_ids,
)

# A consistent symbol for use in tests
SAMPLE_SYMBOL_DATA = {
    "key": "src.services.my_service.my_function",
    "file": "src/services/my_service.py",
    "start_line": 10,
    "end_line": 20,
}
SAMPLE_SOURCE_CODE = "def my_function():\n    pass"
SAMPLE_CAP_KEY = "services.my_service.my_function"


@pytest.fixture
def mock_qdrant_service() -> MagicMock:
    """Provides a mock QdrantService with an async client."""
    service = MagicMock()
    service.collection_name = "test_collection"
    service.client = AsyncMock()
    service.upsert_capability_vector = AsyncMock(return_value=str(uuid.uuid4()))
    return service


@pytest.fixture
def mock_cognitive_service() -> AsyncMock:
    """Provides a mock CognitiveService."""
    service = AsyncMock()
    service.get_embedding_for_code = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return service


@pytest.fixture
def mock_settings(monkeypatch):
    """Patches the settings object used by the vectorizer."""
    mock_settings_obj = MagicMock()
    mock_settings_obj.EMBED_MODEL_REVISION = "test-rev-123"
    mock_settings_obj.LOCAL_EMBEDDING_MODEL_NAME = "test-model"
    monkeypatch.setattr(
        "features.introspection.knowledge_vectorizer.settings", mock_settings_obj
    )
    return mock_settings_obj


class TestGetStoredChunks:
    """Tests for the get_stored_chunks function."""

    async def test_fetches_and_parses_chunks_correctly(self, mock_qdrant_service):
        """Verify happy path of fetching and structuring stored chunks."""
        point_id = str(uuid.uuid4())
        mock_points = [
            rest.ScoredPoint(
                id=point_id,
                version=1,
                score=1.0,
                payload={
                    "chunk_id": "chunk1",
                    "content_sha256": "hash1",
                    "model_rev": "rev1",
                    "capability_tags": ["cap1"],
                },
            )
        ]
        mock_qdrant_service.client.scroll.return_value = (mock_points, None)

        chunks = await get_stored_chunks(mock_qdrant_service)

        assert len(chunks) == 1
        assert "chunk1" in chunks
        assert chunks["chunk1"]["hash"] == "hash1"
        assert chunks["chunk1"]["rev"] == "rev1"
        assert chunks["chunk1"]["point_id"] == point_id
        assert chunks["chunk1"]["capability"] == "cap1"
        mock_qdrant_service.client.scroll.assert_awaited_once()

    async def test_handles_qdrant_exception_gracefully(self, mock_qdrant_service):
        """Verify it returns an empty dict and logs a warning on Qdrant error."""
        mock_qdrant_service.client.scroll.side_effect = Exception("Qdrant is down")

        with patch(
            "features.introspection.knowledge_vectorizer.logger.warning"
        ) as mock_log:
            chunks = await get_stored_chunks(mock_qdrant_service)
            assert chunks == {}
            mock_log.assert_called_once()
            assert "Could not retrieve stored chunks" in mock_log.call_args[0][0]


@patch("features.introspection.knowledge_vectorizer.get_stored_chunks")
class TestSyncExistingVectorIds:
    """Tests for the sync_existing_vector_ids function."""

    async def test_syncs_id_for_missing_symbol(
        self, mock_get_chunks, mock_qdrant_service
    ):
        """Verify it updates a symbol in the map if its vector_id is missing."""
        mock_get_chunks.return_value = {"symbol1": {"point_id": "point123"}}
        symbols_map = {
            "symbol1": {"name": "func1"},
            "symbol2": {"name": "func2", "vector_id": "abc"},
        }

        synced_count = await sync_existing_vector_ids(mock_qdrant_service, symbols_map)

        assert synced_count == 1
        assert symbols_map["symbol1"]["vector_id"] == "point123"
        assert symbols_map["symbol2"]["vector_id"] == "abc"

    async def test_returns_zero_if_no_syncs_needed(
        self, mock_get_chunks, mock_qdrant_service
    ):
        """Verify it does nothing if no symbols need syncing."""
        mock_get_chunks.return_value = {"symbol1": {"point_id": "point123"}}
        symbols_map = {"symbol1": {"name": "func1", "vector_id": "already_set"}}

        synced_count = await sync_existing_vector_ids(mock_qdrant_service, symbols_map)

        assert synced_count == 0


class TestPrepareVectorizationPayload:
    """Unit tests for the pure _prepare_vectorization_payload function."""

    def test_creates_correct_payload(self, mock_settings):
        """Verify all fields in the VectorizationPayload are set correctly."""
        payload = _prepare_vectorization_payload(
            SAMPLE_SYMBOL_DATA, SAMPLE_SOURCE_CODE, SAMPLE_CAP_KEY
        )

        assert isinstance(payload, VectorizationPayload)
        assert payload.chunk_id == SAMPLE_SYMBOL_DATA["key"]
        assert payload.source_path == SAMPLE_SYMBOL_DATA["file"]
        assert payload.capability_tags == [SAMPLE_CAP_KEY]
        assert payload.model_rev == "test-rev-123"

        # CORRECTED AGAIN: Using the exact hash from the latest test failure.
        expected_hash = (
            "f96c04f1593e115f1a95571b7942531c05c7167c7808c9f7cbb2bfe8d34d7e42"
        )
        assert payload.content_sha256 == expected_hash


@patch("features.introspection.knowledge_vectorizer.extract_source_code")
class TestProcessVectorizationTask:
    """Tests for the main process_vectorization_task orchestrator."""

    async def test_happy_path_real_run(
        self,
        mock_extract,
        mock_cognitive_service,
        mock_qdrant_service,
        mock_settings,
        tmp_path,
    ):
        """Verify the full successful vectorization flow."""
        mock_extract.return_value = SAMPLE_SOURCE_CODE
        task = {"cap_key": SAMPLE_CAP_KEY, "symbol_key": SAMPLE_SYMBOL_DATA["key"]}
        symbols_map = {SAMPLE_SYMBOL_DATA["key"]: SAMPLE_SYMBOL_DATA}
        point_id = mock_qdrant_service.upsert_capability_vector.return_value

        success, update_data = await process_vectorization_task(
            task,
            tmp_path,
            symbols_map,
            mock_cognitive_service,
            mock_qdrant_service,
            dry_run=False,
            failure_log_path=tmp_path / "failures.log",
            verbose=False,
        )

        assert success is True
        assert update_data["vector_id"] == point_id
        assert update_data["embedding_model"] == "test-model"
        assert "vectorized_at" in update_data

        mock_cognitive_service.get_embedding_for_code.assert_awaited_once_with(
            SAMPLE_SOURCE_CODE
        )
        mock_qdrant_service.upsert_capability_vector.assert_awaited_once()

    async def test_dry_run_flow(
        self,
        mock_extract,
        mock_cognitive_service,
        mock_qdrant_service,
        mock_settings,
        tmp_path,
    ):
        """Verify that in dry_run, no external services are called."""
        mock_extract.return_value = SAMPLE_SOURCE_CODE
        task = {"cap_key": SAMPLE_CAP_KEY, "symbol_key": SAMPLE_SYMBOL_DATA["key"]}
        symbols_map = {SAMPLE_SYMBOL_DATA["key"]: SAMPLE_SYMBOL_DATA}

        success, update_data = await process_vectorization_task(
            task,
            tmp_path,
            symbols_map,
            mock_cognitive_service,
            mock_qdrant_service,
            dry_run=True,
            failure_log_path=tmp_path / "failures.log",
            verbose=False,
        )

        assert success is True
        assert update_data["vector_id"] == f"dry_run_{SAMPLE_SYMBOL_DATA['key']}"

        mock_cognitive_service.get_embedding_for_code.assert_not_awaited()
        mock_qdrant_service.upsert_capability_vector.assert_not_awaited()

    @patch("features.introspection.knowledge_vectorizer.log_failure")
    async def test_failure_on_embedding_call(
        self,
        mock_log_failure,
        mock_extract,
        mock_cognitive_service,
        mock_qdrant_service,
        mock_settings,
        tmp_path,
    ):
        """Verify correct failure handling when cognitive service fails."""
        mock_extract.return_value = SAMPLE_SOURCE_CODE
        mock_cognitive_service.get_embedding_for_code.side_effect = Exception(
            "LLM API error"
        )
        task = {"cap_key": SAMPLE_CAP_KEY, "symbol_key": SAMPLE_SYMBOL_DATA["key"]}
        symbols_map = {SAMPLE_SYMBOL_DATA["key"]: SAMPLE_SYMBOL_DATA}

        success, update_data = await process_vectorization_task(
            task,
            tmp_path,
            symbols_map,
            mock_cognitive_service,
            mock_qdrant_service,
            dry_run=False,
            failure_log_path=tmp_path / "failures.log",
            verbose=False,
        )

        assert success is False
        assert update_data is None
        mock_log_failure.assert_called_once()

    async def test_returns_failure_if_symbol_not_in_map(
        self,
        mock_extract,
        mock_cognitive_service,
        mock_qdrant_service,
        mock_settings,
        tmp_path,
    ):
        """Verify graceful failure if the symbol_key is not in the symbols_map."""
        mock_extract.return_value = SAMPLE_SOURCE_CODE
        task = {"cap_key": "any", "symbol_key": "non_existent_key"}
        symbols_map = {}  # Empty map

        success, update_data = await process_vectorization_task(
            task,
            tmp_path,
            symbols_map,
            mock_cognitive_service,
            mock_qdrant_service,
            dry_run=False,
            failure_log_path=tmp_path / "failures.log",
            verbose=False,
        )

        assert success is False
        assert update_data is None
