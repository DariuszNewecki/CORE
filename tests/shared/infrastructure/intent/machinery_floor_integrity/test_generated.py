from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from shared.infrastructure.intent.machinery_floor_integrity import find_collisions


# ID: fed8cf08-7b97-4514-ab37-d72f0e50408b
def test_find_collisions(tmp_path: Path) -> None:
    intent_root = tmp_path / ".intent"
    intent_root.mkdir()

    fake_report = MagicMock()
    fake_report.modified = ["a.py", "b.py"]

    with patch(
        "shared.infrastructure.intent.machinery_floor_integrity.verify_floor",
        return_value=fake_report,
    ) as mock_verify:
        result = find_collisions(intent_root)

    assert result == ["a.py", "b.py"]
    mock_verify.assert_called_once_with(intent_root)
