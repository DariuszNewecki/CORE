"""#847/#856 — run_stateless_audit's own PASS/FAIL/DEGRADED verdict.

run_stateless_audit (the DB-free CI-gate / pre-commit path, invoked by
``core-admin code audit --offline``) computed its own PASS/FAIL-only
verdict, entirely independent of ConstitutionalAuditor._determine_verdict
and its DEGRADED semantics / ignored_finding_types carve-out. That gap
mattered specifically here: this function always builds AuditorContext
with no session_provider, so db_session is *always* None in this path —
meaning ENFORCEMENT_UNAVAILABLE findings for
runtime.worker_max_interval_within_observed (and pre-existing
ENFORCEMENT_FAILURE crash findings) are a routine outcome of exactly this
CLI command, not a theoretical one. Empirically confirmed via
`core-admin code audit --offline` before this fix: the real audit run
showed "Final Verdict: FAIL" for a db_session-unavailable finding.

The fix reuses the same governed .intent/enforcement/config/audit_verdict.yaml
ignored_finding_types vocabulary ConstitutionalAuditor consults (via
load_audit_verdict_policy), rather than inventing a second closed
vocabulary -- a blocking-severity finding whose finding_type is in that
list degrades the verdict; a genuine blocking finding without that marker
still fails; no blocking findings at all still passes.

Exit-code behavior is unchanged by this fix: the CLI's blocking-gate
decision (src/cli/resources/code/audit.py::_run_offline_audit) is
severity-based (any finding >= the severity floor), not verdict-string-
based, so DEGRADED and FAIL both still exit non-zero. This file tests
only the "verdict"/"passed" label truthfulness, mirroring
test_stateless_audit__fails_closed.py's own mocked-run_filtered_audit
pattern for the sibling ERROR-verdict proofs.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mind.governance.executable_rule import ExecutableRule
from mind.governance.stateless_audit import run_stateless_audit


def _rule(rule_id: str, engine: str = "regex_gate") -> ExecutableRule:
    return ExecutableRule(rule_id=rule_id, engine=engine, params={}, enforcement="blocking")


def _unavailable_finding(rule_id: str) -> dict:
    return {
        "check_id": rule_id,
        "severity": "BLOCK",
        "evidence_class": "ATTESTED",
        "message": f"{rule_id} could not run: db_session unavailable",
        "file_path": "none",
        "line_number": None,
        "context": {
            "finding_type": "ENFORCEMENT_UNAVAILABLE",
            "reason": "db_session_unavailable",
        },
        "details": {"finding_type": "ENFORCEMENT_UNAVAILABLE"},
    }


def _crash_finding(rule_id: str) -> dict:
    return {
        "check_id": f"{rule_id}.enforcement_failure",
        "severity": "BLOCK",
        "evidence_class": "ATTESTED",
        "message": f"ENFORCEMENT_FAILURE: rule {rule_id} crashed",
        "file_path": "none",
        "line_number": None,
        "context": {"finding_type": "ENFORCEMENT_FAILURE"},
        "details": {"finding_type": "ENFORCEMENT_FAILURE"},
    }


def _genuine_violation(rule_id: str) -> dict:
    return {
        "check_id": rule_id,
        "severity": "BLOCK",
        "evidence_class": "PROVEN",
        "message": "a real constitutional violation",
        "file_path": "src/x.py",
        "line_number": 1,
        "context": {"some_key": "some_value"},
        "details": {"some_key": "some_value"},
    }


async def _run(findings: list[dict], tmp_path: Path):
    intent_repo = MagicMock()
    with (
        patch(
            "mind.governance.stateless_audit.extract_executable_rules",
            return_value=[_rule("some.rule")],
        ),
        patch(
            "mind.governance.stateless_audit._count_declared_rules",
            return_value=1,
        ),
        patch(
            "mind.governance.stateless_audit.run_filtered_audit",
            new=AsyncMock(return_value=(findings, {"some.rule"}, {})),
        ),
    ):
        return await run_stateless_audit(intent_repo, tmp_path)


async def test_blocking_unavailable_finding_yields_degraded(tmp_path: Path) -> None:
    """Governor ruling 3: a blocking ENFORCEMENT_UNAVAILABLE finding makes
    this path's verdict DEGRADED -- never PASS, never FAIL."""
    result = await _run([_unavailable_finding("runtime.worker_max_interval_within_observed")], tmp_path)
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False


async def test_blocking_crash_finding_yields_degraded(tmp_path: Path) -> None:
    """Governor ruling 4: a crash (pre-existing ENFORCEMENT_FAILURE marker)
    also degrades this path -- proving the fix isn't scoped only to the
    new unavailable case, it closes the same pre-existing gap for crashes."""
    result = await _run([_crash_finding("some.rule")], tmp_path)
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False


async def test_genuine_blocking_violation_yields_fail(tmp_path: Path) -> None:
    """A real violation with no ignored finding_type still fails -- DEGRADED
    must not swallow genuine, known non-compliance."""
    result = await _run([_genuine_violation("some.rule")], tmp_path)
    assert result["verdict"] == "FAIL"
    assert result["passed"] is False


async def test_no_blocking_findings_yields_pass(tmp_path: Path) -> None:
    result = await _run([], tmp_path)
    assert result["verdict"] == "PASS"
    assert result["passed"] is True


async def test_mixed_unavailable_and_genuine_yields_degraded_not_fail(
    tmp_path: Path,
) -> None:
    """Same precedence as ConstitutionalAuditor._determine_verdict (ADR-156
    D1a): DEGRADED preconditions take precedence over FAIL, proven here
    too -- a genuine violation alongside an unavailable one must not mask
    the DEGRADED signal as an ordinary FAIL."""
    result = await _run(
        [
            _unavailable_finding("runtime.worker_max_interval_within_observed"),
            _genuine_violation("some.rule"),
        ],
        tmp_path,
    )
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False


async def test_policy_load_failure_yields_degraded_even_with_no_findings(
    tmp_path: Path,
) -> None:
    """ADR-005 S3: DEGRADED must never be silently treated as PASS, even
    when the audit-verdict policy itself fails to load and there happen to
    be no other blocking findings to fall back on."""
    with patch(
        "mind.governance.stateless_audit.load_audit_verdict_policy",
        return_value={"_error": True, "reason": "boom"},
    ):
        result = await _run([], tmp_path)
    assert result["verdict"] == "DEGRADED"
    assert result["passed"] is False


async def test_advisory_unavailable_finding_does_not_degrade(tmp_path: Path) -> None:
    """Governor ruling 6: an advisory rule's unavailable finding carries
    INFO severity (not BLOCK, per rule_executor's per-rule severity
    mapping) and so never reaches this function's blocking_findings filter
    in the first place -- the audit stays PASS."""
    info_unavailable = {
        "check_id": "quality.security_audit",
        "severity": "INFO",
        "evidence_class": "ATTESTED",
        "message": "quality.security_audit could not run: pip-audit missing",
        "file_path": "System",
        "line_number": None,
        "context": {
            "finding_type": "ENFORCEMENT_UNAVAILABLE",
            "reason": "tool_not_installed",
        },
        "details": {"finding_type": "ENFORCEMENT_UNAVAILABLE"},
    }
    result = await _run([info_unavailable], tmp_path)
    assert result["verdict"] == "PASS"
    assert result["passed"] is True
