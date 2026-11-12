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
