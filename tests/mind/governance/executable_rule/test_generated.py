from __future__ import annotations

from mind.governance.executable_rule import ExecutableRule


# ID: f2db902e-63df-4225-8981-cba9e1ec79bd
def test_ExecutableRule():
    rule = ExecutableRule(
        rule_id="async.runtime.no_nested_loop_creation",
        engine="ast_gate",
        params={"check_type": "restrict_event_loop_creation"},
        enforcement="error",
    )

    assert rule.rule_id == "async.runtime.no_nested_loop_creation"
    assert rule.engine == "ast_gate"
    assert rule.params == {"check_type": "restrict_event_loop_creation"}
    assert rule.enforcement == "error"
    assert rule.statement == ""
    assert rule.scope == ["src/**/*.py"]
    assert rule.exclusions == []
    assert rule.policy_id == ""
    assert rule.is_context_level is False
    assert rule.authority == "policy"
    assert rule.requires_findings_from == []
    assert rule.rule_content_hash == ""

    assert repr(rule) == (
        "ExecutableRule(async.runtime.no_nested_loop_creation, "
        "engine=ast_gate, authority=policy)"
    )
