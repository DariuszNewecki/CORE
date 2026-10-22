"""
Tests for :mod:`~mind.governance.policy_coverage_service`.

Covers the public interface: ``PolicyCoverageReport`` and
``PolicyCoverageService``.

2026-06-07 (#572 Cat B batch 12):
- Policy/standards JSON files updated to source's v2 format. Source's
  ``_discover_rules_via_intent`` (file_path:84) reads:
    {"id": "<policy_id>", "rules": [{"id": "<rule_id>", "enforcement":
        "<lvl>", "check": {"engine": {...}}}, ...]}
  The autogen vintage emitted a flat-per-file shape with ``rule_id`` at
  the top level; source rejects those files silently (they yield zero
  rules). ``has_engine`` is now derived from ``check.engine`` presence,
  not a top-level ``engine`` key.
- Summary key drift: source emits ``rules_total``, ``rules_enforced``,
  ``rules_implementable``, ``rules_declared_only``, ``uncovered_error_rules``;
  the autogen vintage asserted on ``enforced`` / ``implementable`` /
  ``declared_only``. Assertions updated.
"""

from __future__ import annotations

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
# ID: dfa71420-d8fb-430b-aeb6-6ea17e19e2d5
def mock_path_resolver() -> MagicMock:
    """Return a mock ``PathResolver`` with commonly-used attributes."""
    resolver = MagicMock()
    resolver.repo_root = Path("/fake/repo")
    resolver.reports_dir = Path("/fake/repo/reports")
    resolver.intent_root = Path("/fake/repo/.intent")
    return resolver


@pytest.fixture
# ID: 9bf3e74d-9f8f-4790-a03d-b475d9039841
def service(mock_path_resolver: MagicMock) -> PolicyCoverageService:
    """Return a ``PolicyCoverageService`` backed by a mock path resolver."""
    return PolicyCoverageService(path_resolver=mock_path_resolver)


# ---------------------------------------------------------------------------
# PolicyCoverageReport
# ---------------------------------------------------------------------------


# ID: 73daf49e-e689-4060-9752-c459eaf980d2
class TestPolicyCoverageReport:
    """Unit tests for the ``PolicyCoverageReport`` data model."""

    # ID: 7ef67773-6a5a-4046-80e6-81aac73a68d4
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

    # ID: 1cc6c429-f3cd-4163-85a8-15ae58e47821
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

    # ID: 08ba4824-c081-49a8-8e3f-7db53965f64c
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
# PolicyCoverageService - construction / initialisation
# ---------------------------------------------------------------------------


# ID: b650fac4-d651-44d9-bcbb-b569dcd7050b
class TestPolicyCoverageServiceInit:
    """Tests for ``PolicyCoverageService.__init__``."""

    # ID: e959b986-7fcb-46ab-965a-1cf637c62a84
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

    # ID: 37f6ecde-3fd9-49a2-9e9b-ed457984ed3a
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


# ID: 4b312e69-4422-4162-89bf-fc39e03a2856
class TestRuleRef:
    """Tests for the ``_RuleRef`` helper class."""

    # ID: 416dba07-d2f7-48a1-bed5-ac6cff77032f
    def test_simple_construction(self) -> None:
        rule = _RuleRef(
            policy_id="P1", rule_id="R1", enforcement="mandatory", has_engine=True
        )
        assert rule.policy_id == "P1"
        assert rule.rule_id == "R1"
        assert rule.enforcement == "mandatory"
        assert rule.has_engine is True

    # ID: e5be1173-cfc7-46d6-bbcc-3460f7a8512c
    def test_missing_engine_flag(self) -> None:
        rule = _RuleRef(
            policy_id="P2", rule_id="R2", enforcement="advisory", has_engine=False
        )
        assert rule.has_engine is False
        assert rule.enforcement == "advisory"


# ---------------------------------------------------------------------------
# _discover_rules_via_intent
# ---------------------------------------------------------------------------


