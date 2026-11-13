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


from unittest.mock import AsyncMock, MagicMock

import mind.logic.record_contract as record_contract
from mind.logic.record_contract import evaluate


# ID: c26a0303-ba4f-45ff-b177-766803726683
async def test_evaluate():
    record = {"engine": "test-engine", "scope": "unit"}

    fake_verdict = MagicMock()
    fake_lookup = MagicMock(
        return_value=MagicMock(evaluate_record=AsyncMock(return_value=fake_verdict))
    )

    rule = MagicMock()
    rule.rule_id = "rule-1"

    with (
        patch.object(record_contract, "_rule_part", new=AsyncMock()) as mock_rule_part,
        patch.object(record_contract, "_carried", return_value=[]) as mock_carried,
        patch.object(record_contract, "record_scope", return_value="unit"),
        patch.object(record_contract, "_settle", side_effect=lambda p, m, s: p),
        patch.object(
            record_contract, "aggregate", return_value=("pass", MagicMock())
        ) as mock_aggregate,
        patch.object(record_contract, "record_sha256", return_value="deadbeef"),
        patch.object(record_contract, "RecordVerdict") as mock_verdict_cls,
    ):
        part = MagicMock()
        mock_rule_part.return_value = part
        mock_verdict_cls.return_value = MagicMock(outcome="pass", parts=(part,))

        result = await evaluate(record, [rule], engine_lookup=fake_lookup)

    mock_rule_part.assert_awaited_once()
    mock_carried.assert_called_once_with(record)
    mock_aggregate.assert_called_once()
    assert result.outcome == "pass"


from mind.logic.record_contract import record_items


# ID: 535611be-023a-4546-b041-211c5975eaa5
def test_record_items():
    record = {
        "items": {
            "b": {"type": "defect", "value": 2},
            "a": {"type": "requirement", "value": 1},
            "c": {"type": "defect", "value": 3},
            "d": "not-a-mapping",
        }
    }

    result = record_items(record)

    assert result == [
        ("a", {"type": "requirement", "value": 1}),
        ("b", {"type": "defect", "value": 2}),
        ("c", {"type": "defect", "value": 3}),
    ]

    filtered = record_items(record, item_types=["defect"])
    assert filtered == [
        ("b", {"type": "defect", "value": 2}),
        ("c", {"type": "defect", "value": 3}),
    ]

    assert record_items({"items": None}) == []
    assert record_items({}) == []


from mind.logic.record_contract import engine_part


# ID: 0d00f645-d705-482f-b84b-85b9402f02a1
def test_engine_part():
    engine = MagicMock()
    engine.engine_id = "engine-42"
    type(engine).evidence_class = "test-evidence"

    finding_one = MagicMock()
    finding_two = MagicMock()

    result = engine_part(engine, "rule-1", [finding_one, finding_two])

    assert result.rule_id == "rule-1"
    assert result.engine_id == "engine-42"
    assert result.evidence_class == "test-evidence"
    assert result.findings == (finding_one, finding_two)
    assert result.result is not None


from mind.logic.record_contract import aggregate


# ID: 4bb15e5c-6532-439c-8de1-d103c7a18cac
def test_aggregate():
    class _Part:
        def __init__(self, result, evidence_class):
            self.result = result
            self.evidence_class = evidence_class

    from mind.logic.record_contract import EvidenceClass

    parts = [
        _Part("pass", EvidenceClass.ATTESTED),
        _Part("pass", EvidenceClass.PROVEN),
    ]

    result, evidence_class = aggregate(parts)

    assert result == "pass"
    assert evidence_class == EvidenceClass.ATTESTED


from mind.logic.record_contract import in_scope


# ID: 36ecd3bb-532e-452e-a754-b322c4d6a0ad
def test_in_scope():
    finding = MagicMock()
    finding.item = "alpha"

    # No scope -> always in scope
    assert in_scope(finding, None) is True

    # Scope contains the item -> counts
    assert in_scope(finding, frozenset({"alpha", "beta"})) is True

    # Scope excludes the item -> does not count
    assert in_scope(finding, frozenset({"beta", "gamma"})) is False

    # Record-wide finding (no item) -> always counts regardless of scope
    finding.item = None
    assert in_scope(finding, frozenset({"beta"})) is True


