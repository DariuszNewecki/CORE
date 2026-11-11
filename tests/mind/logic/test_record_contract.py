"""The record contract (ADR-173, #1328): one test per decision built here.

Records are made up. Engines are the real attestation_gate, regex_gate and
schema_gate, looked up through an injected table (the registry needs a path
resolver); a few stand-in engines cover the cases the real ones cannot.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
from typing import Any, ClassVar

import pytest

from mind.logic.engines.attestation_gate import AttestationGateEngine
from mind.logic.engines.base import BaseEngine, EngineResult
from mind.logic.engines.regex_gate import RegexGateEngine
from mind.logic.engines.schema_gate import SchemaGateEngine
from mind.logic.record_contract import (
    CARRIED_ENGINE_ID,
    RecordFinding,
    RecordRule,
    RecordVerdict,
    RulePart,
    aggregate,
    canonical_json,
    engine_part,
    evaluate,
    part_result,
    record_sha256,
)
from shared.models import EvidenceClass


# --------------------------------------------------------------------------
# Made-up records and engines
# --------------------------------------------------------------------------


def _record(scope: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    items = {
        "D-1": {
            "id": "D-1",
            "type": "document",
            "version": "2",
            "status": "approved",
            "owner": "QA",
            "value": "Approved procedure text.",
            "sha256": "aa",
            "effective": "2026-11-01",
            "withdrawn": None,
            "refs": [{"rel": "contains", "to": "M-4", "occurrence": 1, "pin": "3"}],
        },
        "M-4": {
            "id": "M-4",
            "type": "model",
            "version": "3",
            "status": "approved",
            "owner": "QA",
            "value": "Model text, TBD section.",
            "sha256": "bb",
            "effective": "2026-10-01",
            "withdrawn": None,
            "refs": [],
        },
    }
    record = {
        "format": "library-snapshot/1",
        "items": items,
        "known": sorted(items),
        "scope": scope,
        "load_findings": [],
        "pre_findings": [],
    }
    record.update(extra)
    return record


class _Judged(BaseEngine):
    """A stand-in JUDGED record engine: passes, or fails when told to."""

    engine_id = "judged_stub"
    evidence_class = EvidenceClass.JUDGED
    supports_records: ClassVar[bool] = True

    async def verify(self, file_path, params):  # pragma: no cover - unused
        return EngineResult(True, "", [], self.engine_id)

    async def evaluate_record(self, record, rule, params):
        findings = (
            [RecordFinding(rule=rule, message="judged gap", blocking=True, item="D-1")]
            if params.get("fail")
            else []
        )
        return engine_part(self, rule, findings)


class _FileOnly(BaseEngine):
    engine_id = "file_only"
    evidence_class = EvidenceClass.PROVEN

    async def verify(self, file_path, params):  # pragma: no cover - unused
        return EngineResult(True, "", [], self.engine_id)


class _Crashing(_Judged):
    engine_id = "crashing"
    evidence_class = EvidenceClass.PROVEN

    async def evaluate_record(self, record, rule, params):
        raise RuntimeError("boom")


class _RefReader(_Judged):
    """Reads an out-of-scope item: flags an in-scope item whose reference
    target has status other than approved."""

    engine_id = "ref_reader"
    evidence_class = EvidenceClass.PROVEN

    async def evaluate_record(self, record, rule, params):
        items = record["items"]
        findings = [
            RecordFinding(
                rule=rule,
                message=f"{item_id} refers to {ref['to']} ({items[ref['to']]['status']})",
                blocking=True,
                item=item_id,
            )
            for item_id, item in items.items()
            for ref in item["refs"]
            if items[ref["to"]]["status"] != params["status"]
        ]
        return engine_part(self, rule, findings)


ENGINES = {
    "attestation_gate": AttestationGateEngine(),
    "regex_gate": RegexGateEngine(),
    "schema_gate": SchemaGateEngine(),
    "judged_stub": _Judged(),
    "file_only": _FileOnly(),
    "crashing": _Crashing(),
    "ref_reader": _RefReader(),
}


def _lookup(engine_id: str) -> Any:
    if engine_id not in ENGINES:
        raise ValueError(f"Unsupported Governance Engine: {engine_id}")
    return ENGINES[engine_id]


async def _evaluate(record, rules) -> RecordVerdict:
    return await evaluate(record, rules, engine_lookup=_lookup)


TBD = RecordRule("no_tbd", "regex_gate", {"forbidden_patterns": [r"\bTBD\b"]})
ATTEST = RecordRule(
    "signed", "attestation_gate", {"prompt": "QA has signed the document"}
)
STATUS_SCHEMA = RecordRule(
    "status_known",
    "schema_gate",
    {"field": "status", "schema": {"enum": ["approved", "draft"]}},
)


# --------------------------------------------------------------------------
# D1 — the contract is on BaseEngine
# --------------------------------------------------------------------------


async def test_d1_base_engine_does_not_judge_records_by_default() -> None:
    assert BaseEngine.supports_records is False
    with pytest.raises(NotImplementedError):
        await _FileOnly().evaluate_record(_record(), "r", {})


async def test_d1_engine_without_flag_gives_engine_missing() -> None:
    verdict = await _evaluate(_record(), [RecordRule("r", "file_only")])
    (part,) = verdict.parts
    assert (part.result, part.evidence_class) == ("fail", EvidenceClass.ATTESTED)
    assert "engine_missing" in part.findings[0].message
    assert verdict.outcome == "fail"


async def test_d1_unknown_engine_gives_engine_missing() -> None:
    verdict = await _evaluate(_record(), [RecordRule("r", "no_such_engine")])
    (part,) = verdict.parts
    assert part.result == "fail"
    assert "engine_missing" in part.findings[0].message


async def test_d1_engine_crash_fails_never_passes() -> None:
    verdict = await _evaluate(_record(), [RecordRule("r", "crashing")])
    (part,) = verdict.parts
    assert (part.result, part.evidence_class) == ("fail", EvidenceClass.ATTESTED)
    assert "enforcement_failure" in part.findings[0].message


async def test_d1_evidence_class_comes_from_the_engine_not_the_part() -> None:
    class _Bragging(_Judged):
        engine_id = "bragging"
        evidence_class = EvidenceClass.JUDGED

        async def evaluate_record(self, record, rule, params):
            return RulePart(rule, self.engine_id, EvidenceClass.PROVEN, "pass", ())

    verdict = await evaluate(
        _record(), [RecordRule("r", "bragging")], engine_lookup=lambda _: _Bragging()
    )
    assert verdict.parts[0].evidence_class is EvidenceClass.JUDGED


# --------------------------------------------------------------------------
# D5 — one part per rule (prototype finding 4)
# --------------------------------------------------------------------------


async def test_d5_finding_4_each_rule_keeps_its_own_part_engine_and_findings() -> None:
    record = _record()
    record["items"]["M-4"]["status"] = "retired"
    verdict = await _evaluate(record, [TBD, STATUS_SCHEMA])

    assert verdict.rule_ids == ("no_tbd", "status_known")
    by_rule = {part.rule_id: part for part in verdict.parts}
    assert by_rule["no_tbd"].engine_id == "regex_gate"
    assert by_rule["status_known"].engine_id == "schema_gate"
    for part in verdict.parts:
        assert part.findings, part.rule_id
        assert all(f.rule == part.rule_id for f in part.findings)
    assert "engine_id" not in {f.name for f in dataclasses.fields(RecordVerdict)}


# --------------------------------------------------------------------------
# D6 — evaluate is async (prototype finding 5)
# --------------------------------------------------------------------------


def test_d6_finding_5_evaluate_and_evaluate_record_are_async() -> None:
    assert inspect.iscoroutinefunction(evaluate)
    for engine in (
        AttestationGateEngine,
        RegexGateEngine,
        SchemaGateEngine,
        BaseEngine,
    ):
        assert inspect.iscoroutinefunction(engine.evaluate_record), engine


# --------------------------------------------------------------------------
# D2 — aggregation (prototype finding 2)
# --------------------------------------------------------------------------


async def test_d2_finding_2_proven_fail_with_pending_attestation_is_proven() -> None:
    verdict = await _evaluate(_record(), [TBD, ATTEST])
    assert verdict.outcome == "fail"
    assert verdict.evidence_class is EvidenceClass.PROVEN


async def test_d2_fail_takes_strongest_class_among_failing_parts_only() -> None:
    judged_fail = RecordRule("judged", "judged_stub", {"fail": True})
    verdict = await _evaluate(_record(), [judged_fail, TBD])
    assert (verdict.outcome, verdict.evidence_class) == ("fail", EvidenceClass.PROVEN)

    clean = _record()
    clean["items"]["M-4"]["value"] = "Model text."
    verdict = await _evaluate(clean, [judged_fail, TBD])  # TBD passes now
    assert (verdict.outcome, verdict.evidence_class) == ("fail", EvidenceClass.JUDGED)


async def test_d2_pass_takes_weakest_class() -> None:
    clean = _record()
    clean["items"]["M-4"]["value"] = "Model text."
    verdict = await _evaluate(clean, [TBD, RecordRule("judged", "judged_stub")])
    assert (verdict.outcome, verdict.evidence_class) == ("pass", EvidenceClass.JUDGED)


async def test_d2_undecided_outranks_pass_and_fail_outranks_undecided() -> None:
    clean = _record()
    clean["items"]["M-4"]["value"] = "Model text."
    verdict = await _evaluate(clean, [TBD, ATTEST])
    assert (verdict.outcome, verdict.evidence_class) == (
        "undecided",
        EvidenceClass.ATTESTED,
    )

    verdict = await _evaluate(_record(), [ATTEST, TBD])
    assert verdict.outcome == "fail"


# --------------------------------------------------------------------------
# D4 — record_sha256 over JCS (prototype finding 3)
# --------------------------------------------------------------------------


async def test_d4_finding_3_verdict_names_the_record_it_judged() -> None:
    record = _record(scope=["D-1"])
    verdict = await _evaluate(record, [TBD])
    expected = hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()
    assert verdict.record_sha256 == expected

    reordered = dict(reversed(list(record.items())))
    assert record_sha256(reordered) == expected  # key order does not matter
    assert record_sha256(_record(scope=["M-4"])) != expected  # scope does
    assert record_sha256(_record(scope=None)) != expected


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (1e30, "1e+30"),
        (4.50, "4.5"),
        (2e-3, "0.002"),
        (0.000001, "0.000001"),
        (1e-7, "1e-7"),
        (333333333.33333329, "333333333.3333333"),
        (-0.0, "0"),
        (1e21, "1e+21"),
        (1e20, "100000000000000000000"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (123.0, "123"),
        (-12.5, "-12.5"),
        (42, "42"),
    ],
)
def test_d4_jcs_numbers_match_rfc_8785(value: float, text: str) -> None:
    assert canonical_json(value) == text


def test_d4_jcs_sorts_keys_by_utf16_and_escapes_like_rfc_8785() -> None:
    # RFC 8785 section 3.2.3 sorting example.
    value = {
        "€": "Euro Sign",
        "\r": "Carriage Return",
        "דּ": "Hebrew Letter Dalet With Dagesh",
        "1": "One",
        "\U0001f600": "Emoji: Grinning Face",
        "\u0080": "Control",
        "ö": "Latin Small Letter O With Diaeresis",
    }
    keys = [k for k in value]
    text = canonical_json(value)
    order = sorted(keys, key=lambda k: text.index(canonical_json(k) + ":"))
    assert order == ["\r", "1", "\u0080", "ö", "€", "\U0001f600", "דּ"]
    assert (
        canonical_json({"a": [True, None, "x\n\u0001"]})
        == '{"a":[true,null,"x\\n\\u0001"]}'
    )
    with pytest.raises(ValueError):
        canonical_json(float("nan"))


# --------------------------------------------------------------------------
# D7, D13 — scope and per-rule result
# --------------------------------------------------------------------------


def test_d13_part_result() -> None:
    blocking = RecordFinding("r", "m", blocking=True)
    advisory = RecordFinding("r", "m", blocking=False)
    assert part_result([advisory, blocking]) == "fail"
    assert part_result([advisory]) == "undecided"
    assert part_result([]) == "pass"


async def test_d7_d13_scope_counts_only_findings_on_scoped_items() -> None:
    record = _record(scope=["D-1"])
    record["items"]["D-1"]["value"] = "Procedure, TBD."
    verdict = await _evaluate(record, [TBD])
    (part,) = verdict.parts
    assert [f.item for f in part.findings] == ["D-1"]  # M-4 also has TBD, out of scope

    record["items"]["D-1"]["value"] = "Procedure."
    verdict = await _evaluate(record, [TBD])
    assert verdict.outcome == "pass"  # only the out-of-scope item is broken


async def test_d7_out_of_scope_items_are_still_readable() -> None:
    record = _record(scope=["D-1"])
    record["items"]["M-4"]["status"] = "draft"
    verdict = await _evaluate(
        record, [RecordRule("refs", "ref_reader", {"status": "approved"})]
    )
    assert verdict.outcome == "fail"
    assert verdict.parts[0].findings[0].message == "D-1 refers to M-4 (draft)"


async def test_d13_non_blocking_rule_never_fails() -> None:
    advisory_tbd = dataclasses.replace(TBD, blocking=False)
    verdict = await _evaluate(_record(), [advisory_tbd])
    assert verdict.parts[0].result == "undecided"


# --------------------------------------------------------------------------
# D8 — empty rule set
# --------------------------------------------------------------------------


async def test_d8_empty_rule_set_is_undecided_attested() -> None:
    verdict = await _evaluate(_record(), [])
    assert (verdict.outcome, verdict.evidence_class) == (
        "undecided",
        EvidenceClass.ATTESTED,
    )
    assert aggregate([], has_rules=False) == ("undecided", EvidenceClass.ATTESTED)


# --------------------------------------------------------------------------
# D12 — carried caller findings
# --------------------------------------------------------------------------


async def test_d12_carried_finding_counts_under_its_rule_as_attested() -> None:
    clean = _record()
    clean["items"]["M-4"]["value"] = "Model text."
    clean["pre_findings"] = [
        {"item": "M-4", "rule": "no_tbd", "message": "caller saw TBD", "blocking": True}
    ]
    verdict = await _evaluate(clean, [TBD])
    (part,) = verdict.parts
    assert (part.result, part.evidence_class) == ("fail", EvidenceClass.ATTESTED)
    assert part.findings[0].carried is True


async def test_d12_carried_finding_for_unknown_rule_gets_its_own_part() -> None:
    clean = _record()
    clean["items"]["M-4"]["value"] = "Model text."
    clean["load_findings"] = [
        {
            "item": "M-4",
            "rule": "resolution",
            "message": "pin 3 not found",
            "blocking": True,
        }
    ]
    clean["pre_findings"] = [
        {"item": "D-1", "message": "no rule named", "blocking": False}
    ]
    verdict = await _evaluate(clean, [TBD])

    by_rule = {part.rule_id: part for part in verdict.parts}
    assert set(by_rule) == {"no_tbd", "resolution", "pre"}
    resolution = by_rule["resolution"]
    assert resolution.engine_id == CARRIED_ENGINE_ID
    assert (resolution.result, resolution.evidence_class) == (
        "fail",
        EvidenceClass.ATTESTED,
    )
    assert by_rule["pre"].result == "undecided"
    assert (verdict.outcome, verdict.evidence_class) == ("fail", EvidenceClass.ATTESTED)


# --------------------------------------------------------------------------
# D3, D10 — the first engines
# --------------------------------------------------------------------------


async def test_d3_attestation_never_passes_even_when_the_record_claims_it() -> None:
    record = _record(attested=True, signatures=[{"by": "QA", "item": "D-1"}])
    verdict = await _evaluate(record, [ATTEST])
    (part,) = verdict.parts
    assert (part.result, part.evidence_class) == ("undecided", EvidenceClass.ATTESTED)
    assert "QA has signed the document" in part.findings[0].message


async def test_d3_attestation_without_prompt_fails() -> None:
    verdict = await _evaluate(_record(), [RecordRule("signed", "attestation_gate", {})])
    assert verdict.parts[0].result == "fail"


async def test_d10_regex_gate_checks_a_string_field_of_typed_items() -> None:
    only_documents = RecordRule(
        "no_tbd_docs",
        "regex_gate",
        {"forbidden_patterns": [r"\bTBD\b"], "item_types": ["document"]},
    )
    verdict = await _evaluate(_record(), [only_documents])
    assert verdict.outcome == "pass"  # TBD is only in the model

    verdict = await _evaluate(_record(), [TBD])
    (part,) = verdict.parts
    assert (part.result, part.evidence_class) == ("fail", EvidenceClass.PROVEN)
    assert part.findings[0].item == "M-4"


async def test_d10_schema_gate_validates_a_field() -> None:
    verdict = await _evaluate(_record(), [STATUS_SCHEMA])
    assert (verdict.outcome, verdict.evidence_class) == ("pass", EvidenceClass.PROVEN)

    record = _record()
    record["items"]["D-1"]["status"] = "retired"
    verdict = await _evaluate(record, [STATUS_SCHEMA])
    (part,) = verdict.parts
    assert part.result == "fail"
    assert part.findings[0].item == "D-1"


async def test_d10_schema_gate_without_valid_schema_fails() -> None:
    for params in ({}, {"schema": {"type": 12}}):
        verdict = await _evaluate(_record(), [RecordRule("s", "schema_gate", params)])
        assert verdict.parts[0].result == "fail", params


async def test_d10_schema_gate_reports_files_as_not_evaluated(tmp_path) -> None:
    from mind.logic.engines.base import CONTENT_NOT_EVALUATED

    path = tmp_path / "x.json"
    path.write_text("{}", encoding="utf-8")
    result = await SchemaGateEngine().verify(path, {"schema": {}})
    assert CONTENT_NOT_EVALUATED in result.extra
