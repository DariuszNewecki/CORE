from __future__ import annotations

from unittest.mock import MagicMock

from will.test_generation.prompt_engine import ConstitutionalTestPromptBuilder


# ID: 3b2e9658-f38e-4f5b-874a-377f8d360da6
def test_ConstitutionalTestPromptBuilder_build():
    builder = ConstitutionalTestPromptBuilder()

    strategy = MagicMock()
    strategy.data = {
        "approach": "pure_function_test",
        "constraints": ["no network", " "],
    }

    context_packet = {"problem": {"target_module": "my.module.path"}}

    result = builder.build(
        symbol_name="safe_truncate",
        symbol_code="def safe_truncate(s, n): ...",
        dependencies=[],
        similar_symbols=[],
        strategy=strategy,
        file_type=".py",
        complexity="low",
        has_db_harness=False,
        context_packet=context_packet,
        introspection_facts={"return_type": "str"},
    )

    assert isinstance(result, str)
    assert "# TASK: Generate Pytest Unit Tests for 'safe_truncate'" in result
    assert "# MODULE: my.module.path" in result
    assert "## TARGET CODE" in result
    assert "def safe_truncate(s, n): ..." in result
    assert "from my.module.path import safe_truncate" in result
    assert "pure_function_test" not in result
    assert "NO NETWORK" in result
    assert "## OUTPUT REQUIREMENTS" in result





# ID: d4c61d9c-e579-47a5-bd05-fd8a6db9916a
def test_ConstitutionalTestPromptBuilder():
    builder = ConstitutionalTestPromptBuilder()

    strategy = MagicMock()
    strategy.data = {
        "approach": "unit",
        "constraints": ["no network", "fast"],
    }

    context_packet = {
        "problem": {"target_module": "my.module.path"},
    }

    result = builder.build(
        symbol_name="my_func",
        symbol_code="def my_func(x):\n    return x\n",
        dependencies=[],
        similar_symbols=[],
        strategy=strategy,
        file_type="module",
        complexity="low",
        has_db_harness=False,
        context_packet=context_packet,
        introspection_facts=None,
    )

    assert isinstance(result, str)
    assert "my_func" in result
    assert "my.module.path" in result
    assert "## MANDATORY EXECUTION TRACE" in result
    assert "## CRITICAL RULES" in result
    assert "## TARGET CODE" in result
    assert "## OUTPUT REQUIREMENTS" in result
    assert "from my.module.path import my_func" in result
    assert "- NO NETWORK" in result
    assert "- FAST" in result
    assert "def my_func(x):" in result
