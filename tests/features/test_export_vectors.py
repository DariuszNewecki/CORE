# tests/features/test_export_vectors.py
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import typer

from features.introspection.export_vectors import _async_export, export_vectors
from shared.context import CoreContext


# Force pytest to treat this class as pytest-style (not unittest)
class TestExportVectors:
    __test__ = True  # Ensure pytest collects it

    @pytest.fixture
    def mock_qdrant_service(self):
        mock_instance = MagicMock()
        mock_instance.get_all_vectors = AsyncMock()
        return mock_instance

    @pytest.fixture
    def sample_vector_records(self):
        return [
            Mock(id=1, payload={"text": "hello world"}, vector=[0.1, 0.2, 0.3]),
            Mock(id=2, payload={"text": "test document"}, vector=[0.4, 0.5, 0.6]),
            Mock(id=3, payload={"text": "another example"}, vector=[0.7, 0.8, 0.9]),
        ]

    @pytest.fixture
    def mock_typer_context(self, mock_qdrant_service):
        """Creates a mock Typer context object with the necessary core_context."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = CoreContext(
            git_service=MagicMock(),
            cognitive_service=MagicMock(),
            knowledge_service=MagicMock(),
            qdrant_service=mock_qdrant_service,
            auditor_context=MagicMock(),
            file_handler=MagicMock(),
            planner_config=MagicMock(),
        )
        return ctx

    @pytest.mark.asyncio
    async def test_async_export_success(
        self, mock_qdrant_service, sample_vector_records, tmp_path
    ):
        output_path = tmp_path / "vectors.jsonl"
        mock_qdrant_service.get_all_vectors.return_value = sample_vector_records
        await _async_export(mock_qdrant_service, output_path)
        assert output_path.exists()

        with output_path.open("r") as f:
            lines = f.readlines()
            assert len(lines) == 3
            first_record = json.loads(lines[0])
            assert first_record["id"] == "1"
            assert first_record["payload"] == {"text": "hello world"}
            assert first_record["vector"] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_async_export_no_vectors(self, mock_qdrant_service, tmp_path, capsys):
        output_path = tmp_path / "vectors.jsonl"
        mock_qdrant_service.get_all_vectors.return_value = []
        await _async_export(mock_qdrant_service, output_path)
        # File should not be created if there are no vectors
        assert not output_path.exists()
        captured = capsys.readouterr()
        assert "No vectors found" in captured.out

    @pytest.mark.asyncio
    async def test_async_export_creates_parent_directories(
        self, mock_qdrant_service, sample_vector_records, tmp_path
    ):
        output_path = tmp_path / "deep" / "nested" / "vectors.jsonl"
        mock_qdrant_service.get_all_vectors.return_value = sample_vector_records
        await _async_export(mock_qdrant_service, output_path)
        assert output_path.exists()
        assert output_path.parent.exists()

    @pytest.mark.asyncio
    async def test_async_export_database_error(self, mock_qdrant_service, tmp_path):
        output_path = tmp_path / "vectors.jsonl"
        mock_qdrant_service.get_all_vectors.side_effect = Exception("DB failed")
        with pytest.raises(typer.Exit):
            await _async_export(mock_qdrant_service, output_path)
        assert not output_path.exists()

    @pytest.mark.asyncio
    async def test_export_vectors_function(self, tmp_path, mock_typer_context):
        output_path = tmp_path / "test_vectors.jsonl"
        with patch(
            "features.introspection.export_vectors._async_export",
            new_callable=AsyncMock,
        ) as mock_async:
            await export_vectors(ctx=mock_typer_context, output=output_path)
            mock_async.assert_awaited_once()
            await_args = mock_async.await_args
            assert await_args.args[0] == mock_typer_context.obj.qdrant_service
            assert await_args.args[1] == output_path

    @pytest.mark.asyncio
    async def test_export_vectors_default_output(self, mock_typer_context):
        with patch(
            "features.introspection.export_vectors._async_export",
            new_callable=AsyncMock,
        ) as mock_async:
            await export_vectors(
                ctx=mock_typer_context, output=Path("reports/vectors_export.jsonl")
            )
            mock_async.assert_awaited_once_with(
                mock_typer_context.obj.qdrant_service,
                Path("reports/vectors_export.jsonl"),
            )

    @pytest.mark.asyncio
    async def test_async_export_json_serialization(self, mock_qdrant_service, tmp_path):
        complex_records = [
            Mock(
                id=uuid.uuid4(),
                payload={
                    "text": "complex",
                    "metadata": {"tags": ["a", "b"]},
                    "count": 42,
                },
                vector=[0.1, 0.2, 0.3, 0.4],
            )
        ]
        mock_qdrant_service.get_all_vectors.return_value = complex_records
        output_path = tmp_path / "complex_vectors.jsonl"
        await _async_export(mock_qdrant_service, output_path)
        assert output_path.exists()
        with output_path.open("r") as f:
            record = json.loads(f.readline())
            assert record["payload"]["metadata"]["tags"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_async_export_empty_payload(self, mock_qdrant_service, tmp_path):
        records = [
            Mock(id=uuid.uuid4(), payload=None, vector=[0.1, 0.2]),
            Mock(id=uuid.uuid4(), payload={}, vector=[0.3, 0.4]),
        ]
        mock_qdrant_service.get_all_vectors.return_value = records
        output_path = tmp_path / "empty_payload.jsonl"
        await _async_export(mock_qdrant_service, output_path)
        assert output_path.exists()
        with output_path.open("r") as f:
            lines = f.readlines()
            assert len(lines) == 2
            assert json.loads(lines[0])["payload"] is None
            assert json.loads(lines[1])["payload"] == {}