# ID: 41a22cee-0636-4fe4-9804-942d7b956631
class TestDiscoverRulesViaIntent:
    """Unit tests for the private ``_discover_rules_via_intent`` method."""

    # ID: 5a67ff3a-356d-4b36-8a45-fca8a5e4eda0
    def test_no_intent_directories(self, mock_path_resolver: MagicMock) -> None:
        """If neither policies/ nor standards/ exist, the result is an empty list."""
        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        rules = svc._discover_rules_via_intent()
        assert rules == []

    # ID: cf8e93f9-13e3-4ab7-a604-2c72bbfee735
    def test_policy_without_engine_json(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """A rule without a ``check.engine`` section has ``has_engine=False``."""
        policy_dir = tmp_path / ".intent" / "policies" / "test_policy"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r001.json"
        rule_file.write_text(
            json.dumps(
                {
                    "id": "P001",
                    "rules": [{"id": "R001", "enforcement": "mandatory"}],
                }
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

    # ID: 1d4f9314-9110-49f3-94e4-a19265093558
    def test_policy_with_engine_json(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """When ``check.engine`` is present, ``has_engine`` becomes True."""
        policy_dir = tmp_path / ".intent" / "standards" / "my_std"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "s002.json"
        rule_file.write_text(
            json.dumps(
                {
                    "id": "STD01",
                    "rules": [
                        {
                            "id": "S002",
                            "enforcement": "advisory",
                            "check": {"engine": "regex"},
                        }
                    ],
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

    # ID: ff2ceab7-4554-45cb-a6ff-ccde7c895d95
    def test_collects_from_both_search_roots(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """Rules from ``policies/`` and ``standards/`` are merged."""
        (tmp_path / ".intent" / "policies" / "pol").mkdir(parents=True)
        (tmp_path / ".intent" / "standards" / "std").mkdir(parents=True)

        pol_file = tmp_path / ".intent" / "policies" / "pol" / "p01.json"
        pol_file.write_text(
            json.dumps(
                {
                    "id": "POL",
                    "rules": [{"id": "P01", "enforcement": "mandatory"}],
                }
            )
        )
        std_file = tmp_path / ".intent" / "standards" / "std" / "s01.json"
        std_file.write_text(
            json.dumps(
                {
                    "id": "STD",
                    "rules": [{"id": "S01", "enforcement": "advisory"}],
                }
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


# ID: 0844ceb2-8615-4098-bb1b-20cbd3773fc2
class TestLoadAuditEvidence:
    """Unit tests for the private ``_load_audit_evidence`` method."""

    # ID: 45c6f3f5-7d68-4ca6-adf8-5d6a95ad86f7
    def test_no_evidence_file(self, mock_path_resolver: MagicMock) -> None:
        """Return empty set when the evidence ledger does not exist."""
        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        evidence = svc._load_audit_evidence()
        assert evidence == set()

    # ID: 51b232c1-65ad-4e83-9b42-95835f5ce34d
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

    # ID: 6b71ecba-b1d8-42bb-a87b-cf9ac38fc2d1
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


# ID: c13b6a34-d4bd-4134-8e8a-da5e461e652e
class TestRun:
    """Integration-oriented tests for the ``run`` method."""

    # ID: 1ee63fba-e8b0-42f9-8c19-ab054cf519af
    def test_happy_path_enforces_rules(
        self, tmp_path: Path, mock_path_resolver: MagicMock
    ) -> None:
        """When a rule appears in both intent and evidence, status becomes 'enforced'."""
        # Arrange evidence: rules that have been executed
        audit_dir = tmp_path / "reports" / "audit"
        audit_dir.mkdir(parents=True)
        ev_file = audit_dir / "latest_audit.json"
        ev_file.write_text(json.dumps({"executed_rules": ["R001"]}))

        # Arrange intent: rule declarations (v2 nested format)
        policy_dir = tmp_path / ".intent" / "policies" / "pol"
        policy_dir.mkdir(parents=True)
        rule_file = policy_dir / "r001.json"
        rule_file.write_text(
            json.dumps(
                {
                    "id": "P001",
                    "rules": [
                        {
                            "id": "R001",
                            "enforcement": "mandatory",
                            "check": {"engine": "any"},
                        }
                    ],
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
        assert report.summary["rules_enforced"] == 1

    # ID: 0403eaf0-5dc4-4313-8a9d-47d2029bfc28
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
                    "id": "P002",
                    "rules": [
                        {
                            "id": "R002",
                            "enforcement": "mandatory",
                            "check": {"engine": "x"},
                        }
                    ],
                }
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        report = svc.run()

        assert report.summary["rules_implementable"] == 1
        assert report.summary["rules_enforced"] == 0

    # ID: a4e1b585-b3f5-410c-8cd1-705658a75be1
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
                {
                    "id": "P003",
                    "rules": [{"id": "R003", "enforcement": "mandatory"}],
                }
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        report = svc.run()

        assert report.summary["rules_declared_only"] == 1

    # ID: 0473fd44-6992-477b-98bc-d5e75b1be7e2
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
                    "id": "P004",
                    "rules": [
                        {
                            "id": "R004",
                            "enforcement": "error",
                            "check": {"engine": "any"},
                        }
                    ],
                }
            )
        )

        mock_path_resolver.reports_dir = tmp_path / "reports"
        mock_path_resolver.intent_root = tmp_path / ".intent"
        mock_path_resolver.repo_root = tmp_path

        svc = PolicyCoverageService(path_resolver=mock_path_resolver)
        report = svc.run()

        assert report.exit_code == 1

    # ID: 2d676f01-5626-441b-bf2d-9f4bd171aea5
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


from types import SimpleNamespace
from unittest.mock import patch


# ID: 096e8018-5c77-4744-bfeb-35ff7cc6dcd6
def test_PolicyCoverageService_run() -> None:
    from mind.governance.policy_coverage_service import PolicyCoverageService

    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/repo")
    path_resolver.reports_dir = Path("/repo/reports")

    enforced_rule = SimpleNamespace(
        policy_id="POL-1",
        rule_id="RULE-1",
        enforcement="error",
        has_engine=True,
    )
    implementable_rule = SimpleNamespace(
        policy_id="POL-2",
        rule_id="RULE-2",
        enforcement="warning",
        has_engine=True,
    )
    declared_only_rule = SimpleNamespace(
        policy_id="POL-3",
        rule_id="RULE-3",
        enforcement="info",
        has_engine=False,
    )

    all_rules = [enforced_rule, implementable_rule, declared_only_rule]
    executed_rules = {"RULE-1"}

    with (
        patch.object(
            PolicyCoverageService,
            "_load_audit_evidence",
            return_value=executed_rules,
        ),
        patch.object(
            PolicyCoverageService,
            "_discover_rules_via_intent",
            return_value=all_rules,
        ),
    ):
        service = PolicyCoverageService(path_resolver)
        report = service.run()

    assert report.exit_code == 0
    assert report.summary["rules_total"] == 3
    assert report.summary["rules_enforced"] == 1
    assert report.summary["rules_implementable"] == 1
    assert report.summary["rules_declared_only"] == 1
    assert report.summary["uncovered_error_rules"] == 0
    assert len(report.records) == 3
    coverage_by_rule = {r["rule_id"]: r["coverage"] for r in report.records}
    assert coverage_by_rule == {
        "RULE-1": "enforced",
        "RULE-2": "implementable",
        "RULE-3": "declared_only",
    }
    assert str(report.repo_root) == "/repo"


# ID: 6eb5f775-0c98-48b6-8067-08ba28ad533f
def test_PolicyCoverageService() -> None:
    path_resolver = MagicMock()
    path_resolver.repo_root = MagicMock()
    path_resolver.reports_dir = MagicMock()
    path_resolver.intent_root = MagicMock()

    with (
        patch.object(
            PolicyCoverageService, "_load_audit_evidence", return_value={"R1"}
        ),
        patch.object(
            PolicyCoverageService, "_discover_rules_via_intent", return_value=[]
        ),
    ):
        service = PolicyCoverageService(path_resolver)

    assert service.repo_root is path_resolver.repo_root
    assert (
        service.evidence_path
        == path_resolver.reports_dir / "audit" / "latest_audit.json"
    )

    rule_enforced = MagicMock(
        policy_id="P1", rule_id="R1", enforcement="error", has_engine=False
    )
    rule_implementable = MagicMock(
        policy_id="P1", rule_id="R2", enforcement="warn", has_engine=True
    )
    rule_declared_only = MagicMock(
        policy_id="P2", rule_id="R3", enforcement="warn", has_engine=False
    )

    service.all_rules = [rule_enforced, rule_implementable, rule_declared_only]

    report = service.run()

    assert report.summary["rules_total"] == 3
    assert report.summary["rules_enforced"] == 1
    assert report.summary["rules_implementable"] == 1
    assert report.summary["rules_declared_only"] == 1
    assert report.summary["uncovered_error_rules"] == 0
    assert report.exit_code == 0
    assert len(report.records) == 3




# ID: a9921f6a-176a-4cbd-8d03-c56a69b62134
def test_PolicyCoverageReport():
    report = PolicyCoverageReport(
        report_id="rpt-001",
        generated_at_utc="2024-01-01T00:00:00Z",
        repo_root="/repo/root",
        summary={"total": 2, "covered": 1},
        records=[
            {"policy": "P1", "covered": True},
            {"policy": "P2", "covered": False},
        ],
        exit_code=0,
    )

    assert report.report_id == "rpt-001"
    assert report.generated_at_utc == "2024-01-01T00:00:00Z"
    assert report.repo_root == "/repo/root"
    assert report.summary == {"total": 2, "covered": 1}
    assert len(report.records) == 2
    assert report.records[0]["policy"] == "P1"
    assert report.records[1]["covered"] is False
    assert report.exit_code == 0
