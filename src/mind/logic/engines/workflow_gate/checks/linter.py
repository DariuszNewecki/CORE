# src/mind/logic/engines/workflow_gate/checks/linter.py

"""
Linter compliance workflow check.

Verifies that code passes ruff (linter) and black (formatter) checks.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG = load_operational_config().workflow_gate


# ID: 4d2b4ae8-afee-4354-add7-4db563f1d576
class LinterComplianceCheck(WorkflowCheck):
    """
    Verifies that code passes linter (ruff) and formatter (black) checks.

    Runs external commands asynchronously and reports violations.
    """

    check_type = "linter_compliance"

    # ID: a4257f16-5ca5-4a2d-b8f8-49745c33b7be
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Run ruff and black checks asynchronously.

        Args:
            file_path: Optional specific file to check (if None, checks entire repo)
            params: Check parameters (currently unused)

        Returns:
            List of violation messages if linting fails
        """
        violations: list[str] = []

        # Determine target arguments (IMPORTANT: each path must be its own argv token)
        targets: list[str] = [str(file_path)] if file_path else ["src", "tests"]

        # Check 1: Ruff linter
        try:
            process = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                *targets,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=_CFG.linter_timeout_sec
            )

            if process.returncode != 0:
                output = stdout.decode().strip() or stderr.decode().strip()
                violations.append(f"Ruff check failed: {output}")

        except TimeoutError:
            violations.append(f"Ruff check timed out (>{_CFG.linter_timeout_sec:g}s)")
        except FileNotFoundError as exc:
            # ruff not installed in this environment (e.g., F-10.3 Action's
            # slim Docker image). Silent skip; see #549.
            logger.debug("%s skipped: ruff not installed (%s)", self.check_type, exc)
        except Exception as e:
            violations.append(f"Ruff check error: {e}")

        # Check 2: Black formatter
        try:
            process = await asyncio.create_subprocess_exec(
                "black",
                "--check",
                *targets,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=_CFG.linter_timeout_sec
            )

            if process.returncode != 0:
                output = stdout.decode().strip() or stderr.decode().strip()
                violations.append(f"Black format check failed: {output}")

        except TimeoutError:
            violations.append(f"Black check timed out (>{_CFG.linter_timeout_sec:g}s)")
        except FileNotFoundError as exc:
            # black not installed in this environment. Silent skip; see #549.
            logger.debug("%s skipped: black not installed (%s)", self.check_type, exc)
        except Exception as e:
            violations.append(f"Black check error: {e}")

        return violations
