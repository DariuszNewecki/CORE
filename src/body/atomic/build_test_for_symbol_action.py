# src/body/atomic/build_test_for_symbol_action.py
"""
Atomic action: build.test_for_symbol

Write one pytest test function for one named public symbol, appending to
the existing test file or creating it. Receives pre-generated, pre-validated
code from the generate.test_snippet cognitive step (ADR-140 D7).

MUST only be invoked via flow.build_test_for_symbol. Direct invocation as a
standalone action target is prohibited: no caller would supply generated_code.

Constitutional Alignment:
- Per ADR-133 D3: symbol-granular generation via context_aware_test_gen.
- Per ADR-133 D7: IntentGuard validates the generated snippet, not the
  post-append file. One defensive pass on the received artifact.
- Per ADR-140 D7: cognitive loop removed; action receives generated_code
  as a required parameter from the preceding cognitive step.
- Per ADR-107 D2: files_produced declares the test file path.
- File mutations route through core_context.file_handler (write unified entry).
- No direct settings access; repo_root via CoreContext.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from body.governance.intent_guard import get_intent_guard
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.intent.test_coverage_paths import source_to_test_path
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="build.test_for_symbol",
    description="Write a pre-generated pytest test function for a named public symbol",
    category=ActionCategory.BUILD,
    policies=["rules/code/purity"],
)
@atomic_action(
    action_id="build.test_for_symbol",
    intent="Write a generated pytest test snippet received from the cognitive step to the test file",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: a1bb8e15-cf51-4772-acaf-0d8c3d494a92
async def action_build_test_for_symbol(
    source_file: str,
    symbol_name: str,
    symbol_kind: str,
    generated_code: str,
    core_context: CoreContext,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """
    Write a generated pytest test function to the test file.

    Receives pre-generated, pre-validated code from the generate.test_snippet
    cognitive step. Performs one defensive IntentGuard validation pass before
    writing. No LLM calls. No prompt loading. No iterative loop.

    generated_code is REQUIRED — it is produced by the preceding cognitive step
    and threaded in by FlowExecutor. Passing it is the caller's responsibility;
    do not invoke this action standalone.
    """
    start = time.time()
    repo_root: Path = core_context.git_service.repo_path

    # 1. Resolve test file path.
    try:
        test_file = source_to_test_path(source_file)
    except ValueError as e:
        return ActionResult(
            action_id="build.test_for_symbol",
            ok=False,
            data={"error": f"Cannot derive test path: {e}"},
            duration_sec=time.time() - start,
        )

    # 2. Verify source exists (defensive gate — cognitive step should have caught this).
    source_path = repo_root / source_file
    if not source_path.exists():
        return ActionResult(
            action_id="build.test_for_symbol",
            ok=False,
            data={"error": f"Source file not found: {source_file}"},
            duration_sec=time.time() - start,
        )

    # 3. Defensive IntentGuard pass on the received artifact (ADR-133 D7).
    intent_guard = get_intent_guard(repo_path=repo_root)
    try:
        validation = intent_guard.validate_generated_code(
            code=generated_code,
            pattern_id="test_file",
            component_type="test",
            target_path=test_file,
        )
    except Exception as e:
        logger.error(
            "build.test_for_symbol: IntentGuard raised on received artifact: %s",
            e,
            exc_info=True,
        )
        return ActionResult(
            action_id="build.test_for_symbol",
            ok=False,
            data={
                "error": f"IntentGuard raised: {e}",
                "test_file": test_file,
            },
            duration_sec=time.time() - start,
        )

    if not validation.is_valid:
        violations = [
            {
                "rule_name": getattr(v, "rule_name", "unknown"),
                "message": getattr(v, "message", ""),
                "severity": getattr(v, "severity", "error"),
            }
            for v in validation.violations
        ]
        logger.error(
            "build.test_for_symbol: received artifact failed IntentGuard "
            "(%d violations) — refusing to write",
            len(violations),
        )
        return ActionResult(
            action_id="build.test_for_symbol",
            ok=False,
            data={
                "error": "intent_guard_violations",
                "violations": violations,
                "test_file": test_file,
                "symbol_name": symbol_name,
            },
            duration_sec=time.time() - start,
        )

    # 4. Write if requested.
    if write:
        test_path = repo_root / test_file
        if test_path.exists():
            existing = test_path.read_text(encoding="utf-8")
            full_content = existing.rstrip() + "\n\n\n" + generated_code + "\n"
        else:
            full_content = (
                "from __future__ import annotations\n\n\n" + generated_code + "\n"
            )

        try:
            core_context.file_handler.write(test_file, full_content)
            # Ensure every ancestor directory has an __init__.py so pytest-cov +
            # importlib mode gives each file a fully-qualified module path
            # (avoids pycache name collisions across different test dirs).
            tests_root = repo_root / "tests"
            ancestor = test_path.parent
            while True:
                init_path = ancestor / "__init__.py"
                if not init_path.exists():
                    rel_init = str(init_path.relative_to(repo_root))
                    core_context.file_handler.write(rel_init, "")
                if ancestor == tests_root or ancestor == repo_root:
                    break
                ancestor = ancestor.parent
        except Exception as e:
            return ActionResult(
                action_id="build.test_for_symbol",
                ok=False,
                data={"error": f"File write failed: {e}", "test_file": test_file},
                duration_sec=time.time() - start,
            )

    return ActionResult(
        action_id="build.test_for_symbol",
        ok=True,
        data={
            "source_file": source_file,
            "symbol_name": symbol_name,
            "symbol_kind": symbol_kind,
            "test_file": test_file,
            "write": write,
            "files_produced": [test_file] if write else [],
        },
        duration_sec=time.time() - start,
    )
