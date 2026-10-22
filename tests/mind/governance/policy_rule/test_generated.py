from __future__ import annotations

from mind.governance.policy_rule import PolicyRule


# ID: f4edb74e-3084-47b6-9765-eb399b34d4db
def test_PolicyRule_from_dict():
    data = {
        "id": "rule.name",
        "statement": "description text",
        "authority": "policy",
        "check": {
            "engine": "ast_gate",
            "params": {"check_type": "runtime_import_boundary"},
        },
        "enforcement": "error",
        "scope": ["src/**/*.py"],
    }

    rule = PolicyRule.from_dict(data, source="constitution")

    assert rule.name == "rule.name"
    assert rule.pattern == "src/**/*.py"
    assert rule.action == "deny"
    assert rule.description == "description text"
    assert rule.severity == "error"
    assert rule.source_policy == "constitution"
    assert rule.engine == "ast_gate"
    assert rule.params == {"check_type": "runtime_import_boundary"}
    assert rule.authority == "policy"
