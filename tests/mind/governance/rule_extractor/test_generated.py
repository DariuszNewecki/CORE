from __future__ import annotations

from unittest.mock import MagicMock

from mind.governance.rule_extractor import extract_executable_rules


# ID: 73259dcf-c93c-4bdf-b5b6-844185d0dd87
def test_extract_executable_rules():
    policies = {
        "test_policy": {
            "rules": [
                {
                    "id": "RULE-001",
                    "statement": "Do the thing",
                    "enforcement": "blocking",
                    "authority": "constitution",
                    "phase": "audit",
                }
            ]
        }
    }

    enforcement_loader = MagicMock()
    enforcement_loader.get_enforcement_strategy.return_value = {
        "engine": "some_engine",
        "params": {"check_type": "file_check"},
        "scope": {"applies_to": ["src/*"], "excludes": []},
    }

    result = extract_executable_rules(policies, enforcement_loader)

    assert len(result) == 1
    rule = result[0]
    assert rule.rule_id == "RULE-001"
    assert rule.engine == "some_engine"
    assert rule.enforcement == "blocking"
    assert rule.statement == "Do the thing"
    assert rule.scope == ["src/*"]
    assert rule.authority == "constitution"
    enforcement_loader.get_enforcement_strategy.assert_called_once_with("RULE-001")
