from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.filtered_audit import run_filtered_audit


@pytest.mark.asyncio
# ID: 7ee00dd2-36e7-4542-9fbc-6b66522fae1b
async def test_run_filtered_audit():
    context = MagicMock()
    context.policies = ["policy-a"]
    context.enforcement_loader = MagicMock()
    context.repo_path = "/repo"
    context.reload_governance = MagicMock()
    context.invalidate_file_cache = MagicMock()
    context.sweep_llm_gate_cache = AsyncMock()

    rule = MagicMock()
    rule.rule_id = "rule-1"
    rule.is_context_level = False
    rule.enforcement = "advisory"

    finding = MagicMock()
    finding.as_dict = MagicMock(return_value={"check_id": "c1"})

    with (
        patch(
            "mind.governance.rule_extractor.extract_executable_rules",
            return_value=[rule],
        ),
        patch(
            "mind.governance.rule_executor.execute_rule",
            new=AsyncMock(return_value=[finding]),
        ),
        patch(
            "mind.governance.filtered_audit.normalize_file_filter",
            return_value=None,
        ),
        patch("mind.governance.filtered_audit.RuleFilter") as mock_rule_filter_cls,
    ):
        mock_rule_filter = MagicMock()
        mock_rule_filter.matches = MagicMock(return_value=True)
        mock_rule_filter_cls.return_value = mock_rule_filter

        findings, executed, stats = await run_filtered_audit(
            context, rule_ids=["rule-1"]
        )

    assert findings == [{"check_id": "c1"}]
    assert executed == {"rule-1"}
    assert stats["total_rules"] == 1
    assert stats["filtered_rules"] == 1
    assert stats["executed_rules"] == 1
    assert stats["total_findings"] == 1
    context.reload_governance.assert_called_once()
    context.invalidate_file_cache.assert_called_once()
    context.sweep_llm_gate_cache.assert_awaited_once()


from mind.governance.filtered_audit import normalize_file_filter


# ID: 5fdb75d9-eac2-45c5-90da-e7816178856b
def test_normalize_file_filter(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True)
    (repo_root / "src" / "foo.py").write_text("x = 1\n")
    (repo_root / "src" / "bar.py").write_text("y = 2\n")

    result = normalize_file_filter(
        ["src/foo.py", "./src/bar.py", str(repo_root / "src" / "foo.py")],
        repo_root,
    )

    assert result == frozenset({"src/foo.py", "src/bar.py"})

    assert normalize_file_filter(None, repo_root) is None
    assert normalize_file_filter([], repo_root) is None


from mind.governance.filtered_audit import RuleFilter


# ID: dc0e1fac-863c-4881-b17e-acf9b9fa438e
def test_RuleFilter_matches():
    rule = MagicMock()
    rule.rule_id = "RULE-123"
    rule.policy_id = "POLICY-456"

    # No filters specified -> match everything
    empty_filter = RuleFilter()
    assert empty_filter.matches(rule) is True

    # Exact rule ID match
    id_filter = RuleFilter(rule_ids=["RULE-123"])
    assert id_filter.matches(rule) is True

    # Policy ID match
    policy_filter = RuleFilter(policy_ids=["POLICY-456"])
    assert policy_filter.matches(rule) is True

    # Pattern match
    pattern_filter = RuleFilter(rule_patterns=[r"RULE-.*"])
    assert pattern_filter.matches(rule) is True

    # No match
    non_matching = RuleFilter(
        rule_ids=["OTHER"], policy_ids=["NOPE"], rule_patterns=[r"^XYZ$"]
    )
    assert non_matching.matches(rule) is False


# ID: d090bf3f-8c68-4320-bf70-4db85ef4e656
def test_RuleFilter() -> None:
    # Happy path: an unfiltered RuleFilter matches any rule.
    unfiltered = RuleFilter()
    rule = MagicMock()
    rule.rule_id = "rule-123"
    rule.policy_id = "policy-abc"
    assert unfiltered.matches(rule) is True

    # Exact rule ID match
    by_rule_id = RuleFilter(rule_ids=["rule-123"])
    assert by_rule_id.matches(rule) is True

    # Policy ID match
    by_policy = RuleFilter(policy_ids=["policy-abc"])
    assert by_policy.matches(rule) is True

    # Pattern match on rule id
    by_pattern = RuleFilter(rule_patterns=[r"rule-\d+"])
    assert by_pattern.matches(rule) is True
