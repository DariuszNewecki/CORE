from __future__ import annotations

import pytest


# ID: 5361f47b-6ac2-41a0-8daa-1c47bb6bff35
def test_record_catalogs():
    from unittest.mock import patch

    record_contract = pytest.importorskip("mind.logic.record_contract")
    record_catalogs = record_contract.record_catalogs

    fake_catalogs = {"cat_a": {"id": "cat_a"}, "cat_b": {"id": "cat_b"}}

    with patch(
        "mind.logic.engines.registry.EngineRegistry.record_catalogs",
        return_value=fake_catalogs,
    ) as mock_record_catalogs:
        result = record_catalogs()

    mock_record_catalogs.assert_called_once_with()
    assert result == fake_catalogs
