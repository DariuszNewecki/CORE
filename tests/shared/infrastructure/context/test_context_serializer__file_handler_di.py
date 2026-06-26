"""ContextSerializer — file_handler DI injection (ADR-126 Stage 1).

Pins the graceful-None path and the delegating-to-FileHandler path added
in Stage 1. Neither path existed before; these are behavioral additions.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from shared.infrastructure.context.serializers import ContextSerializer


# ID: 35e6af3f-aff6-40ff-a090-a476d7e3fabf
def test_to_yaml_skips_write_when_file_handler_is_none(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """to_yaml with file_handler=None must not write and must not raise."""
    output = str(tmp_path / "packet.yaml")
    packet = {"header": {"task_id": "t1"}, "evidence": []}

    ContextSerializer.to_yaml(packet, output, file_handler=None)

    assert not Path(output).exists(), "No file should be written when file_handler is None"


# ID: 8ffd88ca-60b7-498a-b0da-00cdc9057dc4
def test_to_yaml_delegates_to_file_handler(tmp_path: Path) -> None:
    """to_yaml with a FileHandler must call write_runtime_text with the YAML content."""
    mock_fh = MagicMock()
    packet = {"header": {"task_id": "t2"}, "evidence": []}
    output = str(tmp_path / "sub" / "packet.yaml")

    ContextSerializer.to_yaml(packet, output, file_handler=mock_fh)

    assert mock_fh.write_runtime_text.called
    positional_path = mock_fh.write_runtime_text.call_args[0][0]
    # Must be a repo-relative path, not absolute
    assert not Path(positional_path).is_absolute()
    # Content must include expected YAML key
    content_arg = mock_fh.write_runtime_text.call_args[0][1]
    assert "task_id" in content_arg


# ID: 2ada137a-f900-44d9-a5d9-18d3880c92eb
def test_to_yaml_default_omits_file_handler() -> None:
    """to_yaml default call (no file_handler arg) must not raise."""
    ContextSerializer.to_yaml({"evidence": []}, "some/path.yaml")
