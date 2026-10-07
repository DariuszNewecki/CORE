# src/mind/logic/engines/workflow_gate/checks/quality.py

"""Universal wrapper for external industrial quality tools (ADR-098).

CONSTITUTIONAL ALIGNMENT (ADR-098 D1/D2): aggregate quality gates emit one
``StructuredViolation`` per affected file — not one collapsed string for the
whole tool run. The audit row-count then equals the number of affected files
(mypy: ~290) instead of 1, and each finding carries structured occurrence
data (``issue_count``, ``sample_issues``, ``tool``, ``first_issue_line``) so
the renderer can surface the iceberg tail. Severity is NOT set here: the
dispatch layer (``rule_executor._map_enforcement_to_severity``) derives it
from the rule's declared ``enforcement`` and overrides every finding.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import (
    StructuredViolation,
    WorkflowCheck,
)
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import run_command_async


logger = getLogger(__name__)

_CFG = load_operational_config().workflow_gate

# Cap on raw issue strings stored per finding (ADR-098 D2). The full output
# remains reproducible by re-running the tool; the payload stays bounded.
_SAMPLE_CAP = 10

# Pattern: "src/foo.py:36: error: message  [code]" (column is optional).
_MYPY_LINE = re.compile(
    r"^(?P<file>[^:]+?\.py):(?P<line>\d+):(?:\d+:)?\s*error:\s*(?P<msg>.*)$"
)

# pytest --collect-only: "ERROR collecting tests/foo.py" / "tests/foo.py:12: in ...".
# The leading (?<!\w) rejects a match starting mid-identifier — without it,
# "_pytest/terminal.py" (pytest's own package, e.g. in a venv traceback line
# during an INTERNALERROR) matches "test/terminal.py" from the "test" tail
# of "_pytest", misattributing pytest's internals to a fake project file.
_PYTEST_ERROR = re.compile(r"(?<!\w)(?P<file>(?:tests?|src)/[^\s:]+?\.py)")


# ID: e56a1a25-9a1e-4938-b6fa-34f7263be922
class QualityGateCheck(WorkflowCheck):
    """Universal wrapper for external industrial quality tools."""

    def __init__(self, path_resolver: PathResolver, check_type: str, cmd: list[str]):
        self._paths = path_resolver
        self.check_type = check_type
        self.cmd = cmd

    # ID: 27f1838d-001f-4f3e-aea9-7c651fea7a62
    async def verify(
        self, file_path: Path | None, params: dict[str, Any]
    ) -> Sequence[str | StructuredViolation]:
        try:
            result = await asyncio.wait_for(
                run_command_async(self.cmd, cwd=self._paths.repo_root),
                timeout=_CFG.quality_timeout_sec,
            )

            if result.returncode != 0:
                if self.check_type == "security_check":
                    return self._parse_pip_audit(result.stdout, result.stderr)
                output = result.stdout or result.stderr
                return self._parse_output(output)
        except TimeoutError:
            # run_command_async kills and reaps the child when wait_for
            # cancels it, so a timed-out tool (e.g. pytest_check, which writes
            # to the shared .coverage/reports/htmlcov store) does not keep
            # running past the point this method has given up and returned.
            logger.warning(
                "%s timed out after %ss; subprocess killed",
                self.check_type,
                _CFG.quality_timeout_sec,
            )
            # A gate that ran out of time found nothing either way: compliance
            # is UNKNOWN, not violated (#876). Same shape as tool-absence
            # below, so blocking rules route to DEGRADED, never FAIL or PASS.
            return [
                self._unavailable(
                    reason="timeout",
                    message=(
                        f"Quality gate {self.check_type} did not complete within "
                        f"{_CFG.quality_timeout_sec}s. Compliance status UNKNOWN "
                        f"for this rule — not a violation, not a pass."
                    ),
                    timeout_sec=_CFG.quality_timeout_sec,
                )
            ]
        except FileNotFoundError as exc:
            # Tool not installed in this environment (the F-10.3 Action's
            # slim Docker image ships without mypy/pytest/pip-audit by
            # design). #549 made this a silent compliant pass to protect
            # GitHub's per-check-run annotation budget; #847 found that
            # trade indistinguishable from a genuine clean result for a
            # blocking rule (G9: "crashes degrade, never comply"). One
            # aggregated ENFORCEMENT_UNAVAILABLE finding per rule preserves
            # the #549 annotation-budget win (still exactly one finding,
            # not one per affected file) while making tool-absence visible
            # to the dispatch layer as unavailable evidence, not a pass —
            # rule_executor / audit_verdict route it to DEGRADED for
            # blocking rules and leave it as a visible, non-blocking signal
            # for advisory/reporting rules.
            tool_name = exc.filename or self.cmd[0]
            logger.debug(
                "%s: tool '%s' not installed in this environment (%s) — "
                "surfacing as ENFORCEMENT_UNAVAILABLE",
                self.check_type,
                tool_name,
                exc,
            )
            return [
                self._unavailable(
                    reason="tool_not_installed",
                    message=(
                        f"Quality gate {self.check_type} could not run: tool "
                        f"'{tool_name}' is not installed in this environment. "
                        f"Compliance status UNKNOWN for this rule — not a pass."
                    ),
                    tool=tool_name,
                )
            ]
        except Exception as e:
            return [f"Gate {self.check_type} error: {e!s}"]
        return []

    def _unavailable(
        self, reason: str, message: str, **extra: Any
    ) -> StructuredViolation:
        """One ENFORCEMENT_UNAVAILABLE finding: the gate could not decide."""
        context: dict[str, Any] = {
            "finding_type": "ENFORCEMENT_UNAVAILABLE",
            "tool": self.cmd[0],
            "check_type": self.check_type,
            "reason": reason,
        }
        context.update(extra)
        return StructuredViolation(file_path="System", message=message, context=context)

    def _parse_pip_audit(self, stdout: str, stderr: str) -> list[StructuredViolation]:
        """Count real vulnerabilities from ``pip-audit --format=json`` (#870).

        A non-zero exit without a parseable report (network or resolver
        failure) is the tool failing to run, not a security finding.
        """
        try:
            report = json.loads(stdout)
            dependencies = report["dependencies"]
        except (ValueError, TypeError, KeyError):
            return [
                self._unavailable(
                    reason="tool_error",
                    message=(
                        "Quality gate security_check could not run: pip-audit "
                        "exited non-zero without a JSON report. Compliance "
                        "status UNKNOWN for this rule — not a pass."
                    ),
                    sample_issues=[
                        ln for ln in (stderr or stdout).splitlines() if ln.strip()
                    ][:_SAMPLE_CAP],
                )
            ]

        vulns = [
            f"{dep.get('name')} {dep.get('version')} {vuln.get('id')}"
            for dep in dependencies
            for vuln in dep.get("vulns", [])
        ]
        if not vulns:
            return [
                self._unavailable(
                    reason="tool_error",
                    message=(
                        "Quality gate security_check could not run cleanly: "
                        "pip-audit exited non-zero but reported no "
                        "vulnerabilities. Compliance status UNKNOWN."
                    ),
                    sample_issues=[ln for ln in stderr.splitlines() if ln.strip()][
                        :_SAMPLE_CAP
                    ],
                )
            ]
        return [
            StructuredViolation(
                file_path="pyproject.toml",
                message=(
                    f"Quality Gate security_check failed: {len(vulns)} known "
                    "vulnerability(ies)"
                ),
                context={
                    "tool": "pip_audit",
                    "issue_count": len(vulns),
                    "sample_issues": vulns[:_SAMPLE_CAP],
                    "first_issue_line": None,
                },
            )
        ]

    def _parse_output(self, output: str) -> list[StructuredViolation]:
        """Parse tool output into per-affected-file structured violations.

        Per ADR-098 D1, the "affected file" is the natural unit of the
        wrapped tool. mypy groups by source path; pytest collection by test
        file; pip-audit (and any other aggregate tool whose output we cannot
        confidently key by file) degrades to a single honest finding whose
        ``issue_count`` still reflects the real scale. pip-audit is parsed
        from its JSON report by ``_parse_pip_audit`` instead.
        """
        if self.check_type == "mypy_check":
            return self._parse_mypy(output)
        if self.check_type == "pytest_check":
            return self._parse_pytest(output)
        return self._parse_generic(output)

    def _parse_mypy(self, output: str) -> list[StructuredViolation]:
        files: OrderedDict[str, list[tuple[int, str]]] = OrderedDict()
        for line in output.splitlines():
            m = _MYPY_LINE.match(line.strip())
            if not m:
                continue
            files.setdefault(m["file"], []).append((int(m["line"]), m["msg"].strip()))

        if not files:
            # Non-zero exit but no parseable per-file errors (e.g. a mypy
            # crash). Don't lose the signal — emit one honest finding.
            return self._parse_generic(output)

        violations: list[StructuredViolation] = []
        for path, errors in files.items():
            samples = [f"{path}:{ln}: {msg}" for ln, msg in errors[:_SAMPLE_CAP]]
            violations.append(
                StructuredViolation(
                    file_path=path,
                    message=f"{len(errors)} type error(s) in {path}",
                    context={
                        "tool": "mypy",
                        "issue_count": len(errors),
                        "sample_issues": samples,
                        "first_issue_line": errors[0][0],
                    },
                )
            )
        return violations

    def _parse_pytest(self, output: str) -> list[StructuredViolation]:
        files: OrderedDict[str, list[str]] = OrderedDict()
        for line in output.splitlines():
            if "error" not in line.lower():
                continue
            m = _PYTEST_ERROR.search(line)
            if not m:
                continue
            files.setdefault(m["file"], []).append(line.strip())

        if not files:
            return self._parse_generic(output)

        violations: list[StructuredViolation] = []
        for path, errors in files.items():
            violations.append(
                StructuredViolation(
                    file_path=path,
                    message=f"{len(errors)} collection error(s) in {path}",
                    context={
                        "tool": "pytest_collection",
                        "issue_count": len(errors),
                        "sample_issues": errors[:_SAMPLE_CAP],
                        "first_issue_line": None,
                    },
                )
            )
        return violations

    def _parse_generic(self, output: str) -> list[StructuredViolation]:
        """Single honest finding for tools we don't key per-file yet.

        ``issue_count`` reflects the number of non-blank output lines so the
        scale is not silently collapsed to 1. Not used for pip-audit, whose
        table framing would inflate the count (#870).
        """
        lines = [ln for ln in output.splitlines() if ln.strip()]
        count = len(lines) or 1
        # pip-audit's natural unit is the dependency manifest; default to it
        # for the security gate, otherwise fall back to a system-level path.
        path = "pyproject.toml" if self.check_type == "security_check" else "System"
        tool = "pip_audit" if self.check_type == "security_check" else self.check_type
        return [
            StructuredViolation(
                file_path=path,
                message=f"Quality Gate {self.check_type} failed: {count} issue(s)",
                context={
                    "tool": tool,
                    "issue_count": count,
                    "sample_issues": lines[:_SAMPLE_CAP],
                    "first_issue_line": None,
                },
            )
        ]
