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


import importlib


# ID: eb3f8d14-7289-492f-b762-63e1752c7637
def test_canonical_json() -> None:
    # Resolve the module robustly regardless of package layout.
    try:
        module = importlib.import_module("mind.logic.record_contract")
    except ModuleNotFoundError:
        module = importlib.import_module("src.mind.logic.record_contract")
    canonical_json = getattr(module, "canonical_json")

    # Scalars
    assert canonical_json(None) == "null"
    assert canonical_json(True) == "true"
    assert canonical_json(False) == "false"
    assert canonical_json(42) == "42"
    assert canonical_json("hi") == '"hi"'

    # Arrays preserve order
    assert canonical_json([1, 2, 3]) == "[1,2,3]"
    assert canonical_json([1, "a", True, None]) == '[1,"a",true,null]'

    # Object keys are sorted, no whitespace
    assert canonical_json({"b": 1, "a": 2, "c": 3}) == '{"a":2,"b":1,"c":3}'
    assert (
        canonical_json({"z": [1, 2], "a": {"y": True, "x": None}})
        == '{"a":{"x":null,"y":true},"z":[1,2]}'
    )

    # Nested/order independence: equal objects give identical text
    left = {"one": 1, "two": [2, {"three": 3}]}
    right = {"two": [2, {"three": 3}], "one": 1}
    assert canonical_json(left) == canonical_json(right)

    # Happy path guard for tuple handling and unsupported type rejection
    assert canonical_json((1, 2)) == "[1,2]"
    with pytest.raises(TypeError):
        canonical_json({"bad": object()})


import hashlib
from unittest.mock import patch


# ID: 7e12b131-1a5b-4482-bbc4-984362b7e960
def test_record_sha256():
    from mind.logic.record_contract import record_sha256

    record = {"scope": "example", "value": 42}
    canonical = '{"scope":"example","value":42}'
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    with patch(
        "mind.logic.record_contract.canonical_json",
        return_value=canonical,
    ) as mock_canonical:
        result = record_sha256(record)

    mock_canonical.assert_called_once_with(record)
    assert result == expected
    assert isinstance(result, str)
    assert len(result) == 64
