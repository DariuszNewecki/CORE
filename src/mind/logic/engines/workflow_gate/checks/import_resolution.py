# src/mind/logic/engines/workflow_gate/checks/import_resolution.py

"""
Import resolution workflow check.

Verifies that all import statements in src/ resolve to existing modules.
Enforces: code.imports.must_resolve, code.imports.no_stale_namespace

Both rules dispatch to this same check_type (import_resolution_check).
What each rule actually verifies comes entirely from its enforcement
mapping's declared ``tools`` list (see
.intent/enforcement/mappings/code/imports.yaml): each entry names a
``tool``, its ``args``, and optionally ``filter`` (a single required
substring) and/or ``filter_all`` (a list of substrings, all required --
AND semantics) used to narrow which output lines count as violations.
Before #855 this check ignored ``params`` altogether and always ran one
hardcoded ``ruff --select F821,F401`` regardless of which rule fired --
F821/F401 do not perform import resolution at all, so the rules' stated
law was never actually verified. This module now runs whatever the
mapping declares.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import (
    StructuredViolation,
    WorkflowCheck,
)
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG = load_operational_config().workflow_gate

_MAX_SHOWN_LINES = 20


# ID: 2f5c6b8e-2b3a-4d7e-9c1f-6a8d0e4b7c9a
def _matches_filter(line: str, spec: dict[str, Any]) -> bool:
    """True if `line` counts as a violation under the tool's declared filter.

    Two distinct, non-overloaded keys -- each name carries its own
    semantics rather than one key silently changing meaning by type:

    - "filter": a single required substring (string).
    - "filter_all": a list of substrings, ALL of which must be present
      (AND semantics) -- this is what lets no_stale_namespace narrow a
      shared instrument (mypy's import-not-found errors) down to the
      "features." subset without needing its own check_type.

    Neither key declared -> every line counts.
    """
    single = spec.get("filter")
    if single is not None and single not in line:
        return False
    conjunction = spec.get("filter_all")
    if conjunction and not all(needle in line for needle in conjunction):
        return False
    return True


# ID: f758fd53-d1cd-4be0-a073-ccc866096cdc
class ImportResolutionCheck(WorkflowCheck):
    """
    Verifies all imports in src/ resolve to existing modules.

    Runs every tool declared in the firing rule's mapping params and
    aggregates the filtered violations. Unlike linter_compliance (which
    checks style), this check specifically targets structural integrity --
    imports that would crash at runtime.
    """

    check_type = "import_resolution_check"

    # ID: 7820a1df-315a-4acf-818e-90956535bf72
    async def verify(
        self, file_path: Path | None, params: dict[str, Any]
    ) -> Sequence[str | StructuredViolation]:
        """
        Run every tool declared in `params["tools"]` and aggregate.

        Args:
            file_path: Optional specific file to check (None = checks src/).
                WorkflowGateEngine._always_context_level makes this
                unconditionally None on every real dispatch today, so
                scope.applies_to/excludes declared in the mapping has no
                effect here -- same engine-level gap as the rest of
                workflow_gate. Tracked separately as #869; not addressed
                by this check.
            params: Rule-specific parameters from the enforcement mapping.
                Required key: "tools" -- a list of {tool, args, filter?}
                entries. must_resolve and no_stale_namespace declare
                different tool lists so they no longer run the same
                hardcoded command (#855 D-a).

        Returns:
            A sequence of violation strings, or a single aggregated
            ENFORCEMENT_UNAVAILABLE StructuredViolation if any declared
            tool is not installed -- a missing dependency must degrade a
            blocking rule's verdict, never silently pass it (#855 D-d,
            mirrors QualityGateCheck.verify in checks/quality.py).
        """
        target = str(file_path) if file_path else "src"
        tool_specs = params.get("tools")
        if not tool_specs:
            return [
                f"{self.check_type} misconfigured: mapping params has no "
                "'tools' declared"
            ]

        violations: list[str] = []
        for spec in tool_specs:
            tool_violations = await self._run_tool(spec, target)
            if tool_violations is None:
                # Tool absent: fail the whole rule closed rather than
                # silently trusting whatever tools did run -- a missing
                # instrument means compliance is unknown, not proven.
                tool_name = spec.get("tool", "?")
                return [
                    StructuredViolation(
                        file_path="System",
                        message=(
                            f"Import resolution check ({self.check_type}) "
                            f"could not run: tool '{tool_name}' is not "
                            "installed in this environment. Compliance "
                            "status UNKNOWN for this rule -- not a pass."
                        ),
                        context={
                            "finding_type": "ENFORCEMENT_UNAVAILABLE",
                            "tool": tool_name,
                            "check_type": self.check_type,
                            "reason": "tool_not_installed",
                        },
                    )
                ]
            violations.extend(tool_violations)
        return violations

    # ID: 8b6b6a1a-4c1e-4a2d-9b0e-1f3a7d5c2e6b
    async def _run_tool(self, spec: dict[str, Any], target: str) -> list[str] | None:
        """Run one declared tool against `target`.

        Returns the filtered violation list, or None if the tool binary
        itself is not installed (the caller treats that as fail-closed
        for the whole check, not just this tool's contribution).
        """
        tool = str(spec.get("tool", ""))
        args = [str(a) for a in spec.get("args", [])]
        cmd = [tool, *args, target]

        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=_CFG.import_timeout_sec
            )
        except TimeoutError:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            return [f"{tool} import check timed out (>{_CFG.import_timeout_sec:g}s)"]
        except FileNotFoundError as exc:
            logger.debug(
                "%s: tool '%s' not installed in this environment (%s)",
                self.check_type,
                tool,
                exc,
            )
            return None
        except Exception as e:
            return [f"{tool} import check error: {e}"]

        if process.returncode == 0:
            return []

        output = stdout.decode().strip()
        if not output:
            err = stderr.decode().strip()
            return [f"{tool} import check failed: {err}"] if err else []

        lines = [ln for ln in output.splitlines() if _matches_filter(ln, spec)]
        if not lines:
            return []

        shown = lines[:_MAX_SHOWN_LINES]
        if len(lines) > _MAX_SHOWN_LINES:
            shown.append(f"... and {len(lines) - _MAX_SHOWN_LINES} more violations")
        return [
            f"Unresolvable imports detected via {tool} ({len(lines)} "
            "violation(s)):\n" + "\n".join(shown)
        ]
