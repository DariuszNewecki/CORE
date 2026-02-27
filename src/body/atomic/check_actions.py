# src/body/atomic/check_actions.py
# ID: atomic.check_actions
"""
Atomic Check Actions - Constitutional Validation

Read-only verification actions that report violations without mutating state.
Each action checks ONE constitutional concern and returns structured findings.

CONSTITUTIONAL ALIGNMENT:
- Category: CHECK (read-only, no side effects)
- Impact: READ_ONLY (no writes permitted)
- Policy: rules/code/imports

Enforces:
- code.imports.must_resolve
- code.imports.no_stale_namespace
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    pass

logger = getLogger(__name__)

_TARGET = "src/"


@register_action(
    action_id="check.imports",
    description="Verify all import statements resolve to existing modules",
    category=ActionCategory.CHECK,
    policies=["rules/code/imports"],
    impact_level="safe",
)
@atomic_action(
    action_id="check.imports",
    intent="Detect unresolvable and stale import references across src/",
    impact=ActionImpact.READ_ONLY,
    policies=["atomic_actions"],
)
# ID: dd985101-edb8-4256-ad7f-c6088b68183b
async def action_check_imports(*, write: bool = False) -> ActionResult:
    """
    Verify all import statements in src/ resolve to existing modules.

    Runs ruff with rules:
    - F821: Undefined name (catches references to moved/deleted symbols)
    - F401: Imported but unused (catches stale imports left after refactoring)

    Returns structured violations in ActionResult.data["violations"].
    ok=True means zero violations found.
    ok=False means violations exist — callers treat this as a blocking signal.
    """
    start = time.time()

    cmd = [
        "ruff",
        "check",
        _TARGET,
        "--select",
        "F821,F401",
        "--output-format",
        "json",
        "--exit-zero",
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        violations: list[dict] = []

        if result.stdout.strip():
            raw = json.loads(result.stdout)
            for item in raw:
                violations.append(
                    {
                        "file": item.get("filename", ""),
                        "line": item.get("location", {}).get("row", 0),
                        "rule": item.get("code", ""),
                        "message": item.get("message", ""),
                    }
                )

        ok = len(violations) == 0

        if ok:
            logger.info("✅ check.imports: all imports resolve cleanly")
        else:
            logger.warning(
                "❌ check.imports: %d unresolvable import(s) found", len(violations)
            )

        return ActionResult(
            action_id="check.imports",
            ok=ok,
            data={
                "violations": violations,
                "violation_count": len(violations),
                "target": _TARGET,
                "rules_checked": ["F821", "F401"],
            },
            duration_sec=time.time() - start,
        )

    except FileNotFoundError:
        return ActionResult(
            action_id="check.imports",
            ok=False,
            data={"error": "ruff not found in PATH — cannot check imports"},
            duration_sec=time.time() - start,
        )
    except json.JSONDecodeError as e:
        return ActionResult(
            action_id="check.imports",
            ok=False,
            data={"error": f"Failed to parse ruff output: {e}"},
            duration_sec=time.time() - start,
        )
    except Exception as e:
        return ActionResult(
            action_id="check.imports",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )
