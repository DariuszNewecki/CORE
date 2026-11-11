"""The publication engine and its catalog (#1328 steps 4 and 5, ADR-173 D14-D16).

All data is made up for these tests. Each rule has a pass and a fail case,
called directly with in-memory params; the workshop pair runs through the
catalog file, so it also proves the catalog path.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from body.services.grc.record_catalog import (
    load_record_catalog,
    record_catalog_warnings,
)
from mind.logic.engines.publication_gate import PublicationGateEngine, catalog_path
from mind.logic.engines.publication_gate import rules as R
from mind.logic.record_contract import RecordRule, evaluate
from shared.models import EvidenceClass


ENGINE = PublicationGateEngine()


def _lookup(engine_id: str) -> Any:
    if engine_id != "publication_gate":
        raise ValueError(engine_id)
    return ENGINE


def _item(type_: str, refs: list[dict] | None = None, **value: Any) -> dict[str, Any]:
    return {
        "type": type_,
        "version": "1",
        "status": "approved",
        "owner": "ROLE-1",
        "value": value,
        "sha256": "00",
        "effective": "2027-01-04",
        "withdrawn": None,
        "refs": refs or [],
    }


def _record(items: dict[str, dict], known: list[str] | None = None) -> dict[str, Any]:
    items = {"ROLE-1": _item("role", name="Keeper"), **items}
    for item_id, item in items.items():
        item["id"] = item_id
    return {
        "format": "library-snapshot/1",
        "items": items,
        "known": sorted(set(items) | set(known or [])),
        "scope": None,
        "load_findings": [],
        "pre_findings": [],
    }


def _ref(rel: str, to: str, occurrence: Any = None) -> dict[str, Any]:
    return {"rel": rel, "to": to, "occurrence": occurrence, "pin": None}


def _run(rule: str, record: dict, params: dict | None = None) -> list[str]:
    return [f.message for f in R.RULES[rule](record, rule, params or {})]


def _catalog_params(check: str) -> dict[str, Any]:
    (rule,) = [
        r for r in load_record_catalog(catalog_path()) if r.params.get("check") == check
    ]
    return dict(rule.params)


COMPOSITION = _catalog_params("composition")
KINDS = COMPOSITION["kinds"]


# --------------------------------------------------------------------------
# 1. reference
# --------------------------------------------------------------------------


def test_reference_pass_and_both_kinds_of_missing() -> None:
    ok = _record({"T-1": _item("definition", [_ref("uses", "ROLE-1")])})
    assert _run("reference", ok) == []

    bad = _record(
        {"T-1": _item("definition", [_ref("uses", "T-9"), _ref("uses", "T-8")])},
        known=["T-9"],
    )
    assert _run("reference", bad) == [
        "T-1: uses ref to T-9: id exists but has no usable version on that date",
        "T-1: uses ref to T-8: no such id",
    ]


# --------------------------------------------------------------------------
# 2. role
# --------------------------------------------------------------------------


def test_role_pass_and_fail() -> None:
    ok = _record({"T-1": _item("definition", [_ref("editor", "ROLE-1")])})
    assert _run("role", ok) == []

    bad = _record(
        {
            "T-1": _item("definition", [_ref("editor", "T-2")]),
            "T-2": _item("definition"),
        }
    )
    bad["items"]["T-2"]["owner"] = "T-1"
    assert _run("role", bad) == [
        "T-1: editor ref to T-2 is a definition, not a role",
        "T-2: owner T-1 is a definition, not a role",
    ]


def test_role_skips_a_missing_target() -> None:
    record = _record({"T-1": _item("definition", [_ref("holder", "ROLE-9")])})
    assert _run("role", record) == []


# --------------------------------------------------------------------------
# 3. composition
# --------------------------------------------------------------------------


def _composition(items: dict) -> list[str]:
    return _run("composition", _record(items), COMPOSITION)


def _doc_types() -> dict[str, dict]:
    return {
        "DT-1": _item("document_type", rank=1),
        "DT-2": _item("document_type", rank=2),
    }


def test_composition_pass() -> None:
    assert (
        _composition(
            {
                **_doc_types(),
                "DOC-1": _item("document", [_ref("contains", "P-1")]),
                "P-1": _item(
                    "policy",
                    [
                        _ref("document_type", "DT-1"),
                        _ref("contains", "S-1"),
                        _ref("contains", "DEF-1"),
                        _ref("contains", "DR-1"),
                        _ref("contains", "RC-1"),
                    ],
                ),
                "S-1": _item("standard", [_ref("document_type", "DT-2")]),
                "DEF-1": _item("definition"),
                "DR-1": _item("decision_right"),
                "RC-1": _item("role_catalogue", [_ref("contains", "ROLE-1")]),
            }
        )
        == []
    )


def test_composition_model_needs_exactly_one_document_type() -> None:
    assert _composition({"P-1": _item("policy")}) == [
        "P-1: a model needs exactly one document_type ref, has 0"
    ]
    assert _composition(
        {
            "P-1": _item("policy", [_ref("document_type", "D-1")]),
            "D-1": _item("definition"),
        }
    ) == ["P-1: document_type ref to D-1 is a definition, not a document_type"]


def test_composition_catalogue_needs_no_document_type_and_holds_only_its_family() -> (
    None
):
    assert _composition({"KS-1": _item("kpi_set")}) == []
    found = _composition(
        {
            "KS-1": _item(
                "kpi_set", [_ref("contains", "K-1"), _ref("contains", "C-1")]
            ),
            "K-1": _item("kpi"),
            "C-1": _item("control"),
        }
    )
    assert found == ["KS-1: contains C-1: control is not in the kpi_set family ['kpi']"]


def test_composition_containment_breaks() -> None:
    found = _composition(
        {
            **_doc_types(),
            "DOC-1": _item("document"),
            "DOC-2": _item("document", [_ref("contains", "DOC-1")]),
            "PR-1": _item(
                "process",
                [_ref("document_type", "DT-1"), _ref("contains", "DR-1")],
            ),
            "DR-1": _item("decision_right"),
            "DEF-1": _item("definition", [_ref("contains", "S-1")]),
            "S-1": _item("standard", [_ref("document_type", "DT-2")]),
        }
    )
    assert found == [
        "DEF-1: contains S-1: a atom may not hold a model",
        "DOC-2: contains DOC-1: a document is never contained",
        "PR-1: contains DR-1: a process holds only ['decision', 'step'], not decision_right",
    ]


def test_composition_rank_comes_from_the_document_type_not_the_model() -> None:
    # Own value.rank says the child is below the parent (9 > 1); the document
    # types say it is above (1 < 2). The document types decide.
    misleading = {
        **_doc_types(),
        "P-1": _item(
            "policy", [_ref("document_type", "DT-2"), _ref("contains", "S-1")], rank=1
        ),
        "S-1": _item("standard", [_ref("document_type", "DT-1")], rank=9),
    }
    assert _composition(misleading) == [
        "P-1: contains S-1: a model holds a model only of a greater rank number (1 <= 2)"
    ]
    # And the other way round: own ranks say no (1 <= 9), document types say yes.
    flipped = {
        **_doc_types(),
        "P-1": _item(
            "policy", [_ref("document_type", "DT-1"), _ref("contains", "S-1")], rank=9
        ),
        "S-1": _item("standard", [_ref("document_type", "DT-2")], rank=1),
    }
    assert _composition(flipped) == []


def test_composition_equal_rank_and_rankless_document_type() -> None:
    same = {
        **_doc_types(),
        "P-1": _item(
            "policy", [_ref("document_type", "DT-1"), _ref("contains", "S-1")]
        ),
        "S-1": _item("standard", [_ref("document_type", "DT-1")]),
    }
    assert _composition(same) == [
        "P-1: contains S-1: a model holds a model only of a greater rank number (1 <= 1)"
    ]
    rankless = {
        "DT-1": _item("document_type", rank=1),
        "DT-3": _item("document_type"),
        "P-1": _item(
            "policy", [_ref("document_type", "DT-1"), _ref("contains", "S-1")]
        ),
        "S-1": _item("standard", [_ref("document_type", "DT-3")]),
    }
    assert _composition(rankless) == [
        "P-1: contains S-1: document_type DT-3 has no numeric value.rank"
    ]


async def test_composition_unknown_type_is_one_blocking_finding() -> None:
    record = _record(
        {
            "X-1": _item("folder", [_ref("contains", "DEF-1")]),
            "DEF-1": _item("definition"),
            "S-1": _item("standard", [_ref("contains", "X-1")]),
        }
    )
    record["items"]["S-1"]["refs"].append(_ref("document_type", "DT-1"))
    record["items"]["DT-1"] = {**_item("document_type", rank=1), "id": "DT-1"}
    found = _run("composition", record, COMPOSITION)
    assert found == ["X-1: type folder has no kind"]
    verdict = await evaluate(
        record,
        [RecordRule("c", "publication_gate", COMPOSITION)],
        engine_lookup=_lookup,
    )
    assert verdict.parts[0].result == "fail"


# --------------------------------------------------------------------------
# 4. trace
# --------------------------------------------------------------------------


TRACE = {"implements": {"requirement": "commitment", "control": "requirement"}}


def test_trace_pass() -> None:
    record = _record(
        {
            "C-1": _item("commitment"),
            "Q-1": _item(
                "requirement", [_ref("implements", "C-1"), _ref("addresses", "CL-1")]
            ),
            "K-1": _item("control", [_ref("implements", "Q-1")]),
            "CL-1": _item("clause"),
        }
    )
    assert _run("trace", record, TRACE) == []


def test_trace_fail() -> None:
    record = _record(
        {
            "C-1": _item("commitment", [_ref("implements", "C-1")]),
            "Q-1": _item("requirement", [_ref("addresses", "C-1")]),
            "K-1": _item("control", [_ref("implements", "C-1")]),
        }
    )
    assert _run("trace", record, TRACE) == [
        "C-1: a commitment may not implements anything",
        "K-1: implements ref to C-1 is a commitment, not a requirement",
        "Q-1: a requirement must implements at least one commitment",
        "Q-1: addresses ref to C-1 is a commitment, not a clause",
    ]


def test_trace_missing_target_is_left_to_reference() -> None:
    record = _record({"Q-1": _item("requirement", [_ref("implements", "C-9")])})
    assert _run("trace", record, TRACE) == []


# --------------------------------------------------------------------------
# 5. cross_reference
# --------------------------------------------------------------------------


def test_cross_reference_pass_and_fail() -> None:
    params = {"kinds": KINDS}
    ok = _record(
        {"P-1": _item("policy"), "T-1": _item("definition", [_ref("cites", "P-1")])}
    )
    assert _run("cross_reference", ok, params) == []
    bad = _record(
        {"D-1": _item("document"), "T-1": _item("definition", [_ref("cites", "D-1")])}
    )
    assert _run("cross_reference", bad, params) == [
        "T-1: cites ref to D-1 points to a document; cite the model behind it"
    ]


# --------------------------------------------------------------------------
# 6-8. flow, occurrence, raci (one made-up process)
# --------------------------------------------------------------------------


def _process(flow: list[dict], raci: dict[str, str] | None = None) -> dict:
    items = {
        "PR-1": _item(
            "process",
            [
                _ref("contains", "S-1", "p1"),
                _ref("contains", "DC-1", "p2"),
                _ref("contains", "S-2", "p3"),
                _ref("contains", "S-3", "p4"),
            ],
            flow=flow,
        ),
        "S-1": _item("step"),
        "S-2": _item("step"),
        "S-3": _item("step"),
        "DC-1": _item("decision", outcomes=["yes", "no"]),
    }
    for n, (position, letters) in enumerate((raci or {}).items(), start=1):
        items[f"RC-{n}"] = _item(
            "raci", [_ref("occurrence", "PR-1", position)], assignment=letters
        )
    return _record(items)


GOOD_FLOW = [
    {"from": "p1", "to": "p2", "kind": "next", "outcome": None},
    {"from": "p2", "to": "p3", "kind": "branch", "outcome": "yes"},
    {"from": "p2", "to": "p1", "kind": "loop", "outcome": "no"},
    {"from": "p3", "to": "p4", "kind": "next", "outcome": None},
]
GOOD_RACI = {"p1": "AR", "p3": "AR", "p4": "RA"}


def test_flow_pass() -> None:
    assert _run("flow", _process(GOOD_FLOW)) == []


def test_flow_fail() -> None:
    flow = [
        {"from": "p1", "to": "p9", "kind": "next", "outcome": None},
        {"from": "p1", "to": "p2", "kind": "branch", "outcome": None},
        {"from": "p2", "to": "p3", "kind": "next", "outcome": "maybe"},
        {"from": "p2", "to": "p4", "kind": "loop", "outcome": "no"},
        {"from": "p3", "to": "p3", "kind": "next", "outcome": None},
    ]
    assert _run("flow", _process(flow)) == [
        "PR-1: flow link 1 (p1 -> p9): both ends must be positions in the process",
        "PR-1: flow link 2 (p1 -> p2): only decisions branch or carry an outcome",
        "PR-1: flow link 3 (p2 -> p3): a link leaving a decision is a branch or a loop",
        "PR-1: flow link 3 (p2 -> p3): outcome 'maybe' is not one of DC-1's outcomes",
        "PR-1: flow link 4 (p2 -> p4): a loop never points forward",
        "PR-1: flow link 5 (p3 -> p3): a non-loop link never points backward or to itself",
        "PR-1: decision at p2: outcome 'yes' has 0 links, needs exactly one",
    ]
    # Every position after the first needs an incoming link.
    gap = [link for link in GOOD_FLOW if link["to"] != "p4"]
    assert _run("flow", _process(gap)) == ["PR-1: position p4 has no incoming link"]


def test_occurrence_pass_and_fail() -> None:
    assert _run("occurrence", _process(GOOD_FLOW, GOOD_RACI)) == []

    record = _process(GOOD_FLOW, {"p2": "R", "p7": "A"})
    record["items"]["PR-1"]["refs"].append(_ref("contains", "S-3", "p1"))
    record["items"]["RC-3"] = _item("raci", [_ref("occurrence", "S-1", "p1")])
    assert _run("occurrence", record) == [
        "PR-1: position id 'p1' is used twice",
        "RC-1: position 'p2' in PR-1 holds a decision, not a step",
        "RC-2: PR-1 has no position 'p7'",
        "RC-3: occurrence ref to S-1 is not a process",
    ]


def test_raci_pass_and_fail() -> None:
    assert _run("raci", _process(GOOD_FLOW, GOOD_RACI)) == []
    assert _run("raci", _process(GOOD_FLOW, {"p1": "AAR", "p3": "C"})) == [
        "PR-1: step at 'p1' needs exactly one A and at least one R, has 2 A and 1 R",
        "PR-1: step at 'p3' needs exactly one A and at least one R, has 0 A and 0 R",
        "PR-1: step at 'p4' needs exactly one A and at least one R, has 0 A and 0 R",
    ]


# --------------------------------------------------------------------------
# 9. dressing
# --------------------------------------------------------------------------


def test_dressing_pass_and_fail() -> None:
    params = {"kinds": KINDS}
    ok = _record(
        {"D-1": _item("document", dressing=["This page explains the musty archive."])}
    )
    assert _run("dressing", ok, params) == []
    bad = _record(
        {"D-1": _item("document", dressing=["Staff MUST log in.", "Unless told."])}
    )
    assert _run("dressing", bad, params) == [
        "D-1: dressing paragraph 1 uses normative word(s): must",
        "D-1: dressing paragraph 2 uses normative word(s): unless",
    ]


async def test_dressing_alone_is_undecided_never_fail() -> None:
    (dressing_rule,) = [
        r for r in load_record_catalog(catalog_path()) if r.rule_id.endswith("dressing")
    ]
    assert dressing_rule.blocking is False
    rule = dressing_rule  # the catalog's own params and enforcement
    record = _record({"D-1": _item("document", dressing=["You shall smile."])})
    verdict = await evaluate(record, [rule], engine_lookup=_lookup)
    assert verdict.outcome == "undecided"


# --------------------------------------------------------------------------
# 10. authority, and the workshop pair through the catalog (step 5)
# --------------------------------------------------------------------------


def _workshop() -> dict[str, Any]:
    def item(type_: str, refs: list[tuple[str, str]], **value: Any) -> dict:
        return {
            "type": type_,
            "version": "1",
            "status": "approved",
            "owner": "ROLE-21",
            "value": value,
            "sha256": "00",
            "effective": "2027-03-15",
            "withdrawn": None,
            "refs": [_ref(rel, to) for rel, to in refs],
        }

    items = {
        "ROLE-21": item(
            "role",
            [],
            name="Treasurer",
            mandate="Keeps the shared budget.",
            authority="Signs off spending.",
        ),
        "ROLE-22": item(
            "role",
            [],
            name="Workshop lead",
            mandate="Runs the tool room.",
            authority="Orders consumables.",
        ),
        "AUT-21": item(
            "authority_level",
            [("holder", "ROLE-21")],
            name="Board",
            rank=1,
            mandate="Final say on money.",
        ),
        "DCL-21": item("decision_class", [], name="Tool purchases"),
        "DRT-21": item(
            "decision_right",
            [("class", "DCL-21"), ("level", "AUT-21")],
            note="Buying a tool is decided at board level.",
        ),
        "DLG-21": item(
            "delegation",
            [("right", "DRT-21"), ("delegate", "ROLE-22")],
            scope="Tools under 200 per item.",
        ),
        "RRL-21": item(
            "role_realisation",
            [("role", "ROLE-22"), ("appointed_by", "AUT-21")],
            party_kind="team",
            party="Tool-room crew",
            scope="Weekday opening hours.",
        ),
    }
    for item_id, entry in items.items():
        entry["id"] = item_id
    return {
        "format": "library-snapshot/1",
        "items": items,
        "known": sorted(items),
        "scope": None,
        "load_findings": [],
        "pre_findings": [],
    }


async def _through_catalog(record: dict) -> Any:
    rules = load_record_catalog(catalog_path())
    assert len(rules) == 10
    return await evaluate(record, rules, engine_lookup=_lookup)


async def test_workshop_pass_authority_fires_and_passes() -> None:
    verdict = await _through_catalog(_workshop())
    assert (verdict.outcome, verdict.evidence_class) == ("pass", EvidenceClass.PROVEN)
    assert len(verdict.parts) == 10
    assert all(p.result == "pass" and not p.findings for p in verdict.parts)
    (authority,) = [p for p in verdict.parts if p.rule_id == "publication.authority"]
    assert authority.engine_id == "publication_gate"  # it ran: D16 "fires"


async def test_workshop_fail_missing_level() -> None:
    record = _workshop()
    record["items"]["DRT-21"]["refs"] = [_ref("class", "DCL-21")]
    verdict = await _through_catalog(record)
    assert verdict.outcome == "fail"
    failing = [p for p in verdict.parts if p.result != "pass"]
    assert [p.rule_id for p in failing] == ["publication.authority"]
    (finding,) = failing[0].findings
    assert finding.item == "DRT-21" and finding.blocking
    assert (
        finding.message == "DRT-21: a decision_right needs exactly one level ref, has 0"
    )


async def test_workshop_fail_level_points_to_a_role() -> None:
    record = _workshop()
    record["items"]["DRT-21"]["refs"] = [
        _ref("class", "DCL-21"),
        _ref("level", "ROLE-22"),
    ]
    verdict = await _through_catalog(record)
    failing = [p for p in verdict.parts if p.result != "pass"]
    assert [p.rule_id for p in failing] == ["publication.authority"]
    assert [f.message for f in failing[0].findings] == [
        "DRT-21: level ref to ROLE-22 is a role, not a authority_level"
    ]


def test_authority_optional_refs_and_tiers() -> None:
    (rule,) = [
        r
        for r in load_record_catalog(catalog_path())
        if r.rule_id.endswith("authority")
    ]
    record = _workshop()
    record["items"]["DRT-21"]["refs"] += [
        _ref("validation", "AUT-21"),
        _ref("validation", "AUT-21"),
    ]
    record["items"]["DCL-21"]["refs"] = [_ref("tier", "ROLE-21")]
    assert _run("authority", record, dict(rule.params)) == [
        "DCL-21: tier ref to ROLE-21 is a role, not a exception_tier",
        "DRT-21: a decision_right has at most 1 validation ref, has 2",
    ]


# --------------------------------------------------------------------------
# The catalog and the module boundary
# --------------------------------------------------------------------------


def test_catalog_meets_the_adr_174_contract_with_no_warnings() -> None:
    assert record_catalog_warnings(catalog_path()) == []


def test_catalog_lives_with_the_module_not_under_grc_catalogs() -> None:
    path = catalog_path()
    assert path.parent.parent == Path(R.__file__).resolve().parent
    assert "grc-catalogs" not in path.parts and "_grc_catalogs" not in path.parts


def test_engine_is_registered() -> None:
    from mind.logic.engines.registry import EngineRegistry

    assert "publication_gate" in EngineRegistry.known_engine_ids()


def test_runtime_does_not_import_the_module() -> None:
    src = Path(R.__file__).resolve().parents[4]
    package = Path(R.__file__).resolve().parent
    importers = [
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if package not in path.parents
        and "publication_gate" in path.read_text(encoding="utf-8")
    ]
    assert importers == []


@pytest.mark.parametrize("check", [None, "nope"])
async def test_unknown_check_fails(check: Any) -> None:
    verdict = await evaluate(
        _workshop(),
        [RecordRule("x", "publication_gate", {"check": check})],
        engine_lookup=_lookup,
    )
    assert verdict.outcome == "fail"


def test_rules_do_not_mutate_the_record() -> None:
    record = _process(GOOD_FLOW, GOOD_RACI)
    before = copy.deepcopy(record)
    for name, rule in R.RULES.items():
        rule(record, name, {"kinds": KINDS})
    assert record == before
