"""
Tests for :mod:`~mind.governance.policy_coverage_service`.

Covers the public interface: ``PolicyCoverageReport`` and
``PolicyCoverageService``.  All symbols referenced here exist in the
target source file shown in the architectural context.  No symbols from
other modules are imported without being explicitly present in the
available dependency section.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mind.governance.policy_coverage_service import (
    PolicyCoverageReport,
    PolicyCoverageService,
    _RuleRef,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_path_resolver() -> MagicMock:
    """Return a mock ``PathResolver`` with commonly-used attributes."""
    resolver = MagicMock()
    resolver.repo_root = Path("/fake/repo")
    resolver.reports_dir = Path("/fake/repo/reports")
    resolver.intent_root = Path("/fake/repo/.intent")
    return resolver


@pytest.fixture
def service(mock_path_resolver: MagicMock) -> PolicyCoverageService:
    """Return a ``PolicyCoverageService`` backed by a mock path resolver."""
    return PolicyCoverageService(path_resolver=mock_path_resolver)


# ---------------------------------------------------------------------------
# PolicyCoverageReport
# ---------------------------------------------------------------------------


class TestPolicyCoverageReport:
    """Unit tests for the ``PolicyCoverageReport`` data model."""

    def test_default_construction(self) -> None:
        """All fields must be provided (no defaults)."""
        report = PolicyCoverageReport(
            report_id="cov-001",
            generated_at_utc="2025-01-01T00:00:00Z",
            repo_root="/tmp/repo",
            summary={"enforced": 2, "implementable": 3, "declared_only": 1},
            records=[
                {"rule_id": "R01", "status": "enforced"},
            ],
            exit_code=0,
        )
        assert report.report_id == "cov-001"
        assert report.generated_at_utc == "2025-01-01T00:00:00Z"
        assert report.repo_root == "/tmp/repo"
        assert report.summary["enforced"] == 2
        assert len(report.records) == 1
        assert report.exit_code == 0

    def test_fields_accept_varied_types(self) -> None:
        """``records`` and ``summary`` should handle arbitrary dicts."""
        record: dict[str, Any] = {"id": 42, "tags": ["a", "b"]}
        report = PolicyCoverageReport(
            report_id="r2",
            generated_at_utc="now",
            repo_root=".",
            summary={"any_key": 0},
            records=[record],
            exit_code=1,
        )
        assert report.records[0]["id"] == 42
        assert report.summary["any_key"] == 0

    def test_repr_includes_key_fields(self) -> None:
        """The repr should mention at least the report_id."""
        report = PolicyCoverageReport(
            report_id="id-abc",
            generated_at_utc="ts",
            repo_root=".",
            summary={},
            records=[],
            exit_code=0,
        )
        r = repr(report)
        assert "PolicyCoverageReport" in r
        assert "id-abc" in r


# ---------------------------------------------------------------------------
# PolicyCoverageService – construction / initialisation
# ---------------------------------------------------------------------------


class TestPolicyCoverageServiceInit:
    """Tests for ``PolicyCoverageService.__init__``."""

    def test_stores_path_resolver_attributes(
        self, mock_path_resolver: MagicMock
    ) -> None:
        """The constructor should copy repo_root and derive evidence_path."""
        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        assert svc.repo_root == mock_path_resolver.repo_root
        expected_evidence = (
            mock_path_resolver.reports_dir / "audit" / "latest_audit.json"
        )
        assert svc.evidence_path == expected_evidence

    def test_init_invokes_discovery_and_loading(
        self, mock_path_resolver: MagicMock
    ) -> None:
        """The constructor should call ``_discover_rules_via_intent`` and
        ``_load_audit_evidence`` (we verify by checking that internal
        attributes are populated)."""
        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        # After __init__ the service has loaded these collections
        assert hasattr(svc, "executed_rules")
        assert hasattr(svc, "all_rules")
        # all_rules should be a list (may be empty if no intent files)
        assert isinstance(svc.all_rules, list)
        # executed_rules should be a set (may be empty if no evidence file exists)
        assert isinstance(svc.executed_rules, set)


# ---------------------------------------------------------------------------
# _RuleRef (internal helper)
# ---------------------------------------------------------------------------


class TestRuleRef:
    """Tests for the ``_RuleRef`` helper class."""

    def test_simple_construction(self) -> None:
        rule = _RuleRef(
            policy_id="P1", rule_id="R1", enforcement="mandatory", has_engine=True
        )
        assert rule.policy_id == "P1"
        assert rule.rule_id == "R1"
        assert rule.enforcement == "mandatory"
        assert rule.has_engine is True

    def test_missing_engine_flag(self) -> None:
        rule = _RuleRef(
            policy_id="P2", rule_id="R2", enforcement="advisory", has_engine=False
        )
        assert rule.has_engine is False
        assert rule.enforcement == "advisory"


# ---------------------------------------------------------------------------
# _discover_rules_via_intent
# ---------------------------------------------------------------------------


class TestDiscoverRulesViaIntent:
    """Unit tests for the private ``_discover_rules_via_intent`` method."""

    def test_no_intent_directories(self, mock_path_resolver: MagicMock) -> None:
        """If neither policies/ nor standards/ exist, the result is an empty list."""
        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        rules = svc._discover_rules_via_intent()
        assert rules == []

    def test_policy_without_engine_json(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """A rule JSON that lacks an 'engine' key should set ``has_engine`` to False."""
        policy_dir = tmp_path / ".intent" / "policies" / "test_policy"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r001.json"
        rule_file.write_text(
            json.dumps(
                {"rule_id": "R001", "enforcement": "mandatory", "policy_id": "P001"}
            )
        )

        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.reports_dir = tmp_path / "reports"
        (mock_path_resolver.reports_dir / "audit").mkdir(parents=True)

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        rules = svc._discover_rules_via_intent()
        assert len(rules) == 1
        assert rules[0].rule_id == "R001"
        assert rules[0].has_engine is False

    def test_policy_with_engine_json(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """When engine section present, ``has_engine`` becomes True."""
        policy_dir = tmp_path / ".intent" / "standards" / "my_std"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "s002.json"
        rule_file.write_text(
            json.dumps(
                {
                    "rule_id": "S002",
                    "enforcement": "advisory",
                    "policy_id": "STD01",
                    "engine": {"type": "regex", "pattern": ".*"},
                }
            )
        )

        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.reports_dir = tmp_path / "reports"
        (mock_path_resolver.reports_dir / "audit").mkdir(parents=True)

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        rules = svc._discover_rules_via_intent()
        assert len(rules) == 1
        assert rules[0].has_engine is True

    def test_collects_from_both_search_roots(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """Rules from ``policies/`` and ``standards/`` are merged."""
        (tmp_path / ".intent" / "policies" / "pol").mkdir(parents=True)
        (tmp_path / ".intent" / "standards" / "std").mkdir(parents=True)

        pol_file = tmp_path / ".intent" / "policies" / "pol" / "p01.json"
        pol_file.write_text(
            json.dumps(
                {"rule_id": "P01", "enforcement": "mandatory", "policy_id": "POL"}
            )
        )
        std_file = tmp_path / ".intent" / "standards" / "std" / "s01.json"
        std_file.write_text(
            json.dumps(
                {"rule_id": "S01", "enforcement": "advisory", "policy_id": "STD"}
            )
        )

        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.reports_dir = tmp_path / "reports"
        (mock_path_resolver.reports_dir / "audit").mkdir(parents=True)

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        rules = svc._discover_rules_via_intent()
        rule_ids = {r.rule_id for r in rules}
        assert "P01" in rule_ids
        assert "S01" in rule_ids


# ---------------------------------------------------------------------------
# _load_audit_evidence
# ---------------------------------------------------------------------------


class TestLoadAuditEvidence:
    """Unit tests for the private ``_load_audit_evidence`` method."""

    def test_no_evidence_file(self, mock_path_resolver: MagicMock) -> None:
        """Return empty set when the evidence ledger does not exist."""
        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        evidence = svc._load_audit_evidence()
        assert evidence == set()

    def test_evidence_file_with_executed_rules(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """Return set of rule IDs when the file contains ``executed_rules``."""
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        evidence_file = audit_dir / "latest_audit.json"
        evidence_file.write_text(json.dumps({"executed_rules": ["R1", "R2", "R3"]}))

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        evidence = svc._load_audit_evidence()
        assert evidence == {"R1", "R2", "R3"}

    def test_malformed_evidence_file(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """Return empty set when the JSON is invalid (and log a warning)."""
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        evidence_file = audit_dir / "latest_audit.json"
        evidence_file.write_text("not valid json")

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        evidence = svc._load_audit_evidence()
        assert evidence == set()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


class TestRun:
    """Integration-oriented tests for the ``run`` method."""

    def test_happy_path_enforces_rules(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """When a rule appears in both intent and evidence, status becomes 'enforced'."""
        # Arrange evidence: rules that have been executed
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        ev_file = audit_dir / "latest_audit.json"
        ev_file.write_text(json.dumps({"executed_rules": ["R001"]}))

        # Arrange intent: rule declarations
        policy_dir = tmp_path / ".intent" / "policies" / "pol"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r001.json"
        rule_file.write_text(
            json.dumps(
                {
                    "rule_id": "R001",
                    "enforcement": "mandatory",
                    "policy_id": "P001",
                    "engine": {},
                }
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        report = svc.run()

        assert isinstance(report, PolicyCoverageReport)
        assert report.repo_root == str(tmp_path)
        assert report.summary.get("enforced", 0) == 1

    def test_implementable_rule_has_engine_but_not_executed(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """Rule with engine but absent from evidence is 'implementable'."""
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        ev_file = audit_dir / "latest_audit.json"
        ev_file.write_text(json.dumps({"executed_rules": []}))

        policy_dir = tmp_path / ".intent" / "policies" / "pol"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r002.json"
        rule_file.write_text(
            json.dumps(
                {
                    "rule_id": "R002",
                    "enforcement": "mandatory",
                    "policy_id": "P002",
                    "engine": {"type": "x"},
                }
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        report = svc.run()

        assert report.summary.get("implementable", 0) == 1
        assert report.summary.get("enforced", 0) == 0

    def test_declared_only_rule_has_no_engine_and_not_executed(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """Rule without engine and absent from evidence is 'declared_only'."""
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        ev_file = audit_dir / "latest_audit.json"
        ev_file.write_text(json.dumps({"executed_rules": []}))

        policy_dir = tmp_path / ".intent" / "policies" / "pol"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r003.json"
        rule_file.write_text(
            json.dumps(
                {"rule_id": "R003", "enforcement": "mandatory", "policy_id": "P003"}
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        report = svc.run()

        assert report.summary.get("declared_only", 0) == 1

    def test_exit_code_nonzero_when_uncovered_errors_exist(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """If a rule with enforcement 'error' is not enforced, exit_code should be 1."""
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        ev_file = audit_dir / "latest_audit.json"
        ev_file.write_text(json.dumps({"executed_rules": []}))

        policy_dir = tmp_path / ".intent" / "policies" / "pol"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r004.json"
        rule_file.write_text(
            json.dumps(
                {
                    "rule_id": "R004",
                    "enforcement": "error",
                    "policy_id": "P004",
                    "engine": {},
                }
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        report = svc.run()

        assert report.exit_code == 1

    def test_exit_code_zero_when_no_uncovered_errors(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """All 'error' rules enforced -> exit_code 0."""
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        ev_file = audit_dir / "latest_audit.json"
        ev_file.write_text(json.dumps({"executed_rules": ["R005"]}))

        policy_dir = tmp_path / ".intent" / "policies" / "pol"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r005.json"
        rule_file.write_text(
            json.dumps(
                {
                    "rule_id": "R005",
                    "enforcement": "error",
                    "policy_id": "P005",
                    "engine": {},
                }
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path
