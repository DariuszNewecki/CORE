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


# ID: c1dd7065-0bf5-44ac-85fd-2d6ca16876b1
def test_PolicyRule():
    data = {
        "id": "di.no_global_session_import",
        "statement": "No global session import",
        "authority": "constitution",
        "check": {
            "engine": "ast_gate",
            "params": {"check_type": "runtime_import_boundary"},
        },
        "enforcement": "error",
        "scope": ["src/**/*.py"],
    }

    rule = PolicyRule.from_dict(data, source="core.intent")

    assert isinstance(rule, PolicyRule)
    assert rule.name == "di.no_global_session_import"
    assert rule.pattern == "src/**/*.py"
    assert rule.action == "deny"
    assert rule.description == "No global session import"
    assert rule.severity == "error"
    assert rule.source_policy == "core.intent"
    assert rule.engine == "ast_gate"
    assert rule.params == {"check_type": "runtime_import_boundary"}
    assert rule.authority == "constitution"
