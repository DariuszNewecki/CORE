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
