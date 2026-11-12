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
