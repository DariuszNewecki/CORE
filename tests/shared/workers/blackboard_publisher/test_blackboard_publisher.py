# tests/shared/workers/blackboard_publisher/test_blackboard_publisher.py

"""Unit tests for BlackboardPublisher.

All DB calls are patched out so these run without a live database.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.workers.blackboard_publisher import (
    BlackboardPublisher,
    _sanitize_payload,
)


def _publisher(
    *,
    artifact_type: str = "",
    rule_namespace: str = "",
) -> BlackboardPublisher:
    scope: dict = {}
    if artifact_type:
        scope["artifact_type"] = [artifact_type]
    if rule_namespace:
        scope["rule_namespace"] = rule_namespace
    declaration = {
        "mandate": {"scope": scope, "phase": "execution", "responsibility": "test"},
        "metadata": {"title": "test-worker"},
        "identity": {"uuid": str(uuid.uuid4()), "class": "TestWorker"},
    }
    return BlackboardPublisher(
        worker_uuid=uuid.uuid4(),
        worker_name="test-worker",
        phase="execution",
        declaration=declaration,
    )


def _mock_session() -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.begin.return_value = cm
    session.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=None)))
    return session


# ── _sanitize_payload ─────────────────────────────────────────────────────────


# ID: b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e
def test_sanitize_payload_replaces_non_ascii() -> None:
    result = _sanitize_payload({"key": "café"})
    assert result == {"key": "caf?"}


# ID: c2d3e4f5-a6b7-4c8d-9e0f-1a2b3c4d5e6f
def test_sanitize_payload_sanitizes_dict_keys() -> None:
    result = _sanitize_payload({"é": "val"})
    assert "?" in result


# ID: d3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a
def test_sanitize_payload_handles_nested() -> None:
    result = _sanitize_payload({"a": ["é", {"b": "é"}]})
    assert result["a"][0] == "?"
    assert result["a"][1]["b"] == "?"


# ID: e4f5a6b7-c8d9-4e0f-1a2b-3c4d5e6f7a8b
def test_sanitize_payload_passes_through_ascii() -> None:
    original = {"key": "clean", "num": 42}
    assert _sanitize_payload(original) == original


# ── post_observation ──────────────────────────────────────────────────────────


# ID: f5a6b7c8-d9e0-4f1a-2b3c-4d5e6f7a8b9c
def test_post_observation_rejects_open_status() -> None:
    pub = _publisher()
    with pytest.raises(ValueError, match="terminal status"):
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            pub.post_observation("subj", {}, status="open")
        )


# ID: a6b7c8d9-e0f1-4a2b-3c4d-5e6f7a8b9c0d
async def test_post_observation_accepts_abandoned() -> None:
    pub = _publisher()
    mock_session = _mock_session()
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        result = await pub.post_observation("subj", {}, status="abandoned")
    assert isinstance(result, uuid.UUID)


# ID: b7c8d9e0-f1a2-4b3c-4d5e-6f7a8b9c0d1e
async def test_post_observation_indeterminate_raises_on_duplicate() -> None:
    pub = _publisher()
    # Simulate existing indeterminate row
    mock_session = _mock_session()
    mock_session.execute.return_value = MagicMock(
        first=MagicMock(return_value=("1",))
    )
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        with pytest.raises(ValueError, match="duplicate indeterminate"):
            await pub.post_observation("subj", {}, status="indeterminate")


# ── post_artifact_finding ─────────────────────────────────────────────────────


# ID: c8d9e0f1-a2b3-4c4d-5e6f-7a8b9c0d1e2f
async def test_post_artifact_finding_raises_on_undeclared_type() -> None:
    pub = _publisher(artifact_type="source_file")
    mock_session = _mock_session()
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        with pytest.raises(ValueError, match="artifact_type"):
            await pub.post_artifact_finding("other_type", "ns", "key", {})


# ID: d9e0f1a2-b3c4-4d5e-6f7a-8b9c0d1e2f3a
async def test_post_artifact_finding_raises_on_wrong_namespace() -> None:
    pub = _publisher(artifact_type="source_file", rule_namespace="test.runner")
    mock_session = _mock_session()
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        with pytest.raises(ValueError, match="sub_namespace"):
            await pub.post_artifact_finding("source_file", "other.ns", "key", {})


# ID: e0f1a2b3-c4d5-4e6f-7a8b-9c0d1e2f3a4b
async def test_post_artifact_finding_allows_dotted_extension() -> None:
    pub = _publisher(artifact_type="source_file", rule_namespace="test.runner")
    mock_session = _mock_session()
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        result = await pub.post_artifact_finding(
            "source_file", "test.runner.missing", "src/foo.py", {}
        )
    assert isinstance(result, uuid.UUID)


# ── post_finding / post_report / post_heartbeat ───────────────────────────────


# ID: f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c
async def test_post_finding_returns_uuid() -> None:
    pub = _publisher()
    mock_session = _mock_session()
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        result = await pub.post_finding("subj", {}, resolution_mechanism="human")
    assert isinstance(result, uuid.UUID)


# ID: a2b3c4d5-e6f7-4a8b-9c0d-1e2f3a4b5c6d
async def test_post_report_returns_uuid() -> None:
    pub = _publisher()
    mock_session = _mock_session()
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        result = await pub.post_report("sync.done", {"count": 5})
    assert isinstance(result, uuid.UUID)


# ID: b3c4d5e6-f7a8-4b9c-0d1e-2f3a4b5c6d7e
async def test_post_heartbeat_returns_uuid() -> None:
    pub = _publisher()
    mock_session = _mock_session()
    with patch("shared.workers.blackboard_publisher.get_session", return_value=mock_session):
        result = await pub.post_heartbeat()
    assert isinstance(result, uuid.UUID)
