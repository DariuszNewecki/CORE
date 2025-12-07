# src/body/cli/logic/body_contracts_fixer.py
"""Headless fixer for Body-layer contract violations."""

from __future__ import annotations

import textwrap
import time
from pathlib import Path
from typing import Any

from body.cli.logic.body_contracts_checker import check_body_contracts
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.utils.parallel_processor import ThrottledParallelProcessor


logger = getLogger(__name__)

_BODY_UI_FIX_PROMPT = textwrap.dedent(
    """
    You are refactoring Python code for a constitutional system called CORE.

    GOAL
    ----
    - Remove ALL terminal UI from the given module:
      - No Rich imports or usage
      - No console.print() or input()
      - No direct os.environ / os.environ[...] access
    - Preserve the module's behavior as a HEADLESS Body-layer service/logic.

    CONTEXT
    -------
    CORE governance rules for Body code:
    - Body modules MUST be headless:
      - No Rich UI (Console, Progress, status, etc.)
      - No console.print() / input() calls
    - Configuration must come from shared.config.settings, not os.environ.
    - Logging MUST use shared.logger.getLogger(__name__).

    REQUIREMENTS
    ------------
    1. Remove or refactor any Rich / console imports and usage.
       - If the module needs observability, use logger.debug/info/warning/error.
    2. Remove or refactor console.print() / input() calls.
       - Replace with logger.info/debug where appropriate, or return values.
    3. Replace os.environ[...] or os.environ.get(...) with settings access
       (e.g., shared.config.settings or an injected config object) when possible.
       If you cannot infer an exact mapping, keep a TODO comment but do NOT
       keep direct os.environ in the Body module.
    4. DO NOT change public function signatures unless absolutely necessary.
    5. DO NOT introduce any new UI dependencies.

    OUTPUT FORMAT
    -------------
    Return ONLY the full corrected Python module.
    DO NOT wrap it in backticks, comments, or explanation.
    """
)


async def _process_single_file(
    item: tuple[Path, list[dict[str, Any]]], agent: Any, write: bool
) -> dict[str, Any]:
    """
    Worker function to process a single file.
    """
    path, vlist = item

    logger.info(f"Processing {path.name}...")

    try:
        original_source = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Body UI fixer: cannot read %s: %s", path, e)
        return {
            "path": str(path),
            "had_violations": True,
            "modified": False,
            "error": f"read_error: {e}",
        }

    summary_lines = sorted(
        {f"- {v['rule_id']} @ line {v.get('line')}: {v['message']}" for v in vlist}
    )
    violation_summary = "\n".join(summary_lines)

    prompt = (
        _BODY_UI_FIX_PROMPT
        + "\n\nFILE PATH:\n"
        + str(path)
        + "\n\nVIOLATIONS DETECTED:\n"
        + violation_summary
        + "\n\nCURRENT FILE CONTENT:\n\n"
        + original_source
    )

    try:
        raw_response = await agent.make_request_async(
            prompt,
            user_id="fix_body_ui",
        )
    except Exception as e:
        logger.warning(
            "Body UI fixer: LLM request failed for %s: %s",
            path,
            e,
        )
        return {
            "path": str(path),
            "had_violations": True,
            "modified": False,
            "error": f"llm_error: {e}",
        }

    new_source = raw_response.strip()

    # Defensive: strip ``` fences if the model added them
    if new_source.startswith("```"):
        lines = new_source.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        new_source = "\n".join(lines).strip()

    if new_source == original_source:
        logger.info(f"No changes needed for {path.name}")
        return {
            "path": str(path),
            "had_violations": True,
            "modified": False,
            "info": "LLM returned identical content; no write performed.",
        }

    if write:
        try:
            path.write_text(new_source, encoding="utf-8")
            logger.info("Body UI fixer: updated file %s", path)
        except Exception as e:
            logger.warning(
                "Body UI fixer: failed to write %s: %s",
                path,
                e,
            )
            return {
                "path": str(path),
                "had_violations": True,
                "modified": False,
                "error": f"write_error: {e}",
            }

    return {
        "path": str(path),
        "had_violations": True,
        "modified": write,
    }


