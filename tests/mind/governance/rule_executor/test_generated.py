from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.rule_executor import execute_rule


# ID: d0712c45-1b5b-4c73-9875-2822628a55c6
async def test_execute_rule() -> None:
    rule = MagicMock()
    rule.rule_id = "test.rule"
    rule.engine = "some_engine"
    rule.is_context_level = False
    rule.scope = frozenset({"src/**"})
    rule.exclusions = frozenset()
    rule.enforcement = "block"
    rule.params = {}
    rule.requires_findings_from = ()
    rule.rule_content_hash = ""

    context = MagicMock()
    context.force_llm = False
    context.get_files.return_value = []

    verify_result = MagicMock()
    verify_result.ok = True
    verify_result.violations = []
    verify_result.extra = {}

    engine = MagicMock()
    engine.evidence_class = "ATTESTED"
    engine.verify = AsyncMock(return_value=verify_result)
    # Make isinstance(engine, LLMGateStubEngine) evaluate False since the real
    # LLMGateStubEngine class is imported locally inside execute_rule.
    engine.__class__ = type("NotStubEngine", (), {})

    with (
        patch("mind.logic.engines.registry.EngineRegistry.get", return_value=engine),
        patch("mind.governance.rule_executor.declared_check_types", return_value=None),
    ):
        findings = await execute_rule(rule, context)

    assert findings == []
    context.get_files.assert_called_once()


# ID: a31d89b4-98a8-43fb-98c9-0a68f9190293
def test_clear_eval_cache():
    from mind.governance.rule_executor import _EVAL_CACHE, clear_eval_cache

    _EVAL_CACHE[("a.py", "hash1", "rule-x", 1, 2)] = [MagicMock()]
    _EVAL_CACHE[("b.py", "hash2", "rule-y", 3, 4)] = [MagicMock(), MagicMock()]
    assert len(_EVAL_CACHE) == 2

    clear_eval_cache()

    assert _EVAL_CACHE == {}
    assert len(_EVAL_CACHE) == 0
