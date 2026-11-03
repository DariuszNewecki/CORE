from __future__ import annotations

import json
from unittest.mock import MagicMock

from will.test_generation.artifacts import TestGenArtifactStore


# ID: 25832380-190a-40d0-8ff5-da9e4357a1cc
def test_TestGenArtifactStore_write_summary():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler=file_handler)

    session_dir = "/tmp/session"
    summary = {"total": 3, "passed": 2}

    result = store.write_summary(session_dir, summary)

    assert result == "/tmp/session/SUMMARY.json"
    file_handler.write.assert_called_once()
    called_path, called_content = file_handler.write.call_args[0]
    assert called_path == "/tmp/session/SUMMARY.json"
    assert json.loads(called_content) == summary


from unittest.mock import patch


# ID: 7384cb81-192d-42b0-a891-ae99caed8550
def test_TestGenArtifactStore_write_sandbox():
    file_handler = MagicMock()
    store = TestGenArtifactStore(file_handler)

    with patch("will.test_generation.artifacts.time") as mock_time:
        mock_time.strftime.return_value = "2024-01-01 00:00:00"

        path = store.write_sandbox(
            session_dir="/tmp/session",
            symbol="foo",
            passed=True,
            error="",
        )

    assert path == "/tmp/session/foo_sandbox.json"
    file_handler.write.assert_called_once()

    write_args = file_handler.write.call_args
    assert write_args[0][0] == "/tmp/session/foo_sandbox.json"

    payload = json.loads(write_args[0][1])
    assert payload["symbol"] == "foo"
    assert payload["passed"] is True
    assert payload["error"] == ""
    assert payload["timestamp"] == "2024-01-01 00:00:00"
