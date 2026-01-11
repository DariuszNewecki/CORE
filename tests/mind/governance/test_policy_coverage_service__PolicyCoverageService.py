"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/governance/policy_coverage_service.py
- Symbol: PolicyCoverageService
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:52:08
"""

import json

from mind.governance.policy_coverage_service import (
    PolicyCoverageReport,
    PolicyCoverageService,
)


# Detected return type: PolicyCoverageReport (from run() method)
# The service is synchronous (not async), so using regular test functions


class TestPolicyCoverageService:
    """Unit tests for PolicyCoverageService"""

    def test_init_with_default_repo_root(self, tmp_path):
        """Test initialization with default repo root"""
        # Create minimal structure to avoid errors
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        # Create a mock settings object if needed, but service should handle missing files
        service = PolicyCoverageService(repo_root=tmp_path)

        assert service.repo_root == tmp_path
        assert service.evidence_path == tmp_path / "reports/audit/latest_audit.json"
        assert isinstance(service.executed_rules, set)
        assert isinstance(service.all_rules, list)

    def test_load_audit_evidence_missing_file(self, tmp_path):
        """Test loading audit evidence when file doesn't exist"""
        service = PolicyCoverageService(repo_root=tmp_path)

        # Evidence file doesn't exist in tmp_path
        assert service.executed_rules == set()

    def test_load_audit_evidence_valid_file(self, tmp_path):
        """Test loading audit evidence from valid JSON file"""
        evidence_path = tmp_path / "reports/audit/latest_audit.json"
        evidence_path.parent.mkdir(parents=True)

        evidence_data = {
            "executed_rules": ["rule_1", "rule_2", "rule_3"],
            "other_field": "value",
        }
        evidence_path.write_text(json.dumps(evidence_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        assert service.executed_rules == {"rule_1", "rule_2", "rule_3"}

    def test_load_audit_evidence_invalid_json(self, tmp_path):
        """Test loading audit evidence from invalid JSON file"""
        evidence_path = tmp_path / "reports/audit/latest_audit.json"
        evidence_path.parent.mkdir(parents=True)
        evidence_path.write_text("invalid json content", encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        assert service.executed_rules == set()

    def test_load_audit_evidence_missing_executed_rules_key(self, tmp_path):
        """Test loading audit evidence when executed_rules key is missing"""
        evidence_path = tmp_path / "reports/audit/latest_audit.json"
        evidence_path.parent.mkdir(parents=True)

        evidence_data = {"other_field": "value"}
        evidence_path.write_text(json.dumps(evidence_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        assert service.executed_rules == set()

    def test_discover_rules_via_intent_no_intent_dir(self, tmp_path):
        """Test rule discovery when .intent directory doesn't exist"""
        service = PolicyCoverageService(repo_root=tmp_path)
        assert service.all_rules == []

    def test_discover_rules_via_intent_valid_policy(self, tmp_path):
        """Test rule discovery from valid policy JSON files"""
        # Create policy structure
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        policy_data = {
            "id": "test_policy",
            "rules": [
                {
                    "id": "rule_1",
                    "enforcement": "error",
                    "check": {"engine": "test_engine"},
                },
                {
                    "id": "rule_2",
                    "enforcement": "warn",
                    "check": {"engine": "test_engine"},
                },
            ],
        }

        policy_file = policies_dir / "test_policy.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)

        assert len(service.all_rules) == 2

        # Check first rule
        rule1 = service.all_rules[0]
        assert rule1.policy_id == "test_policy"
        assert rule1.rule_id == "rule_1"
        assert rule1.enforcement == "error"
        assert rule1.has_engine

        # Check second rule
        rule2 = service.all_rules[1]
        assert rule2.policy_id == "test_policy"
        assert rule2.rule_id == "rule_2"
        assert rule2.enforcement == "warn"
        assert rule2.has_engine

    def test_discover_rules_via_intent_rule_without_engine(self, tmp_path):
        """Test rule discovery for rules without engine definition"""
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        policy_data = {
            "id": "test_policy",
            "rules": [
                {
                    "id": "rule_1",
                    "enforcement": "error",
                    # No check/engine defined
                }
            ],
        }

        policy_file = policies_dir / "test_policy.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)

        assert len(service.all_rules) == 1
        rule = service.all_rules[0]
        assert not rule.has_engine

    def test_discover_rules_via_intent_invalid_json(self, tmp_path):
        """Test rule discovery skips invalid JSON files"""
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        # Create invalid JSON file
        invalid_file = policies_dir / "invalid.json"
        invalid_file.write_text("{invalid json", encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        assert service.all_rules == []

    def test_discover_rules_via_intent_standards_dir(self, tmp_path):
        """Test rule discovery from standards directory"""
        standards_dir = tmp_path / ".intent" / "charter" / "standards"
        standards_dir.mkdir(parents=True)

        policy_data = {
            "id": "standard_1",
            "rules": [
                {
                    "id": "std_rule_1",
                    "enforcement": "error",
                    "check": {"engine": "std_engine"},
                }
            ],
        }

        policy_file = standards_dir / "standard_1.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)

        assert len(service.all_rules) == 1
        rule = service.all_rules[0]
        assert rule.policy_id == "standard_1"
        assert rule.rule_id == "std_rule_1"

    def test_run_no_rules_no_evidence(self, tmp_path):
        """Test run() with no rules and no evidence"""
        service = PolicyCoverageService(repo_root=tmp_path)
        report = service.run()

        assert isinstance(report, PolicyCoverageReport)
        assert report.summary["rules_total"] == 0
        assert report.summary["rules_enforced"] == 0
        assert report.summary["rules_implementable"] == 0
        assert report.summary["rules_declared_only"] == 0
        assert report.summary["uncovered_error_rules"] == 0
        assert report.exit_code == 0
        assert len(report.records) == 0
        assert report.repo_root == str(tmp_path)

    def test_run_enforced_rules(self, tmp_path):
        """Test run() with rules that are enforced (in evidence)"""
        # Create policy with rules
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        policy_data = {
            "id": "test_policy",
            "rules": [
                {
                    "id": "enforced_rule",
                    "enforcement": "error",
                    "check": {"engine": "test_engine"},
                },
                {
                    "id": "another_rule",
                    "enforcement": "warn",
                    "check": {"engine": "test_engine"},
                },
            ],
        }

        policy_file = policies_dir / "test_policy.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        # Create evidence with one rule executed
        evidence_path = tmp_path / "reports/audit/latest_audit.json"
        evidence_path.parent.mkdir(parents=True)

        evidence_data = {"executed_rules": ["enforced_rule"]}
        evidence_path.write_text(json.dumps(evidence_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        report = service.run()

        assert report.summary["rules_total"] == 2
        assert report.summary["rules_enforced"] == 1
        assert (
            report.summary["rules_implementable"] == 1
        )  # another_rule has engine but not enforced
        assert report.summary["rules_declared_only"] == 0
        assert (
            report.summary["uncovered_error_rules"] == 0
        )  # enforced_rule is error and enforced

        # Check records
        enforced_record = next(
            r for r in report.records if r["rule_id"] == "enforced_rule"
        )
        assert enforced_record["coverage"] == "enforced"
        assert enforced_record["covered"]

        implementable_record = next(
            r for r in report.records if r["rule_id"] == "another_rule"
        )
        assert implementable_record["coverage"] == "implementable"
        assert not implementable_record["covered"]

        assert report.exit_code == 0

    def test_run_uncovered_error_rules(self, tmp_path):
        """Test run() with error-level rules that are not enforced"""
        # Create policy with error-level rule
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        policy_data = {
            "id": "test_policy",
            "rules": [
                {
                    "id": "critical_rule",
                    "enforcement": "error",
                    "check": {"engine": "test_engine"},
                }
            ],
        }

        policy_file = policies_dir / "test_policy.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        # Evidence is empty (no rules executed)
        evidence_path = tmp_path / "reports/audit/latest_audit.json"
        evidence_path.parent.mkdir(parents=True)
        evidence_path.write_text(json.dumps({"executed_rules": []}), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        report = service.run()

        assert report.summary["rules_total"] == 1
        assert report.summary["rules_enforced"] == 0
        assert report.summary["rules_implementable"] == 1
        assert report.summary["rules_declared_only"] == 0
        assert (
            report.summary["uncovered_error_rules"] == 1
        )  # critical rule not enforced

        assert report.exit_code == 1  # Should fail due to uncovered error rule

    def test_run_declared_only_rules(self, tmp_path):
        """Test run() with rules that are declared only (no engine)"""
        # Create policy with declared-only rule
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        policy_data = {
            "id": "test_policy",
            "rules": [
                {
                    "id": "declared_rule",
                    "enforcement": "warn",
                    # No check/engine defined
                }
            ],
        }

        policy_file = policies_dir / "test_policy.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        report = service.run()

        assert report.summary["rules_total"] == 1
        assert report.summary["rules_enforced"] == 0
        assert report.summary["rules_implementable"] == 0
        assert report.summary["rules_declared_only"] == 1

        record = report.records[0]
        assert record["coverage"] == "declared_only"
        assert not record["covered"]

        assert report.exit_code == 0

    def test_run_mixed_coverage_types(self, tmp_path):
        """Test run() with mixed coverage types"""
        # Create policies with various rule types
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        policy_data = {
            "id": "mixed_policy",
            "rules": [
                {
                    "id": "enforced_error",
                    "enforcement": "error",
                    "check": {"engine": "engine1"},
                },
                {
                    "id": "uncovered_error",
                    "enforcement": "error",
                    "check": {"engine": "engine2"},
                },
                {
                    "id": "implementable_warn",
                    "enforcement": "warn",
                    "check": {"engine": "engine3"},
                },
                {
                    "id": "declared_only",
                    "enforcement": "info",
                    # No engine
                },
            ],
        }

        policy_file = policies_dir / "mixed_policy.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        # Evidence with only one rule executed
        evidence_path = tmp_path / "reports/audit/latest_audit.json"
        evidence_path.parent.mkdir(parents=True)

        evidence_data = {"executed_rules": ["enforced_error"]}
        evidence_path.write_text(json.dumps(evidence_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)
        report = service.run()

        assert report.summary["rules_total"] == 4
        assert report.summary["rules_enforced"] == 1
        assert (
            report.summary["rules_implementable"] == 2
        )  # uncovered_error + implementable_warn
        assert report.summary["rules_declared_only"] == 1
        assert report.summary["uncovered_error_rules"] == 1  # uncovered_error

        assert report.exit_code == 1  # Should fail due to uncovered error rule

    def test_run_report_structure(self, tmp_path):
        """Test the structure and data types of the generated report"""
        service = PolicyCoverageService(repo_root=tmp_path)
        report = service.run()

        # Check report has all required fields
        assert hasattr(report, "report_id")
        assert hasattr(report, "generated_at_utc")
        assert hasattr(report, "repo_root")
        assert hasattr(report, "summary")
        assert hasattr(report, "records")
        assert hasattr(report, "exit_code")

        # Check data types
        assert isinstance(report.report_id, str)
        assert len(report.report_id) == 12  # SHA256 hex digest first 12 chars

        assert isinstance(report.generated_at_utc, str)
        # Should be ISO format with UTC
        assert "Z" in report.generated_at_utc or "+00:00" in report.generated_at_utc

        assert isinstance(report.repo_root, str)
        assert isinstance(report.summary, dict)
        assert isinstance(report.records, list)
        assert isinstance(report.exit_code, int)

        # Check summary structure
        expected_summary_keys = [
            "rules_total",
            "rules_enforced",
            "rules_implementable",
            "rules_declared_only",
            "uncovered_error_rules",
        ]
        for key in expected_summary_keys:
            assert key in report.summary
            assert isinstance(report.summary[key], int)

    def test_run_enforcement_case_insensitive(self, tmp_path):
        """Test that enforcement levels are normalized to lowercase"""
        policies_dir = tmp_path / ".intent" / "policies"
        policies_dir.mkdir(parents=True)

        policy_data = {
            "id": "test_policy",
            "rules": [
                {
                    "id": "uppercase_rule",
                    "enforcement": "ERROR",  # Uppercase
                    "check": {"engine": "test_engine"},
                }
            ],
        }

        policy_file = policies_dir / "test_policy.json"
        policy_file.write_text(json.dumps(policy_data), encoding="utf-8")

        service = PolicyCoverageService(repo_root=tmp_path)

        # Check that enforcement is normalized to lowercase
        rule = service.all_rules[0]
        assert rule.enforcement == "error"  # Lowercase

        # Run report to ensure it works with lowercase enforcement
        report = service.run()
        record = report.records[0]
        assert record["enforcement"] == "error"
