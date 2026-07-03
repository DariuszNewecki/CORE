# src/body/atomic/build_test_for_symbol_action.py
"""
Atomic action: build.test_for_symbol

Generates one pytest test function for one named public symbol, appending to
the existing test file or creating it. Supports two generation modes (ADR-135 D1):

  single_shot (default) — one LLM call via context_aware_test_gen; one IntentGuard
                          validation. Existing behaviour.
  iterative             — loop: generate → IntentGuard → feed violations back → repeat,
                          up to the governed cap in generation_budget.yaml. Uses
                          context_aware_test_gen_repair for repair iterations.

Constitutional Alignment:
- Per ADR-133 D3: symbol-granular generation via context_aware_test_gen.
- Per ADR-133 D7: IntentGuard validates the generated snippet, not the
  post-append file.
- Per ADR-135 D1/D3: iterative mode + governed budget.
- Per ADR-107 D2: files_produced declares the test file path.
- File mutations route through core_context.file_handler (write unified entry).
- No direct settings access; repo_root via CoreContext.
"""

from __future__ import annotations

import ast
import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from body.governance.intent_guard import get_intent_guard
from shared.action_types import ActionImpact, ActionResult
from shared.ai.prompt_model import PromptModel
from shared.atomic_action import atomic_action
from shared.infrastructure.intent.generation_budget import load_generation_budget
from shared.infrastructure.intent.test_coverage_paths import source_to_test_path
from shared.logger import getLogger
from shared.models.generation_mode import GenerationMode


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: f9ba0892-14fd-4517-8ab0-915d47d6e6ad
def _extract_symbol_code(source_path: Path, symbol_name: str) -> str | None:
    """Extract the source text of a named top-level symbol via AST."""
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (OSError, SyntaxError):
        return None

    for node in ast.iter_child_nodes(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == symbol_name
        ):
            return ast.get_source_segment(source, node)
    return None


# ID: e22c3ee1-9348-42c8-a393-ddd77e99df6b
def _derive_module_path(source_file: str) -> str:
    """Convert repo-relative source path to importable module path.

    "src/will/workers/foo.py" -> "will.workers.foo"
    """
    return source_file.removeprefix("src/").removesuffix(".py").replace("/", ".")


# ID: e88719b7-a363-4de9-8b64-8c6d94a88a93
def _extract_from_fences(raw: str) -> str | None:
    """Extract code content from ```python ... ``` or ``` ... ``` fences."""
    for fence_start in ("```python", "```"):
        start = raw.find(fence_start)
        if start != -1:
            newline = raw.find("\n", start)
            if newline == -1:
                continue
            end = raw.find("```", newline + 1)
            if end == -1:
                continue
            return raw[newline + 1 : end].strip()
    return None


# ID: c2b924b9-a172-4aa3-b3d7-49d7b14a2c68
def _format_violations(violations: list[dict]) -> str:
    """Format IntentGuard violations into a concise summary for the repair prompt."""
    lines = []
    for v in violations:
        rule = v.get("rule_name", "unknown")
        msg = v.get("message", "")
        lines.append(f"- [{rule}] {msg}" if msg else f"- [{rule}]")
    return "\n".join(lines) if lines else "Unknown violations"


