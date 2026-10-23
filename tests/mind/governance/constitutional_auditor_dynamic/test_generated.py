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


# ID: bd5a2b94-9eaa-47df-a7b4-396bcee82965
class TestCountTotalDeclaredRules:
    # ID: 798c5c4c-cd61-42d4-9a0f-0c2b71c17843
    def test_empty_policies(self):
        policies = {}
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    # ID: e98ee0e0-22a9-433d-be84-0e7543be8afd
    def test_invalid_policy_data_skipped(self):
        policies = {
            "policy1": "not a dict",
            "policy2": None,
        }
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    # ID: 7dc07f1f-9c78-4287-9742-872df292118e
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

    # ID: 0a63b459-0512-4749-a922-ec3b3274187f
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

    # ID: 743389e7-43e8-4f13-b8a7-08cd85121e79
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

    # ID: 17115820-1ce9-48cc-aa21-1228976bb6cb
    def test_policy_with_no_rules_key(self):
        policies = {"policy1": {}}
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    # ID: 2c741d55-cdf0-43a7-a437-9b53183b81cb
    def test_policy_with_empty_rules_list(self):
        policies = {"policy1": {"rules": []}}
        total, rule_ids = _count_total_declared_rules(policies)
        assert total == 0
        assert rule_ids == []

    # ID: 55404d77-ed9b-48ff-8fe8-bb3cb8cb60da
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


