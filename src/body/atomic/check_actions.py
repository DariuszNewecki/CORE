# src/body/atomic/check_actions.py
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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    pass

logger = getLogger(__name__)

# The conventional Python tree of a CORE-shaped repository. The check binds
# to the repository the process is BOUND to, never to the process cwd: a
# literal "src/" resolved against cwd examined the runner's own source when
# the runner was bound to an execution copy elsewhere (#894 seeded live run
# -- a false pass on the subject's behalf). A repository without src/ is
# checked at its root.
_SRC_SUBDIR = "src"


def _import_check_target(core_context: Any | None) -> Path:
    """The tree ``check.imports`` examines: ``<bound repo>/src`` when it
    exists, else the bound repository root. The bound repository is the
    context's git root (what ActionExecutor injects); a direct call without
    a context falls back to the bootstrap registry's bound path."""
    if core_context is not None and getattr(core_context, "git_service", None):
        root = Path(core_context.git_service.repo_path)
    else:
        from shared.infrastructure.bootstrap_registry import bootstrap_registry

        root = bootstrap_registry.get_repo_path()
    root = root.resolve()
    src = root / _SRC_SUBDIR
    return src if src.is_dir() else root


@register_action(
    action_id="check.imports",
    description="Verify all import statements resolve to existing modules",
    category=ActionCategory.CHECK,
    policies=["rules/code/imports"],
)
@atomic_action(
    action_id="check.imports",
    intent="Detect unresolvable and stale import references across src/",
    impact=ActionImpact.READ_ONLY,
    policies=["atomic_actions"],
)
# ID: dd985101-edb8-4256-ad7f-c6088b68183b
async def action_check_imports(
    *, core_context: Any | None = None, write: bool = False, **kwargs
) -> ActionResult:
    """
    Verify all import statements in the bound repository resolve to existing
    modules (its ``src/`` tree when it has one, else its root).

    Runs ruff with rules:
    - F821: Undefined name (catches references to moved/deleted symbols)
    - F401: Imported but unused (catches stale imports left after refactoring)

    Returns structured violations in ActionResult.data["violations"].
    ok=True means zero violations found.
    ok=False means violations exist — callers treat this as a blocking signal.
    """
    start = time.time()
    target = _import_check_target(core_context)

    cmd = [
        "ruff",
        "check",
        str(target),
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
                "target": str(target),
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
