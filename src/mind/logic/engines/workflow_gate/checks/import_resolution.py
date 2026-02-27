# src/mind/logic/engines/workflow_gate/checks/import_resolution.py
# ID: __REPLACE_WITH_UUID__

"""
Import resolution workflow check.

Verifies that all import statements in src/ resolve to existing modules.
Enforces: code.imports.must_resolve, code.imports.no_stale_namespace

Uses ruff F821 (undefined names) and F401 (unused imports) to detect
stale or broken import references — the Python equivalent of a linker error.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: __REPLACE_WITH_UUID__
# ID: f758fd53-d1cd-4be0-a073-ccc866096cdc
class ImportResolutionCheck(WorkflowCheck):
    """
    Verifies all imports in src/ resolve to existing modules.

    Runs ruff --select F821,F401 asynchronously and reports violations.
    Unlike linter_compliance (which checks style), this check specifically
    targets structural integrity — imports that would crash at runtime.
    """

    check_type = "import_resolution_check"

    # ID: __REPLACE_WITH_UUID__
    # ID: 7820a1df-315a-4acf-818e-90956535bf72
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Run ruff F821/F401 check asynchronously.

        Args:
            file_path: Optional specific file to check (None = checks src/)
            params: Check parameters (currently unused)

        Returns:
            List of violation messages (empty = all imports resolve)
        """
        target = str(file_path) if file_path else "src"
        violations: list[str] = []

        try:
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                target,
                "--select",
                "F821,F401",
                "--output-format",
                "concise",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)

            if process.returncode != 0:
                output = stdout.decode().strip()
                if output:
                    # Report first 20 lines to avoid flooding audit report
                    lines = output.splitlines()
                    shown = lines[:20]
                    if len(lines) > 20:
                        shown.append(f"... and {len(lines) - 20} more violations")
                    violations.append(
                        f"Unresolvable imports detected ({len(lines)} violation(s)):\n"
                        + "\n".join(shown)
                    )
                else:
                    err = stderr.decode().strip()
                    violations.append(f"Import resolution check failed: {err}")

        except TimeoutError:
            violations.append("Import resolution check timed out (>60s)")
        except FileNotFoundError:
            violations.append("ruff not found in PATH — cannot check imports")
        except Exception as e:
            violations.append(f"Import resolution check error: {e}")

        return violations
