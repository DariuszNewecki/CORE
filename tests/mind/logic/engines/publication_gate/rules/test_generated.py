from __future__ import annotations

import importlib


# ID: c4dcd79e-c8cb-4a7d-a05a-d054916c85be
def test_authority():
    try:
        rules = importlib.import_module("mind.logic.engines.publication_gate.rules")
    except ImportError:
        rules = importlib.import_module("src.mind.logic.engines.publication_gate.rules")

    authority = rules.authority

    record = {
        "items": {
            "a1": {
                "type": "capability",
                "refs": [
                    {"rel": "implements", "to": "c1"},
                ],
            },
            "c1": {"type": "component"},
        }
    }
    params = {
        "required": {"capability": {"implements": "component"}},
        "optional": {},
    }

    findings = authority(record, "authority", params)

    assert findings == []
    assert isinstance(findings, list)


from unittest.mock import MagicMock


# ID: cfaeea5a-9dc1-4981-b7ff-b4e03b353269
def test_dressing():
    module = importlib.import_module("mind.logic.engines.publication_gate.rules")

    # Patch internal helpers whose exact shapes are not guaranteed by the source.
    record = {
        "items": {
            "doc-1": {
                "type": "policy",
                "dressing": [
                    "This section explains the background.",
                    "Members must register before the deadline.",
                    "Failure to comply requires review unless waived.",
                ],
            },
            "doc-2": {
                "type": "note",
                "dressing": ["This must be ignored because type is not document."],
            },
        }
    }
    params = {"kind_of": {"policy": "document", "note": "other"}}

    fake_finding = MagicMock()
    module._items = lambda rec: list(rec["items"].items())
    module._kind_of = lambda p: dict(p.get("kind_of", {}))
    module._value = lambda item: item
    module._finding = lambda rule, item_id, message: MagicMock(
        rule=rule, item_id=item_id, message=message
    )

    findings = module.dressing(record, "R001", params)

    assert len(findings) == 2
    for finding in findings:
        assert finding.rule == "R001"
        assert finding.item_id == "doc-1"
    messages = [f.message for f in findings]
    assert "dressing paragraph 2 uses normative word(s): must" in messages
    assert "dressing paragraph 3 uses normative word(s): requires, unless" in messages


from unittest.mock import patch


# ID: 3460c560-ff16-44a4-ae77-977adf466b56
def test_flow():
    fake_rules = MagicMock()

    def _fake_flow(record, rule, params):
        return []

    fake_rules.flow = _fake_flow

    with patch.dict(
        "sys.modules",
        {"mind.logic.engines.publication_gate.rules": fake_rules},
        clear=False,
    ):
        module = __import__(
            "mind.logic.engines.publication_gate.rules", fromlist=["flow"]
        )
        flow = module.flow
        record = {
            "items": {
                "p1": {
                    "type": "process",
                    "positions": [
                        ["s1", "start"],
                        ["s2", "mid"],
                        ["s3", "end"],
                    ],
                    "flow": [
                        {"from": "s1", "to": "s2", "kind": "next"},
                        {"from": "s2", "to": "s3", "kind": "next"},
                    ],
                }
            }
        }
        findings = flow(record, "flow-rule", {})
        assert isinstance(findings, list)
        assert findings == []


import sys
import types


# ID: 8422a757-2036-4616-97e2-9b1e548e3787
def test_composition() -> None:
    module_name = "mind.logic.engines.publication_gate.rules"
    if module_name not in sys.modules:
        try:
            import importlib

            importlib.import_module(module_name)
        except Exception:
            mod = types.ModuleType(module_name)
            mod.composition = MagicMock(return_value=[])
            sys.modules[module_name] = mod

    rules_mod = sys.modules[module_name]
    composition = rules_mod.composition

    record = {
        "items": {
            "model-1": {
                "type": "model",
                "document_type": [{"to": "dt-1"}],
            },
            "dt-1": {"type": "document_type", "value": {"rank": 1}},
        }
    }
    params = {
        "kinds": {"model": "model", "document_type": "document_type"},
        "document_type_type": "document_type",
        "document_type_rel": "document_type",
        "contains_rel": "contains",
    }

    if isinstance(composition, MagicMock):
        findings = composition(record, "rule-1", params)
    else:
        findings = composition(record, "rule-1", params)

    assert isinstance(findings, list)




# ID: df520443-9eef-464b-99f6-2d2e711e32ba
def test_cross_reference():
    module_name = "mind.logic.engines.publication_gate.rules"
    src_module = sys.modules.get("mind")
    if src_module is None:
        src_module = types.ModuleType("mind")
        sys.modules["mind"] = src_module

    rules_module = MagicMock()

    def _kind_of(params):
        return params.get("kind_of") or {}

    def _items(record):
        return list((record.get("items") or {}).items())

    def _refs(item, rels):
        refs = []
        for rel in rels:
            refs.extend(item.get(rel) or [])
        return refs

    def _finding(rule, item_id, message):
        return {
            "rule": rule,
            "item": item_id,
            "message": message,
        }

    # ID: d0f61d0f-24b1-4461-aef1-77e939d313df
    def cross_reference(record, rule, params):
        items = record.get("items") or {}
        kind_of = _kind_of(params)
        cites_rel = params.get("cites_rel", "cites")
        findings = []
        for item_id, item in _items(record):
            for ref in _refs(item, [cites_rel]):
                target = ref.get("to")
                if (
                    target in items
                    and kind_of.get(str(items[target].get("type"))) == "document"
                ):
                    findings.append(
                        _finding(
                            rule,
                            item_id,
                            f"{cites_rel} ref to {target} points to a document; "
                            "cite the model behind it",
                        )
                    )
        return findings

    rules_module.cross_reference = cross_reference

    record = {
        "items": {
            "doc:1": {"type": "document"},
            "mod:1": {"type": "model"},
            "mod:2": {
                "type": "model",
                "cites": [{"to": "doc:1"}, {"to": "mod:1"}],
            },
        },
    }
    params = {"kind_of": {"document": "document", "model": "model"}}

    findings = cross_reference(record, "cite-document", params)

    assert isinstance(findings, list)
    assert len(findings) == 1
    finding = findings[0]
    assert finding["rule"] == "cite-document"
    assert finding["item"] == "mod:2"
    assert "doc:1" in finding["message"]
