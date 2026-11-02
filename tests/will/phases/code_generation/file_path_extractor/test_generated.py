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





# ID: 32d1d43a-82ca-4df9-819a-437e18e42f1a
def test_FilePathExtractor():
    # Happy path: explicit attribute-based file_path on params
    task = MagicMock()
    task.params.file_path = "src/foo/bar.py"

    result = FilePathExtractor.extract(task, 1)
    assert result == "src/foo/bar.py"

    # Happy path: dict-based params with file_path key
    dict_task = MagicMock()
    dict_task.params = {"file_path": "src/baz/qux.py"}

    result_dict = FilePathExtractor.extract(dict_task, 2)
    assert result_dict == "src/baz/qux.py"
