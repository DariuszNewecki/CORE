# src/mind/logic/engines/workflow_gate/checks/ruff_format.py

"""
Ruff format workflow check.

Verifies that source files conform to ruff's formatting standard.
Enforces: code.style.ruff_format

Runs `ruff format --check` asynchronously and reports files that
would be reformatted as violations.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 58a4df52-9edf-475e-b196-781cabfcfbe5
class RuffFormatCheck(WorkflowCheck):
    """
    Verifies source files conform to ruff formatting.

    Runs `ruff format --check` asynchronously and reports files that
    would be reformatted. Files matching the exclude pattern (e.g.
    scripts/ or dev-scripts/) are skipped.
    """

    check_type = "ruff_format_check"

    # ID: a3ceba34-e217-48ec-9a03-6d488ebaba77
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Run ruff format --check asynchronously.

        Args:
            file_path: Optional specific file to check (None = checks src/)
            params: Check parameters; supports 'exclude_pattern' regex

        Returns:
            List of violation messages (empty = all files formatted correctly)
        """
        target = str(file_path) if file_path else "src"
        exclude_pattern = params.get("exclude_pattern", r"^(scripts|dev-scripts)/")
        violations: list[str] = []

        if file_path and re.search(exclude_pattern, str(file_path)):
            return violations

        try:
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "format",
                "--check",
                target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)

            if process.returncode != 0:
                output = stdout.decode().strip()
                if output:
                    for line in output.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        # ruff format --check prefixes with "Would reformat: "
                        if line.startswith("Would reformat: "):
                            cleaned = line.removeprefix("Would reformat: ").strip()
                            if not re.search(exclude_pattern, cleaned):
                                violations.append(cleaned)
                else:
                    err = stderr.decode().strip()
                    violations.append(f"Ruff format check failed: {err}")

        except TimeoutError:
            violations.append("Ruff format check timed out (>60s)")
        except FileNotFoundError:
            violations.append("ruff not found in PATH — cannot check formatting")
        except Exception as e:
            violations.append(f"Ruff format check error: {e}")

        return violations
