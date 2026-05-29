import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Any, Optional

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
                    {"rule_id": "rule1"},
                    {"rule_id": "rule2"},
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
                    {"rule_id": "rule_a"},
                ]
            },
            "policy2": {
                "rules": [
                    {"rule_id": "rule_b"},
                    {"rule_id": "rule_c"},
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
                    {"rule_id": "dup_rule"},
                ]
            },
            "policy2": {
                "rules": [
                    {"rule_id": "dup_rule"},
                ]
            },
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 2
        assert rule_ids == ["dup_rule", "dup_rule"]

    def test_policy_with_no_rules_key(self):
        policies = {
            "policy1": {}
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    def test_policy_with_empty_rules_list(self):
        policies = {
            "policy1": {
                "rules": []
            }
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    def test_rule_without_rule_id_skipped(self):
        policies = {
            "policy1": {
                "rules": [
                    {"rule_id": "valid_rule"},
                    {"name": "no_id"},
                ]
            }
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 1
        assert rule_ids == ["valid_rule"]


class TestFindUnmappedRuleIds:
    def test_all_rules_mapped(self):
        policies = {
            "p1": {"rules": [{"rule_id": "r1"}, {"rule_id": "r2"}]}
        }
        executable = {"r1", "r2"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []

    def test_some_rules_unmapped(self):
        policies = {
            "p1": {"rules": [{"rule_id": "r1"}, {"rule_id": "r2"}, {"rule_id": "r3"}]}
        }
        executable = {"r1", "r3"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == ["r2"]

    def test_all_rules_unmapped(self):
        policies = {
            "p1": {"rules": [{"rule_id": "r1"}, {"rule_id": "r2"}]}
        }
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
            "p1": {"rules": [{"rule_id": "z_rule"}, {"rule_id": "a_rule"}, {"rule_id": "m_rule"}]}
        }
        executable = {"a_rule"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == ["m_rule", "z_rule"]

    def test_extra_executable_ids_ignored(self):
        policies = {
            "p1": {"rules": [{"rule_id": "r1"}]}
        }
        executable = {"r1", "extra_rule"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []


class TestCheckPerFileScopeCoverage:
    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.get_files.return_value = ["file1.py", "file2.py"]
        return ctx

    def make_mock_rule(self, rule_id="rule1", is_context_level=False, scope=None,
                       exclusions=None, engine="file_scanner", enforcement="blocking",
                       policy_id="pol1"):
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
        rule1 = self.make_mock_rule(rule_id="inert_a", scope=["a/*"], enforcement="blocking")
        rule2 = self.make_mock_rule(rule_id="inert_b", scope=["b/*"], enforcement="blocking")
        rule3 = self.make_mock_rule(rule_id="ok_rule", scope=["ok/*"], enforcement="blocking")
        mock_context.get_files.side_effect = [[], [], ["file.py"]]
        findings = _check_per_file_scope_coverage(mock_context, [rule1, rule2, rule3])
        assert len(findings) == 2
        check_ids = {f.check_id for f in findings}
        assert check_ids == {"inert_a.scope_inert", "inert_b.scope_inert"}

    def test_exclusions_still_empty_scope_match(self, mock_context):
        mock_context.get_files.return_value = ["src/main.py"]
        rule = self.make_mock_rule(scope=["src/*.py"], exclusions=["*.bak"], enforcement="blocking")
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []


class TestGetDynamicExecutionStats:
    def make_mock_context(self, policies=None):
        ctx = MagicMock()
        ctx.policies = policies or {}
        return ctx

    def test_no_executed_or_crashed_rules(self):
        ctx = self.make_mock_context({"pol1": {"rules": [{"rule_id": "r1"}]}})
        stats = get_dynamic_execution_stats(ctx, set())
        assert stats["total_declared"] == 1
        assert stats["total_executed"] == 0
        assert stats["unmapped_rule_ids"] == ["r1"]
        assert stats["crashed_rule_ids"] == []

    def test_all_rules_executed_none_crashed(self):
        ctx = self.make_mock_context({"pol1": {"rules": [{"rule_id": "r1"}, {"rule_id": "r2"}]}})
        stats = get_dynamic_execution_stats(ctx, {"r1", "r2"})
        assert stats["total_declared"] == 2
        assert stats["total_executed"] == 2
        assert stats["unmapped_rule_ids"] == []
        assert stats["crashed_rule_ids"] == []

    def test_with_crashed_rules(self):
        ctx = self.make_mock_context({"pol1": {"rules": [{"rule_id": "r1"}, {"rule_id": "r2"}, {"rule_id": "r3"}]}})
        stats = get_dynamic_execution_stats(ctx, {"r1", "r2"}, crashed_rule_ids={"r2"})
        assert stats["total_declared"] == 3
        assert stats["total_executed"] == 2
        assert stats["crashed_rule_ids"] == ["r2"]
        assert stats["unmapped_rule_ids"] == ["r3"]

    def test_crashed_rule_also_unmapped_not_counted_twice(self):
        ctx = self.make_mock_context({"pol1": {"rules": [{"rule_id": "r1"}, {"rule_id": "r2"}]}})
        stats = get_dynamic_execution_stats(ctx, {"r1"}, crashed_rule_ids={"r2"})
        assert stats["total_declared"] == 2
        assert stats["total_executed"] == 1
        assert stats["crashed_rule_ids"] == ["r2"]
        assert stats["unmapped_rule_ids"] == []

    def test_default_crashed_rule_ids_is_empty_set(self):
        ctx = self.make_mock_context({"pol1": {"rules": [{"rule_id": "r1"}]}})
        stats = get_dynamic_execution_stats(ctx, set())
        assert stats["crashed_rule_ids"] == []

    def test_mixed_scenario(self):
        ctx = self.make_mock_context({
            "pol1": {"rules": [{"rule_id": "r1"}, {"rule_id": "r2"}, {"rule_id": "r3"}]}
        })
        stats = get_dynamic_execution_stats(ctx, {"r1", "r2"}, crashed_rule_ids={"r1"})
        assert stats["total_declared"] == 3
        assert stats["total_executed"] == 2
        assert stats["crashed_rule_ids"] == ["r1"]
        assert stats["unmapped_rule_ids"] == ["r3"]
        assert stats["coverage_percentage"] == pytest.approx(66.6667, rel=0.001)


class TestRunDynamicRules:
    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.enforcement_loader = MagicMock()
        ctx.policies = {}
        return ctx

    @pytest.mark.asyncio
    async def test_empty_executable_rules(self, mock_context):
        executed = set()
        crashed = set()
        results = await run_dynamic_rules(mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed)
        assert executed == set()
        assert crashed == set()
        assert results == []

    @pytest.mark.asyncio
    async def test_single_rule_executes_successfully(self, mock_context):
        mock_rule = MagicMock()
        mock_rule.rule_id = "r1"
        mock_rule.engine = "file_scanner"
        mock_rule.dispatch_engine = AsyncMock(return_value=[])
        executed = set()
        crashed = set()
        mock_context.enforcement_loader.get_enforcing_rules.return_value = [mock_rule]
        results = await run_dynamic_rules(mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed)
        assert "r1" in executed
        assert "r1" not in crashed
        mock_rule.dispatch_engine.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rule_crash_produces_enforcement_failure(self, mock_context):
        mock_rule = MagicMock()
        mock_rule.rule_id = "crash_rule"
        mock_rule.engine = "file_scanner"
        mock_rule.dispatch_engine = AsyncMock(side_effect=Exception("Engine crash"))
        executed = set()
        crashed = set()
        results = await run_dynamic_rules(mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed)
        assert "crash_rule" in executed
        assert "crash_rule" in crashed
        assert len(results) == 1
        finding = results[0]
        assert finding.check_id == "crash_rule.ENFORCEMENT_FAILURE"

    @pytest.mark.asyncio
    async def test_crashed_rule_ids_defaults_to_none(self, mock_context):
        mock_rule = MagicMock()
        mock_rule.rule_id = "r1"
        mock_rule.engine = "file_scanner"
        mock_rule.dispatch_engine = AsyncMock(return_value=[])
        executed = set()
        results = await run_dynamic_rules(mock_context, executed_rule_ids=executed)
        assert "r1" in executed

    @pytest.mark.asyncio
    async def test_multiple_rules_all_succeed(self, mock_context):
        rules = []
        for i in range(3):
            rule = MagicMock()
            rule.rule_id = f"r{i}"
            rule.engine = "file_scanner"
            rule.dispatch_engine = AsyncMock(return_value=[])
            rules.append(rule)
        mock_context.enforcement_loader.get_enforcing_rules.return_value = rules
        executed = set()
        crashed = set()
        results = await run_dynamic_rules(mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed)
        assert executed == {"r0", "r1", "r2"}
        assert crashed == set()

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self, mock_context):
        good_rule = MagicMock()
        good_rule.rule_id = "good"
        good_rule.engine = "scanner"
        good_rule.dispatch_engine = AsyncMock(return_value=[MagicMock(check_id="good.result")])

        bad_rule = MagicMock()
        bad_rule.rule_id = "bad"
        bad_rule.engine = "scanner"
        bad_rule.dispatch_engine = AsyncMock(side_effect=RuntimeError("broken"))

        mock_context.enforcement_loader.get_enforcing_rules.return_value = [good_rule, bad_rule]
        executed = set()
        crashed = set()
        results = await run_dynamic_rules(mock_context, executed_rule_ids=executed, crashed_rule_ids=crashed)
        assert executed == {"good", "bad"}
        assert crashed == {"bad"}
        assert any(f.check_id == "good.result" for f in results)
        assert any(f.check_id == "bad.ENFORCEMENT_FAILURE" for f in results)
