import pytest


pytestmark = pytest.mark.legacy

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from features.introspection.export_vectors import (
    VectorExportError,
    _async_export,
    export_vectors,
)
from shared.config import settings
from shared.context import CoreContext


class DummyFileHandler:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def ensure_dir(self, rel_dir: str):
        (self.base_path / rel_dir).mkdir(parents=True, exist_ok=True)

    def write_runtime_text(self, rel_path: str, content: str):
        target = self.base_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(settings, "REPO_PATH", root)
    return root


@pytest.fixture
def dummy_file_handler(repo_root):
    return DummyFileHandler(repo_root)


@pytest.fixture
def mock_qdrant_service():
    mock_instance = MagicMock()
    mock_instance.get_all_vectors = AsyncMock()
    return mock_instance


@pytest.fixture
def sample_vector_records():
    return [
        Mock(id=1, payload={"text": "hello world"}, vector=[0.1, 0.2, 0.3]),
        Mock(id=2, payload={"text": "test document"}, vector=[0.4, 0.5, 0.6]),
        Mock(id=3, payload={"text": "another example"}, vector=[0.7, 0.8, 0.9]),
    ]


@pytest.fixture
def core_context(mock_qdrant_service, dummy_file_handler):
    return CoreContext(
        registry=MagicMock(),
        git_service=None,
        cognitive_service=None,
        knowledge_service=None,
        qdrant_service=mock_qdrant_service,
        auditor_context=None,
        file_handler=dummy_file_handler,
        planner_config=None,
    )


@pytest.mark.asyncio
async def test_async_export_success(
    mock_qdrant_service, dummy_file_handler, sample_vector_records, repo_root
):
    output_path = repo_root / "reports" / "vectors.jsonl"
    mock_qdrant_service.get_all_vectors.return_value = sample_vector_records

    await _async_export(mock_qdrant_service, dummy_file_handler, output_path)

    result_path = repo_root / "reports" / "vectors.jsonl"
    assert result_path.exists()
    with result_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 3
        first_record = json.loads(lines[0])
        assert first_record["id"] == "1"
        assert first_record["payload"] == {"text": "hello world"}
        assert first_record["vector"] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_async_export_no_vectors(
    mock_qdrant_service, dummy_file_handler, repo_root, caplog
):
    output_path = repo_root / "reports" / "vectors.jsonl"
    mock_qdrant_service.get_all_vectors.return_value = []

    with caplog.at_level("INFO"):
        await _async_export(mock_qdrant_service, dummy_file_handler, output_path)

    result_path = repo_root / "reports" / "vectors.jsonl"
    assert not result_path.exists()
    assert "No vectors found in the database" in caplog.text


@pytest.mark.asyncio
async def test_async_export_creates_parent_directories(
    mock_qdrant_service, dummy_file_handler, sample_vector_records, repo_root
):
    output_path = repo_root / "deep" / "nested" / "vectors.jsonl"
    mock_qdrant_service.get_all_vectors.return_value = sample_vector_records

    await _async_export(mock_qdrant_service, dummy_file_handler, output_path)

    assert output_path.exists()
    assert output_path.parent.exists()


@pytest.mark.asyncio
async def test_async_export_database_error(
    mock_qdrant_service, dummy_file_handler, repo_root
):
    output_path = repo_root / "reports" / "vectors.jsonl"
    mock_qdrant_service.get_all_vectors.side_effect = Exception("DB failed")

    with pytest.raises(VectorExportError) as exc:
        await _async_export(mock_qdrant_service, dummy_file_handler, output_path)

    assert exc.value.exit_code == 1
    assert not output_path.exists()


@pytest.mark.asyncio
async def test_export_vectors_function(core_context):
    output_path = Path("reports/test_vectors.jsonl")
    with patch(
        "features.introspection.export_vectors._async_export",
        new_callable=AsyncMock,
    ) as mock_async:
        await export_vectors(core_context, output_path)
        mock_async.assert_awaited_once_with(
            core_context.qdrant_service,
            core_context.file_handler,
            output_path,
        )


@pytest.mark.asyncio
async def test_export_vectors_default_output(core_context):
    default_output = Path("reports/vectors_export.jsonl")
    with patch(
        "features.introspection.export_vectors._async_export",
        new_callable=AsyncMock,
    ) as mock_async:
        await export_vectors(core_context)
        mock_async.assert_awaited_once_with(
            core_context.qdrant_service,
            core_context.file_handler,
            default_output,
        )


@pytest.mark.asyncio
async def test_async_export_json_serialization(
    mock_qdrant_service, dummy_file_handler, repo_root
):
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
    output_path = repo_root / "reports" / "complex_vectors.jsonl"

    await _async_export(mock_qdrant_service, dummy_file_handler, output_path)

    assert output_path.exists()
    with output_path.open("r", encoding="utf-8") as f:
        record = json.loads(f.readline())
        assert record["payload"]["metadata"]["tags"] == ["a", "b"]


@pytest.mark.asyncio
async def test_async_export_empty_payload(
    mock_qdrant_service, dummy_file_handler, repo_root
):
    records = [
        Mock(id=uuid.uuid4(), payload=None, vector=[0.1, 0.2]),
        Mock(id=uuid.uuid4(), payload={}, vector=[0.3, 0.4]),
    ]
    mock_qdrant_service.get_all_vectors.return_value = records
    output_path = repo_root / "reports" / "empty_payload.jsonl"

    await _async_export(mock_qdrant_service, dummy_file_handler, output_path)

    assert output_path.exists()
    with output_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["payload"] is None
        assert json.loads(lines[1])["payload"] == {}


@pytest.mark.asyncio
async def test_export_vectors_without_services_raises(core_context):
    broken_context = CoreContext(registry=MagicMock())
    with pytest.raises(VectorExportError):
        await export_vectors(broken_context, Path("reports/vectors.jsonl"))


@pytest.mark.asyncio
async def test_export_path_must_be_within_repo(
    mock_qdrant_service, dummy_file_handler, tmp_path, repo_root
):
    output_path = tmp_path / "outside" / "vectors.jsonl"

    with pytest.raises(VectorExportError) as exc:
        await _async_export(mock_qdrant_service, dummy_file_handler, output_path)

    assert exc.value.exit_code == 1