# ID: 89a322d7-e633-4e45-87e8-04735e372dca
class TestFindUnmappedRuleIds:
    # ID: eca0fb6c-b51e-41cd-bdcd-d78d2e802428
    def test_all_rules_mapped(self):
        policies = {"p1": {"rules": [{"id": "r1"}, {"id": "r2"}]}}
        executable = {"r1", "r2"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []

    # ID: d4cb28b2-a530-4060-a74b-8304b0421909
    def test_some_rules_unmapped(self):
        policies = {"p1": {"rules": [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]}}
        executable = {"r1", "r3"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == ["r2"]

    # ID: 0b48c985-6c1e-4056-a678-d13045cb122a
    def test_all_rules_unmapped(self):
        policies = {"p1": {"rules": [{"id": "r1"}, {"id": "r2"}]}}
        executable = set()
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == ["r1", "r2"]

    # ID: 48b6ea2e-7b83-4b97-b21c-a619c173eebc
    def test_no_rules_declared(self):
        policies = {}
        executable = {"some_rule"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []

    # ID: 97b18fe7-44b0-4444-b2fc-b5b9dc7c9aa8
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

    # ID: 4412ac40-7d87-4f63-8ef6-3a18deefb1c7
    def test_extra_executable_ids_ignored(self):
        policies = {"p1": {"rules": [{"id": "r1"}]}}
        executable = {"r1", "extra_rule"}
        unmapped = _find_unmapped_rule_ids(policies, executable)
        assert unmapped == []


# ID: 8ac72a4b-b6f2-42a2-8a11-a7acf8fcc18a
class TestCheckPerFileScopeCoverage:
    @pytest.fixture
    # ID: 95d48ac6-6035-4b8f-9ff8-7ea3f013f3da
    def mock_context(self):
        ctx = MagicMock()
        ctx.get_files.return_value = ["file1.py", "file2.py"]
        return ctx

    # ID: 625ccd3c-b6ac-4155-ab8f-066a0c537644
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

    # ID: b882c111-83de-4713-8bc8-a75338749771
    def test_no_executable_rules(self, mock_context):
        findings = _check_per_file_scope_coverage(mock_context, [])
        assert findings == []

    # ID: 46fdea07-09d3-4525-8ede-fd0382a5f744
    def test_context_level_rule_excluded(self, mock_context):
        rule = self.make_mock_rule(is_context_level=True)
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    # ID: d3ae8b35-fccd-4042-8f19-876a3ecdad93
    def test_passive_engine_excluded(self, mock_context):
        rule = self.make_mock_rule(engine="passive_gate")
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    # ID: b8ebfcb2-71f3-4d60-ac26-3ddbb1325fe5
    def test_empty_scope_excluded(self, mock_context):
        rule = self.make_mock_rule(scope=[])
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    # ID: 59a56bed-9376-4f47-a46e-a27d64b89122
    def test_non_blocking_rule_excluded(self, mock_context):
        for enforcement in ["advisory", "reporting", "info"]:
            rule = self.make_mock_rule(enforcement=enforcement)
            findings = _check_per_file_scope_coverage(mock_context, [rule])
            assert findings == [], f"failed for enforcement={enforcement}"

    # ID: ac6bbe6b-336b-4fe9-b7d5-14f0523bd735
    def test_rule_scope_has_match(self, mock_context):
        mock_context.get_files.return_value = ["src/main.py"]
        rule = self.make_mock_rule(scope=["src/*.py"], enforcement="blocking")
        findings = _check_per_file_scope_coverage(mock_context, [rule])
        assert findings == []

    # ID: 4b34ce91-2cd4-4165-a3b5-1e5f2915aea4
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

    # ID: a22e5cc0-d643-4564-bdef-0475a5ff0b7e
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

    # ID: ac102aa0-405b-4811-9a12-3c3f50da366a
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


# ID: a4d84ec2-8a7f-4be1-b647-416fd24f68d4
class TestGetDynamicExecutionStats:
    # ID: 381107a2-b362-4c53-a99e-13946c781959
    def make_mock_context(self, policies=None):
        ctx = MagicMock()
        ctx.policies = policies or {}
        return ctx

    # ID: eaade599-d3fc-4751-8762-0e082f082506
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

    # ID: a666de74-f17a-4437-9f02-3557b3594f23
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

    # ID: 817fb6d9-0c19-4dd6-87cb-3d4e011052aa
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

    # ID: 3a47b501-2efb-4c71-b898-dccf40785a61
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

    # ID: d5c4f8d6-0269-4cda-a821-a01ea97583ee
    def test_default_crashed_rule_ids_is_empty_set(self, monkeypatch):
        ctx = self.make_mock_context({"pol1": {"rules": [{"id": "r1"}]}})
        monkeypatch.setattr(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            lambda *a, **k: [],
        )
        stats = get_dynamic_execution_stats(ctx, set())
        assert stats["crashed_rule_ids"] == []

    # ID: 1aa4a875-a59c-4755-9628-4a16ec762702
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


# ID: 1212cdfe-b611-472a-abdc-6019b03a12aa
class TestRunDynamicRules:
    @pytest.fixture
    # ID: b915feb3-1c2a-4a50-9f10-4e58c9c7e6e8
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

    # ID: 5fa90cb1-7f7a-472e-be6b-9097e099be30
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

    # ID: b4091dda-9674-4d25-bd92-0914d20db001
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

    # ID: 005c5ee7-226d-408f-a352-0e85c3ba298e
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

    # ID: 10f1c18e-7cdd-48fe-aff0-9eafd01d941c
    async def test_crashed_rule_ids_defaults_to_none(self, mock_context, monkeypatch):
        rule = _make_executable_rule("r1")
        execute_rule_mock = AsyncMock(return_value=[])
        self._patch_boundaries(
            monkeypatch, rules=[rule], execute_rule_mock=execute_rule_mock
        )
        executed = set()
        await run_dynamic_rules(mock_context, executed_rule_ids=executed)
        assert "r1" in executed

    # ID: a4dcf1b9-9f2c-4ef7-9080-3f7550952d47
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

    # ID: d79b30c2-ec56-4fc6-b7b0-91d236cd6a3a
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


from types import SimpleNamespace
from unittest.mock import patch


# ID: fe2b510e-cc55-4980-8965-8a7990460170
def test_get_dynamic_execution_stats():
    context = SimpleNamespace(policies=MagicMock(), enforcement_loader=MagicMock())

    executable_rules = [
        SimpleNamespace(rule_id="R1", enforcement="blocking", is_context_level=True),
        SimpleNamespace(rule_id="R2", enforcement="advisory", is_context_level=False),
        SimpleNamespace(rule_id="R3", enforcement="blocking", is_context_level=False),
    ]

    with (
        patch(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            return_value=executable_rules,
        ),
        patch(
            "mind.governance.constitutional_auditor_dynamic._count_total_declared_rules",
            return_value=(5, 0),
        ),
        patch(
            "mind.governance.constitutional_auditor_dynamic._mapping_required_rule_ids",
            return_value={"R1", "R2", "R3"},
        ),
        patch(
            "mind.governance.constitutional_auditor_dynamic._find_unmapped_rule_ids",
            return_value=["Rx"],
        ),
    ):
        stats = get_dynamic_execution_stats(
            context=context,
            executed_rule_ids={"R1", "R2", "R3"},
            crashed_rule_ids={"R3"},
            unavailable_rule_ids={"R1"},
        )

    assert stats["total_declared_rules"] == 5
    assert stats["mapping_required_rules"] == 3
    assert stats["total_executable_rules"] == 3
    assert stats["unmapped_rules"] == 1
    assert stats["unmapped_rule_ids"] == ["Rx"]
    assert stats["executed_dynamic_rules"] == 3
    assert stats["cleanly_executed_rules"] == 2
    assert stats["crashed_rules"] == 1
    assert stats["crashed_rule_ids"] == ["R3"]
    assert stats["unavailable_rules"] == 1
    assert stats["unavailable_rule_ids"] == ["R1"]
    assert stats["blocking_unavailable_rules"] == 1
    assert stats["blocking_unavailable_rule_ids"] == ["R1"]
    assert stats["context_level_rule_ids"] == ["R1"]
    assert stats["per_file_rule_ids"] == ["R2", "R3"]
    assert stats["effective_coverage_percent"] == 67
    assert stats["mapped_coverage_percent"] == 67
    assert stats["coverage_percent"] == stats["mapped_coverage_percent"]
    assert "stats_error" not in stats


import pytest


@pytest.mark.asyncio
# ID: 6ca11ff8-2b8e-4bc7-93f4-ba7a970912c1
async def test_run_dynamic_rules():
    from mind.governance.constitutional_auditor_dynamic import run_dynamic_rules

    context = MagicMock()
    context.policies = MagicMock()
    context.enforcement_loader = MagicMock()

    rule = MagicMock()
    rule.rule_id = "RULE-1"
    rule.engine = "static"
    rule.policy_id = "POLICY-1"

    finding1 = MagicMock()
    finding1.check_id = "RULE-1"
    finding1.context = {}

    fake_engine = MagicMock()
    fake_engine.__class__ = type("StaticEngine", (), {})

    executed_rule_ids: set[str] = set()
    crashed_rule_ids: set[str] = set()
    unavailable_rule_ids: set[str] = set()

    with (
        patch(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            return_value=[rule],
        ),
        patch(
            "mind.governance.constitutional_auditor_dynamic._check_per_file_scope_coverage",
            return_value=[],
        ),
        patch(
            "mind.logic.engines.registry.EngineRegistry.get",
            return_value=fake_engine,
        ),
        patch(
            "mind.governance.rule_executor.execute_rule",
            new=AsyncMock(return_value=[finding1]),
        ),
    ):
        findings = await run_dynamic_rules(
            context,
            executed_rule_ids=executed_rule_ids,
            crashed_rule_ids=crashed_rule_ids,
            unavailable_rule_ids=unavailable_rule_ids,
        )

    assert findings == [finding1]
    assert executed_rule_ids == {"RULE-1"}
    assert crashed_rule_ids == set()
    assert unavailable_rule_ids == set()
