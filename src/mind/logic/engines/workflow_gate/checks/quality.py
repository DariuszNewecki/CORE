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
_PYTEST_ERROR = re.compile(r"(?P<file>(?:tests?|src)/[^\s:]+?\.py)")


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
            process = await asyncio.create_subprocess_exec(
                *self.cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._paths.repo_root),
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=_CFG.quality_timeout_sec
            )

            if process.returncode != 0:
                output = stdout.decode().strip() or stderr.decode().strip()
                return self._parse_output(output)
        except FileNotFoundError as exc:
            # Tool not installed in this environment (the F-10.3 Action's
            # slim Docker image ships without mypy/pytest/pip-audit by
            # design). Silent skip rather than surfacing as a finding —
            # the consumer cannot act on tool-absence from a PR change,
            # and the noise consumes GitHub's per-check-run annotation
            # budget. See #549.
            logger.debug(
                "%s skipped: tool '%s' not installed in this environment (%s)",
                self.check_type,
                exc.filename or self.cmd[0],
                exc,
            )
            return []
        except Exception as e:
            return [f"Gate {self.check_type} error: {e!s}"]
        return []

    def _parse_output(self, output: str) -> list[StructuredViolation]:
        """Parse tool output into per-affected-file structured violations.

        Per ADR-098 D1, the "affected file" is the natural unit of the
        wrapped tool. mypy groups by source path; pytest collection by test
        file; pip-audit (and any other aggregate tool whose output we cannot
        confidently key by file) degrades to a single honest finding whose
        ``issue_count`` still reflects the real scale.
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
        scale is not silently collapsed to 1. Refining pip-audit to true
        per-package findings (ADR-098 D1) is tracked as follow-up work.
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
