from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mind.governance.constitutional_auditor_dynamic import (
    _check_per_file_scope_coverage,
    _count_total_declared_rules,
    _find_unmapped_rule_ids,
    get_dynamic_execution_stats,
    run_dynamic_rules,
)


class TestCountTotalDeclaredRules:
    def test_empty_policies(self):
        policies = {}
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    def test_invalid_policy_data_skipped(self):
        policies = {
            "policy1": "not a dict",
            "policy2": None,
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    def test_single_policy_with_rules(self):
        policies = {
            "policy1": {
                "rules": [
                    {"id": "rule1"},
                    {"id": "rule2"},
                ]
            }
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 2
        assert rule_ids == ["rule1", "rule2"]

    def test_multiple_policies_combined(self):
        policies = {
            "policy1": {
                "rules": [
                    {"id": "rule_a"},
                ]
            },
            "policy2": {
                "rules": [
                    {"id": "rule_b"},
                    {"id": "rule_c"},
                ]
            },
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 3
        assert rule_ids == ["rule_a", "rule_b", "rule_c"]

    def test_duplicate_rule_ids_across_policies(self):
        policies = {
            "policy1": {
                "rules": [
                    {"id": "dup_rule"},
                ]
            },
            "policy2": {
                "rules": [
                    {"id": "dup_rule"},
                ]
            },
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 2
        assert rule_ids == ["dup_rule", "dup_rule"]

    def test_policy_with_no_rules_key(self):
        policies = {"policy1": {}}
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    def test_policy_with_empty_rules_list(self):
        policies = {"policy1": {"rules": []}}
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    def test_rule_without_rule_id_skipped(self):
        policies = {
            "policy1": {
                "rules": [
                    {"id": "valid_rule"},
                    {"name": "no_id"},
                ]
            }
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 1
        assert rule_ids == ["valid_rule"]


class TestFindUnmappedRuleIds:
    def test_all_rules_mapped(self):
        policies = {"p1": {"rules": [{"id": "r1"}, {"id": "r2"}]}}
        executable = {"r1", "r2"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []

    def test_some_rules_unmapped(self):
        policies = {"p1": {"rules": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]}}
        executable = {"r1", "r3"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == ["r2"]

    def test_all_rules_unmapped(self):
        policies = {"p1": {"rules": [{"id": "r1"}, {"id": "r2"}]}}
        executable = set()
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == ["r1", "r2"]

    def test_no_rules_declared(self):
        policies = {}
        executable = {"some_rule"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []

    def test_returns_sorted_result(self):
        policies = {
            "p1": {
                "rules": [
                    {"id": "z_rule"},
                    {"id": "a_rule"},
                    {"id": "m_rule"},
                ]
            }
        }
        executable = {"a_rule"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == ["m_rule", "z_rule"]

    def test_extra_executable_ids_ignored(self):
        policies = {"p1": {"rules": [{"id": "r1"}]}}
        executable = {"r1", "extra_rule"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []


class TestCheckPerFileScopeCoverage:
    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.get_files.return_value = ["file1.py", "file2.py"]
        return ctx

    def make_mock_rule(
        self,
        rule_id="rule1",
        is_context_level=False,
        scope=None,
        exclusions=None,
        engine="file_scanner",
        enforcement="blocking",
        policy_id="pol1",
    ):
        rule = MagicMock()
        rule.rule_id = rule_id
        rule.is_context_level = is_context_level
        rule.scope = scope or ["*.py"]
        rule.exclusions = exclusions or []
        rule.engine = engine
        rule.enforcement = enforcement
        rule.policy_id = policy_id
        return rule

    def test_no_executable_rules(self, mock_context):
        findings = _check_per_file_scope_coverage(mock_context, [])
        assert findings == []

    def test_context_level_rule_excluded(self, mock_context):
        rule = self.make_mock_rule(is_context_level=True)
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    def test_passive_engine_excluded(self, mock_context):
        rule = self.make_mock_rule(engine="passive_gate")
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    def test_empty_scope_excluded(self, mock_context):
        rule = self.make_mock_rule(scope=[])
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    def test_non_blocking_rule_excluded(self, mock_context):
        for enforcement in ["advisory", "reporting", "info"]:
            rule = self.make_mock_rule(enforcement=enforcement)
            findings = _check_per_file_scope_coverage(mock_context, [rule])
            assert findings == [], f"failed for enforcement={enforcement}"

    def test_rule_scope_has_match(self, mock_context):
        mock_context.get_files.return_value = ["src/main.py"]
        rule = self.make_mock_rule(scope=["src/*.py"], enforcement="blocking")
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    def test_rule_scope_has_no_match(self, mock_context):
        mock_context.get_files.return_value = []
        rule = self.make_mock_rule(scope=["non_existent/*.py"], enforcement="blocking")
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "rule1.scope_inert"
        assert finding.severity.name == "BLOCK"
        assert "SCOPE_INERT" in str(finding.message)
        assert finding.context["finding_type"] == "SCOPE_INERT"
        assert finding.context["policy_id"] == "pol1"
        assert finding.context["scope"] == ["non_existent/*.py"]

    def test_multiple_inert_rules_reported(self, mock_context):
        mock_context.get_files.return_value = []
        rule1 = self.make_mock_rule(
            rule_id="inert_a", scope=["a/*"], enforcement="blocking"
        )
        rule2 = self.make_mock_rule(
            rule_id="inert_b", scope=["b/*"], enforcement="blocking"
        )
        rule3 = self.make_mock_rule(
            rule_id="ok_rule", scope=["ok/*"], enforcement="blocking"
        )
        mock_context.get_files.side_effect = [[], [], ["file.py"]]
        findings = _check_per_file_scope_coverage(mock_context, [rule1, rule2, rule3])
        assert len(findings) == 2
        check_ids = {f.check_id for f in findings}
        assert check_ids == {"inert_a.scope_inert", "inert_b.scope_inert"}

    def test_exclusions_still_empty_scope_match(self, mock_context):
        mock_context.get_files.return_value = ["src/main.py"]
        rule = self.make_mock_rule(
            scope=["src/*.py"], exclusions=["*.bak"], enforcement="blocking"
        )
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []


def _make_executable_rule(rule_id: str) -> MagicMock:
    """Mock satisfying the attribute surface read by source during stats and
    run_dynamic_rules — rule_id, engine, policy_id, plus is_context_level so
    the SCOPE_INERT firing-coverage gate skips the rule cleanly."""
    rule = MagicMock()
    rule.rule_id = rule_id
    rule.engine = "file_scanner"
    rule.policy_id = "pol1"
    rule.is_context_level = True
    return rule


class TestGetDynamicExecutionStats:
    def make_mock_context(self, policies=None):
        ctx = MagicMock()
        ctx.policies = policies or {}
        return ctx

    def test_no_executed_or_crashed_rules(self, monkeypatch):
        ctx = self.make_mock_context({"pol1": {"rules": [{"id": "r1"}]}})
        monkeypatch.setattr(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            lambda *a, **k: [],
        )
        stats = get_dynamic_execution_stats(ctx, set())
        assert stats["total_declared_rules"] == 1
        assert stats["executed_dynamic_rules"] == 0
        assert stats["unmapped_rule_ids"] == ["r1"]
        assert stats["crashed_rule_ids"] == []

    def test_all_rules_executed_none_crashed(self, monkeypatch):
        ctx = self.make_mock_context({"pol1": {"rules": [{"id": "r1"}, {"id": "r2"}]}})
        monkeypatch.setattr(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            lambda *a, **k: [_make_executable_rule("r1"), _make_executable_rule("r2")],
        )
        stats = get_dynamic_execution_stats(ctx, {"r1", "r2"})
        assert stats["total_declared_rules"] == 2
        assert stats["executed_dynamic_rules"] == 2
        assert stats["unmapped_rule_ids"] == []
        assert stats["crashed_rule_ids"] == []

    def test_with_crashed_rules(self, monkeypatch):
        ctx = self.make_mock_context(
            {"pol1": {"rules": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]}}
        )
        monkeypatch.setattr(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            lambda *a, **k: [_make_executable_rule("r1"), _make_executable_rule("r2")],
        )
        stats = get_dynamic_execution_stats(ctx, {"r1", "r2"}, crashed_rule_ids={"r2"})
        assert stats["total_declared_rules"] == 3
        assert stats["executed_dynamic_rules"] == 2
        assert stats["crashed_rule_ids"] == ["r2"]
        assert stats["unmapped_rule_ids"] == ["r3"]

    def test_crashed_rule_also_unmapped_not_counted_twice(self, monkeypatch):
        ctx = self.make_mock_context({"pol1": {"rules": [{"id": "r1"}, {"id": "r2"}]}})
        monkeypatch.setattr(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            lambda *a, **k: [_make_executable_rule("r1"), _make_executable_rule("r2")],
        )
        stats = get_dynamic_execution_stats(ctx, {"r1"}, crashed_rule_ids={"r2"})
        assert stats["total_declared_rules"] == 2
        assert stats["executed_dynamic_rules"] == 1
        assert stats["crashed_rule_ids"] == ["r2"]
        assert stats["unmapped_rule_ids"] == []

    def test_default_crashed_rule_ids_is_empty_set(self, monkeypatch):
        ctx = self.make_mock_context({"pol1": {"rules": [{"id": "r1"}]}})
        monkeypatch.setattr(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            lambda *a, **k: [],
        )
        stats = get_dynamic_execution_stats(ctx, set())
        assert stats["crashed_rule_ids"] == []

    def test_mixed_scenario(self, monkeypatch):
        ctx = self.make_mock_context(
            {"pol1": {"rules": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]}}
        )
        monkeypatch.setattr(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            lambda *a, **k: [_make_executable_rule("r1"), _make_executable_rule("r2")],
        )
        stats = get_dynamic_execution_stats(ctx, {"r1", "r2"}, crashed_rule_ids={"r1"})
        assert stats["total_declared_rules"] == 3
        assert stats["executed_dynamic_rules"] == 2
        assert stats["crashed_rule_ids"] == ["r1"]
        assert stats["unmapped_rule_ids"] == ["r3"]
        # Source's "honesty" semantic: crashed rules don't count as cleanly
        # executed. With cleanly_executed = {r2} and total_declared = 3,
        # effective_coverage_percent is round(1/3 * 100) = 33, not the
        # pre-honesty 2/3 = 66.67. See ADR-P0.2 in source docstring.
        assert stats["effective_coverage_percent"] == 33


class TestRunDynamicRules:
    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.enforcement_loader = MagicMock()
        ctx.policies = {}
        return ctx

    @staticmethod
    def _patch_boundaries(monkeypatch, *, rules, execute_rule_mock):
        """Patch run_dynamic_rules's collaborators at the boundary source
        actually crosses: extract_executable_rules (module-top import),
        rule_executor.execute_rule (deferred import inside the function),
        and EngineRegistry.get (classmethod consulted before dispatch)."""
        from mind.governance import constitutional_auditor_dynamic as mod
        from mind.governance import rule_executor
        from mind.logic.engines import registry as engine_registry

        monkeypatch.setattr(mod, "extract_executable_rules", lambda *a, **k: rules)
        monkeypatch.setattr(rule_executor, "execute_rule", execute_rule_mock)

        class _NonStubEngine:
            pass

        monkeypatch.setattr(
            engine_registry.EngineRegistry,
            "get",
            classmethod(lambda cls, _engine_id: _NonStubEngine()),
        )

    @pytest.mark.asyncio
    async def test_empty_executable_rules(self, mock_context, monkeypatch):
        execute_rule_mock = AsyncMock(return_value=[])
        self._patch_boundaries(
            monkeypatch, rules=[], execute_rule_mock=execute_rule_mock
        )
        executed = set()
        crashed = set()
        results = await run_dynamic_rules(
            mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed
        )
        assert executed == set()
        assert crashed == set()
        assert results == []
        execute_rule_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_single_rule_executes_successfully(self, mock_context, monkeypatch):
        rule = _make_executable_rule("r1")
        execute_rule_mock = AsyncMock(return_value=[])
        self._patch_boundaries(
            monkeypatch, rules=[rule], execute_rule_mock=execute_rule_mock
        )
        executed = set()
        crashed = set()
        await run_dynamic_rules(
            mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed
        )
        assert "r1" in executed
        assert "r1" not in crashed
        execute_rule_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rule_crash_produces_enforcement_failure(
        self, mock_context, monkeypatch
    ):
        rule = _make_executable_rule("crash_rule")
        execute_rule_mock = AsyncMock(side_effect=Exception("Engine crash"))
        self._patch_boundaries(
            monkeypatch, rules=[rule], execute_rule_mock=execute_rule_mock
        )
        executed = set()
        crashed = set()
        results = await run_dynamic_rules(
            mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed
        )
        assert "crash_rule" in executed
        assert "crash_rule" in crashed
        assert len(results) == 1
        finding = results[0]
        # Source emits the bare rule_id as check_id for top-level crashes;
        # the ".enforcement_failure" suffix variant is reserved for per-file
        # crashes raised inside execute_rule (see source line 133-144).
        assert finding.check_id == "crash_rule"
        assert finding.context["finding_type"] == "ENFORCEMENT_FAILURE"

    @pytest.mark.asyncio
    async def test_crashed_rule_ids_defaults_to_none(self, mock_context, monkeypatch):
        rule = _make_executable_rule("r1")
        execute_rule_mock = AsyncMock(return_value=[])
        self._patch_boundaries(
            monkeypatch, rules=[rule], execute_rule_mock=execute_rule_mock
        )
        executed = set()
        await run_dynamic_rules(mock_context, executed_rule_ids=executed)
        assert "r1" in executed

    @pytest.mark.asyncio
    async def test_multiple_rules_all_succeed(self, mock_context, monkeypatch):
        rules = [_make_executable_rule(f"r{i}") for i in range(3)]
        execute_rule_mock = AsyncMock(return_value=[])
        self._patch_boundaries(
            monkeypatch, rules=rules, execute_rule_mock=execute_rule_mock
        )
        executed = set()
        crashed = set()
        await run_dynamic_rules(
            mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed
        )
        assert executed == {"r0", "r1", "r2"}
        assert crashed == set()
        assert execute_rule_mock.await_count == 3

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self, mock_context, monkeypatch):
        good_rule = _make_executable_rule("good")
        bad_rule = _make_executable_rule("bad")

        good_finding = MagicMock()
        good_finding.check_id = "good.result"
        # Source iterates rules in extract_executable_rules order. Returning
        # the good finding for the first call and raising on the second
        # produces the mixed scenario without coupling tests to mock-call
        # ordering internals.
        execute_rule_mock = AsyncMock(
            side_effect=[[good_finding], RuntimeError("broken")]
        )
        self._patch_boundaries(
            monkeypatch,
            rules=[good_rule, bad_rule],
            execute_rule_mock=execute_rule_mock,
        )
        executed = set()
        crashed = set()
        results = await run_dynamic_rules(
            mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed
        )
        assert executed == {"good", "bad"}
        assert crashed == {"bad"}
        assert any(f.check_id == "good.result" for f in results)
        # Top-level crash: bare rule_id (see test_rule_crash_produces_enforcement_failure).
        assert any(
            getattr(f, "check_id", None) == "bad"
            and getattr(f, "context", {}).get("finding_type") == "ENFORCEMENT_FAILURE"
            for f in results
        )
