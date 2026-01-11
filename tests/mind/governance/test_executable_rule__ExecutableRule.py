"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/executable_rule.py
- Symbol: ExecutableRule
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:38:28
"""

from mind.governance.executable_rule import ExecutableRule


# Detected return type: ExecutableRule is a regular class (not async)


def test_executable_rule_initialization_with_minimal_fields():
    """Test basic initialization with required fields."""
    rule = ExecutableRule(
        rule_id="test.rule.id",
        engine="ast_gate",
        params={"check_type": "restrict_event_loop_creation"},
        enforcement="error",
    )

    assert rule.rule_id == "test.rule.id"
    assert rule.engine == "ast_gate"
    assert rule.params == {"check_type": "restrict_event_loop_creation"}
    assert rule.enforcement == "error"
    assert rule.statement == ""
    assert rule.scope == ["src/**/*.py"]
    assert rule.exclusions == []
    assert rule.policy_id == ""
    assert not rule.is_context_level


def test_executable_rule_initialization_with_all_fields():
    """Test initialization with all optional fields explicitly set."""
    rule = ExecutableRule(
        rule_id="async.runtime.no_nested_loop_creation",
        engine="knowledge_gate",
        params={"max_depth": 2, "allowed_patterns": ["safe_pattern"]},
        enforcement="warning",
        statement="Do not create nested event loops in async code",
        scope=["src/**/*.py", "lib/**/*.py"],
        exclusions=["tests/**", "docs/**"],
        policy_id="policy_001",
        is_context_level=True,
    )

    assert rule.rule_id == "async.runtime.no_nested_loop_creation"
    assert rule.engine == "knowledge_gate"
    assert rule.params == {"max_depth": 2, "allowed_patterns": ["safe_pattern"]}
    assert rule.enforcement == "warning"
    assert rule.statement == "Do not create nested event loops in async code"
    assert rule.scope == ["src/**/*.py", "lib/**/*.py"]
    assert rule.exclusions == ["tests/**", "docs/**"]
    assert rule.policy_id == "policy_001"
    assert rule.is_context_level


def test_executable_rule_initialization_with_empty_params():
    """Test initialization with empty params dictionary."""
    rule = ExecutableRule(
        rule_id="empty.params.rule", engine="llm_gate", params={}, enforcement="error"
    )

    assert rule.rule_id == "empty.params.rule"
    assert rule.engine == "llm_gate"
    assert rule.params == {}
    assert rule.enforcement == "error"


def test_executable_rule_initialization_with_nested_params():
    """Test initialization with nested parameter structures."""
    rule = ExecutableRule(
        rule_id="complex.params.rule",
        engine="ast_gate",
        params={
            "check_type": "complex_check",
            "options": {"level": "high", "threshold": 0.95},
            "patterns": ["pattern1", "pattern2"],
        },
        enforcement="error",
    )

    assert rule.rule_id == "complex.params.rule"
    assert rule.engine == "ast_gate"
    assert rule.params == {
        "check_type": "complex_check",
        "options": {"level": "high", "threshold": 0.95},
        "patterns": ["pattern1", "pattern2"],
    }
    assert rule.enforcement == "error"


def test_executable_rule_default_scope_is_list():
    """Test that default scope is a list and not shared between instances."""
    rule1 = ExecutableRule(
        rule_id="rule1", engine="ast_gate", params={}, enforcement="error"
    )

    rule2 = ExecutableRule(
        rule_id="rule2", engine="ast_gate", params={}, enforcement="error"
    )

    # Both should have the same default value
    assert rule1.scope == ["src/**/*.py"]
    assert rule2.scope == ["src/**/*.py"]

    # Modifying one shouldn't affect the other
    rule1.scope.append("additional/**/*.py")
    assert rule1.scope == ["src/**/*.py", "additional/**/*.py"]
    assert rule2.scope == ["src/**/*.py"]


def test_executable_rule_default_exclusions_is_empty_list():
    """Test that default exclusions is an empty list and not shared between instances."""
    rule1 = ExecutableRule(
        rule_id="rule1", engine="ast_gate", params={}, enforcement="error"
    )

    rule2 = ExecutableRule(
        rule_id="rule2", engine="ast_gate", params={}, enforcement="error"
    )

    # Both should have empty list
    assert rule1.exclusions == []
    assert rule2.exclusions == []

    # Modifying one shouldn't affect the other
    rule1.exclusions.append("excluded/**")
    assert rule1.exclusions == ["excluded/**"]
    assert rule2.exclusions == []


def test_executable_rule_repr_method():
    """Test the __repr__ method for concise representation."""
    rule = ExecutableRule(
        rule_id="test.repr.rule",
        engine="llm_gate",
        params={"param": "value"},
        enforcement="warning",
    )

    # Note: Using == not 'is' for string comparison
    assert repr(rule) == "ExecutableRule(test.repr.rule, engine=llm_gate)"


def test_executable_rule_with_context_level_engines():
    """Test that is_context_level can be set independently of engine."""
    # Test with context-level engine
    rule1 = ExecutableRule(
        rule_id="context.rule",
        engine="knowledge_gate",
        params={},
        enforcement="error",
        is_context_level=True,
    )
    assert rule1.is_context_level

    # Test with file-level engine but context-level flag
    rule2 = ExecutableRule(
        rule_id="mixed.rule",
        engine="ast_gate",  # Normally file-level
        params={},
        enforcement="error",
        is_context_level=True,  # But explicitly set to context-level
    )
    assert rule2.is_context_level

    # Test with context-level engine but file-level flag
    rule3 = ExecutableRule(
        rule_id="mixed2.rule",
        engine="workflow_gate",  # Normally context-level
        params={},
        enforcement="error",
        is_context_level=False,  # But explicitly set to file-level
    )
    assert not rule3.is_context_level


def test_executable_rule_with_empty_scope_list():
    """Test initialization with explicitly empty scope list."""
    rule = ExecutableRule(
        rule_id="empty.scope.rule",
        engine="glob_gate",
        params={},
        enforcement="warning",
        scope=[],  # Explicitly empty
    )

    assert rule.scope == []


def test_executable_rule_with_special_characters_in_id():
    """Test initialization with special characters in rule_id."""
    rule = ExecutableRule(
        rule_id="special.chars.rule-1.2_3@test",
        engine="regex_gate",
        params={},
        enforcement="error",
    )

    assert rule.rule_id == "special.chars.rule-1.2_3@test"


def test_executable_rule_enforcement_values():
    """Test initialization with different enforcement values."""
    # Test with 'error'
    rule1 = ExecutableRule(
        rule_id="error.rule", engine="ast_gate", params={}, enforcement="error"
    )
    assert rule1.enforcement == "error"

    # Test with 'warning'
    rule2 = ExecutableRule(
        rule_id="warning.rule", engine="ast_gate", params={}, enforcement="warning"
    )
    assert rule2.enforcement == "warning"


def test_executable_rule_statement_with_multiline_text():
    """Test initialization with multiline statement text."""
    multiline_statement = """This is a multiline statement.
It spans multiple lines.
With special characters: !@#$%^&*()"""

    rule = ExecutableRule(
        rule_id="multiline.rule",
        engine="llm_gate",
        params={},
        enforcement="error",
        statement=multiline_statement,
    )

    assert rule.statement == multiline_statement