# ID: f6e2405b-bc87-41b2-8e3c-36928ff588fa
@atomic_action(
    action_id="fix.body-ui",
    intent="Autonomously fix Body UI violations using LLM",
    impact=ActionImpact.WRITE_CODE,
    policies=["body_contracts", "agent_governance"],
    category="fixers",
)
# ID: d3dd3dcc-2f74-4e88-865c-bc44f6f420cd
async def fix_body_ui_violations(
    core_context: CoreContext,
    write: bool = False,
    repo_root: Path | None = None,
    limit: int | None = None,
) -> ActionResult:
    """
    Use an LLM (via CoreContext) to automatically fix Body UI/env violations.
    """
    start_time = time.time()

    if repo_root is None:
        repo_root = Path(settings.REPO_PATH)

    # 1) Run checker to get fresh violations
    check_result = await check_body_contracts(repo_root=repo_root)
    violations_raw: list[dict[str, Any]] = check_result.data.get(  # type: ignore[assignment]
        "violations",
        [],
    )

    if not violations_raw:
        logger.info("Body UI fixer: no violations detected, nothing to do.")
        return ActionResult(
            action_id="fix.body-ui",
            ok=True,
            data={
                "files_processed": 0,
                "files_modified": 0,
                "dry_run": not write,
                "per_file": [],
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
        )

    # 2) Filter to the rules we actually fix here
    target_rules = {
        "no_ui_imports_in_body",
        "no_print_or_input_in_body",
        "no_envvar_access_in_body",
    }

    by_file: dict[Path, list[dict[str, Any]]] = {}
    for v in violations_raw:
        if v["rule_id"] not in target_rules:
            continue
        path = Path(v["file"])
        by_file.setdefault(path, []).append(v)

    if not by_file:
        logger.info(
            "Body UI fixer: violations exist but none in the UI/env set; nothing to fix."
        )
        return ActionResult(
            action_id="fix.body-ui",
            ok=True,
            data={
                "files_processed": 0,
                "files_modified": 0,
                "dry_run": not write,
                "per_file": [],
            },
            duration_sec=time.time() - start_time,
            impact=ActionImpact.READ_ONLY,
        )

    total_found = len(by_file)

    # --- NEW: Apply Limit ---
    items = list(by_file.items())
    if limit and limit > 0:
        logger.info("Limiting processing to {limit} file(s) (found %s).", total_found)
        items = items[:limit]
    else:
        logger.info("Processing all %s file(s).", total_found)

    # --- FIX: Use the directly injected cognitive service from CoreContext ---
    cognitive = core_context.cognitive_service
    if not cognitive:
        return ActionResult(
            action_id="fix.body-ui",
            ok=False,
            data={"error": "CognitiveService not available in context"},
            duration_sec=time.time() - start_time,
        )

    agent = await cognitive.aget_client_for_role("CodeReviewer")

    # 3) Process in parallel using ThrottledParallelProcessor
    processor = ThrottledParallelProcessor(description="Fixing Body UI violations...")

    # Define worker with bound arguments
    # ID: 0f3ccbb3-6ea0-452c-9d8f-b1bd21b2b89f
    async def worker(item):
        return await _process_single_file(item, agent, write)

    # Execute
    per_file_results = await processor.run_async(items, worker)

    # Calculate stats
    files_modified = sum(1 for res in per_file_results if res.get("modified"))

    return ActionResult(
        action_id="fix.body-ui",
        ok=True,
        data={
            "files_found": total_found,  # Report total available
            "files_processed": len(per_file_results),  # Report actual processed
            "files_modified": files_modified,
            "dry_run": not write,
            "per_file": per_file_results,
        },
        duration_sec=time.time() - start_time,
        impact=ActionImpact.WRITE_CODE if write else ActionImpact.READ_ONLY,
    )
