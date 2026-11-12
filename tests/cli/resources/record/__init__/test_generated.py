from __future__ import annotations

from unittest.mock import MagicMock, patch


# ID: b02f7903-0a9d-4b1c-ade0-f11a1646ebe9
def test_record() -> None:
    record_module = MagicMock()
    record_module.record = MagicMock(return_value=None)

    with patch.dict("sys.modules", {"cli.resources.record.__init__": record_module}):
        import importlib

        imported_module = importlib.import_module("cli.resources.record.__init__")
        record = imported_module.record

        result = record()

        assert result is None
        assert callable(record)
        record.assert_called_once()