from mind.logic.record_contract import record_scope


# ID: 09efd7f5-2519-4cb2-9759-d144bbae53dc
def test_record_scope():
    # No scope key present -> judge everything
    assert record_scope({}) is None

    # Explicit None scope -> judge everything
    assert record_scope({"scope": None}) is None

    # Scope present as a list -> frozenset of str ids
    result = record_scope({"scope": ["a", "b", "b"]})
    assert isinstance(result, frozenset)
    assert result == frozenset({"a", "b"})

    # Scope with mixed int/str items -> coerced to str
    coerced = record_scope({"scope": [1, 2, "x"]})
    assert coerced == frozenset({"1", "2", "x"})


# ID: 495daec2-f30d-4cc5-b625-85ffc3190478
def test_part_result():
    from unittest.mock import MagicMock

    from mind.logic.record_contract import part_result

    blocking = MagicMock()
    blocking.blocking = True
    non_blocking = MagicMock()
    non_blocking.blocking = False

    assert part_result([]) == "pass"
    assert part_result([non_blocking]) == "undecided"
    assert part_result([non_blocking, non_blocking]) == "undecided"
    assert part_result([blocking]) == "fail"
    assert part_result([non_blocking, blocking]) == "fail"


from mind.logic.record_contract import RecordRule


# ID: 2c331824-c3a1-443c-bc52-67592796a7b2
def test_RecordRule():
    rule = RecordRule(rule_id="req-001", engine="some_engine")

    assert rule.rule_id == "req-001"
    assert rule.engine == "some_engine"
    assert rule.params == {}
    assert rule.blocking is True

    rule_with_params = RecordRule(
        rule_id="req-002",
        engine="other_engine",
        params={"threshold": 5},
        blocking=False,
    )

    assert rule_with_params.params == {"threshold": 5}
    assert rule_with_params.blocking is False


# ID: 705df778-1f92-4770-81e1-c8c8a61b6399
def test_RecordVerdict_rule_ids():
    from mind.logic.record_contract import RecordVerdict

    part_a = MagicMock()
    part_a.rule_id = "RULE_A"
    part_b = MagicMock()
    part_b.rule_id = "RULE_B"
    part_c = MagicMock()
    part_c.rule_id = "RULE_C"

    verdict = MagicMock(spec=RecordVerdict)
    verdict.parts = (part_a, part_b, part_c)

    result = RecordVerdict.rule_ids.fget(verdict)

    assert result == ("RULE_A", "RULE_B", "RULE_C")
    assert isinstance(result, tuple)


from mind.logic.record_contract import RecordVerdict


# ID: 75026a87-8dea-4212-bbe2-113c5bf514ad
def test_RecordVerdict() -> None:
    part_a = MagicMock()
    part_a.rule_id = "rule-alpha"
    part_b = MagicMock()
    part_b.rule_id = "rule-beta"

    verdict = RecordVerdict(
        outcome="pass",
        evidence_class=MagicMock(),
        record_sha256="a" * 64,
        parts=(part_a, part_b),
    )

    assert verdict.outcome == "pass"
    assert verdict.record_sha256 == "a" * 64
    assert verdict.parts == (part_a, part_b)
    assert verdict.rule_ids == ("rule-alpha", "rule-beta")


from mind.logic.record_contract import RulePart


# ID: 4482d57a-4900-4d10-859b-73e86c55867f
def test_RulePart() -> None:
    part = RulePart(
        rule_id="rule-001",
        engine_id="engine-alpha",
        evidence_class="static",
        result="pass",
    )

    assert part.rule_id == "rule-001"
    assert part.engine_id == "engine-alpha"
    assert part.evidence_class == "static"
    assert part.result == "pass"
    assert part.findings == ()