@register_action(
    action_id="build.test_for_symbol",
    description="Generate one pytest test function for a named public symbol",
    category=ActionCategory.BUILD,
    policies=["rules/code/purity"],
    remediates=["test.runner.missing", "test.runner.failure"],
)
@atomic_action(
    action_id="build.test_for_symbol",
    intent="Generate a single targeted pytest test for one source symbol via context_aware_test_gen",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: a1bb8e15-cf51-4772-acaf-0d8c3d494a92
async def action_build_test_for_symbol(
    source_file: str,
    symbol_name: str,
    symbol_kind: str,
    signature: str,
    core_context: CoreContext,
    write: bool = False,
    generation_mode: str = GenerationMode.SINGLE_SHOT,
    **kwargs,
) -> ActionResult:
    """
    Generate one pytest test function for symbol_name from source_file.

    single_shot mode (default):
      1. Extract symbol source code from source_file via AST.
      2. Derive importable module path from source_file.
      3. Call context_aware_test_gen prompt via PromptModel.
      4. Extract generated code from ```python fences.
      5. Run IntentGuard on the generated snippet (ADR-133 D7).
      6. If write=True: append to test file (or create if absent) via FileHandler.

    iterative mode (ADR-135 D1):
      Same as single_shot but loops up to generation_budget.yaml cap, feeding
      IntentGuard violation detail back as repair context on each failed attempt.
      Uses context_aware_test_gen_repair prompt for repair iterations.

    Returns ActionResult with files_produced=[test_file] on write (ADR-107 D2).
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

    # 2. Verify source exists.
    source_path = repo_root / source_file
    if not source_path.exists():
        return ActionResult(
            action_id="build.test_for_symbol",
            ok=False,
            data={"error": f"Source file not found: {source_file}"},
            duration_sec=time.time() - start,
        )

    # 3. Extract symbol source code for context grounding.
    symbol_code = _extract_symbol_code(source_path, symbol_name)
    if not symbol_code:
        symbol_code = f"# {signature}"

    module_path = _derive_module_path(source_file)

    # 4. Load initial prompt and get cognitive client.
    try:
        model = PromptModel.load("context_aware_test_gen")
        cognitive_service = core_context.cognitive_service
        if cognitive_service is None:
            cognitive_service = await core_context.registry.get_cognitive_service()
        generator = await cognitive_service.aget_client_for_role(model.manifest.role)
    except Exception as e:
        logger.error("build.test_for_symbol: failed to initialise prompt/client: %s", e)
        return ActionResult(
            action_id="build.test_for_symbol",
            ok=False,
            data={
                "error": f"Prompt/client initialisation failed: {e}",
                "test_file": test_file,
            },
            duration_sec=time.time() - start,
        )

    intent_guard = get_intent_guard(repo_path=repo_root)

    use_iterative = generation_mode == GenerationMode.ITERATIVE
    if use_iterative:
        budget = load_generation_budget().for_task_type("test_generation")
        max_iterations = budget.max_iterations
        wall_clock_cap = budget.wall_clock_cap_secs
        logger.info(
            "build.test_for_symbol: iterative mode — cap=%d iterations, %ds wall-clock",
            max_iterations,
            wall_clock_cap,
        )
    else:
        max_iterations = 1
        wall_clock_cap = 600

    previous_code: str | None = None
    last_violations: list[dict] = []

    for attempt in range(max_iterations):
        is_repair = attempt > 0

        # 5. Invoke LLM — initial or repair prompt.
        try:
            if is_repair:
                repair_model = PromptModel.load("context_aware_test_gen_repair")
                raw_response = await asyncio.wait_for(
                    repair_model.invoke(
                        context={
                            "file_path": source_file,
                            "symbol_name": symbol_name,
                            "symbol_code": symbol_code,
                            "module_path": module_path,
                            "violations_summary": _format_violations(last_violations),
                            "previous_code": previous_code or "",
                        },
                        client=generator,
                        user_id="build_test_for_symbol_repair",
                    ),
                    timeout=wall_clock_cap,
                )
            else:
                raw_response = await asyncio.wait_for(
                    model.invoke(
                        context={
                            "file_path": source_file,
                            "symbol_name": symbol_name,
                            "symbol_code": symbol_code,
                            "module_path": module_path,
                        },
                        client=generator,
                        user_id="build_test_for_symbol",
                    ),
                    timeout=wall_clock_cap,
                )
        except TimeoutError:
            logger.warning(
                "build.test_for_symbol: wall-clock cap hit on attempt %d/%d",
                attempt + 1,
                max_iterations,
            )
            return ActionResult(
                action_id="build.test_for_symbol",
                ok=False,
                data={
                    "error": "wall_clock_cap_exceeded",
                    "test_file": test_file,
                    "attempts": attempt + 1,
                },
                duration_sec=time.time() - start,
            )
        except Exception as e:
            logger.error(
                "build.test_for_symbol: LLM invocation failed on attempt %d: %s",
                attempt + 1,
                e,
            )
            return ActionResult(
                action_id="build.test_for_symbol",
                ok=False,
                data={
                    "error": f"LLM invocation failed: {e}",
                    "test_file": test_file,
                    "attempts": attempt + 1,
                },
                duration_sec=time.time() - start,
            )

        # 6. Extract code from fences.
        generated_code = _extract_from_fences(raw_response)
        if not generated_code:
            if use_iterative and attempt < max_iterations - 1:
                last_violations = [
                    {
                        "rule_name": "output.no_code_fence",
                        "message": "LLM response contained no ```python fences",
                    }
                ]
                previous_code = raw_response[:500]
                logger.warning(
                    "build.test_for_symbol: no fences on attempt %d — retrying",
                    attempt + 1,
                )
                continue
            return ActionResult(
                action_id="build.test_for_symbol",
                ok=False,
                data={
                    "error": "LLM response contained no ```python fences",
                    "test_file": test_file,
                    "symbol_name": symbol_name,
                    "attempts": attempt + 1,
                },
                duration_sec=time.time() - start,
            )

        # 7. IntentGuard on the snippet (ADR-133 D7).
        try:
            validation = intent_guard.validate_generated_code(
                code=generated_code,
                pattern_id="test_file",
                component_type="test",
                target_path=test_file,
            )
        except Exception as e:
            logger.error(
                "build.test_for_symbol: IntentGuard raised on attempt %d: %s",
                attempt + 1,
                e,
                exc_info=True,
            )
            return ActionResult(
                action_id="build.test_for_symbol",
                ok=False,
                data={
                    "error": f"IntentGuard raised: {e}",
                    "test_file": test_file,
                    "attempts": attempt + 1,
                },
                duration_sec=time.time() - start,
            )

        if validation.is_valid:
            # Accepted — fall through to write.
            if use_iterative and attempt > 0:
                logger.info(
                    "build.test_for_symbol: accepted on attempt %d/%d",
                    attempt + 1,
                    max_iterations,
                )
            break

        # Validation failed.
        last_violations = [
            {
                "rule_name": getattr(v, "rule_name", "unknown"),
                "message": getattr(v, "message", ""),
                "severity": getattr(v, "severity", "error"),
            }
            for v in validation.violations
        ]
        previous_code = generated_code

        if not use_iterative or attempt == max_iterations - 1:
            return ActionResult(
                action_id="build.test_for_symbol",
                ok=False,
                data={
                    "error": "intent_guard_violations",
                    "violations": last_violations,
                    "test_file": test_file,
                    "symbol_name": symbol_name,
                    "attempts": attempt + 1,
                },
                duration_sec=time.time() - start,
            )

        logger.info(
            "build.test_for_symbol: attempt %d/%d failed (%d violations) — retrying",
            attempt + 1,
            max_iterations,
            len(last_violations),
        )
    else:
        # Loop exhausted without break (all attempts failed).
        return ActionResult(
            action_id="build.test_for_symbol",
            ok=False,
            data={
                "error": "intent_guard_violations",
                "violations": last_violations,
                "test_file": test_file,
                "symbol_name": symbol_name,
                "attempts": max_iterations,
            },
            duration_sec=time.time() - start,
        )

    # 8. Write if requested (only reached on success).
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
            # Ensure every ancestor directory of test_generated.py has an
            # __init__.py so pytest-cov + importlib mode gives each file a
            # fully-qualified module path (avoids pycache name collisions when
            # multiple test_generated.py files exist across different dirs).
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
            "generation_mode": generation_mode,
            "attempts": attempt + 1,
        },
        duration_sec=time.time() - start,
    )
