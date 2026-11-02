from __future__ import annotations

from unittest.mock import MagicMock

from will.phases.code_generation.file_path_extractor import FilePathExtractor


# ID: 046665fc-b04f-409d-921f-f96c5d048efe
def test_FilePathExtractor_extract() -> None:
    task = MagicMock()
    task.params = MagicMock()
    task.params.file_path = "src/will/example.py"

    result = FilePathExtractor.extract(task, step_index=1)

    assert result == "src/will/example.py"
